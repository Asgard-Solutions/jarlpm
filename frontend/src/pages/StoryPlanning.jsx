import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { featureAPI, userStoryAPI, subscriptionAPI, llmProviderAPI } from '@/api';
import { useSubscriptionStore, useLLMProviderStore, useThemeStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import ThemeToggle from '@/components/ThemeToggle';
import { LinkedBugs } from '@/components/LinkedBugs';
import { 
  ArrowLeft, Send, Loader2, Lock, CheckCircle2, 
  XCircle, FileText, AlertCircle, User, Bot, Settings, 
  Plus, Sparkles, RefreshCw, Edit3, MessageSquare, BookOpen, Trash2, Puzzle, Flag
} from 'lucide-react';

const STORY_STAGES = {
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

const StoryPlanning = () => {
  const { featureId } = useParams();
  const navigate = useNavigate();
  const { isActive, setSubscription } = useSubscriptionStore();
  const { activeProvider, setProviders } = useLLMProviderStore();
  const { theme } = useThemeStore();

  const [feature, setFeature] = useState(null);
  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Generated drafts (not yet saved)
  const [generatedDrafts, setGeneratedDrafts] = useState([]);
  const [generatingStories, setGeneratingStories] = useState(false);
  
  // Story refinement dialog
  const [selectedStory, setSelectedStory] = useState(null);
  const [storyConversation, setStoryConversation] = useState([]);
  const [refinementMessage, setRefinementMessage] = useState('');
  const [sendingRefinement, setSendingRefinement] = useState(false);
  const [streamingRefinement, setStreamingRefinement] = useState('');
  
  // Manual story creation
  const [showManualCreate, setShowManualCreate] = useState(false);
  const [manualPersona, setManualPersona] = useState('');
  const [manualAction, setManualAction] = useState('');
  const [manualBenefit, setManualBenefit] = useState('');
  const [manualCriteria, setManualCriteria] = useState('');
  const [manualPoints, setManualPoints] = useState('');
  const [creatingManual, setCreatingManual] = useState(false);

  const refinementEndRef = useRef(null);
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

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

  const loadData = useCallback(async () => {
    try {
      const [featureRes, storiesRes] = await Promise.all([
        featureAPI.get(featureId),
        userStoryAPI.listForFeature(featureId),
      ]);
      setFeature(featureRes.data);
      setStories(storiesRes.data || []);
    } catch (err) {
      if (err.response?.status === 404) {
        navigate('/dashboard');
      }
      setError('Failed to load feature data');
    } finally {
      setLoading(false);
    }
  }, [featureId, navigate]);

  useEffect(() => { loadData(); }, [loadData]);

  // Generate user story suggestions
  const generateStorySuggestions = async () => {
    if (!isActive || !activeProvider) {
      setError('Active subscription and LLM provider required.');
      return;
    }
    
    setGeneratingStories(true);
    setError('');
    setGeneratedDrafts([]);
    
    try {
      const response = await userStoryAPI.generate(featureId, 5);
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
              if (data.type === 'stories') {
                setGeneratedDrafts(data.stories.map((s, i) => ({
                  tempId: `draft_${Date.now()}_${i}`,
                  ...s
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
      setError('Failed to generate user stories. Please try again.');
    } finally {
      setGeneratingStories(false);
    }
  };

  // Save a draft story to the database
  const handleSaveDraftStory = async (draft) => {
    try {
      const res = await userStoryAPI.create(featureId, {
        persona: draft.persona,
        action: draft.action,
        benefit: draft.benefit,
        acceptance_criteria: draft.acceptance_criteria,
        story_points: draft.story_points,
        source: 'ai_generated'
      });
      
      setStories(prev => [...prev, res.data]);
      setGeneratedDrafts(prev => prev.filter(d => d.tempId !== draft.tempId));
    } catch (err) {
      setError('Failed to save user story.');
    }
  };

  // Discard a draft
  const handleDiscardDraft = (tempId) => {
    setGeneratedDrafts(prev => prev.filter(d => d.tempId !== tempId));
  };

  // Open refinement dialog for a story
  const handleOpenRefinement = async (story) => {
    setSelectedStory(story);
    setStoryConversation([]);
    setRefinementMessage('');
    setStreamingRefinement('');
    
    try {
      const res = await userStoryAPI.getConversation(story.story_id);
      setStoryConversation(res.data || []);
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  };

  // Send refinement message
  const handleSendRefinement = async () => {
    if (!refinementMessage.trim() || sendingRefinement || !selectedStory) return;
    
    setSendingRefinement(true);
    const userMsg = refinementMessage.trim();
    setRefinementMessage('');
    setStreamingRefinement('');
    
    setStoryConversation(prev => [...prev, { 
      event_id: `temp_${Date.now()}`, 
      role: 'user', 
      content: userMsg,
      created_at: new Date().toISOString()
    }]);

    try {
      const response = await userStoryAPI.chat(selectedStory.story_id, userMsg);
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
              else if (data.type === 'story_updated') {
                const updated = await userStoryAPI.get(selectedStory.story_id);
                setSelectedStory(updated.data);
                setStories(prev => prev.map(s => 
                  s.story_id === updated.data.story_id ? updated.data : s
                ));
              }
              else if (data.type === 'done') {
                setStoryConversation(prev => [...prev, {
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

  // Approve a story
  const handleApproveStory = async (storyId) => {
    try {
      const res = await userStoryAPI.approve(storyId);
      setStories(prev => prev.map(s => 
        s.story_id === storyId ? res.data : s
      ));
      if (selectedStory?.story_id === storyId) {
        setSelectedStory(res.data);
      }
    } catch (err) {
      setError('Failed to approve user story.');
    }
  };

  // Delete a story
  const handleDeleteStory = async (storyId) => {
    try {
      await userStoryAPI.delete(storyId);
      setStories(prev => prev.filter(s => s.story_id !== storyId));
      if (selectedStory?.story_id === storyId) {
        setSelectedStory(null);
      }
    } catch (err) {
      setError('Failed to delete user story.');
    }
  };

  // Create manual story
  const handleCreateManual = async () => {
    if (!manualPersona.trim() || !manualAction.trim() || !manualBenefit.trim()) return;
    setCreatingManual(true);
    try {
      const criteriaList = manualCriteria.split('\n').filter(c => c.trim());
      const res = await userStoryAPI.create(featureId, {
        persona: manualPersona.trim(),
        action: manualAction.trim(),
        benefit: manualBenefit.trim(),
        acceptance_criteria: criteriaList.length > 0 ? criteriaList : null,
        story_points: manualPoints ? parseInt(manualPoints) : null,
        source: 'manual'
      });
      setStories(prev => [...prev, res.data]);
      setShowManualCreate(false);
      setManualPersona('');
      setManualAction('');
      setManualBenefit('');
      setManualCriteria('');
      setManualPoints('');
    } catch (err) {
      setError('Failed to create user story.');
    } finally {
      setCreatingManual(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (!feature) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Feature not found</p>
      </div>
    );
  }

  const draftStories = stories.filter(s => s.current_stage === 'draft');
  const refiningStories = stories.filter(s => s.current_stage === 'refining');
  const approvedStories = stories.filter(s => s.current_stage === 'approved');

  return (
    <div className="flex flex-col overflow-hidden -m-6" style={{ height: 'calc(100vh - 4rem)' }}>
      {/* Page Title Bar */}
      <div className="flex-shrink-0 border-b-2 border-blue-500/50 bg-blue-500/5" data-testid="story-planning-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4 h-14">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => navigate(`/epic/${feature.epic_id}`)} 
              className="text-muted-foreground hover:text-foreground" 
              data-testid="back-btn"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Epic →</span>
              <span className="text-foreground font-medium truncate max-w-[200px]">{feature.title}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Stepper */}
      <WorkflowStepper currentStep="stories" />

      {/* Story Planning Banner */}
      <div className="flex-shrink-0 bg-gradient-to-r from-blue-500/20 via-cyan-500/20 to-blue-500/20 border-b border-blue-500/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">User Story Planning</h1>
                <p className="text-sm text-muted-foreground">
                  Break down this feature into sprint-sized user stories using the standard format
                </p>
              </div>
            </div>
            <div className="flex items-center gap-6 text-center">
              <div>
                <p className="text-lg font-bold text-amber-400">{draftStories.length + generatedDrafts.length}</p>
                <p className="text-xs text-muted-foreground">Drafts</p>
              </div>
              <div>
                <p className="text-lg font-bold text-violet-400">{refiningStories.length}</p>
                <p className="text-xs text-muted-foreground">Refining</p>
              </div>
              <div>
                <p className="text-lg font-bold text-success">{approvedStories.length}</p>
                <p className="text-xs text-muted-foreground">Approved</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto space-y-8">
            
            {/* Generate Stories CTA */}
            {stories.length === 0 && generatedDrafts.length === 0 && (
              <Card className="border-2 border-dashed border-blue-500/30 bg-blue-500/5" data-testid="generate-stories-cta">
                <CardContent className="p-8 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-blue-500/20 flex items-center justify-center mx-auto mb-4">
                    <BookOpen className="w-8 h-8 text-blue-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">Create User Stories</h3>
                  <p className="text-muted-foreground mb-2 max-w-md mx-auto">
                    Let AI break down this feature into sprint-sized user stories, each following the standard format:
                  </p>
                  <p className="text-sm text-blue-400 italic mb-6">
                    &quot;As a [persona], I want to [action] so that [benefit]&quot;
                  </p>
                  <div className="flex gap-3 justify-center">
                    <Button 
                      onClick={generateStorySuggestions}
                      disabled={generatingStories}
                      className="bg-blue-500 hover:bg-blue-600 text-white"
                      data-testid="generate-stories-btn"
                    >
                      {generatingStories ? (
                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating...</>
                      ) : (
                        <><Sparkles className="w-4 h-4 mr-2" /> Generate User Stories</>
                      )}
                    </Button>
                    <Button variant="outline" onClick={() => setShowManualCreate(true)} data-testid="create-manual-story-btn">
                      <Plus className="w-4 h-4 mr-2" />
                      Create Manually
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Generated Drafts (not yet saved) */}
            {generatedDrafts.length > 0 && (
              <div data-testid="generated-story-drafts-section">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-blue-400" />
                    AI Generated ({generatedDrafts.length})
                  </h2>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={generateStorySuggestions}
                    disabled={generatingStories}
                    className="border-blue-500/50 text-blue-400"
                    data-testid="regenerate-stories-btn"
                  >
                    <RefreshCw className={`w-4 h-4 mr-1 ${generatingStories ? 'animate-spin' : ''}`} />
                    Regenerate
                  </Button>
                </div>
                
                <div className="space-y-4">
                  {generatedDrafts.map((draft) => (
                    <StoryDraftCard
                      key={draft.tempId}
                      draft={draft}
                      onSave={() => handleSaveDraftStory(draft)}
                      onDiscard={() => handleDiscardDraft(draft.tempId)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Draft Stories */}
            {draftStories.length > 0 && (
              <div data-testid="draft-stories-section">
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-4">
                  <Edit3 className="w-5 h-5 text-amber-400" />
                  Draft Stories ({draftStories.length})
                </h2>
                <div className="space-y-4">
                  {draftStories.map((story) => (
                    <StoryCard 
                      key={story.story_id} 
                      story={story}
                      onRefine={() => handleOpenRefinement(story)}
                      onApprove={() => handleApproveStory(story.story_id)}
                      onDelete={() => handleDeleteStory(story.story_id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Refining Stories */}
            {refiningStories.length > 0 && (
              <div data-testid="refining-stories-section">
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-4">
                  <MessageSquare className="w-5 h-5 text-violet-400" />
                  In Refinement ({refiningStories.length})
                </h2>
                <div className="space-y-4">
                  {refiningStories.map((story) => (
                    <StoryCard 
                      key={story.story_id} 
                      story={story}
                      onRefine={() => handleOpenRefinement(story)}
                      onApprove={() => handleApproveStory(story.story_id)}
                      onDelete={() => handleDeleteStory(story.story_id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Approved Stories */}
            {approvedStories.length > 0 && (
              <div data-testid="approved-stories-section">
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-4">
                  <Lock className="w-5 h-5 text-success" />
                  Approved & Locked ({approvedStories.length})
                </h2>
                <div className="space-y-4">
                  {approvedStories.map((story) => (
                    <StoryCard 
                      key={story.story_id} 
                      story={story}
                      onDelete={() => handleDeleteStory(story.story_id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Action buttons when stories exist */}
            {(stories.length > 0 || generatedDrafts.length > 0) && (
              <div className="flex gap-3 justify-center pt-4" data-testid="story-actions">
                <Button 
                  variant="outline" 
                  onClick={generateStorySuggestions}
                  disabled={generatingStories}
                  className="border-blue-500/50 text-blue-400"
                  data-testid="generate-more-stories-btn"
                >
                  {generatingStories ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  Generate More
                </Button>
                <Button variant="outline" onClick={() => setShowManualCreate(true)} data-testid="add-manual-story-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Add Manually
                </Button>
              </div>
            )}
            
            {/* Completion Banner - when all stories are approved */}
            {stories.length > 0 && approvedStories.length === stories.length && generatedDrafts.length === 0 && (
              <Card className="border-2 border-success/50 bg-success/10" data-testid="stories-complete-banner">
                <CardContent className="p-6 text-center">
                  <div className="w-16 h-16 rounded-full bg-success/20 flex items-center justify-center mx-auto mb-4">
                    <CheckCircle2 className="w-8 h-8 text-success" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    All Stories Approved! 🎉
                  </h3>
                  <p className="text-muted-foreground mb-4 max-w-md mx-auto">
                    You&apos;ve completed all {approvedStories.length} user stories for &quot;{feature.title}&quot;. 
                    Return to Feature Planning to continue with other features.
                  </p>
                  <Button 
                    onClick={() => navigate(`/epic/${feature.epic_id}`)}
                    className="bg-success hover:bg-success/90 text-white"
                    data-testid="return-to-features-btn"
                  >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Return to Feature Planning
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Sidebar - Feature Reference */}
        <div className="w-80 flex-shrink-0 border-l border-border bg-card/50 hidden lg:flex lg:flex-col overflow-hidden" data-testid="feature-reference-sidebar">
          <div className="p-4 border-b border-border bg-blue-500/10">
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Puzzle className="w-4 h-4 text-blue-400" />
              Working on Feature
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Use this reference to ensure stories match the feature
            </p>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
              <h4 className="text-sm font-semibold text-foreground mb-1 flex items-center gap-1">
                {feature.title}
                <Lock className="w-3 h-3 text-success" />
              </h4>
              <p className="text-xs text-muted-foreground">{feature.description}</p>
            </div>
            
            {feature.acceptance_criteria?.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                  Feature Acceptance Criteria
                </h4>
                <ul className="text-xs text-foreground bg-muted p-2 rounded space-y-1">
                  {feature.acceptance_criteria.map((c, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <CheckCircle2 className="w-3 h-3 text-success mt-0.5 flex-shrink-0" />
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            <div className="pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground italic mb-3">
                Each story should be completable within one sprint and align with the acceptance criteria above.
              </p>
              
              {/* Progress summary */}
              <div className="bg-muted rounded-lg p-3 space-y-2">
                <p className="text-xs font-medium text-foreground">Story Progress</p>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-amber-400">Drafts: {draftStories.length + generatedDrafts.length}</span>
                  <span className="text-violet-400">Refining: {refiningStories.length}</span>
                  <span className="text-success">Done: {approvedStories.length}</span>
                </div>
                {stories.length > 0 && (
                  <div className="w-full bg-background rounded-full h-2 overflow-hidden">
                    <div 
                      className="h-full bg-success transition-all duration-300" 
                      style={{ width: `${(approvedStories.length / stories.length) * 100}%` }}
                    />
                  </div>
                )}
              </div>
              
              {/* Linked Bugs for this Feature */}
              <div className="pt-2">
                <LinkedBugs
                  entityType="feature"
                  entityId={featureId}
                  entityTitle={feature?.title || 'Feature'}
                  collapsed={true}
                />
              </div>
            </div>
          </div>
          
          {/* Bottom action */}
          <div className="p-4 border-t border-border bg-muted/30">
            <Button 
              variant="outline" 
              className="w-full"
              onClick={() => navigate(`/epic/${feature.epic_id}`)}
              data-testid="back-to-features-sidebar-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Feature Planning
            </Button>
          </div>
        </div>
      </div>

      {/* Story Refinement Dialog */}
      <Dialog open={!!selectedStory} onOpenChange={() => setSelectedStory(null)}>
        <DialogContent className="bg-card border-border max-w-2xl max-h-[80vh] flex flex-col" data-testid="story-refinement-dialog">
          <DialogHeader>
            <DialogTitle className="text-foreground flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-blue-400" />
              Refine User Story
            </DialogTitle>
            <DialogDescription>
              Chat with AI to improve this user story before approving
            </DialogDescription>
          </DialogHeader>
          
          {selectedStory && (
            <div className="flex-1 flex flex-col min-h-0 space-y-4">
              {/* Current Story State */}
              <Card className="bg-muted/50 flex-shrink-0">
                <CardContent className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant="outline" className={STORY_STAGES[selectedStory.current_stage]?.color}>
                      {STORY_STAGES[selectedStory.current_stage]?.label}
                    </Badge>
                    {selectedStory.story_points && (
                      <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30">
                        {selectedStory.story_points} pts
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-foreground italic mb-2">&quot;{selectedStory.story_text}&quot;</p>
                  {selectedStory.acceptance_criteria?.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border">
                      <p className="text-xs font-medium text-muted-foreground mb-1">Acceptance Criteria:</p>
                      <ul className="text-xs text-muted-foreground">
                        {selectedStory.acceptance_criteria.map((c, i) => (
                          <li key={i}>• {c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
              
              {/* Conversation */}
              <div className="flex-1 overflow-y-auto space-y-3 bg-background rounded-lg p-3 min-h-[200px]">
                {storyConversation.filter(m => m.role !== 'system').map((msg, i) => (
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
              {selectedStory.current_stage !== 'approved' && (
                <div className="flex gap-2 flex-shrink-0">
                  <Textarea
                    value={refinementMessage}
                    onChange={(e) => setRefinementMessage(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendRefinement(); }}}
                    placeholder="Suggest changes... (e.g., 'Make the persona more specific' or 'Add error handling acceptance criteria')"
                    disabled={sendingRefinement}
                    className="bg-background border-border text-foreground resize-none"
                    rows={2}
                    data-testid="story-refinement-input"
                  />
                  <Button
                    onClick={handleSendRefinement}
                    disabled={!refinementMessage.trim() || sendingRefinement}
                    className="bg-blue-500 hover:bg-blue-600 h-auto"
                    data-testid="send-story-refinement-btn"
                  >
                    {sendingRefinement ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                  </Button>
                </div>
              )}
            </div>
          )}
          
          <DialogFooter className="flex-shrink-0">
            <Button variant="outline" onClick={() => setSelectedStory(null)} data-testid="close-story-refinement-btn">Close</Button>
            {selectedStory?.current_stage !== 'approved' && (
              <Button 
                onClick={() => {
                  handleApproveStory(selectedStory.story_id);
                  setSelectedStory(null);
                }}
                className="bg-success hover:bg-success/90"
                data-testid="approve-story-btn"
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
        <DialogContent className="bg-card border-border max-w-lg" data-testid="manual-story-create-dialog">
          <DialogHeader>
            <DialogTitle className="text-foreground">Create User Story Manually</DialogTitle>
            <DialogDescription>
              Use the standard format: As a [persona], I want to [action] so that [benefit]
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm text-foreground">As a...</label>
              <Input
                value={manualPersona}
                onChange={(e) => setManualPersona(e.target.value)}
                placeholder="user role (e.g., 'logged-in user', 'admin')"
                className="bg-background border-border text-foreground"
                data-testid="manual-persona-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-foreground">I want to...</label>
              <Textarea
                value={manualAction}
                onChange={(e) => setManualAction(e.target.value)}
                placeholder="action (e.g., 'filter search results by date')"
                className="bg-background border-border text-foreground min-h-[60px]"
                data-testid="manual-action-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-foreground">So that...</label>
              <Textarea
                value={manualBenefit}
                onChange={(e) => setManualBenefit(e.target.value)}
                placeholder="benefit (e.g., 'I can find recent items more quickly')"
                className="bg-background border-border text-foreground min-h-[60px]"
                data-testid="manual-benefit-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-foreground">Acceptance Criteria (Given/When/Then, one per line)</label>
              <Textarea
                value={manualCriteria}
                onChange={(e) => setManualCriteria(e.target.value)}
                placeholder="Given I am on the search page, When I select a date filter, Then results are filtered by that date"
                className="bg-background border-border text-foreground min-h-[80px]"
                data-testid="manual-criteria-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-foreground">Story Points (optional)</label>
              <Input
                type="number"
                value={manualPoints}
                onChange={(e) => setManualPoints(e.target.value)}
                placeholder="1, 2, 3, 5, or 8"
                className="bg-background border-border text-foreground w-24"
                data-testid="manual-points-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowManualCreate(false)}>Cancel</Button>
            <Button 
              onClick={handleCreateManual} 
              disabled={creatingManual || !manualPersona.trim() || !manualAction.trim() || !manualBenefit.trim()}
              className="bg-blue-500 hover:bg-blue-600"
              data-testid="create-story-btn"
            >
              {creatingManual ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Create User Story
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
};

// Story Draft Card Component (for AI-generated, not yet saved)
const StoryDraftCard = ({ draft, onSave, onDiscard }) => {
  const storyText = `As a ${draft.persona}, I want to ${draft.action} so that ${draft.benefit}.`;
  
  return (
    <Card className="border-blue-500/30 bg-blue-500/5" data-testid={`story-draft-card-${draft.tempId}`}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                AI Generated - Not Saved
              </Badge>
              {draft.story_points && (
                <Badge variant="outline" className="text-xs ml-2 bg-muted text-muted-foreground">
                  {draft.story_points} pts
                </Badge>
              )}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-foreground italic">&quot;{storyText}&quot;</p>
        
        {draft.acceptance_criteria?.length > 0 && (
          <div className="bg-background/50 rounded-lg p-3">
            <p className="text-xs font-medium text-foreground mb-2">Acceptance Criteria:</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              {draft.acceptance_criteria.map((c, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-blue-400">•</span>
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        <div className="flex gap-2 pt-2">
          <Button 
            size="sm" 
            onClick={onSave}
            className="bg-blue-500 hover:bg-blue-600"
            data-testid={`save-story-draft-btn-${draft.tempId}`}
          >
            <Plus className="w-4 h-4 mr-1" />
            Save as Draft
          </Button>
          <Button 
            size="sm" 
            variant="outline"
            onClick={onDiscard}
            className="border-destructive/50 text-destructive"
            data-testid={`discard-story-draft-btn-${draft.tempId}`}
          >
            <XCircle className="w-4 h-4 mr-1" />
            Discard
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

// Story Card Component (for saved stories)
const StoryCard = ({ story, onRefine, onApprove, onDelete }) => {
  const stageInfo = STORY_STAGES[story.current_stage];
  const StageIcon = stageInfo?.icon || Edit3;
  const isApproved = story.current_stage === 'approved';

  return (
    <Card className={`border-${isApproved ? 'success' : story.current_stage === 'refining' ? 'violet-500' : 'amber-500'}/30 bg-${isApproved ? 'success' : story.current_stage === 'refining' ? 'violet-500' : 'amber-500'}/5`} data-testid={`story-card-${story.story_id}`}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isApproved ? 'bg-success/20' : story.current_stage === 'refining' ? 'bg-violet-500/20' : 'bg-amber-500/20'}`}>
              <StageIcon className={`w-5 h-5 ${isApproved ? 'text-success' : story.current_stage === 'refining' ? 'text-violet-400' : 'text-amber-400'}`} />
            </div>
            <div>
              {story.title && (
                <h4 className="font-medium text-foreground text-sm">{story.title}</h4>
              )}
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className={`text-xs ${stageInfo?.color}`}>
                  {isApproved && <Lock className="w-3 h-3 mr-1" />}
                  {stageInfo?.label}
                </Badge>
                <Badge variant="outline" className="text-xs bg-muted text-muted-foreground">
                  {story.source === 'ai_generated' ? 'AI' : 'Manual'}
                </Badge>
                {story.story_points && (
                  <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                    {story.story_points} pts
                  </Badge>
                )}
                {story.rice_total && (
                  <Badge variant="outline" className="text-xs bg-purple-500/10 text-purple-400 border-purple-500/30">
                    RICE: {story.rice_total.toFixed(1)}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onDelete}
              className="text-muted-foreground hover:text-destructive"
              data-testid={`delete-story-btn-${story.story_id}`}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Story text */}
        <p className="text-sm text-foreground italic">&quot;{story.story_text}&quot;</p>
        
        {/* Labels */}
        {story.labels?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {story.labels.map((label, i) => (
              <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0 bg-blue-500/10 text-blue-400">
                {label}
              </Badge>
            ))}
          </div>
        )}
        
        {/* Acceptance Criteria */}
        {story.acceptance_criteria?.length > 0 && (
          <div className="bg-background/50 rounded-lg p-3">
            <p className="text-xs font-medium text-foreground mb-2">Acceptance Criteria:</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              {story.acceptance_criteria.map((c, i) => (
                <li key={i} className="flex items-start gap-2">
                  {isApproved ? (
                    <CheckCircle2 className="w-3 h-3 mt-0.5 text-success flex-shrink-0" />
                  ) : (
                    <span className={story.current_stage === 'refining' ? 'text-violet-400' : 'text-amber-400'}>•</span>
                  )}
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Edge Cases */}
        {story.edge_cases?.length > 0 && (
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
            <p className="text-xs font-medium text-amber-400 mb-2">Edge Cases:</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              {story.edge_cases.map((ec, i) => (
                <li key={i} className="flex items-start gap-2">
                  <AlertCircle className="w-3 h-3 mt-0.5 text-amber-400 flex-shrink-0" />
                  {ec}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Notes for Engineering */}
        {story.notes_for_engineering && (
          <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
            <p className="text-xs font-medium text-blue-400 mb-1">Notes for Engineering:</p>
            <p className="text-xs text-muted-foreground">{story.notes_for_engineering}</p>
          </div>
        )}
        
        {!isApproved && (
          <div className="flex gap-2 pt-2">
            {onApprove && (
              <Button 
                size="sm" 
                onClick={onApprove}
                className="bg-success hover:bg-success/90 text-white"
                data-testid={`approve-story-btn-${story.story_id}`}
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
                className="border-blue-500/50 text-blue-400"
                data-testid={`refine-story-btn-${story.story_id}`}
              >
                <MessageSquare className="w-4 h-4 mr-1" />
                Refine with AI
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Workflow Stepper Component
const WorkflowStepper = ({ currentStep }) => {
  const getStepStatus = (stepId) => {
    if (stepId === 'definition') return 'complete';
    if (stepId === 'features') return 'complete';
    if (stepId === 'stories') return currentStep === 'stories' ? 'current' : 'complete';
    if (stepId === 'complete') return currentStep === 'complete' ? 'complete' : 'upcoming';
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
                    <p className="text-xs text-muted-foreground">{step.description}</p>
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

export default StoryPlanning;
