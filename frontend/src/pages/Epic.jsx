import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { epicAPI } from '@/api';
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
import { 
  ArrowLeft, Send, Loader2, Lock, CheckCircle2, 
  XCircle, FileText, History, AlertCircle, Layers,
  User, Bot, Settings, Plus, Puzzle, BookOpen, Bug, Trash2,
  ChevronRight, Sparkles, RefreshCw, Edit3, MessageSquare
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

const ARTIFACT_ICONS = {
  feature: Puzzle,
  user_story: BookOpen,
  bug: Bug,
};

const Epic = () => {
  const { epicId } = useParams();
  const navigate = useNavigate();
  const { isActive } = useSubscriptionStore();
  const { activeProvider } = useLLMProviderStore();

  const [epic, setEpic] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [pendingProposal, setPendingProposal] = useState(null);
  const [confirmingProposal, setConfirmingProposal] = useState(false);
  const [error, setError] = useState('');
  
  // Feature creation state
  const [suggestedFeatures, setSuggestedFeatures] = useState([]);
  const [generatingFeatures, setGeneratingFeatures] = useState(false);
  const [featuresGenerated, setFeaturesGenerated] = useState(false);
  const [confirmingFeature, setConfirmingFeature] = useState(null);
  const [refiningFeature, setRefiningFeature] = useState(null);
  const [refinementChat, setRefinementChat] = useState([]);
  const [refinementMessage, setRefinementMessage] = useState('');
  const [sendingRefinement, setSendingRefinement] = useState(false);
  
  // Manual feature creation
  const [showManualCreate, setShowManualCreate] = useState(false);
  const [manualTitle, setManualTitle] = useState('');
  const [manualDescription, setManualDescription] = useState('');
  const [manualCriteria, setManualCriteria] = useState('');
  const [creatingManual, setCreatingManual] = useState(false);

  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [transcript, streamingContent, scrollToBottom]);

  const loadEpic = useCallback(async () => {
    try {
      const [epicRes, transcriptRes, decisionsRes, artifactsRes] = await Promise.all([
        epicAPI.get(epicId),
        epicAPI.getTranscript(epicId),
        epicAPI.getDecisions(epicId),
        epicAPI.listArtifacts(epicId),
      ]);
      setEpic(epicRes.data);
      setTranscript(transcriptRes.data.events);
      setDecisions(decisionsRes.data.decisions);
      setArtifacts(artifactsRes.data || []);
      if (epicRes.data.pending_proposal) {
        setPendingProposal(epicRes.data.pending_proposal);
      }
    } catch (err) {
      if (err.response?.status === 404) { navigate('/dashboard'); }
    } finally {
      setLoading(false);
    }
  }, [epicId, navigate]);

  useEffect(() => { loadEpic(); }, [loadEpic]);

  // Auto-generate features when epic is locked and no features exist
  const generateFeatureSuggestions = async () => {
    if (!isActive || !activeProvider) {
      setError('Active subscription and LLM provider required.');
      return;
    }
    
    setGeneratingFeatures(true);
    setError('');
    
    const prompt = `Based on this locked epic, suggest 3-5 specific features that would implement it. For each feature, provide:
1. A clear title
2. A description (2-3 sentences)
3. 2-3 acceptance criteria

Epic Summary: ${epic.snapshot?.epic_summary || 'Not available'}

Acceptance Criteria:
${epic.snapshot?.acceptance_criteria?.join('\n') || 'Not available'}

Format your response as a JSON array like this:
[
  {
    "title": "Feature Title",
    "description": "Feature description...",
    "acceptance_criteria": ["Criterion 1", "Criterion 2"]
  }
]

Only respond with the JSON array, no other text.`;

    try {
      const response = await epicAPI.chat(epicId, prompt);
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
              }
              else if (data.type === 'done') {
                // Parse the JSON response
                try {
                  // Find JSON array in the response
                  const jsonMatch = fullContent.match(/\[[\s\S]*\]/);
                  if (jsonMatch) {
                    const features = JSON.parse(jsonMatch[0]);
                    setSuggestedFeatures(features.map((f, i) => ({
                      id: `suggested_${Date.now()}_${i}`,
                      title: f.title,
                      description: f.description,
                      acceptance_criteria: f.acceptance_criteria || [],
                      status: 'pending' // pending, confirmed, rejected
                    })));
                    setFeaturesGenerated(true);
                  }
                } catch (parseErr) {
                  console.error('Failed to parse features:', parseErr);
                  setError('Failed to parse AI suggestions. Please try again.');
                }
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

  const handleConfirmFeature = async (feature) => {
    setConfirmingFeature(feature.id);
    try {
      await epicAPI.createArtifact(epicId, {
        artifact_type: 'feature',
        title: feature.title,
        description: feature.description,
        acceptance_criteria: feature.acceptance_criteria,
      });
      
      // Remove from suggestions and refresh artifacts
      setSuggestedFeatures(prev => prev.filter(f => f.id !== feature.id));
      const artifactsRes = await epicAPI.listArtifacts(epicId);
      setArtifacts(artifactsRes.data || []);
    } catch (err) {
      setError('Failed to confirm feature.');
    } finally {
      setConfirmingFeature(null);
    }
  };

  const handleRejectFeature = (featureId) => {
    setSuggestedFeatures(prev => prev.filter(f => f.id !== featureId));
  };

  const handleStartRefinement = (feature) => {
    setRefiningFeature(feature);
    setRefinementChat([{
      role: 'system',
      content: `Refining feature: "${feature.title}". Current description: ${feature.description}`
    }]);
  };

  const handleSendRefinement = async () => {
    if (!refinementMessage.trim() || sendingRefinement) return;
    
    setSendingRefinement(true);
    const userMsg = refinementMessage.trim();
    setRefinementMessage('');
    setRefinementChat(prev => [...prev, { role: 'user', content: userMsg }]);

    const prompt = `The user wants to refine this feature:
Title: ${refiningFeature.title}
Description: ${refiningFeature.description}
Acceptance Criteria: ${refiningFeature.acceptance_criteria?.join(', ')}

User's refinement request: ${userMsg}

Please provide an updated version of the feature. Respond with JSON:
{
  "title": "Updated title",
  "description": "Updated description",
  "acceptance_criteria": ["Criterion 1", "Criterion 2"]
}

Only respond with the JSON, no other text.`;

    try {
      const response = await epicAPI.chat(epicId, prompt);
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
              }
              else if (data.type === 'done') {
                try {
                  const jsonMatch = fullContent.match(/\{[\s\S]*\}/);
                  if (jsonMatch) {
                    const updated = JSON.parse(jsonMatch[0]);
                    // Update the feature in suggestions
                    setSuggestedFeatures(prev => prev.map(f => 
                      f.id === refiningFeature.id 
                        ? { ...f, title: updated.title, description: updated.description, acceptance_criteria: updated.acceptance_criteria || [] }
                        : f
                    ));
                    setRefiningFeature(prev => ({
                      ...prev,
                      title: updated.title,
                      description: updated.description,
                      acceptance_criteria: updated.acceptance_criteria || []
                    }));
                    setRefinementChat(prev => [...prev, { 
                      role: 'assistant', 
                      content: `Updated the feature:\n\n**${updated.title}**\n\n${updated.description}\n\nAcceptance Criteria:\n${updated.acceptance_criteria?.map(c => `• ${c}`).join('\n') || 'None'}`
                    }]);
                  }
                } catch (parseErr) {
                  setRefinementChat(prev => [...prev, { role: 'assistant', content: fullContent }]);
                }
              }
            } catch (e) { /* Ignore */ }
          }
        }
      }
    } catch (err) {
      setRefinementChat(prev => [...prev, { role: 'assistant', content: 'Failed to process refinement. Please try again.' }]);
    } finally {
      setSendingRefinement(false);
    }
  };

  const handleCreateManual = async () => {
    if (!manualTitle.trim() || !manualDescription.trim()) return;
    setCreatingManual(true);
    try {
      const criteriaList = manualCriteria.split('\n').filter(c => c.trim());
      await epicAPI.createArtifact(epicId, {
        artifact_type: 'feature',
        title: manualTitle.trim(),
        description: manualDescription.trim(),
        acceptance_criteria: criteriaList.length > 0 ? criteriaList : null,
      });
      setShowManualCreate(false);
      setManualTitle('');
      setManualDescription('');
      setManualCriteria('');
      const artifactsRes = await epicAPI.listArtifacts(epicId);
      setArtifacts(artifactsRes.data || []);
    } catch (err) {
      setError('Failed to create feature.');
    } finally {
      setCreatingManual(false);
    }
  };

  const handleDeleteArtifact = async (artifactId) => {
    try {
      await epicAPI.deleteArtifact(epicId, artifactId);
      const artifactsRes = await epicAPI.listArtifacts(epicId);
      setArtifacts(artifactsRes.data || []);
    } catch (err) {
      setError('Failed to delete feature.');
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
    return (
      <div className="h-screen bg-background flex flex-col overflow-hidden">
        {/* Header */}
        <header className="flex-shrink-0 border-b-2 border-violet-500/50 bg-violet-500/5">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Epic:</span>
                  <span className="text-foreground font-medium">{epic.title}</span>
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  <Badge className="bg-violet-500 text-white">
                    <Puzzle className="w-3 h-3 mr-1" />
                    Feature Planning
                  </Badge>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-success/10 text-success border-success/30">
                  <Lock className="w-3 h-3 mr-1" />
                  Epic Locked
                </Badge>
                <ThemeToggle />
                <Button variant="ghost" size="icon" onClick={() => navigate('/settings')} className="text-muted-foreground hover:text-foreground">
                  <Settings className="w-5 h-5" />
                </Button>
              </div>
            </div>
          </div>
        </header>

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
                  <p className="text-sm text-muted-foreground">Review AI-suggested features, refine them, and lock in your approved features</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-foreground">{artifacts.length}</p>
                <p className="text-xs text-muted-foreground">Confirmed Features</p>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl mx-auto space-y-8">
              
              {/* Pending Feature Suggestions */}
              {!featuresGenerated && suggestedFeatures.length === 0 && (
                <Card className="border-2 border-dashed border-violet-500/30 bg-violet-500/5">
                  <CardContent className="p-8 text-center">
                    <div className="w-16 h-16 rounded-2xl bg-violet-500/20 flex items-center justify-center mx-auto mb-4">
                      <Sparkles className="w-8 h-8 text-violet-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Generate Feature Suggestions</h3>
                    <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                      Let AI analyze your epic and suggest specific features to implement. You can then review, refine, and approve each one.
                    </p>
                    <div className="flex gap-3 justify-center">
                      <Button 
                        onClick={generateFeatureSuggestions}
                        disabled={generatingFeatures}
                        className="bg-violet-500 hover:bg-violet-600 text-white"
                      >
                        {generatingFeatures ? (
                          <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating...</>
                        ) : (
                          <><Sparkles className="w-4 h-4 mr-2" /> Generate Features</>
                        )}
                      </Button>
                      <Button variant="outline" onClick={() => setShowManualCreate(true)}>
                        <Plus className="w-4 h-4 mr-2" />
                        Create Manually
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Suggested Features (Pending Approval) */}
              {suggestedFeatures.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-amber-400" />
                      Pending Review ({suggestedFeatures.length})
                    </h2>
                    <div className="flex gap-2">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={generateFeatureSuggestions}
                        disabled={generatingFeatures}
                        className="border-violet-500/50 text-violet-400"
                      >
                        <RefreshCw className={`w-4 h-4 mr-1 ${generatingFeatures ? 'animate-spin' : ''}`} />
                        Regenerate
                      </Button>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    {suggestedFeatures.map((feature) => (
                      <Card key={feature.id} className="border-amber-500/30 bg-amber-500/5">
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                                <Puzzle className="w-5 h-5 text-amber-400" />
                              </div>
                              <div>
                                <CardTitle className="text-base text-foreground">{feature.title}</CardTitle>
                                <Badge variant="outline" className="text-xs mt-1 bg-amber-500/10 text-amber-400 border-amber-500/30">
                                  Pending Approval
                                </Badge>
                              </div>
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
                                    <span className="text-amber-400">•</span>
                                    {c}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          
                          <div className="flex gap-2 pt-2">
                            <Button 
                              size="sm" 
                              onClick={() => handleConfirmFeature(feature)}
                              disabled={confirmingFeature === feature.id}
                              className="bg-success hover:bg-success/90 text-white"
                            >
                              {confirmingFeature === feature.id ? (
                                <Loader2 className="w-4 h-4 animate-spin mr-1" />
                              ) : (
                                <CheckCircle2 className="w-4 h-4 mr-1" />
                              )}
                              Approve & Lock
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => handleStartRefinement(feature)}
                              className="border-violet-500/50 text-violet-400"
                            >
                              <MessageSquare className="w-4 h-4 mr-1" />
                              Refine with AI
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => handleRejectFeature(feature.id)}
                              className="border-destructive/50 text-destructive"
                            >
                              <XCircle className="w-4 h-4 mr-1" />
                              Reject
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* Confirmed Features */}
              {artifacts.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <Lock className="w-5 h-5 text-success" />
                      Confirmed Features ({artifacts.length})
                    </h2>
                    <Button variant="outline" size="sm" onClick={() => setShowManualCreate(true)}>
                      <Plus className="w-4 h-4 mr-1" />
                      Add Feature
                    </Button>
                  </div>
                  
                  <div className="space-y-4">
                    {artifacts.map((artifact) => (
                      <Card key={artifact.artifact_id} className="border-success/30 bg-success/5">
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
                                <Puzzle className="w-5 h-5 text-success" />
                              </div>
                              <div>
                                <CardTitle className="text-base text-foreground">{artifact.title}</CardTitle>
                                <Badge variant="outline" className="text-xs mt-1 bg-success/10 text-success border-success/30">
                                  <Lock className="w-3 h-3 mr-1" />
                                  Locked
                                </Badge>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteArtifact(artifact.artifact_id)}
                              className="text-muted-foreground hover:text-destructive"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <p className="text-sm text-muted-foreground mb-3">{artifact.description}</p>
                          {artifact.acceptance_criteria?.length > 0 && (
                            <div className="bg-background/50 rounded-lg p-3">
                              <p className="text-xs font-medium text-foreground mb-2">Acceptance Criteria:</p>
                              <ul className="text-xs text-muted-foreground space-y-1">
                                {artifact.acceptance_criteria.map((c, i) => (
                                  <li key={i} className="flex items-start gap-2">
                                    <CheckCircle2 className="w-3 h-3 mt-0.5 text-success flex-shrink-0" />
                                    {c}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* Show generate button if features were generated but all handled */}
              {featuresGenerated && suggestedFeatures.length === 0 && (
                <div className="flex gap-3 justify-center pt-4">
                  <Button 
                    variant="outline" 
                    onClick={generateFeatureSuggestions}
                    disabled={generatingFeatures}
                    className="border-violet-500/50 text-violet-400"
                  >
                    {generatingFeatures ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                    Generate More Features
                  </Button>
                  <Button variant="outline" onClick={() => setShowManualCreate(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Add Manually
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Sidebar - Epic Reference */}
          <div className="w-80 flex-shrink-0 border-l border-border bg-card/50 hidden lg:flex lg:flex-col overflow-hidden">
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
            </div>
          </div>
        </div>

        {/* Refinement Dialog */}
        <Dialog open={!!refiningFeature} onOpenChange={() => setRefiningFeature(null)}>
          <DialogContent className="bg-card border-border max-w-2xl">
            <DialogHeader>
              <DialogTitle className="text-foreground flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-violet-400" />
                Refine Feature with AI
              </DialogTitle>
              <DialogDescription>
                Chat with AI to improve this feature before approving it
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Card className="bg-muted/50">
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-foreground">{refiningFeature?.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{refiningFeature?.description}</p>
                </CardContent>
              </Card>
              
              <div className="max-h-64 overflow-y-auto space-y-3 bg-background rounded-lg p-3">
                {refinementChat.filter(m => m.role !== 'system').map((msg, i) => (
                  <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                      msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                    }`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="flex gap-2">
                <Textarea
                  value={refinementMessage}
                  onChange={(e) => setRefinementMessage(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendRefinement(); }}}
                  placeholder="Suggest changes... (e.g., 'Make it more specific' or 'Add criteria for error handling')"
                  disabled={sendingRefinement}
                  className="bg-background border-border text-foreground resize-none"
                  rows={2}
                />
                <Button
                  onClick={handleSendRefinement}
                  disabled={!refinementMessage.trim() || sendingRefinement}
                  className="bg-violet-500 hover:bg-violet-600 h-auto"
                >
                  {sendingRefinement ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </Button>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRefiningFeature(null)}>Close</Button>
              <Button 
                onClick={() => {
                  handleConfirmFeature(refiningFeature);
                  setRefiningFeature(null);
                }}
                className="bg-success hover:bg-success/90"
              >
                <CheckCircle2 className="w-4 h-4 mr-1" />
                Approve & Lock
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Manual Create Dialog */}
        <Dialog open={showManualCreate} onOpenChange={setShowManualCreate}>
          <DialogContent className="bg-card border-border">
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
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm text-foreground">Description</label>
                <Textarea
                  value={manualDescription}
                  onChange={(e) => setManualDescription(e.target.value)}
                  placeholder="Describe the feature..."
                  className="bg-background border-border text-foreground min-h-[100px]"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm text-foreground">Acceptance Criteria (one per line)</label>
                <Textarea
                  value={manualCriteria}
                  onChange={(e) => setManualCriteria(e.target.value)}
                  placeholder="Given... When... Then..."
                  className="bg-background border-border text-foreground min-h-[80px]"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowManualCreate(false)}>Cancel</Button>
              <Button 
                onClick={handleCreateManual} 
                disabled={creatingManual || !manualTitle.trim() || !manualDescription.trim()}
                className="bg-violet-500 hover:bg-violet-600"
              >
                {creatingManual ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Create & Lock
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Error Toast */}
        {error && (
          <div className="fixed bottom-4 right-4 bg-destructive text-destructive-foreground px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
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
    <div className="h-screen bg-background flex flex-col overflow-hidden">
      <header className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur-sm z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground"><ArrowLeft className="w-5 h-5" /></Button>
              <div>
                <h1 className="text-lg font-semibold text-foreground line-clamp-1">{epic.title}</h1>
                <p className="text-xs text-muted-foreground">Epic Creation</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button variant="ghost" size="icon" onClick={() => navigate('/settings')} className="text-muted-foreground hover:text-foreground"><Settings className="w-5 h-5" /></Button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-shrink-0 border-b border-border bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between gap-2">
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
          <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4">
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
            <div className="flex-shrink-0 border-t border-warning/30 bg-warning/10 p-4">
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
                      <Button onClick={() => handleConfirmProposal(true)} disabled={confirmingProposal} className="bg-success hover:bg-success/90 text-success-foreground">
                        {confirmingProposal ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CheckCircle2 className="w-4 h-4 mr-2" />} Confirm
                      </Button>
                      <Button onClick={() => handleConfirmProposal(false)} disabled={confirmingProposal} variant="outline" className="border-destructive/50 text-destructive hover:bg-destructive/10">
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

          <div className="flex-shrink-0 border-t border-border p-4 bg-background">
            <div className="max-w-3xl mx-auto">
              <div className="flex gap-3">
                <Textarea placeholder="Type your message..." value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={handleKeyDown} disabled={sending || !!pendingProposal} className="bg-background border-border text-foreground resize-none min-h-[60px]" rows={2} />
                <Button onClick={handleSendMessage} disabled={!message.trim() || sending || !!pendingProposal} className="bg-primary hover:bg-primary/90 text-primary-foreground h-auto px-4">
                  {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="w-80 flex-shrink-0 border-l border-border bg-card/50 hidden lg:flex lg:flex-col overflow-hidden">
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

export default Epic;
