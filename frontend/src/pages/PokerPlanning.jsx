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
import { toast } from 'sonner';
import { 
  Loader2, Users, Play, Check, RotateCcw, Sparkles, 
  ChevronRight, ChevronLeft, AlertCircle, Trophy, Target
} from 'lucide-react';
import { epicAPI, featureAPI, userStoryAPI, pokerAPI } from '@/api';

const FIBONACCI = [1, 2, 3, 5, 8, 13];

const PokerPlanning = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [estimating, setEstimating] = useState(false);
  const [epics, setEpics] = useState([]);
  const [selectedEpic, setSelectedEpic] = useState('');
  const [stories, setStories] = useState([]);
  const [currentStoryIndex, setCurrentStoryIndex] = useState(0);
  
  // AI estimation state
  const [aiEstimates, setAiEstimates] = useState([]);
  const [estimateSummary, setEstimateSummary] = useState(null);
  const [currentPersona, setCurrentPersona] = useState(null);
  const [estimatedStories, setEstimatedStories] = useState({});

  useEffect(() => {
    loadEpics();
    loadSavedEstimates();
  }, []);

  useEffect(() => {
    if (selectedEpic) {
      loadStories();
    }
  }, [selectedEpic]);

  const loadEpics = async () => {
    try {
      const response = await epicAPI.list();
      setEpics(response.data?.epics || []);
    } catch (error) {
      console.error('Failed to load epics:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStories = async () => {
    if (!selectedEpic) return;
    
    setLoading(true);
    try {
      const featuresRes = await featureAPI.listForEpic(selectedEpic);
      const features = featuresRes.data || [];
      
      // Collect all stories from all features
      const allStories = [];
      for (const feature of features) {
        try {
          const storiesRes = await userStoryAPI.listForFeature(feature.feature_id);
          allStories.push(...(storiesRes.data || []));
        } catch (e) {
          console.error(`Failed to load stories for feature ${feature.feature_id}`);
        }
      }
      
      setStories(allStories);
      setCurrentStoryIndex(0);
      resetEstimation();
    } catch (error) {
      console.error('Failed to load stories:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSavedEstimates = () => {
    try {
      const saved = localStorage.getItem('jarlpm_ai_poker_estimates');
      if (saved) {
        setEstimatedStories(JSON.parse(saved));
      }
    } catch (error) {
      console.error('Failed to load saved estimates:', error);
    }
  };

  const saveEstimates = (estimates) => {
    localStorage.setItem('jarlpm_ai_poker_estimates', JSON.stringify(estimates));
  };

  const resetEstimation = () => {
    setAiEstimates([]);
    setEstimateSummary(null);
    setCurrentPersona(null);
  };

  const runAIEstimation = async () => {
    const currentStory = stories[currentStoryIndex];
    if (!currentStory) return;
    
    setEstimating(true);
    resetEstimation();
    
    try {
      const response = await pokerAPI.estimateStory(currentStory.story_id);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ''; // SSE buffer for handling split chunks
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'start':
                  // Estimation started
                  break;
                case 'persona_start':
                  setCurrentPersona(data.persona);
                  break;
                case 'persona_estimate':
                  setAiEstimates(prev => [...prev, data.estimate]);
                  setCurrentPersona(null);
                  break;
                case 'persona_error':
                  console.error(`Error from ${data.persona_id}:`, data.error);
                  setCurrentPersona(null);
                  break;
                case 'summary':
                  setEstimateSummary(data.summary);
                  break;
                case 'done':
                  setEstimating(false);
                  break;
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (error) {
      console.error('AI estimation failed:', error);
      setEstimating(false);
    }
  };

  const acceptEstimate = async (points) => {
    const currentStory = stories[currentStoryIndex];
    if (!currentStory) return;
    
    // Save to database
    try {
      await pokerAPI.saveEstimate(currentStory.story_id, points);
      toast.success(`Saved ${points} story points for "${currentStory.title}"`);
    } catch (error) {
      console.error('Failed to save estimate to database:', error);
      toast.error('Failed to save estimate to database');
    }
    
    const newEstimates = {
      ...estimatedStories,
      [currentStory.story_id]: {
        points,
        aiEstimates,
        summary: estimateSummary,
        estimatedAt: new Date().toISOString()
      }
    };
    setEstimatedStories(newEstimates);
    saveEstimates(newEstimates);
    
    // Move to next story
    if (currentStoryIndex < stories.length - 1) {
      setCurrentStoryIndex(prev => prev + 1);
      resetEstimation();
    }
  };

  const handleNextStory = () => {
    if (currentStoryIndex < stories.length - 1) {
      setCurrentStoryIndex(prev => prev + 1);
      resetEstimation();
    }
  };

  const handlePrevStory = () => {
    if (currentStoryIndex > 0) {
      setCurrentStoryIndex(prev => prev - 1);
      resetEstimation();
    }
  };

  const getConfidenceColor = (confidence) => {
    switch (confidence) {
      case 'high': return 'text-green-500';
      case 'medium': return 'text-yellow-500';
      case 'low': return 'text-red-500';
      default: return 'text-muted-foreground';
    }
  };

  const getConsensusColor = (consensus) => {
    switch (consensus) {
      case 'high': return 'bg-green-500/10 text-green-500 border-green-500/30';
      case 'medium': return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30';
      case 'low': return 'bg-red-500/10 text-red-500 border-red-500/30';
      default: return 'bg-muted';
    }
  };

  const currentStory = stories[currentStoryIndex];
  const estimatedCount = Object.keys(estimatedStories).filter(id => 
    stories.some(s => s.story_id === id)
  ).length;
  const totalStories = stories.length;

  if (loading && !selectedEpic) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">AI Poker Planning</h1>
          <p className="text-muted-foreground mt-1">Get story estimates from AI team personas</p>
        </div>
      </div>

      {/* Epic Selector */}
      <Card className="bg-card border-border">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1">
              <Select value={selectedEpic} onValueChange={setSelectedEpic}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an epic to estimate stories" />
                </SelectTrigger>
                <SelectContent>
                  {epics.map((epic) => (
                    <SelectItem key={epic.epic_id} value={epic.epic_id}>
                      {epic.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedEpic && stories.length > 0 && (
              <div className="text-sm text-muted-foreground">
                Story {currentStoryIndex + 1} of {stories.length}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {selectedEpic && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content Area */}
          <div className="lg:col-span-2 space-y-6">
            {/* Progress */}
            {stories.length > 0 && (
              <Card className="bg-card border-border">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">Estimation Progress</span>
                    <span className="text-sm font-medium text-foreground">
                      {estimatedCount} / {totalStories} stories
                    </span>
                  </div>
                  <Progress value={(estimatedCount / Math.max(totalStories, 1)) * 100} className="h-2" />
                </CardContent>
              </Card>
            )}

            {/* Current Story */}
            {loading ? (
              <div className="flex justify-center py-20">
                <Loader2 className="h-8 w-8 text-primary animate-spin" />
              </div>
            ) : currentStory ? (
              <Card className="bg-card border-border">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">Story {currentStoryIndex + 1}</Badge>
                    {estimatedStories[currentStory.story_id] && (
                      <Badge className="bg-green-500/10 text-green-500 border-green-500/30">
                        <Check className="h-3 w-3 mr-1" />
                        {estimatedStories[currentStory.story_id].points} pts
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-xl">{currentStory.title || 'Untitled Story'}</CardTitle>
                  <CardDescription className="text-base">
                    As a <span className="font-medium text-foreground">{currentStory.persona}</span>, 
                    I want to <span className="font-medium text-foreground">{currentStory.action}</span>, 
                    so that <span className="font-medium text-foreground">{currentStory.benefit}</span>.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Acceptance Criteria */}
                  {currentStory.acceptance_criteria?.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-foreground mb-2">Acceptance Criteria</h4>
                      <ul className="space-y-1">
                        {currentStory.acceptance_criteria.map((c, i) => (
                          <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                            <span className="text-primary mt-1">•</span>
                            <span>{c}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <Separator />

                  {/* AI Estimation Controls */}
                  {!estimating && aiEstimates.length === 0 && (
                    <div className="text-center py-6">
                      <Sparkles className="h-12 w-12 text-primary mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-foreground mb-2">
                        Ready to Estimate
                      </h3>
                      <p className="text-muted-foreground mb-4 max-w-md mx-auto">
                        Click the button below to get estimates from 5 AI team personas: 
                        Sr. Developer, Jr. Developer, QA Engineer, DevOps, and UX Designer.
                      </p>
                      <Button onClick={runAIEstimation} size="lg" data-testid="start-ai-estimation">
                        <Play className="h-5 w-5 mr-2" />
                        Get AI Estimates
                      </Button>
                    </div>
                  )}

                  {/* Estimating Progress */}
                  {estimating && (
                    <div className="py-6">
                      <div className="flex items-center justify-center gap-3 mb-4">
                        <Loader2 className="h-6 w-6 text-primary animate-spin" />
                        <span className="text-lg font-medium text-foreground">
                          {currentPersona ? (
                            <>
                              <span className="text-2xl mr-2">{currentPersona.avatar}</span>
                              {currentPersona.name} is thinking...
                            </>
                          ) : (
                            'Starting estimation...'
                          )}
                        </span>
                      </div>
                      <Progress value={(aiEstimates.length / 5) * 100} className="h-2" />
                      <p className="text-center text-sm text-muted-foreground mt-2">
                        {aiEstimates.length} of 5 personas have voted
                      </p>
                    </div>
                  )}

                  {/* AI Estimates Display */}
                  {aiEstimates.length > 0 && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                        <Users className="h-4 w-4" />
                        Team Estimates
                      </h4>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {aiEstimates.map((estimate) => (
                          <div 
                            key={estimate.persona_id}
                            className="p-3 rounded-lg border border-border bg-muted/30"
                          >
                            <div className="flex items-center gap-3 mb-2">
                              <Avatar className="h-10 w-10">
                                <AvatarFallback className="text-lg bg-primary/10">
                                  {estimate.avatar}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-foreground truncate">
                                  {estimate.name}
                                </p>
                                <p className="text-xs text-muted-foreground truncate">
                                  {estimate.role}
                                </p>
                              </div>
                              <div className="text-2xl font-bold text-primary">
                                {estimate.estimate}
                              </div>
                            </div>
                            <p className="text-sm text-muted-foreground line-clamp-2">
                              {estimate.reasoning}
                            </p>
                            <div className="mt-2 flex items-center gap-1 text-xs">
                              <span className="text-muted-foreground">Confidence:</span>
                              <span className={getConfidenceColor(estimate.confidence)}>
                                {estimate.confidence}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Summary & Accept */}
                  {estimateSummary && (
                    <div className="space-y-4 pt-4 border-t border-border">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                          <Trophy className="h-4 w-4 text-yellow-500" />
                          Estimation Summary
                        </h4>
                        <Badge className={getConsensusColor(estimateSummary.consensus)}>
                          {estimateSummary.consensus} consensus
                        </Badge>
                      </div>
                      
                      <div className="grid grid-cols-4 gap-4 text-center">
                        <div className="p-3 rounded-lg bg-muted/50">
                          <p className="text-xs text-muted-foreground">Suggested</p>
                          <p className="text-2xl font-bold text-primary">{estimateSummary.suggested}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-muted/50">
                          <p className="text-xs text-muted-foreground">Average</p>
                          <p className="text-2xl font-bold text-foreground">{estimateSummary.average}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-muted/50">
                          <p className="text-xs text-muted-foreground">Min</p>
                          <p className="text-2xl font-bold text-foreground">{estimateSummary.min}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-muted/50">
                          <p className="text-xs text-muted-foreground">Max</p>
                          <p className="text-2xl font-bold text-foreground">{estimateSummary.max}</p>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row items-center gap-3 pt-4">
                        <Button 
                          variant="outline" 
                          onClick={() => {
                            resetEstimation();
                            runAIEstimation();
                          }}
                          disabled={estimating}
                        >
                          <RotateCcw className="h-4 w-4 mr-2" />
                          Re-estimate
                        </Button>
                        <div className="flex-1 flex flex-wrap justify-center gap-2">
                          {FIBONACCI.map((value) => (
                            <Button
                              key={value}
                              variant={value === estimateSummary.suggested ? 'default' : 'outline'}
                              className="h-12 w-12 text-lg font-bold"
                              onClick={() => acceptEstimate(value)}
                              data-testid={`accept-estimate-${value}`}
                            >
                              {value}
                            </Button>
                          ))}
                        </div>
                      </div>
                      
                      <p className="text-center text-sm text-muted-foreground">
                        Click a number to accept that estimate for this story
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-card border-border">
                <CardContent className="p-12 text-center">
                  <AlertCircle className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-xl font-medium text-foreground mb-2">
                    No Stories to Estimate
                  </h3>
                  <p className="text-muted-foreground mb-6">
                    This epic doesn&apos;t have any user stories yet. Create stories first, then come back to estimate them.
                  </p>
                  <Button onClick={() => navigate('/dashboard')}>
                    Go to Dashboard
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Navigation */}
            {stories.length > 0 && (
              <div className="flex justify-between">
                <Button 
                  variant="outline" 
                  onClick={handlePrevStory}
                  disabled={currentStoryIndex === 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-2" />
                  Previous Story
                </Button>
                <Button 
                  variant="outline" 
                  onClick={handleNextStory}
                  disabled={currentStoryIndex >= stories.length - 1}
                >
                  Next Story
                  <ChevronRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* AI Team */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  AI Team Personas
                </CardTitle>
                <CardDescription>
                  Each persona evaluates from their unique perspective
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { avatar: '👩‍💻', name: 'Sarah', role: 'Sr. Developer', focus: 'Technical complexity' },
                  { avatar: '👨‍💻', name: 'Alex', role: 'Jr. Developer', focus: 'Learning curve' },
                  { avatar: '🧪', name: 'Maya', role: 'QA Engineer', focus: 'Test coverage' },
                  { avatar: '🔧', name: 'Jordan', role: 'DevOps', focus: 'Deployment & infra' },
                  { avatar: '🎨', name: 'Riley', role: 'UX Designer', focus: 'User experience' },
                ].map((persona) => (
                  <div 
                    key={persona.name}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50"
                  >
                    <span className="text-2xl">{persona.avatar}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-foreground">{persona.name}</p>
                      <p className="text-xs text-muted-foreground">{persona.role}</p>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {persona.focus}
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Fibonacci Scale */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Target className="h-4 w-4" />
                  Fibonacci Scale
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <Badge variant="outline">1</Badge>
                  <span className="text-muted-foreground">Trivial - few hours</span>
                </div>
                <div className="flex justify-between">
                  <Badge variant="outline">2</Badge>
                  <span className="text-muted-foreground">Small - about a day</span>
                </div>
                <div className="flex justify-between">
                  <Badge variant="outline">3</Badge>
                  <span className="text-muted-foreground">Medium - 2-3 days</span>
                </div>
                <div className="flex justify-between">
                  <Badge variant="outline">5</Badge>
                  <span className="text-muted-foreground">Large - about a week</span>
                </div>
                <div className="flex justify-between">
                  <Badge variant="outline">8</Badge>
                  <span className="text-muted-foreground">Very large - 1-2 weeks</span>
                </div>
                <div className="flex justify-between">
                  <Badge variant="outline">13</Badge>
                  <span className="text-muted-foreground">Huge - consider splitting</span>
                </div>
              </CardContent>
            </Card>

            {/* Tips */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-yellow-500" />
                  Tips
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground space-y-2">
                <p>• AI personas consider different aspects of the work</p>
                <p>• Low consensus means the story may need more clarity</p>
                <p>• Consider splitting stories estimated at 13 points</p>
                <p>• The suggested estimate is based on team consensus</p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
};

export default PokerPlanning;
