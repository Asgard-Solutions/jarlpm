import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { epicAPI } from '@/api';
import { useSubscriptionStore, useLLMProviderStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ThemeToggle from '@/components/ThemeToggle';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { 
  ArrowLeft, Send, Loader2, Lock, CheckCircle2, 
  XCircle, FileText, History, AlertCircle, Layers,
  User, Bot, Settings
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

const Epic = () => {
  const { epicId } = useParams();
  const navigate = useNavigate();
  const { isActive } = useSubscriptionStore();
  const { activeProvider } = useLLMProviderStore();

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

  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

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
    } catch (err) {
      if (err.response?.status === 404) { navigate('/dashboard'); }
    } finally {
      setLoading(false);
    }
  }, [epicId, navigate]);

  useEffect(() => { loadEpic(); }, [loadEpic]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript, streamingContent]);

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
            } catch (e) {}
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
    } catch (err) {
      setError('Failed to process proposal. Please try again.');
    } finally {
      setConfirmingProposal(false);
    }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };
  const getCurrentStageIndex = () => STAGE_INDEX[epic?.current_stage] || 0;

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
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground" data-testid="back-to-dashboard-btn"><ArrowLeft className="w-5 h-5" /></Button>
              <div><h1 className="text-lg font-semibold text-foreground line-clamp-1">{epic.title}</h1><p className="text-xs text-muted-foreground">Epic</p></div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button variant="ghost" size="icon" onClick={() => navigate('/settings')} className="text-muted-foreground hover:text-foreground" data-testid="epic-settings-btn"><Settings className="w-5 h-5" /></Button>
            </div>
          </div>
        </div>
      </header>

      {/* Stage Progress */}
      <div className="border-b border-border bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
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
                      {isCompleted ? (isLocked ? <Lock className="w-3 h-3" /> : <CheckCircle2 className="w-4 h-4" />) : (index + 1)}
                    </div>
                    <span className={`text-xs mt-1 hidden sm:block ${isCurrent ? 'text-primary' : 'text-muted-foreground'}`}>{stage.label}</span>
                  </div>
                  {index < STAGES.length - 1 && (<div className={`flex-1 h-1 rounded ${index < currentIndex ? 'bg-success' : 'bg-muted'}`} />)}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          <ScrollArea ref={scrollRef} className="flex-1 p-4" data-testid="chat-messages">
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
            </div>
          </ScrollArea>

          {/* Pending Proposal */}
          {pendingProposal && (
            <div className="border-t border-warning/30 bg-warning/10 p-4">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-start gap-4">
                  <AlertCircle className="w-6 h-6 text-warning flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <h4 className="text-foreground font-medium mb-2">Pending Proposal</h4>
                    <p className="text-muted-foreground text-sm mb-3">The AI has proposed the following. Do you want to confirm it?</p>
                    <div className="bg-card rounded-lg p-4 mb-4 border border-warning/30">
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

          {/* Error Message */}
          {error && (
            <div className="border-t border-destructive/30 bg-destructive/10 p-4">
              <div className="max-w-3xl mx-auto flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-destructive" />
                <p className="text-destructive text-sm">{error}</p>
                <Button variant="ghost" size="sm" onClick={() => setError('')} className="ml-auto text-destructive">Dismiss</Button>
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="border-t border-border p-4 bg-muted/30">
            <div className="max-w-3xl mx-auto">
              {epic.current_stage === 'epic_locked' ? (
                <div className="flex items-center justify-center gap-3 py-4">
                  <Lock className="w-5 h-5 text-success" />
                  <span className="text-success">This epic is locked and complete.</span>
                </div>
              ) : (
                <div className="flex gap-3">
                  <Textarea ref={textareaRef} placeholder="Type your message..." value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={handleKeyDown} disabled={sending || !!pendingProposal} className="bg-background border-border text-foreground resize-none min-h-[60px]" rows={2} data-testid="chat-input" />
                  <Button onClick={handleSendMessage} disabled={!message.trim() || sending || !!pendingProposal} className="bg-primary hover:bg-primary/90 text-primary-foreground h-auto px-4" data-testid="send-message-btn">
                    {sending ? (<Loader2 className="w-5 h-5 animate-spin" />) : (<Send className="w-5 h-5" />)}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Side Panel */}
        <div className="w-80 border-l border-border bg-card/50 hidden lg:block">
          <Tabs defaultValue="snapshot" className="h-full flex flex-col">
            <TabsList className="bg-transparent border-b border-border rounded-none p-0 h-auto">
              <TabsTrigger value="snapshot" className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-3"><FileText className="w-4 h-4 mr-2" /> Snapshot</TabsTrigger>
              <TabsTrigger value="history" className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-3"><History className="w-4 h-4 mr-2" /> Decisions</TabsTrigger>
            </TabsList>

            <TabsContent value="snapshot" className="flex-1 m-0 overflow-auto">
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

            <TabsContent value="history" className="flex-1 m-0 overflow-auto">
              <div className="p-4 space-y-4">
                {decisions.length === 0 ? (<p className="text-sm text-muted-foreground italic text-center py-8">No decisions recorded yet</p>) : (
                  decisions.map((decision) => (
                    <div key={decision.decision_id} className="bg-muted p-3 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        {decision.decision_type === 'confirm_proposal' ? (<CheckCircle2 className="w-4 h-4 text-success" />) : (<XCircle className="w-4 h-4 text-destructive" />)}
                        <span className="text-sm font-medium text-foreground capitalize">{decision.decision_type.replace('_', ' ')}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{decision.from_stage} → {decision.to_stage || 'same'}</p>
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
