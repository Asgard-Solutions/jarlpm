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
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import ThemeToggle from '@/components/ThemeToggle';
import { 
  ArrowLeft, Send, Loader2, Lock, CheckCircle2, 
  XCircle, FileText, History, AlertCircle, Layers,
  User, Bot, Settings, Plus, Puzzle, BookOpen, Bug, Trash2
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
  const [showCreateArtifact, setShowCreateArtifact] = useState(false);
  const [artifactType, setArtifactType] = useState('feature');
  const [artifactTitle, setArtifactTitle] = useState('');
  const [artifactDescription, setArtifactDescription] = useState('');
  const [artifactCriteria, setArtifactCriteria] = useState('');
  const [creatingArtifact, setCreatingArtifact] = useState(false);
  const [featureChatMode, setFeatureChatMode] = useState(false);

  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const textareaRef = useRef(null);

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

  const handleSendMessage = async () => {
    if (!message.trim() || sending) return;
    if (!isActive) { setError('Active subscription required. Please subscribe in Settings.'); return; }
    if (!activeProvider) { setError('No LLM provider configured. Please add your API key in Settings.'); return; }

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
      if (err.message?.includes('402')) { setError('Active subscription required.'); }
      else { setError('Failed to send message. Please try again.'); }
      setTranscript(prev => prev.filter(e => e.event_id !== tempUserEvent.event_id));
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
      setError('Failed to process proposal. Please try again.');
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
              else if (data.type === 'error') { setError(data.message); }
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
      console.error('Continuation message failed:', err);
    } finally {
      setSending(false);
    }
  };

  const handleCreateArtifact = async () => {
    if (!artifactTitle.trim() || !artifactDescription.trim()) return;
    setCreatingArtifact(true);
    try {
      const criteriaList = artifactCriteria.split('\n').filter(c => c.trim());
      await epicAPI.createArtifact(epicId, {
        artifact_type: artifactType,
        title: artifactTitle.trim(),
        description: artifactDescription.trim(),
        acceptance_criteria: criteriaList.length > 0 ? criteriaList : null,
      });
      setShowCreateArtifact(false);
      setArtifactTitle('');
      setArtifactDescription('');
      setArtifactCriteria('');
      const artifactsRes = await epicAPI.listArtifacts(epicId);
      setArtifacts(artifactsRes.data || []);
    } catch (err) {
      setError('Failed to create artifact. Please try again.');
    } finally {
      setCreatingArtifact(false);
    }
  };

  const handleDeleteArtifact = async (artifactId) => {
    try {
      await epicAPI.deleteArtifact(epicId, artifactId);
      const artifactsRes = await epicAPI.listArtifacts(epicId);
      setArtifacts(artifactsRes.data || []);
    } catch (err) {
      setError('Failed to delete artifact.');
    }
  };

  const handleStartFeatureChat = () => {
    setFeatureChatMode(true);
    // Send initial message to AI to help create features
    const initMessage = "The epic is now locked. Help me break this down into features. Based on the epic summary and acceptance criteria, what features would you suggest?";
    setMessage(initMessage);
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

  return (
    <div className="h-screen bg-background flex flex-col overflow-hidden">
      {/* Fixed Header */}
      <header className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur-sm z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground" data-testid="back-to-dashboard-btn"><ArrowLeft className="w-5 h-5" /></Button>
              <div>
                <h1 className="text-lg font-semibold text-foreground line-clamp-1">{epic.title}</h1>
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  Epic {isEpicLocked && <><Lock className="w-3 h-3 text-success" /> Locked</>}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button variant="ghost" size="icon" onClick={() => navigate('/settings')} className="text-muted-foreground hover:text-foreground" data-testid="epic-settings-btn"><Settings className="w-5 h-5" /></Button>
            </div>
          </div>
        </div>
      </header>

      {/* Fixed Stage Progress */}
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
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                      isCompleted ? 'bg-success text-success-foreground' : isCurrent ? 'bg-primary text-primary-foreground ring-2 ring-primary/30' : 'bg-muted text-muted-foreground'
                    }`}>
                      {isCompleted ? (isLocked ? <Lock className="w-3 h-3" /> : <CheckCircle2 className="w-4 h-4" />) : isCurrent && isEpicLocked ? <Lock className="w-3 h-3" /> : (index + 1)}
                    </div>
                    <span className={`text-xs mt-1 hidden sm:block ${isCurrent ? 'text-primary font-medium' : 'text-muted-foreground'}`}>{stage.label}</span>
                  </div>
                  {index < STAGES.length - 1 && (<div className={`flex-1 h-1 rounded ${index < currentIndex ? 'bg-success' : isCurrent && isEpicLocked ? 'bg-success' : 'bg-border'}`} />)}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat/Features Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {isEpicLocked ? (
            /* Feature Management View for Locked Epics */
            <div className="flex-1 overflow-y-auto p-4">
              <div className="max-w-4xl mx-auto space-y-6">
                {/* Epic Complete Banner */}
                <Card className="bg-success/10 border-success/30">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center">
                        <CheckCircle2 className="w-5 h-5 text-success" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground">Epic Complete</h3>
                        <p className="text-sm text-muted-foreground">This epic is locked and ready for feature breakdown</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Features Section */}
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-foreground flex items-center gap-2">
                      <Puzzle className="w-5 h-5 text-primary" />
                      Features & Artifacts
                    </h2>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={handleStartFeatureChat}
                        className="border-primary/50 text-primary hover:bg-primary/10"
                        data-testid="ai-suggest-features-btn"
                      >
                        <Bot className="w-4 h-4 mr-2" />
                        AI Suggest Features
                      </Button>
                      <Dialog open={showCreateArtifact} onOpenChange={setShowCreateArtifact}>
                        <DialogTrigger asChild>
                          <Button className="bg-primary hover:bg-primary/90" data-testid="create-artifact-btn">
                            <Plus className="w-4 h-4 mr-2" />
                            Create Artifact
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-card border-border">
                          <DialogHeader>
                            <DialogTitle className="text-foreground">Create New Artifact</DialogTitle>
                            <DialogDescription className="text-muted-foreground">
                              Add a feature, user story, or bug to this epic
                            </DialogDescription>
                          </DialogHeader>
                          <div className="space-y-4 py-4">
                            <div className="flex gap-2">
                              {['feature', 'user_story', 'bug'].map((type) => {
                                const Icon = ARTIFACT_ICONS[type];
                                return (
                                  <Button
                                    key={type}
                                    variant={artifactType === type ? 'default' : 'outline'}
                                    onClick={() => setArtifactType(type)}
                                    className={artifactType === type ? 'bg-primary' : ''}
                                    size="sm"
                                  >
                                    <Icon className="w-4 h-4 mr-1" />
                                    {type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                  </Button>
                                );
                              })}
                            </div>
                            <div className="space-y-2">
                              <label className="text-sm text-foreground">Title</label>
                              <Input
                                value={artifactTitle}
                                onChange={(e) => setArtifactTitle(e.target.value)}
                                placeholder="Enter title..."
                                className="bg-background border-border text-foreground"
                              />
                            </div>
                            <div className="space-y-2">
                              <label className="text-sm text-foreground">Description</label>
                              <Textarea
                                value={artifactDescription}
                                onChange={(e) => setArtifactDescription(e.target.value)}
                                placeholder="Describe the artifact..."
                                className="bg-background border-border text-foreground min-h-[100px]"
                              />
                            </div>
                            <div className="space-y-2">
                              <label className="text-sm text-foreground">Acceptance Criteria (one per line)</label>
                              <Textarea
                                value={artifactCriteria}
                                onChange={(e) => setArtifactCriteria(e.target.value)}
                                placeholder="Given... When... Then..."
                                className="bg-background border-border text-foreground min-h-[80px]"
                              />
                            </div>
                          </div>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setShowCreateArtifact(false)}>Cancel</Button>
                            <Button 
                              onClick={handleCreateArtifact} 
                              disabled={creatingArtifact || !artifactTitle.trim() || !artifactDescription.trim()}
                              className="bg-primary hover:bg-primary/90"
                            >
                              {creatingArtifact ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                              Create
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </div>
                  </div>

                  {artifacts.length === 0 ? (
                    <Card className="border-dashed border-2 border-border bg-transparent">
                      <CardContent className="p-8 text-center">
                        <Puzzle className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                        <h3 className="text-lg font-medium text-foreground mb-2">No Features Yet</h3>
                        <p className="text-muted-foreground mb-4">Break down this epic into features, user stories, or bugs</p>
                        <div className="flex gap-2 justify-center">
                          <Button variant="outline" onClick={handleStartFeatureChat}>
                            <Bot className="w-4 h-4 mr-2" />
                            Get AI Suggestions
                          </Button>
                          <Button onClick={() => setShowCreateArtifact(true)} className="bg-primary hover:bg-primary/90">
                            <Plus className="w-4 h-4 mr-2" />
                            Create Manually
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="grid gap-4">
                      {artifacts.map((artifact) => {
                        const Icon = ARTIFACT_ICONS[artifact.artifact_type] || Puzzle;
                        return (
                          <Card key={artifact.artifact_id} className="bg-card border-border hover:border-primary/30 transition-colors">
                            <CardHeader className="pb-2">
                              <div className="flex items-start justify-between">
                                <div className="flex items-center gap-2">
                                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                                    artifact.artifact_type === 'feature' ? 'bg-primary/20 text-primary' :
                                    artifact.artifact_type === 'user_story' ? 'bg-blue-500/20 text-blue-500' :
                                    'bg-destructive/20 text-destructive'
                                  }`}>
                                    <Icon className="w-4 h-4" />
                                  </div>
                                  <div>
                                    <CardTitle className="text-base text-foreground">{artifact.title}</CardTitle>
                                    <Badge variant="outline" className="text-xs mt-1">
                                      {artifact.artifact_type.replace('_', ' ')}
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
                                <div className="bg-muted/50 rounded-lg p-3">
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
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* AI Chat for Feature Suggestions */}
                {featureChatMode && (
                  <Card className="border-primary/30">
                    <CardHeader>
                      <CardTitle className="text-foreground flex items-center gap-2">
                        <Bot className="w-5 h-5 text-primary" />
                        AI Feature Assistant
                      </CardTitle>
                      <CardDescription>
                        Chat with AI to help break down your epic into features
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="max-h-64 overflow-y-auto space-y-3 bg-muted/30 rounded-lg p-3">
                        {transcript.slice(-10).map(renderMessage)}
                        {streamingContent && (
                          <div className="flex gap-3">
                            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                              <Bot className="w-4 h-4 text-primary" />
                            </div>
                            <div className="max-w-[80%] rounded-lg px-4 py-3 bg-muted text-foreground">
                              <p className="whitespace-pre-wrap">{streamingContent}</p>
                              <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Textarea
                          value={message}
                          onChange={(e) => setMessage(e.target.value)}
                          onKeyDown={handleKeyDown}
                          placeholder="Ask about features..."
                          disabled={sending}
                          className="bg-background border-border text-foreground resize-none"
                          rows={2}
                        />
                        <Button
                          onClick={handleSendMessage}
                          disabled={!message.trim() || sending}
                          className="bg-primary hover:bg-primary/90 h-auto"
                        >
                          {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                        </Button>
                      </div>
                      <Button variant="outline" onClick={() => setFeatureChatMode(false)} className="w-full">
                        Close Chat
                      </Button>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          ) : (
            /* Regular Chat View for Unlocked Epics */
            <>
              <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4" data-testid="chat-messages">
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
                          <Button onClick={() => handleConfirmProposal(true)} disabled={confirmingProposal} className="bg-success hover:bg-success/90 text-success-foreground" data-testid="confirm-proposal-btn">
                            {confirmingProposal ? (<Loader2 className="w-4 h-4 animate-spin mr-2" />) : (<CheckCircle2 className="w-4 h-4 mr-2" />)} Confirm
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

              <div className="flex-shrink-0 border-t border-border p-4 bg-background">
                <div className="max-w-3xl mx-auto">
                  <div className="flex gap-3">
                    <Textarea ref={textareaRef} placeholder="Type your message..." value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={handleKeyDown} disabled={sending || !!pendingProposal} className="bg-background border-border text-foreground resize-none min-h-[60px]" rows={2} data-testid="chat-input" />
                    <Button onClick={handleSendMessage} disabled={!message.trim() || sending || !!pendingProposal} className="bg-primary hover:bg-primary/90 text-primary-foreground h-auto px-4" data-testid="send-message-btn">
                      {sending ? (<Loader2 className="w-5 h-5 animate-spin" />) : (<Send className="w-5 h-5" />)}
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Fixed Side Panel */}
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
