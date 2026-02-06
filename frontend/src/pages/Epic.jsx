import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { epicAPI, featureAPI, userStoryAPI, llmProviderAPI, subscriptionAPI, leanCanvasAPI, prdAPI, integrationsAPI } from '@/api';
import { useSubscriptionStore, useLLMProviderStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import ThemeToggle from '@/components/ThemeToggle';
import { MoSCoWBadge, RICEBadge, FeatureScoringDialog } from '@/components/ScoringComponents';
import { LinkedBugs } from '@/components/LinkedBugs';
import PushToLinearModal from '@/components/PushToLinearModal';
import { 
  ArrowLeft, Send, Loader2, Lock, CheckCircle2, 
  XCircle, FileText, History, AlertCircle, Layers,
  User, Bot, Settings, Plus, Puzzle, BookOpen, Bug, Trash2,
  ChevronRight, Sparkles, RefreshCw, Edit3, MessageSquare, Target, Flag, TrendingUp,
  LayoutGrid, Upload
} from 'lucide-react';

const STAGES = [
  { id: 'problem_capture', label: 'Problem', locked: false },
  { id: 'problem_confirmed', label: 'Problem Confirmed', locked: true },
  { id: 'outcome_capture', label: 'Outcome', locked: false },
  { id: 'outcome_confirmed', label: 'Outcome Confirmed', locked: true },
  { id: 'epic_drafted', label: 'Draft', locked: false },
  { id: 'epic_locked', label: 'Locked', locked: true },
];

const STAGE_INDEX = {
  problem_capture: 0,
  problem_confirmed: 1,
  outcome_capture: 2,
  outcome_confirmed: 3,
  epic_drafted: 4,
  epic_locked: 5,
};

const FEATURE_STAGES = {
  draft: { label: 'Draft', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: Edit3 },
  refining: { label: 'Refining', color: 'bg-violet-500/20 text-violet-400 border-violet-500/30', icon: MessageSquare },
  approved: { label: 'Approved', color: 'bg-success/20 text-success border-success/30', icon: Lock },
};

// Workflow steps for the visual stepper
const WORKFLOW_STEPS = [
  { id: 'definition', label: 'Epic Definition', icon: FileText, description: 'Problem & Outcome' },
  { id: 'features', label: 'Features', icon: Puzzle, description: 'Break down epic' },
  { id: 'stories', label: 'User Stories', icon: BookOpen, description: 'Sprint-sized tasks' },
  { id: 'complete', label: 'Complete', icon: Flag, description: 'Ready for development' },
];

const Epic = () => {
  const { epicId } = useParams();
  const navigate = useNavigate();
  const { isActive, setSubscription } = useSubscriptionStore();
  const { activeProvider, setProviders } = useLLMProviderStore();

  const [epic, setEpic] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [pendingProposal, setPendingProposal] = useState(null);
  const [confirmingProposal, setConfirmingProposal] = useState(false);
  const [error, setError] = useState('');
  
  // Feature state (using new lifecycle API)
  const [features, setFeatures] = useState([]);
  const [generatingFeatures, setGeneratingFeatures] = useState(false);
  const [generatedDrafts, setGeneratedDrafts] = useState([]); // Temporary drafts before saving
  
  // Feature refinement dialog
  const [selectedFeature, setSelectedFeature] = useState(null);
  const [featureConversation, setFeatureConversation] = useState([]);
  const [refinementMessage, setRefinementMessage] = useState('');
  const [sendingRefinement, setSendingRefinement] = useState(false);
  const [streamingRefinement, setStreamingRefinement] = useState('');
  
  // Manual feature creation
  const [showManualCreate, setShowManualCreate] = useState(false);
  const [manualTitle, setManualTitle] = useState('');
  const [manualDescription, setManualDescription] = useState('');
  const [manualCriteria, setManualCriteria] = useState('');
  const [creatingManual, setCreatingManual] = useState(false);
  
  // Story counts for approved features
  const [featureStoryCounts, setFeatureStoryCounts] = useState({});
  
  // PRD and Lean Canvas state
  const [hasPRD, setHasPRD] = useState(false);
  const [hasLeanCanvas, setHasLeanCanvas] = useState(false);
  
  // Push to Linear state
  const [showPushToLinear, setShowPushToLinear] = useState(false);
  const [hasLinearIntegration, setHasLinearIntegration] = useState(false);

  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const refinementEndRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [transcript, streamingContent, scrollToBottom]);

  // Always fetch subscription and LLM providers on mount (for direct navigation)
  useEffect(() => {
    const fetchUserSettings = async () => {
      try {
        const [subRes, llmRes] = await Promise.all([
          subscriptionAPI.getStatus(),
          llmProviderAPI.list()
        ]);
        setSubscription(subRes.data);
        setProviders(llmRes.data || []);
      } catch (err) {
        console.error('Failed to fetch user settings:', err);
      }
    };
    fetchUserSettings();
  }, [setSubscription, setProviders]);

  const loadEpic = useCallback(async () => {
    try {
      const [epicRes, transcriptRes, decisionsRes] = await Promise.all([
        epicAPI.get(epicId),
        epicAPI.getTranscript(epicId),
        epicAPI.getDecisions(epicId),
      ]);
      setEpic(epicRes.data);
      setTranscript(transcriptRes.data.events);
      setDecisions(decisionsRes.data.decisions);
      if (epicRes.data.pending_proposal) {
        setPendingProposal(epicRes.data.pending_proposal);
      }
      
      // Load features if epic is locked
      if (epicRes.data.current_stage === 'epic_locked') {
        const featuresRes = await featureAPI.listForEpic(epicId);
        const featuresData = featuresRes.data || [];
        setFeatures(featuresData);
        
        // Fetch story counts for approved features
        const storyCounts = {};
        let allFeaturesComplete = true;
        let hasAnyStories = false;
        
        for (const feature of featuresData) {
          if (feature.current_stage === 'approved') {
            try {
              const storiesRes = await userStoryAPI.listForFeature(feature.feature_id);
              const stories = storiesRes.data || [];
              const approvedCount = stories.filter(s => s.current_stage === 'approved').length;
              storyCounts[feature.feature_id] = {
                total: stories.length,
                approved: approvedCount,
                allApproved: stories.length > 0 && approvedCount === stories.length
              };
              
              if (stories.length > 0) {
                hasAnyStories = true;
                if (approvedCount !== stories.length) {
                  allFeaturesComplete = false;
                }
              } else {
                allFeaturesComplete = false;
              }
            } catch (e) {
              storyCounts[feature.feature_id] = { total: 0, approved: 0, allApproved: false };
              allFeaturesComplete = false;
            }
          } else {
            // Non-approved features mean not complete
            allFeaturesComplete = false;
          }
        }
        
        setFeatureStoryCounts(storyCounts);
        
        // Check if PRD and Lean Canvas exist for this epic
        try {
          const [prdRes, canvasRes] = await Promise.all([
            prdAPI.get(epicId),
            leanCanvasAPI.get(epicId)
          ]);
          setHasPRD(prdRes.data?.exists || false);
          setHasLeanCanvas(canvasRes.data?.exists || false);
        } catch (e) {
          // Ignore errors - just means they don't exist
          setHasPRD(false);
          setHasLeanCanvas(false);
        }
        
        // Check if Linear integration is connected
        try {
          const intRes = await integrationsAPI.getProviderStatus('linear');
          setHasLinearIntegration(intRes.data?.connected || false);
        } catch (e) {
          // Ignore - may not have subscription or integration
          setHasLinearIntegration(false);
        }
        
        // If fully complete (all features approved, all have approved stories), redirect to review
        if (featuresData.length > 0 && allFeaturesComplete && hasAnyStories) {
          navigate(`/epic/${epicId}/review`);
          return;
        }
      }
    } catch (err) {
      if (err.response?.status === 404) { navigate('/dashboard'); }
    } finally {
      setLoading(false);
    }
  }, [epicId, navigate]);

  useEffect(() => { loadEpic(); }, [loadEpic]);

  // Generate feature suggestions using new API
  const generateFeatureSuggestions = async () => {
    if (!isActive || !activeProvider) {
      setError('Active subscription and LLM provider required.');
      return;
    }
    
    setGeneratingFeatures(true);
    setError('');
    setGeneratedDrafts([]);
    
    try {
      const response = await featureAPI.generate(epicId, 5);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'features') {
                // Store generated features as drafts
                setGeneratedDrafts(data.features.map((f, i) => ({
                  tempId: `draft_${Date.now()}_${i}`,
                  ...f
                })));
              }
              else if (data.type === 'error') { 
                setError(data.message); 
              }
            } catch (e) { /* Ignore */ }
          }
        }
      }
    } catch (err) {
      setError('Failed to generate features. Please try again.');
    } finally {
      setGeneratingFeatures(false);
    }
  };

  // Save a draft feature to the database
  const handleSaveDraftFeature = async (draft) => {
    try {
      const res = await featureAPI.create(epicId, {
        title: draft.title,
        description: draft.description,
        acceptance_criteria: draft.acceptance_criteria,
        source: 'ai_generated'
      });
      
      // Add to features list and remove from drafts
      setFeatures(prev => [...prev, res.data]);
      setGeneratedDrafts(prev => prev.filter(d => d.tempId !== draft.tempId));
    } catch (err) {
      setError('Failed to save feature.');
    }
  };

  // Discard a draft
  const handleDiscardDraft = (tempId) => {
    setGeneratedDrafts(prev => prev.filter(d => d.tempId !== tempId));
  };

  // Open refinement dialog for a feature
  const handleOpenRefinement = async (feature) => {
    setSelectedFeature(feature);
    setFeatureConversation([]);
    setRefinementMessage('');
    setStreamingRefinement('');
    
    // Load existing conversation
    try {
      const res = await featureAPI.getConversation(feature.feature_id);
      setFeatureConversation(res.data || []);
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  };

  // Send refinement message
  const handleSendRefinement = async () => {
    if (!refinementMessage.trim() || sendingRefinement || !selectedFeature) return;
    
    setSendingRefinement(true);
    const userMsg = refinementMessage.trim();
    setRefinementMessage('');
    setStreamingRefinement('');
    
    // Optimistic UI update
    setFeatureConversation(prev => [...prev, { 
      event_id: `temp_${Date.now()}`, 
      role: 'user', 
      content: userMsg,
      created_at: new Date().toISOString()
    }]);

    try {
      const response = await featureAPI.chat(selectedFeature.feature_id, userMsg);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') { 
                fullContent += data.content; 
                setStreamingRefinement(fullContent);
              }
              else if (data.type === 'feature_updated') {
                // Feature was updated - refresh
                const updated = await featureAPI.get(selectedFeature.feature_id);
                setSelectedFeature(updated.data);
                setFeatures(prev => prev.map(f => 
                  f.feature_id === updated.data.feature_id ? updated.data : f
                ));
              }
              else if (data.type === 'done') {
                setFeatureConversation(prev => [...prev, {
                  event_id: `asst_${Date.now()}`,
                  role: 'assistant',
                  content: fullContent,
                  created_at: new Date().toISOString()
                }]);
                setStreamingRefinement('');
              }
              else if (data.type === 'error') {
                setError(data.message);
              }
            } catch (e) { /* Ignore */ }
          }
        }
      }
    } catch (err) {
      setError('Failed to send message.');
    } finally {
      setSendingRefinement(false);
    }
  };

  // Approve a feature
  const handleApproveFeature = async (featureId) => {
    try {
      const res = await featureAPI.approve(featureId);
      setFeatures(prev => prev.map(f => 
        f.feature_id === featureId ? res.data : f
      ));
      if (selectedFeature?.feature_id === featureId) {
        setSelectedFeature(res.data);
      }
    } catch (err) {
      setError('Failed to approve feature.');
    }
  };

  // Delete a feature
  const handleDeleteFeature = async (featureId) => {
    try {
      await featureAPI.delete(featureId);
      setFeatures(prev => prev.filter(f => f.feature_id !== featureId));
      if (selectedFeature?.feature_id === featureId) {
        setSelectedFeature(null);
      }
    } catch (err) {
      setError('Failed to delete feature.');
    }
  };

  // Create manual feature
  const handleCreateManual = async () => {
    if (!manualTitle.trim() || !manualDescription.trim()) return;
    setCreatingManual(true);
    try {
      const criteriaList = manualCriteria.split('\n').filter(c => c.trim());
      const res = await featureAPI.create(epicId, {
        title: manualTitle.trim(),
        description: manualDescription.trim(),
        acceptance_criteria: criteriaList.length > 0 ? criteriaList : null,
        source: 'manual'
      });
      setFeatures(prev => [...prev, res.data]);
      setShowManualCreate(false);
      setManualTitle('');
      setManualDescription('');
      setManualCriteria('');
    } catch (err) {
      setError('Failed to create feature.');
    } finally {
      setCreatingManual(false);
    }
  };

  // Epic creation flow handlers
  const handleSendMessage = async () => {
    if (!message.trim() || sending) return;
    if (!isActive) { setError('Active subscription required.'); return; }
    if (!activeProvider) { setError('No LLM provider configured.'); return; }

    const userMessage = message.trim();
    setMessage(''); setSending(true); setError(''); setStreamingContent('');

    const tempUserEvent = { event_id: `temp_${Date.now()}`, role: 'user', content: userMessage, stage: epic.current_stage, created_at: new Date().toISOString() };
    setTranscript(prev => [...prev, tempUserEvent]);

    try {
      const response = await epicAPI.chat(epicId, userMessage);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let receivedProposal = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') { fullContent += data.content; setStreamingContent(fullContent); }
              else if (data.type === 'proposal') { receivedProposal = data; }
              else if (data.type === 'error') { setError(data.message); }
              else if (data.type === 'done') {
                const assistantEvent = { event_id: `asst_${Date.now()}`, role: 'assistant', content: fullContent, stage: epic.current_stage, created_at: new Date().toISOString() };
                setTranscript(prev => [...prev, assistantEvent]);
                setStreamingContent('');
                if (receivedProposal) { setPendingProposal(receivedProposal); }
              }
            } catch (e) { /* Ignore */ }
          }
        }
      }
    } catch (err) {
      setTranscript(prev => prev.filter(e => e.event_id !== tempUserEvent.event_id));
      setError('Failed to send message.');
    } finally {
      setSending(false);
    }
  };

  const handleConfirmProposal = async (confirmed) => {
    if (!pendingProposal) return;
    setConfirmingProposal(true);
    try {
      const response = await epicAPI.confirmProposal(epicId, pendingProposal.proposal_id, confirmed);
      setEpic(response.data);
      setPendingProposal(null);
      const transcriptRes = await epicAPI.getTranscript(epicId);
      setTranscript(transcriptRes.data.events);
      const decisionsRes = await epicAPI.getDecisions(epicId);
      setDecisions(decisionsRes.data.decisions);
      
      if (confirmed && response.data.current_stage !== 'epic_locked') {
        setConfirmingProposal(false);
        await sendContinuationMessage(response.data.current_stage);
      }
    } catch (err) {
      setError('Failed to process proposal.');
    } finally {
      setConfirmingProposal(false);
    }
  };

  const sendContinuationMessage = async (newStage) => {
    setSending(true);
    setStreamingContent('');
    
    let continuationPrompt = "Let's continue.";
    if (newStage === 'outcome_capture') {
      continuationPrompt = "The problem is now confirmed. Let's define the desired outcome.";
    } else if (newStage === 'epic_drafted') {
      continuationPrompt = "The outcome is now confirmed. Let's draft the epic.";
    }
    
    const tempUserEvent = { event_id: `auto_${Date.now()}`, role: 'user', content: continuationPrompt, stage: newStage, created_at: new Date().toISOString() };
    setTranscript(prev => [...prev, tempUserEvent]);

    try {
      const response = await epicAPI.chat(epicId, continuationPrompt);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let receivedProposal = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') { fullContent += data.content; setStreamingContent(fullContent); }
              else if (data.type === 'proposal') { receivedProposal = data; }
              else if (data.type === 'done') {
                const assistantEvent = { event_id: `asst_${Date.now()}`, role: 'assistant', content: fullContent, stage: newStage, created_at: new Date().toISOString() };
                setTranscript(prev => [...prev, assistantEvent]);
                setStreamingContent('');
                if (receivedProposal) { setPendingProposal(receivedProposal); }
              }
            } catch (e) { /* Ignore */ }
          }
        }
      }
    } catch (err) {
      console.error('Continuation failed:', err);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };
  const getCurrentStageIndex = () => STAGE_INDEX[epic?.current_stage] || 0;
  const isEpicLocked = epic?.current_stage === 'epic_locked';

  const renderMessage = (event) => {
    const isUser = event.role === 'user';
    const isSystem = event.role === 'system';

    if (isSystem) {
      return (
        <div key={event.event_id} className="flex justify-center my-4">
          <Badge variant="outline" className="bg-muted text-muted-foreground border-border">{event.content}</Badge>
        </div>
      );
    }

    return (
      <div key={event.event_id} className={`flex gap-3 mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
        {!isUser && (
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
            <Bot className="w-4 h-4 text-primary" />
          </div>
        )}
        <div className={`max-w-[80%] rounded-lg px-4 py-3 ${isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'}`}>
          <p className="whitespace-pre-wrap">{event.content}</p>
        </div>
        {isUser && (
          <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-secondary-foreground" />
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (<div className="min-h-screen bg-background flex items-center justify-center"><Loader2 className="w-8 h-8 text-primary animate-spin" /></div>);
  }

  if (!epic) {
    return (<div className="min-h-screen bg-background flex items-center justify-center"><p className="text-muted-foreground">Epic not found</p></div>);
  }

  // ============================================
  // FEATURE PLANNING MODE (Epic Locked)
  // ============================================
  if (isEpicLocked) {
    const draftFeatures = features.filter(f => f.current_stage === 'draft');
    const refiningFeatures = features.filter(f => f.current_stage === 'refining');
    const approvedFeatures = features.filter(f => f.current_stage === 'approved');
    
    // Calculate workflow progress
    const allFeaturesApproved = features.length > 0 && approvedFeatures.length === features.length;
    const featuresWithCompleteStories = approvedFeatures.filter(f => featureStoryCounts[f.feature_id]?.allApproved).length;
    const allStoriesComplete = allFeaturesApproved && featuresWithCompleteStories === approvedFeatures.length && approvedFeatures.length > 0;

    return (
      <div className="flex flex-col overflow-hidden -m-6" style={{ height: 'calc(100vh - 4rem)' }}>
        {/* Page Title Bar */}
        <div className="flex-shrink-0 border-b-2 border-violet-500/50 bg-violet-500/5" data-testid="feature-planning-header">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-4 h-14">
              <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground" data-testid="back-to-dashboard-btn">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Epic:</span>
                <span className="text-foreground font-medium">{epic.title}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Workflow Stepper */}
        <WorkflowStepper 
          currentStep={allFeaturesApproved ? 'stories' : 'features'}
          featuresComplete={allFeaturesApproved}
          storiesComplete={allStoriesComplete}
          totalFeatures={features.length}
          featuresWithStories={featuresWithCompleteStories}
        />

        {/* Feature Planning Banner */}
        <div className="flex-shrink-0 bg-gradient-to-r from-violet-500/20 via-purple-500/20 to-violet-500/20 border-b border-violet-500/30">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-violet-500/20 flex items-center justify-center">
                  <Sparkles className="w-6 h-6 text-violet-400" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-foreground">Feature Planning Mode</h1>
                  <p className="text-sm text-muted-foreground">Generate features with AI, refine them through conversation, then approve to lock</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {/* PRD and Lean Canvas Quick Links */}
                {(hasPRD || hasLeanCanvas || hasLinearIntegration) && (
                  <div className="flex items-center gap-2 mr-4">
                    {hasLinearIntegration && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowPushToLinear(true)}
                        className="bg-[#5E6AD2]/10 border-[#5E6AD2]/30 hover:bg-[#5E6AD2]/20"
                        data-testid="push-to-linear-btn"
                      >
                        <Upload className="w-4 h-4 mr-2 text-[#5E6AD2]" />
                        Push to Linear
                      </Button>
                    )}
                    {hasLeanCanvas && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/lean-canvas?epic=${epicId}`)}
                        className="bg-purple-500/10 border-purple-500/30 hover:bg-purple-500/20"
                        data-testid="view-lean-canvas-btn"
                      >
                        <LayoutGrid className="w-4 h-4 mr-2 text-purple-400" />
                        Lean Canvas
                      </Button>
                    )}
                    {hasPRD && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/prd?epic=${epicId}`)}
                        className="bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20"
                        data-testid="view-prd-btn"
                      >
                        <FileText className="w-4 h-4 mr-2 text-blue-400" />
                        PRD
                      </Button>
                    )}
                  </div>
                )}
                {/* Show create buttons if documents don't exist */}
                {(!hasPRD || !hasLeanCanvas) && (
                  <div className="flex items-center gap-2 mr-4">
                    {!hasLeanCanvas && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/lean-canvas?epic=${epicId}&create=true`)}
                        className="bg-purple-500/5 border-purple-500/20 hover:bg-purple-500/10"
                        data-testid="create-lean-canvas-btn"
                      >
                        <LayoutGrid className="w-4 h-4 mr-2 text-purple-400/70" />
                        + Lean Canvas
                      </Button>
                    )}
                    {!hasPRD && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/prd?epic=${epicId}&create=true`)}
                        className="bg-blue-500/5 border-blue-500/20 hover:bg-blue-500/10"
                        data-testid="create-prd-btn"
                      >
                        <FileText className="w-4 h-4 mr-2 text-blue-400/70" />
                        + PRD
                      </Button>
                    )}
                  </div>
                )}
                <div className="flex items-center gap-6 text-center">
                  <div>
                    <p className="text-lg font-bold text-amber-400">{draftFeatures.length + generatedDrafts.length}</p>
                    <p className="text-xs text-muted-foreground">Drafts</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-violet-400">{refiningFeatures.length}</p>
                    <p className="text-xs text-muted-foreground">Refining</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-success">{approvedFeatures.length}</p>
                    <p className="text-xs text-muted-foreground">Approved</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto space-y-8">
              
              {/* Generate Features CTA */}
              {features.length === 0 && generatedDrafts.length === 0 && (
                <Card className="border-2 border-dashed border-violet-500/30 bg-violet-500/5" data-testid="generate-features-cta">
                  <CardContent className="p-8 text-center">
                    <div className="w-16 h-16 rounded-2xl bg-violet-500/20 flex items-center justify-center mx-auto mb-4">
                      <Sparkles className="w-8 h-8 text-violet-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Break Down Your Epic</h3>
                    <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                      Let AI analyze your locked epic and suggest implementable features. Review each one, refine through conversation, then approve.
                    </p>
                    <div className="flex gap-3 justify-center">
                      <Button 
                        onClick={generateFeatureSuggestions}
                        disabled={generatingFeatures}
                        className="bg-violet-500 hover:bg-violet-600 text-white"
                        data-testid="generate-features-btn"
                      >
                        {generatingFeatures ? (
                          <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating...</>
                        ) : (
                          <><Sparkles className="w-4 h-4 mr-2" /> Generate Features</>
                        )}
                      </Button>
                      <Button variant="outline" onClick={() => setShowManualCreate(true)} data-testid="create-manual-btn">
                        <Plus className="w-4 h-4 mr-2" />
                        Create Manually
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Generated Drafts (not yet saved) */}
              {generatedDrafts.length > 0 && (
                <div data-testid="generated-drafts-section">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-violet-400" />
                      AI Generated ({generatedDrafts.length})
                    </h2>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={generateFeatureSuggestions}
                      disabled={generatingFeatures}
                      className="border-violet-500/50 text-violet-400"
                      data-testid="regenerate-btn"
                    >
                      <RefreshCw className={`w-4 h-4 mr-1 ${generatingFeatures ? 'animate-spin' : ''}`} />
                      Regenerate
                    </Button>
                  </div>
                  
                  <div className="space-y-4">
                    {generatedDrafts.map((draft) => (
                      <Card key={draft.tempId} className="border-violet-500/30 bg-violet-500/5" data-testid={`draft-card-${draft.tempId}`}>
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-violet-500/20 flex items-center justify-center">
                                <Sparkles className="w-5 h-5 text-violet-400" />
                              </div>
                              <div>
                                <CardTitle className="text-base text-foreground">{draft.title}</CardTitle>
                                <Badge variant="outline" className="text-xs mt-1 bg-violet-500/10 text-violet-400 border-violet-500/30">
                                  AI Generated - Not Saved
                                </Badge>
                              </div>
                            </div>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          <p className="text-sm text-muted-foreground">{draft.description}</p>
                          
                          {draft.acceptance_criteria?.length > 0 && (
                            <div className="bg-background/50 rounded-lg p-3">
                              <p className="text-xs font-medium text-foreground mb-2">Acceptance Criteria:</p>
                              <ul className="text-xs text-muted-foreground space-y-1">
                                {draft.acceptance_criteria.map((c, i) => (
                                  <li key={i} className="flex items-start gap-2">
                                    <span className="text-violet-400">•</span>
                                    {c}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          
                          <div className="flex gap-2 pt-2">
                            <Button 
                              size="sm" 
                              onClick={() => handleSaveDraftFeature(draft)}
                              className="bg-violet-500 hover:bg-violet-600"
                              data-testid={`save-draft-btn-${draft.tempId}`}
                            >
                              <Plus className="w-4 h-4 mr-1" />
                              Save as Draft
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => handleDiscardDraft(draft.tempId)}
                              className="border-destructive/50 text-destructive"
                              data-testid={`discard-draft-btn-${draft.tempId}`}
                            >
                              <XCircle className="w-4 h-4 mr-1" />
                              Discard
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* Draft Features (saved but not yet refined) */}
              {draftFeatures.length > 0 && (
                <div data-testid="draft-features-section">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <Edit3 className="w-5 h-5 text-amber-400" />
                      Draft Features ({draftFeatures.length})
                    </h2>
                  </div>
                  
                  <div className="space-y-4">
                    {draftFeatures.map((feature) => (
                      <FeatureCard 
                        key={feature.feature_id} 
                        feature={feature}
                        onRefine={() => handleOpenRefinement(feature)}
                        onApprove={() => handleApproveFeature(feature.feature_id)}
                        onDelete={() => handleDeleteFeature(feature.feature_id)}
                        onScoreUpdate={loadEpic}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Refining Features (in conversation) */}
              {refiningFeatures.length > 0 && (
                <div data-testid="refining-features-section">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <MessageSquare className="w-5 h-5 text-violet-400" />
                      In Refinement ({refiningFeatures.length})
                    </h2>
                  </div>
                  
                  <div className="space-y-4">
                    {refiningFeatures.map((feature) => (
                      <FeatureCard 
                        key={feature.feature_id} 
                        feature={feature}
                        onRefine={() => handleOpenRefinement(feature)}
                        onApprove={() => handleApproveFeature(feature.feature_id)}
                        onDelete={() => handleDeleteFeature(feature.feature_id)}
                        onScoreUpdate={loadEpic}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Approved Features (locked) */}
              {approvedFeatures.length > 0 && (
                <div data-testid="approved-features-section">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <Lock className="w-5 h-5 text-success" />
                      Approved & Locked ({approvedFeatures.length})
                    </h2>
                    {/* Progress indicator */}
                    {approvedFeatures.length > 0 && (
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-muted-foreground">Story Progress:</span>
                        <span className="text-success font-medium">
                          {approvedFeatures.filter(f => featureStoryCounts[f.feature_id]?.allApproved).length}/{approvedFeatures.length} complete
                        </span>
                      </div>
                    )}
                  </div>
                  
                  <div className="space-y-4">
                    {approvedFeatures.map((feature) => (
                      <FeatureCard 
                        key={feature.feature_id} 
                        feature={feature}
                        storyCount={featureStoryCounts[feature.feature_id]}
                        onDelete={() => handleDeleteFeature(feature.feature_id)}
                        onCreateStories={() => navigate(`/feature/${feature.feature_id}/stories`)}
                        onScoreUpdate={loadEpic}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Action buttons when features exist */}
              {(features.length > 0 || generatedDrafts.length > 0) && (
                <div className="flex gap-3 justify-center pt-4" data-testid="feature-actions">
                  <Button 
                    variant="outline" 
                    onClick={generateFeatureSuggestions}
                    disabled={generatingFeatures}
                    className="border-violet-500/50 text-violet-400"
                    data-testid="generate-more-btn"
                  >
                    {generatingFeatures ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    Generate More
                  </Button>
                  <Button variant="outline" onClick={() => setShowManualCreate(true)} data-testid="add-manual-btn">
                    <Plus className="w-4 h-4 mr-2" />
                    Add Manually
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Sidebar - Epic Reference */}
          <div className="w-80 flex-shrink-0 border-l border-border bg-card/50 hidden lg:flex lg:flex-col overflow-hidden" data-testid="epic-reference-sidebar">
            <div className="p-4 border-b border-border bg-muted/30">
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                <FileText className="w-4 h-4 text-muted-foreground" />
                Epic Reference
              </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                  Problem <Lock className="w-3 h-3" />
                </h4>
                <p className="text-xs text-foreground bg-muted p-2 rounded">{epic.snapshot?.problem_statement || 'N/A'}</p>
              </div>
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                  Outcome <Lock className="w-3 h-3" />
                </h4>
                <p className="text-xs text-foreground bg-muted p-2 rounded">{epic.snapshot?.desired_outcome || 'N/A'}</p>
              </div>
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                  Summary <Lock className="w-3 h-3" />
                </h4>
                <p className="text-xs text-foreground bg-muted p-2 rounded">{epic.snapshot?.epic_summary || 'N/A'}</p>
              </div>
              {epic.snapshot?.acceptance_criteria?.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                    Criteria <Lock className="w-3 h-3" />
                  </h4>
                  <ul className="text-xs text-foreground bg-muted p-2 rounded space-y-1">
                    {epic.snapshot.acceptance_criteria.map((c, i) => (
                      <li key={i} className="flex items-start gap-1">
                        <CheckCircle2 className="w-3 h-3 text-success mt-0.5 flex-shrink-0" />
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Linked Bugs Section */}
              <div className="pt-4">
                <LinkedBugs
                  entityType="epic"
                  entityId={epic.epic_id}
                  entityTitle={epic.title}
                  collapsed={true}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Feature Refinement Dialog */}
        <Dialog open={!!selectedFeature} onOpenChange={() => setSelectedFeature(null)}>
          <DialogContent className="bg-card border-border max-w-2xl max-h-[80vh] flex flex-col" data-testid="refinement-dialog">
            <DialogHeader>
              <DialogTitle className="text-foreground flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-violet-400" />
                Refine Feature
              </DialogTitle>
              <DialogDescription>
                Chat with AI to improve this feature before approving
              </DialogDescription>
            </DialogHeader>
            
            {selectedFeature && (
              <div className="flex-1 flex flex-col min-h-0 space-y-4">
                {/* Current Feature State */}
                <Card className="bg-muted/50 flex-shrink-0">
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-foreground">{selectedFeature.title}</p>
                      <Badge variant="outline" className={FEATURE_STAGES[selectedFeature.current_stage]?.color}>
                        {FEATURE_STAGES[selectedFeature.current_stage]?.label}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{selectedFeature.description}</p>
                    {selectedFeature.acceptance_criteria?.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-border">
                        <p className="text-xs font-medium text-muted-foreground mb-1">Acceptance Criteria:</p>
                        <ul className="text-xs text-muted-foreground">
                          {selectedFeature.acceptance_criteria.map((c, i) => (
                            <li key={i}>• {c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
                
                {/* Conversation */}
                <div className="flex-1 overflow-y-auto space-y-3 bg-background rounded-lg p-3 min-h-[200px]">
                  {featureConversation.filter(m => m.role !== 'system').map((msg, i) => (
                    <div key={msg.event_id || i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {msg.role !== 'user' && (
                        <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                          <Bot className="w-3 h-3 text-primary" />
                        </div>
                      )}
                      <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                        msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                      }`}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      </div>
                      {msg.role === 'user' && (
                        <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
                          <User className="w-3 h-3 text-secondary-foreground" />
                        </div>
                      )}
                    </div>
                  ))}
                  {streamingRefinement && (
                    <div className="flex gap-2 justify-start">
                      <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                        <Bot className="w-3 h-3 text-primary" />
                      </div>
                      <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-muted text-foreground">
                        <p className="whitespace-pre-wrap">{streamingRefinement}</p>
                        <span className="inline-block w-2 h-3 bg-primary animate-pulse ml-1" />
                      </div>
                    </div>
                  )}
                  <div ref={refinementEndRef} />
                </div>
                
                {/* Input */}
                {selectedFeature.current_stage !== 'approved' && (
                  <div className="flex gap-2 flex-shrink-0">
                    <Textarea
                      value={refinementMessage}
                      onChange={(e) => setRefinementMessage(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendRefinement(); }}}
                      placeholder="Suggest changes... (e.g., 'Make the description more specific' or 'Add an acceptance criterion for error handling')"
                      disabled={sendingRefinement}
                      className="bg-background border-border text-foreground resize-none"
                      rows={2}
                      data-testid="refinement-input"
                    />
                    <Button
                      onClick={handleSendRefinement}
                      disabled={!refinementMessage.trim() || sendingRefinement}
                      className="bg-violet-500 hover:bg-violet-600 h-auto"
                      data-testid="send-refinement-btn"
                    >
                      {sendingRefinement ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                    </Button>
                  </div>
                )}
              </div>
            )}
            
            <DialogFooter className="flex-shrink-0">
              <Button variant="outline" onClick={() => setSelectedFeature(null)} data-testid="close-refinement-btn">Close</Button>
              {selectedFeature?.current_stage !== 'approved' && (
                <Button 
                  onClick={() => {
                    handleApproveFeature(selectedFeature.feature_id);
                    setSelectedFeature(null);
                  }}
                  className="bg-success hover:bg-success/90"
                  data-testid="approve-feature-btn"
                >
                  <CheckCircle2 className="w-4 h-4 mr-1" />
                  Approve & Lock
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Manual Create Dialog */}
        <Dialog open={showManualCreate} onOpenChange={setShowManualCreate}>
          <DialogContent className="bg-card border-border" data-testid="manual-create-dialog">
            <DialogHeader>
              <DialogTitle className="text-foreground">Create Feature Manually</DialogTitle>
              <DialogDescription>Add a custom feature to this epic</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm text-foreground">Title</label>
                <Input
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="Feature title..."
                  className="bg-background border-border text-foreground"
                  data-testid="manual-title-input"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm text-foreground">Description</label>
                <Textarea
                  value={manualDescription}
                  onChange={(e) => setManualDescription(e.target.value)}
                  placeholder="Describe the feature..."
                  className="bg-background border-border text-foreground min-h-[100px]"
                  data-testid="manual-description-input"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm text-foreground">Acceptance Criteria (one per line)</label>
                <Textarea
                  value={manualCriteria}
                  onChange={(e) => setManualCriteria(e.target.value)}
                  placeholder="Given... When... Then..."
                  className="bg-background border-border text-foreground min-h-[80px]"
                  data-testid="manual-criteria-input"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowManualCreate(false)}>Cancel</Button>
              <Button 
                onClick={handleCreateManual} 
                disabled={creatingManual || !manualTitle.trim() || !manualDescription.trim()}
                className="bg-violet-500 hover:bg-violet-600"
                data-testid="create-feature-btn"
              >
                {creatingManual ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Create Feature
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Push to Linear Modal */}
        <PushToLinearModal
          isOpen={showPushToLinear}
          onClose={() => setShowPushToLinear(false)}
          epicId={epicId}
          epicTitle={epic?.title || ''}
        />

        {/* Error Toast */}
        {error && (
          <div className="fixed bottom-4 right-4 bg-destructive text-destructive-foreground px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 z-50" data-testid="error-toast">
            <AlertCircle className="w-5 h-5" />
            <p className="text-sm">{error}</p>
            <Button variant="ghost" size="sm" onClick={() => setError('')} className="text-destructive-foreground hover:bg-destructive-foreground/10">
              Dismiss
            </Button>
          </div>
        )}
      </div>
    );
  }

  // ============================================
  // EPIC CREATION MODE (Not Locked)
  // ============================================
  return (
    <div className="flex flex-col overflow-hidden -m-6" style={{ height: 'calc(100vh - 4rem)' }} data-testid="epic-creation-page">
      {/* Page Title Bar */}
      <div className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4 h-14">
            <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground" data-testid="back-btn"><ArrowLeft className="w-5 h-5" /></Button>
            <div>
              <h1 className="text-lg font-semibold text-foreground line-clamp-1">{epic.title}</h1>
              <p className="text-xs text-muted-foreground">Epic Creation</p>
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Stepper - Epic Definition Mode */}
      <WorkflowStepper 
        currentStep="definition"
        featuresComplete={false}
        storiesComplete={false}
        totalFeatures={0}
        featuresWithStories={0}
      />

      <div className="flex-shrink-0 border-b border-border bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between gap-2" data-testid="stage-progress">
            {STAGES.map((stage, index) => {
              const currentIndex = getCurrentStageIndex();
              const isCompleted = index < currentIndex;
              const isCurrent = index === currentIndex;
              const isLocked = stage.locked && (isCompleted || isCurrent);
              return (
                <React.Fragment key={stage.id}>
                  <div className="flex flex-col items-center">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${isCompleted ? 'bg-success text-success-foreground' : isCurrent ? 'bg-primary text-primary-foreground ring-2 ring-primary/30' : 'bg-muted text-muted-foreground'}`}>
                      {isCompleted ? (isLocked ? <Lock className="w-3 h-3" /> : <CheckCircle2 className="w-4 h-4" />) : (index + 1)}
                    </div>
                    <span className={`text-xs mt-1 hidden sm:block ${isCurrent ? 'text-primary font-medium' : 'text-muted-foreground'}`}>{stage.label}</span>
                  </div>
                  {index < STAGES.length - 1 && (<div className={`flex-1 h-1 rounded ${index < currentIndex ? 'bg-success' : 'bg-border'}`} />)}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0">
          <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4" data-testid="chat-container">
            <div className="max-w-3xl mx-auto">
              {transcript.length === 0 && !streamingContent ? (
                <div className="text-center py-20">
                  <Layers className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-foreground mb-2">Start the Conversation</h3>
                  <p className="text-muted-foreground">Describe the problem you&apos;re trying to solve</p>
                </div>
              ) : (
                <>
                  {transcript.map(renderMessage)}
                  {streamingContent && (
                    <div className="flex gap-3 mb-4">
                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0"><Bot className="w-4 h-4 text-primary" /></div>
                      <div className="max-w-[80%] rounded-lg px-4 py-3 bg-muted text-foreground">
                        <p className="whitespace-pre-wrap">{streamingContent}</p>
                        <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
                      </div>
                    </div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {pendingProposal && (
            <div className="flex-shrink-0 border-t border-warning/30 bg-warning/10 p-4" data-testid="pending-proposal">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-start gap-4">
                  <AlertCircle className="w-6 h-6 text-warning flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <h4 className="text-foreground font-medium mb-2">Pending Proposal</h4>
                    <p className="text-muted-foreground text-sm mb-3">The AI has proposed the following. Do you want to confirm it?</p>
                    <div className="bg-card rounded-lg p-4 mb-4 border border-warning/30 max-h-48 overflow-y-auto">
                      <p className="text-foreground whitespace-pre-wrap text-sm">{pendingProposal.content}</p>
                    </div>
                    <div className="flex gap-3">
                      <Button onClick={() => handleConfirmProposal(true)} disabled={confirmingProposal} className="bg-success hover:bg-success/90 text-success-foreground" data-testid="confirm-proposal-btn">
                        {confirmingProposal ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CheckCircle2 className="w-4 h-4 mr-2" />} Confirm
                      </Button>
                      <Button onClick={() => handleConfirmProposal(false)} disabled={confirmingProposal} variant="outline" className="border-destructive/50 text-destructive hover:bg-destructive/10" data-testid="reject-proposal-btn">
                        <XCircle className="w-4 h-4 mr-2" /> Reject
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex-shrink-0 border-t border-destructive/30 bg-destructive/10 p-4">
              <div className="max-w-3xl mx-auto flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-destructive" />
                <p className="text-destructive text-sm">{error}</p>
                <Button variant="ghost" size="sm" onClick={() => setError('')} className="ml-auto text-destructive">Dismiss</Button>
              </div>
            </div>
          )}

          <div className="flex-shrink-0 border-t border-border p-4 bg-background" data-testid="chat-input-area">
            <div className="max-w-3xl mx-auto">
              <div className="flex gap-3">
                <Textarea placeholder="Type your message..." value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={handleKeyDown} disabled={sending || !!pendingProposal} className="bg-background border-border text-foreground resize-none min-h-[60px]" rows={2} data-testid="chat-input" />
                <Button onClick={handleSendMessage} disabled={!message.trim() || sending || !!pendingProposal} className="bg-primary hover:bg-primary/90 text-primary-foreground h-auto px-4" data-testid="send-message-btn">
                  {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="w-80 flex-shrink-0 border-l border-border bg-card/50 hidden lg:flex lg:flex-col overflow-hidden" data-testid="sidebar">
          {/* Next best action */}
          <div className="p-4 border-b border-border">
            {pendingProposal ? (
              <Card className="border-amber-500/30 bg-amber-500/5">
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                    <div className="min-w-0">
                      <div className="font-medium">Pending proposal</div>
                      <div className="text-sm text-muted-foreground mt-1">
                        Confirm or reject the AI proposal to progress this epic.
                      </div>
                      <div className="mt-3">
                        <Button
                          size="sm"
                          className="gap-2"
                          onClick={() => {
                            const el = document.querySelector('[data-testid="pending-proposal"]');
                            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                          }}
                        >
                          Review proposal
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <Target className="w-5 h-5 text-primary mt-0.5" />
                    <div className="min-w-0">
                      <div className="font-medium">Next best action</div>
                      <div className="text-sm text-muted-foreground mt-1">
                        {epic.current_stage === 'problem_capture' && 'Capture a crisp problem statement. Ask the AI to propose a concrete version.'}
                        {epic.current_stage === 'problem_confirmed' && 'Define a measurable desired outcome and success metrics.'}
                        {epic.current_stage === 'outcome_capture' && 'Define a measurable desired outcome and success metrics.'}
                        {epic.current_stage === 'outcome_confirmed' && 'Draft the epic summary and acceptance criteria.'}
                        {epic.current_stage === 'epic_drafted' && 'Finalize the epic summary and acceptance criteria, then lock the epic.'}
                        {epic.current_stage === 'epic_locked' && 'Epic is locked — move to Feature Planning Mode.'}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {epic.current_stage !== 'epic_locked' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const templates = {
                                problem_capture: 'Propose a concise problem statement (2-3 sentences) and 3 measurable success metrics.',
                                problem_confirmed: 'Propose a measurable desired outcome and 3-5 measurable key metrics with numeric targets.',
                                outcome_capture: 'Propose a measurable desired outcome and 3-5 measurable key metrics with numeric targets.',
                                outcome_confirmed: 'Draft the epic summary and 5-8 acceptance criteria. Keep criteria testable.',
                                epic_drafted: 'Review the epic for gaps: missing NFRs, unclear acceptance criteria, or stories that are too large. Propose fixes.',
                              };
                              setMessage(templates[epic.current_stage] || 'Help me refine this epic for implementation readiness.');
                              const input = document.querySelector('[data-testid="chat-input"]');
                              if (input) input.focus();
                            }}
                          >
                            Ask AI
                          </Button>
                        )}
                        <Button
                          size="sm"
                          onClick={() => navigate('/delivery-reality/' + epic.epic_id)}
                          className="gap-2"
                        >
                          Delivery Reality
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
          <Tabs defaultValue="snapshot" className="flex-1 flex flex-col overflow-hidden">
            <TabsList className="flex-shrink-0 bg-transparent border-b border-border rounded-none p-0 h-auto">
              <TabsTrigger value="snapshot" className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-3"><FileText className="w-4 h-4 mr-2" /> Snapshot</TabsTrigger>
              <TabsTrigger value="history" className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-3"><History className="w-4 h-4 mr-2" /> Decisions</TabsTrigger>
            </TabsList>
            <TabsContent value="snapshot" className="flex-1 m-0 overflow-y-auto">
              <div className="p-4 space-y-4">
                <div>
                  <div className="flex items-center gap-2 mb-2"><h4 className="text-sm font-medium text-foreground">Problem Statement</h4>{epic.snapshot?.problem_statement && (<Lock className="w-3 h-3 text-success" />)}</div>
                  {epic.snapshot?.problem_statement ? (<p className="text-sm text-foreground bg-muted p-3 rounded-lg">{epic.snapshot.problem_statement}</p>) : (<p className="text-sm text-muted-foreground italic">Not yet defined</p>)}
                </div>
                <Separator className="bg-border" />
                <div>
                  <div className="flex items-center gap-2 mb-2"><h4 className="text-sm font-medium text-foreground">Desired Outcome</h4>{epic.snapshot?.desired_outcome && (<Lock className="w-3 h-3 text-success" />)}</div>
                  {epic.snapshot?.desired_outcome ? (<p className="text-sm text-foreground bg-muted p-3 rounded-lg">{epic.snapshot.desired_outcome}</p>) : (<p className="text-sm text-muted-foreground italic">Not yet defined</p>)}
                </div>
                <Separator className="bg-border" />
                <div>
                  <div className="flex items-center gap-2 mb-2"><h4 className="text-sm font-medium text-foreground">Epic Summary</h4>{epic.snapshot?.epic_summary && (<Lock className="w-3 h-3 text-success" />)}</div>
                  {epic.snapshot?.epic_summary ? (<p className="text-sm text-foreground bg-muted p-3 rounded-lg">{epic.snapshot.epic_summary}</p>) : (<p className="text-sm text-muted-foreground italic">Not yet defined</p>)}
                </div>
                {epic.snapshot?.acceptance_criteria?.length > 0 && (<><Separator className="bg-border" /><div><div className="flex items-center gap-2 mb-2"><h4 className="text-sm font-medium text-foreground">Acceptance Criteria</h4><Lock className="w-3 h-3 text-success" /></div><ul className="text-sm text-foreground bg-muted p-3 rounded-lg space-y-2">{epic.snapshot.acceptance_criteria.map((criterion, i) => (<li key={i} className="flex items-start gap-2"><CheckCircle2 className="w-4 h-4 text-success mt-0.5 flex-shrink-0" /><span>{criterion}</span></li>))}</ul></div></>)}
              </div>
            </TabsContent>
            <TabsContent value="history" className="flex-1 m-0 overflow-y-auto">
              <div className="p-4 space-y-4">
                {decisions.length === 0 ? (<p className="text-sm text-muted-foreground italic text-center py-8">No decisions recorded yet</p>) : (
                  decisions.map((decision) => (
                    <div key={decision.decision_id} className="bg-muted p-3 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        {decision.decision_type === 'confirm_proposal' || decision.decision_type === 'auto_advance' ? (<CheckCircle2 className="w-4 h-4 text-success" />) : (<XCircle className="w-4 h-4 text-destructive" />)}
                        <span className="text-sm font-medium text-foreground capitalize">{decision.decision_type.replace(/_/g, ' ')}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{decision.from_stage?.replace(/_/g, ' ')} → {decision.to_stage?.replace(/_/g, ' ') || 'same'}</p>
                      <p className="text-xs text-muted-foreground mt-1">{new Date(decision.created_at).toLocaleString()}</p>
                    </div>
                  ))
                )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

// Workflow Stepper Component
const WorkflowStepper = ({ currentStep, featuresComplete, storiesComplete, totalFeatures, featuresWithStories }) => {
  const getStepStatus = (stepId) => {
    if (stepId === 'definition') {
      return currentStep === 'definition' ? 'current' : 'complete';
    }
    if (stepId === 'features') {
      if (currentStep === 'definition') return 'upcoming';
      if (currentStep === 'features' && !featuresComplete) return 'current';
      return 'complete';
    }
    if (stepId === 'stories') {
      if (currentStep === 'definition') return 'upcoming';
      if (currentStep === 'features' && !featuresComplete) return 'upcoming';
      if (!storiesComplete) return 'current';
      return 'complete';
    }
    if (stepId === 'complete') {
      if (storiesComplete) return 'complete';
      return 'upcoming';
    }
    return 'upcoming';
  };

  return (
    <div className="bg-card/50 border-b border-border" data-testid="workflow-stepper">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex items-center justify-between">
          {WORKFLOW_STEPS.map((step, index) => {
            const status = getStepStatus(step.id);
            const StepIcon = step.icon;
            const isLast = index === WORKFLOW_STEPS.length - 1;
            
            return (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex items-center gap-3">
                  <div className={`
                    w-10 h-10 rounded-full flex items-center justify-center transition-all
                    ${status === 'complete' ? 'bg-success text-white' : ''}
                    ${status === 'current' ? 'bg-primary text-primary-foreground ring-2 ring-primary/30 ring-offset-2 ring-offset-background' : ''}
                    ${status === 'upcoming' ? 'bg-muted text-muted-foreground' : ''}
                  `}>
                    {status === 'complete' ? (
                      <CheckCircle2 className="w-5 h-5" />
                    ) : (
                      <StepIcon className="w-5 h-5" />
                    )}
                  </div>
                  <div className="hidden sm:block">
                    <p className={`text-sm font-medium ${status === 'upcoming' ? 'text-muted-foreground' : 'text-foreground'}`}>
                      {step.label}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {step.id === 'features' && totalFeatures > 0 
                        ? `${totalFeatures} features` 
                        : step.id === 'stories' && featuresWithStories !== undefined
                        ? `${featuresWithStories}/${totalFeatures} ready`
                        : step.description}
                    </p>
                  </div>
                </div>
                {!isLast && (
                  <div className={`flex-1 h-0.5 mx-4 ${status === 'complete' ? 'bg-success' : 'bg-border'}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// Feature Card Component
const FeatureCard = ({ feature, onRefine, onApprove, onDelete, onCreateStories, storyCount, onScoreUpdate }) => {
  const stageInfo = FEATURE_STAGES[feature.current_stage];
  const StageIcon = stageInfo?.icon || Edit3;
  const isApproved = feature.current_stage === 'approved';
  const [showScoring, setShowScoring] = useState(false);
  
  // Determine story status for approved features
  const hasStories = storyCount && storyCount.total > 0;
  const allStoriesApproved = storyCount && storyCount.allApproved;
  const storiesInProgress = hasStories && !allStoriesApproved;

  return (
    <>
      <Card className={`border-${isApproved ? 'success' : feature.current_stage === 'refining' ? 'violet-500' : 'amber-500'}/30 bg-${isApproved ? 'success' : feature.current_stage === 'refining' ? 'violet-500' : 'amber-500'}/5`} data-testid={`feature-card-${feature.feature_id}`}>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isApproved ? 'bg-success/20' : feature.current_stage === 'refining' ? 'bg-violet-500/20' : 'bg-amber-500/20'}`}>
                <StageIcon className={`w-5 h-5 ${isApproved ? 'text-success' : feature.current_stage === 'refining' ? 'text-violet-400' : 'text-amber-400'}`} />
              </div>
              <div>
                <CardTitle className="text-base text-foreground">{feature.title}</CardTitle>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <Badge variant="outline" className={`text-xs ${stageInfo?.color}`}>
                    {isApproved && <Lock className="w-3 h-3 mr-1" />}
                    {stageInfo?.label}
                  </Badge>
                  <Badge variant="outline" className="text-xs bg-muted text-muted-foreground">
                    {feature.source === 'ai_generated' ? 'AI' : 'Manual'}
                  </Badge>
                  {/* Scoring badges */}
                  {feature.moscow_score && <MoSCoWBadge score={feature.moscow_score} size="sm" />}
                  {feature.rice_total && <RICEBadge score={feature.rice_total} size="sm" />}
                  {/* Story status badge for approved features */}
                  {isApproved && (
                    allStoriesApproved ? (
                      <Badge variant="outline" className="text-xs bg-success/10 text-success border-success/30">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        {storyCount.total} Stories Done
                      </Badge>
                    ) : hasStories ? (
                      <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                        <BookOpen className="w-3 h-3 mr-1" />
                        {storyCount.approved}/{storyCount.total} Stories
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-xs bg-amber-500/10 text-amber-400 border-amber-500/30">
                        <AlertCircle className="w-3 h-3 mr-1" />
                        No Stories
                      </Badge>
                    )
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {/* Prioritize button */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowScoring(true)}
                className="text-violet-400 hover:text-violet-500 hover:bg-violet-500/10"
                data-testid={`prioritize-feature-btn-${feature.feature_id}`}
              >
                <TrendingUp className="w-4 h-4" />
              </Button>
              {onDelete && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onDelete}
                  className="text-muted-foreground hover:text-destructive"
                  data-testid={`delete-feature-btn-${feature.feature_id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{feature.description}</p>
          
          {feature.acceptance_criteria?.length > 0 && (
            <div className="bg-background/50 rounded-lg p-3">
              <p className="text-xs font-medium text-foreground mb-2">Acceptance Criteria:</p>
              <ul className="text-xs text-muted-foreground space-y-1">
                {feature.acceptance_criteria.map((c, i) => (
                  <li key={i} className="flex items-start gap-2">
                    {isApproved ? (
                      <CheckCircle2 className="w-3 h-3 mt-0.5 text-success flex-shrink-0" />
                    ) : (
                      <span className={feature.current_stage === 'refining' ? 'text-violet-400' : 'text-amber-400'}>•</span>
                    )}
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {!isApproved && (
            <div className="flex gap-2 pt-2">
              {onApprove && (
                <Button 
                  size="sm" 
                  onClick={onApprove}
                  className="bg-success hover:bg-success/90 text-white"
                  data-testid={`approve-btn-${feature.feature_id}`}
                >
                <CheckCircle2 className="w-4 h-4 mr-1" />
                Approve & Lock
              </Button>
            )}
            {onRefine && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={onRefine}
                className="border-violet-500/50 text-violet-400"
                data-testid={`refine-btn-${feature.feature_id}`}
              >
                <MessageSquare className="w-4 h-4 mr-1" />
                Refine with AI
              </Button>
            )}
          </div>
        )}
        
        {/* User Stories action for approved features */}
        {isApproved && onCreateStories && (
          <div className="flex gap-2 pt-2 border-t border-success/20">
            {allStoriesApproved ? (
              <Button 
                size="sm" 
                variant="outline"
                onClick={onCreateStories}
                className="border-success/50 text-success"
                data-testid={`view-stories-btn-${feature.feature_id}`}
              >
                <CheckCircle2 className="w-4 h-4 mr-1" />
                View Stories
              </Button>
            ) : storiesInProgress ? (
              <Button 
                size="sm" 
                onClick={onCreateStories}
                className="bg-blue-500 hover:bg-blue-600 text-white"
                data-testid={`continue-stories-btn-${feature.feature_id}`}
              >
                <BookOpen className="w-4 h-4 mr-1" />
                Continue Stories ({storyCount.approved}/{storyCount.total})
              </Button>
            ) : (
              <Button 
                size="sm" 
                onClick={onCreateStories}
                className="bg-blue-500 hover:bg-blue-600 text-white"
                data-testid={`create-stories-btn-${feature.feature_id}`}
              >
                <BookOpen className="w-4 h-4 mr-1" />
                Create User Stories
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
    
    {/* Scoring Dialog */}
    <FeatureScoringDialog
      open={showScoring}
      onOpenChange={setShowScoring}
      featureId={feature.feature_id}
      featureTitle={feature.title}
      onUpdate={onScoreUpdate}
    />
    </>
  );
};

export default Epic;
