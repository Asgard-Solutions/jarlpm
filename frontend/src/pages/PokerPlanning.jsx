import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { toast } from 'sonner';
import { 
  Loader2, Users, Play, Check, RotateCcw, Sparkles, 
  ChevronRight, ChevronLeft, AlertCircle, Trophy, Target,
  ArrowLeft, Plus, Calendar, ChevronDown, ChevronUp,
  MessageSquare, Clock
} from 'lucide-react';
import { epicAPI, featureAPI, userStoryAPI, pokerAPI } from '@/api';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';

const FIBONACCI = [1, 2, 3, 5, 8, 13];

const PERSONA_AVATARS = {
  'Sarah': '👩‍💻',
  'Alex': '👨‍💻',
  'Maya': '🧪',
  'Jordan': '🔧',
  'Riley': '🎨',
};

const PokerPlanning = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  
  // View state: list | review | planning
  const [view, setView] = useState('list');
  
  // List view state
  const [completedEpics, setCompletedEpics] = useState([]);
  const [availableEpics, setAvailableEpics] = useState([]);
  
  // Review view state (viewing completed poker)
  const [selectedEpicForReview, setSelectedEpicForReview] = useState(null);
  const [epicSessions, setEpicSessions] = useState([]);
  const [expandedStories, setExpandedStories] = useState({});
  const [loadingReview, setLoadingReview] = useState(false);
  
  // Planning view state (new poker planning)
  const [selectedEpicForPlanning, setSelectedEpicForPlanning] = useState('');
  const [stories, setStories] = useState([]);
  const [currentStoryIndex, setCurrentStoryIndex] = useState(0);
  const [estimating, setEstimating] = useState(false);
  const [aiEstimates, setAiEstimates] = useState([]);
  const [estimateSummary, setEstimateSummary] = useState(null);
  const [currentPersona, setCurrentPersona] = useState(null);
  
  // Dialog state
  const [showStartDialog, setShowStartDialog] = useState(false);
  const [newPlanningEpic, setNewPlanningEpic] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [completedRes, availableRes] = await Promise.all([
        pokerAPI.getCompletedEpics(),
        pokerAPI.getEpicsWithoutEstimation()
      ]);
      setCompletedEpics(completedRes.data?.epics || []);
      setAvailableEpics(availableRes.data?.epics || []);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load poker planning data');
    } finally {
      setLoading(false);
    }
  };

  const openReview = async (epicId, epicTitle) => {
    setSelectedEpicForReview({ epic_id: epicId, title: epicTitle });
    setLoadingReview(true);
    setView('review');
    
    try {
      const response = await pokerAPI.getEpicSessions(epicId);
      setEpicSessions(response.data?.stories || []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
      toast.error('Failed to load poker sessions');
    } finally {
      setLoadingReview(false);
    }
  };

  const startNewPlanning = async () => {
    if (!newPlanningEpic) {
      toast.error('Please select an epic');
      return;
    }
    
    const epic = availableEpics.find(e => e.epic_id === newPlanningEpic);
    setShowStartDialog(false);
    setSelectedEpicForPlanning(newPlanningEpic);
    setView('planning');
    
    // Load stories for this epic
    setLoading(true);
    try {
      const featuresRes = await featureAPI.listForEpic(newPlanningEpic);
      const features = featuresRes.data || [];
      
      const allStories = [];
      for (const feature of features) {
        try {
          const storiesRes = await userStoryAPI.listForFeature(feature.feature_id);
          const featureStories = (storiesRes.data || []).filter(s => !s.story_points || s.story_points === 0);
          allStories.push(...featureStories);
        } catch (e) {
          console.error(`Failed to load stories for feature ${feature.feature_id}`);
        }
      }
      
      setStories(allStories);
      setCurrentStoryIndex(0);
    } catch (error) {
      console.error('Failed to load stories:', error);
      toast.error('Failed to load stories');
    } finally {
      setLoading(false);
    }
  };

  const backToList = () => {
    setView('list');
    setSelectedEpicForReview(null);
    setSelectedEpicForPlanning('');
    setEpicSessions([]);
    setStories([]);
    setAiEstimates([]);
    setEstimateSummary(null);
    setNewPlanningEpic('');
    loadData();
  };

  const toggleStory = (storyId) => {
    setExpandedStories(prev => ({
      ...prev,
      [storyId]: !prev[storyId]
    }));
  };

  const getConfidenceColor = (confidence) => {
    switch (confidence) {
      case 'high': return 'text-green-500';
      case 'medium': return 'text-yellow-500';
      case 'low': return 'text-red-500';
      default: return 'text-muted-foreground';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  };

  // Estimation functions for planning view
  const runAIEstimation = async () => {
    const currentStory = stories[currentStoryIndex];
    if (!currentStory) return;
    
    setEstimating(true);
    setAiEstimates([]);
    setEstimateSummary(null);
    
    try {
      const response = await pokerAPI.estimateStory(currentStory.story_id);
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
              
              if (data.type === 'persona_start') {
                setCurrentPersona(data.persona);
              } else if (data.type === 'persona_estimate') {
                setAiEstimates(prev => [...prev, data.estimate]);
                setCurrentPersona(null);
              } else if (data.type === 'summary') {
                setEstimateSummary(data.summary);
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }
    } catch (error) {
      console.error('Estimation failed:', error);
      toast.error('Failed to get AI estimates');
    } finally {
      setEstimating(false);
      setCurrentPersona(null);
    }
  };

  const acceptEstimate = async (points) => {
    const currentStory = stories[currentStoryIndex];
    if (!currentStory) return;
    
    const sessionId = estimateSummary?.session_id || null;
    
    try {
      await pokerAPI.saveEstimate(currentStory.story_id, points, sessionId);
      toast.success(`Saved ${points} story points`);
      
      // Move to next story
      if (currentStoryIndex < stories.length - 1) {
        setCurrentStoryIndex(prev => prev + 1);
        setAiEstimates([]);
        setEstimateSummary(null);
      } else {
        toast.success('All stories estimated!');
        backToList();
      }
    } catch (error) {
      console.error('Failed to save:', error);
      toast.error('Failed to save estimate');
    }
  };

  const resetEstimation = () => {
    setAiEstimates([]);
    setEstimateSummary(null);
    setCurrentPersona(null);
  };

  // ==================== LIST VIEW ====================
  if (view === 'list') {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Poker Planning</h1>
            <p className="text-muted-foreground mt-1">AI-powered story point estimation</p>
          </div>
          
          <Dialog open={showStartDialog} onOpenChange={setShowStartDialog}>
            <DialogTrigger asChild>
              <Button disabled={availableEpics.length === 0} data-testid="start-new-poker">
                <Plus className="h-4 w-4 mr-2" />
                Start New Session
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Start Poker Planning</DialogTitle>
                <DialogDescription>
                  Select an epic with unestimated stories.
                </DialogDescription>
              </DialogHeader>
              <div className="py-4">
                <Select value={newPlanningEpic} onValueChange={setNewPlanningEpic}>
                  <SelectTrigger data-testid="select-epic-for-poker">
                    <SelectValue placeholder="Select an epic..." />
                  </SelectTrigger>
                  <SelectContent>
                    {availableEpics.map((epic) => (
                      <SelectItem key={epic.epic_id} value={epic.epic_id}>
                        <div className="flex items-center justify-between w-full gap-4">
                          <span>{epic.title}</span>
                          <Badge variant="secondary" className="text-xs">
                            {epic.unestimated_stories} stories
                          </Badge>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {availableEpics.length === 0 && (
                  <p className="text-sm text-muted-foreground mt-2">
                    All stories have been estimated.
                  </p>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowStartDialog(false)}>Cancel</Button>
                <Button onClick={startNewPlanning} disabled={!newPlanningEpic}>Start</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
          </div>
        ) : completedEpics.length === 0 ? (
          <Card className="bg-card border-border">
            <CardContent className="p-12 text-center">
              <Users className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-xl font-medium text-foreground mb-2">
                No Poker Sessions Yet
              </h3>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                Start a poker planning session to get AI-powered story point estimates.
              </p>
              {availableEpics.length > 0 ? (
                <Button onClick={() => setShowStartDialog(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Start Your First Session
                </Button>
              ) : (
                <Button onClick={() => navigate('/stories')}>
                  Create Stories First
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {completedEpics.map((epic) => (
              <Card 
                key={epic.epic_id} 
                className="bg-card border-border hover:border-primary/50 cursor-pointer transition-colors"
                onClick={() => openReview(epic.epic_id, epic.title)}
                data-testid={`poker-card-${epic.epic_id}`}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-lg">{epic.title}</CardTitle>
                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30">
                      <Check className="h-3 w-3 mr-1" />
                      Completed
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {epic.estimated_stories} stories
                    </div>
                    <div className="flex items-center gap-1">
                      <Calendar className="h-4 w-4" />
                      {epic.updated_at ? formatDate(epic.updated_at) : 'N/A'}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ==================== REVIEW VIEW ====================
  if (view === 'review') {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={backToList}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{selectedEpicForReview?.title}</h1>
            <p className="text-muted-foreground">Poker Planning Results</p>
          </div>
        </div>

        {loadingReview ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
          </div>
        ) : epicSessions.length === 0 ? (
          <Card className="bg-card border-border">
            <CardContent className="p-12 text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium">No Estimation Data</h3>
              <p className="text-muted-foreground mt-2">
                No poker planning sessions found for this epic.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {epicSessions.map((story) => (
              <Collapsible 
                key={story.story_id}
                open={expandedStories[story.story_id]}
                onOpenChange={() => toggleStory(story.story_id)}
              >
                <Card className="border-border">
                  <CollapsibleTrigger asChild>
                    <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors py-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <CardTitle className="text-base truncate">{story.title}</CardTitle>
                          <p className="text-sm text-muted-foreground mt-1 truncate">
                            {story.description?.substring(0, 100)}...
                          </p>
                        </div>
                        <div className="flex items-center gap-3 ml-4">
                          {story.session?.accepted_estimate && (
                            <Badge className="bg-green-500/10 text-green-500 border-green-500/30 text-lg font-bold">
                              {story.session.accepted_estimate} pts
                            </Badge>
                          )}
                          {!story.session?.accepted_estimate && story.session?.suggested_estimate && (
                            <Badge variant="outline" className="text-lg font-bold">
                              {story.session.suggested_estimate} pts
                            </Badge>
                          )}
                          {expandedStories[story.story_id] ? (
                            <ChevronUp className="h-5 w-5 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-5 w-5 text-muted-foreground" />
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-sm mt-2">
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Trophy className="h-4 w-4 text-yellow-500" />
                          Suggested: {story.session?.suggested_estimate}
                        </div>
                        <Separator orientation="vertical" className="h-4" />
                        <span className="text-muted-foreground">
                          Range: {story.session?.min_estimate} - {story.session?.max_estimate}
                        </span>
                        <Separator orientation="vertical" className="h-4" />
                        <span className="text-muted-foreground">
                          Avg: {story.session?.average_estimate?.toFixed(1)}
                        </span>
                      </div>
                    </CardHeader>
                  </CollapsibleTrigger>
                  
                  <CollapsibleContent>
                    <CardContent className="pt-0">
                      <Separator className="mb-4" />
                      <div className="space-y-4">
                        <h4 className="text-sm font-medium flex items-center gap-2">
                          <MessageSquare className="h-4 w-4" />
                          AI Persona Reasoning
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {story.session?.estimates?.map((estimate, idx) => (
                            <div 
                              key={idx}
                              className="p-3 rounded-lg border border-border bg-muted/20"
                            >
                              <div className="flex items-center gap-3 mb-2">
                                <Avatar className="h-8 w-8">
                                  <AvatarFallback className="text-base bg-primary/10">
                                    {PERSONA_AVATARS[estimate.persona_name] || '🤖'}
                                  </AvatarFallback>
                                </Avatar>
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium text-sm">{estimate.persona_name}</p>
                                  <p className="text-xs text-muted-foreground">{estimate.persona_role}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className={`text-xs ${getConfidenceColor(estimate.confidence)}`}>
                                    {estimate.confidence}
                                  </span>
                                  <Badge variant="outline" className="text-lg font-bold">
                                    {estimate.estimate_points}
                                  </Badge>
                                </div>
                              </div>
                              <p className="text-sm text-muted-foreground">
                                {estimate.reasoning}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </CollapsibleContent>
                </Card>
              </Collapsible>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ==================== PLANNING VIEW ====================
  const currentStory = stories[currentStoryIndex];
  
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={backToList}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Poker Planning</h1>
            <p className="text-muted-foreground">
              Story {currentStoryIndex + 1} of {stories.length}
            </p>
          </div>
        </div>
        <Progress value={(currentStoryIndex / stories.length) * 100} className="w-48" />
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
        </div>
      ) : stories.length === 0 ? (
        <Card className="bg-card border-border">
          <CardContent className="p-12 text-center">
            <Check className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-lg font-medium">All Stories Estimated!</h3>
            <p className="text-muted-foreground mt-2">
              All stories in this epic have been estimated.
            </p>
            <Button className="mt-4" onClick={backToList}>
              Back to List
            </Button>
          </CardContent>
        </Card>
      ) : currentStory ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Story Card */}
          <Card className="bg-card border-border">
            <CardHeader>
              <div className="flex items-center justify-between">
                <Badge variant="outline">Story {currentStoryIndex + 1}</Badge>
              </div>
              <CardTitle className="text-xl mt-2">{currentStory.title}</CardTitle>
              <CardDescription>{currentStory.description}</CardDescription>
            </CardHeader>
            <CardContent>
              {currentStory.acceptance_criteria && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Acceptance Criteria</h4>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    {(Array.isArray(currentStory.acceptance_criteria) 
                      ? currentStory.acceptance_criteria 
                      : [currentStory.acceptance_criteria]
                    ).map((criterion, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <Check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                        <span>{criterion}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              <div className="mt-6">
                <Button 
                  className="w-full" 
                  onClick={runAIEstimation}
                  disabled={estimating}
                >
                  {estimating ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  {estimating ? 'AI Team Estimating...' : 'Run AI Estimation'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Estimates Card */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                AI Team Estimates
              </CardTitle>
            </CardHeader>
            <CardContent>
              {aiEstimates.length === 0 && !estimating && !currentPersona ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Click "Run AI Estimation" to get team estimates</p>
                </div>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-3">
                    {currentPersona && (
                      <div className="p-3 rounded-lg border border-primary/50 bg-primary/5 animate-pulse">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-10 w-10">
                            <AvatarFallback>{PERSONA_AVATARS[currentPersona.name] || '🤖'}</AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="font-medium">{currentPersona.name}</p>
                            <p className="text-sm text-muted-foreground">{currentPersona.role}</p>
                          </div>
                          <Loader2 className="h-4 w-4 animate-spin ml-auto" />
                        </div>
                      </div>
                    )}
                    
                    {aiEstimates.map((estimate, idx) => (
                      <div key={idx} className="p-3 rounded-lg border border-border bg-muted/20">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-10 w-10">
                            <AvatarFallback>{PERSONA_AVATARS[estimate.name] || '🤖'}</AvatarFallback>
                          </Avatar>
                          <div className="flex-1">
                            <p className="font-medium">{estimate.name}</p>
                            <p className="text-sm text-muted-foreground">{estimate.role}</p>
                          </div>
                          <Badge variant="outline" className="text-lg font-bold">
                            {estimate.estimate}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mt-2 ml-13">
                          {estimate.reasoning}
                        </p>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
              
              {estimateSummary && (
                <div className="mt-4 pt-4 border-t border-border">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Suggested Estimate</p>
                      <p className="text-3xl font-bold">{estimateSummary.suggested}</p>
                    </div>
                    <div className="text-right text-sm text-muted-foreground">
                      <p>Range: {estimateSummary.min} - {estimateSummary.max}</p>
                      <p>Average: {estimateSummary.average}</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    {FIBONACCI.map(points => (
                      <Button
                        key={points}
                        variant={points === estimateSummary.suggested ? "default" : "outline"}
                        className="flex-1"
                        onClick={() => acceptEstimate(points)}
                      >
                        {points}
                      </Button>
                    ))}
                  </div>
                  
                  <Button 
                    variant="ghost" 
                    className="w-full mt-2"
                    onClick={resetEstimation}
                  >
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Re-estimate
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
};

export default PokerPlanning;
