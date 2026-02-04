import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { 
  Loader2, Users, Play, SkipForward, Check, RotateCcw,
  Eye, EyeOff, ChevronRight, Sparkles, Clock
} from 'lucide-react';
import { epicAPI, featureAPI, userStoryAPI } from '@/api';

const FIBONACCI = [0, 1, 2, 3, 5, 8, 13, 21, '?', '☕'];

const PokerPlanning = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [epics, setEpics] = useState([]);
  const [selectedEpic, setSelectedEpic] = useState('');
  const [stories, setStories] = useState([]);
  const [currentStoryIndex, setCurrentStoryIndex] = useState(0);
  const [votes, setVotes] = useState({});
  const [revealed, setRevealed] = useState(false);
  const [selectedVote, setSelectedVote] = useState(null);
  const [participants, setParticipants] = useState(['You']);
  const [newParticipant, setNewParticipant] = useState('');
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
      const response = await epicAPI.getEpics();
      setEpics(response.data || []);
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
      const featuresRes = await featureAPI.getFeatures(selectedEpic);
      const features = featuresRes.data || [];
      
      // Collect all stories from all features
      const allStories = [];
      for (const feature of features) {
        try {
          const storiesRes = await userStoryAPI.getStoriesForFeature(feature.feature_id);
          allStories.push(...(storiesRes.data || []));
        } catch (e) {
          console.error(`Failed to load stories for feature ${feature.feature_id}`);
        }
      }
      
      setStories(allStories);
      setCurrentStoryIndex(0);
      resetVoting();
    } catch (error) {
      console.error('Failed to load stories:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSavedEstimates = () => {
    try {
      const saved = localStorage.getItem('jarlpm_poker_estimates');
      if (saved) {
        setEstimatedStories(JSON.parse(saved));
      }
    } catch (error) {
      console.error('Failed to load saved estimates:', error);
    }
  };

  const saveEstimates = (estimates) => {
    localStorage.setItem('jarlpm_poker_estimates', JSON.stringify(estimates));
  };

  const resetVoting = () => {
    setVotes({});
    setRevealed(false);
    setSelectedVote(null);
  };

  const handleVote = (value) => {
    setSelectedVote(value);
    setVotes(prev => ({
      ...prev,
      'You': value
    }));
    
    // Simulate other participants voting (for demo)
    participants.forEach(p => {
      if (p !== 'You') {
        setTimeout(() => {
          setVotes(prev => ({
            ...prev,
            [p]: FIBONACCI[Math.floor(Math.random() * 8)]
          }));
        }, Math.random() * 2000);
      }
    });
  };

  const handleReveal = () => {
    setRevealed(true);
  };

  const handleAcceptEstimate = (points) => {
    const currentStory = stories[currentStoryIndex];
    if (!currentStory) return;
    
    const newEstimates = {
      ...estimatedStories,
      [currentStory.story_id]: {
        points,
        estimatedAt: new Date().toISOString()
      }
    };
    setEstimatedStories(newEstimates);
    saveEstimates(newEstimates);
    
    // Move to next story
    if (currentStoryIndex < stories.length - 1) {
      setCurrentStoryIndex(prev => prev + 1);
      resetVoting();
    }
  };

  const handleNextStory = () => {
    if (currentStoryIndex < stories.length - 1) {
      setCurrentStoryIndex(prev => prev + 1);
      resetVoting();
    }
  };

  const handlePrevStory = () => {
    if (currentStoryIndex > 0) {
      setCurrentStoryIndex(prev => prev - 1);
      resetVoting();
    }
  };

  const addParticipant = () => {
    if (newParticipant.trim() && !participants.includes(newParticipant.trim())) {
      setParticipants(prev => [...prev, newParticipant.trim()]);
      setNewParticipant('');
    }
  };

  const removeParticipant = (name) => {
    if (name !== 'You') {
      setParticipants(prev => prev.filter(p => p !== name));
      setVotes(prev => {
        const newVotes = { ...prev };
        delete newVotes[name];
        return newVotes;
      });
    }
  };

  const getAverageVote = () => {
    const numericVotes = Object.values(votes).filter(v => typeof v === 'number');
    if (numericVotes.length === 0) return null;
    const avg = numericVotes.reduce((a, b) => a + b, 0) / numericVotes.length;
    // Find closest Fibonacci number
    const closest = FIBONACCI.filter(f => typeof f === 'number').reduce((prev, curr) => 
      Math.abs(curr - avg) < Math.abs(prev - avg) ? curr : prev
    );
    return closest;
  };

  const currentStory = stories[currentStoryIndex];
  const allVoted = participants.every(p => votes[p] !== undefined);
  const estimatedCount = Object.keys(estimatedStories).length;
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
          <h1 className="text-3xl font-bold text-foreground">Planning Poker</h1>
          <p className="text-muted-foreground mt-1">Estimate story points collaboratively</p>
        </div>
      </div>

      {/* Epic Selector */}
      <Card className="bg-card border-border">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
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
                {currentStoryIndex + 1} of {stories.length} stories
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {selectedEpic && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main Voting Area */}
          <div className="lg:col-span-3 space-y-6">
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
                  <CardTitle className="text-xl">{currentStory.title}</CardTitle>
                  {currentStory.description && (
                    <CardDescription>{currentStory.description}</CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  {currentStory.acceptance_criteria && (
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-foreground mb-2">Acceptance Criteria</h4>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {currentStory.acceptance_criteria}
                      </p>
                    </div>
                  )}

                  {/* Voting Cards */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium text-foreground">Your Vote</h4>
                    <div className="flex flex-wrap gap-2">
                      {FIBONACCI.map((value) => (
                        <Button
                          key={value}
                          variant={selectedVote === value ? 'default' : 'outline'}
                          className={`h-16 w-12 text-lg font-bold ${
                            selectedVote === value ? 'bg-primary text-primary-foreground' : ''
                          }`}
                          onClick={() => handleVote(value)}
                          disabled={revealed}
                        >
                          {value}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Results */}
                  {Object.keys(votes).length > 0 && (
                    <div className="mt-6 space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-medium text-foreground">Votes</h4>
                        {!revealed && allVoted && (
                          <Button size="sm" onClick={handleReveal}>
                            <Eye className="h-4 w-4 mr-2" />
                            Reveal
                          </Button>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-3">
                        {participants.map((participant) => (
                          <div 
                            key={participant}
                            className="flex flex-col items-center gap-1"
                          >
                            <div className={`h-12 w-10 rounded-lg border-2 flex items-center justify-center font-bold ${
                              revealed ? 'bg-primary/10 border-primary text-primary' : 'bg-muted border-border'
                            }`}>
                              {revealed ? (votes[participant] ?? '—') : (votes[participant] ? '✓' : '?')}
                            </div>
                            <span className="text-xs text-muted-foreground truncate max-w-[60px]">
                              {participant}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Average & Accept */}
                      {revealed && (
                        <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                          <div>
                            <p className="text-sm text-muted-foreground">Suggested Estimate</p>
                            <p className="text-2xl font-bold text-primary">{getAverageVote()} points</p>
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" onClick={resetVoting}>
                              <RotateCcw className="h-4 w-4 mr-2" />
                              Re-vote
                            </Button>
                            <Button onClick={() => handleAcceptEstimate(getAverageVote())}>
                              <Check className="h-4 w-4 mr-2" />
                              Accept
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-card border-border">
                <CardContent className="p-12 text-center">
                  <Clock className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-xl font-medium text-foreground mb-2">
                    No Stories to Estimate
                  </h3>
                  <p className="text-muted-foreground">
                    This epic doesn't have any approved stories yet.
                  </p>
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

          {/* Participants Sidebar */}
          <div className="space-y-4">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Participants
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="Add participant"
                    value={newParticipant}
                    onChange={(e) => setNewParticipant(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addParticipant()}
                  />
                  <Button size="icon" onClick={addParticipant}>
                    <Users className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-2">
                  {participants.map((p) => (
                    <div 
                      key={p}
                      className="flex items-center justify-between p-2 rounded-lg bg-muted/50"
                    >
                      <span className="text-sm font-medium">{p}</span>
                      {p !== 'You' && (
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => removeParticipant(p)}
                        >
                          ×
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-yellow-500" />
                  Tips
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground space-y-2">
                <p>• Use Fibonacci sequence for more accurate estimates</p>
                <p>• Discuss stories before voting</p>
                <p>• Re-vote if there's large variance</p>
                <p>• Add team members as participants</p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
};

export default PokerPlanning;
