import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { epicAPI, featureAPI, userStoryAPI } from '@/api';
import { useThemeStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import ThemeToggle from '@/components/ThemeToggle';
import { 
  ArrowLeft, Loader2, Lock, CheckCircle2, 
  ChevronDown, ChevronRight, FileText, Settings,
  Layers, Puzzle, BookOpen, Trophy, Calendar
} from 'lucide-react';

const CompletedEpic = () => {
  const { epicId } = useParams();
  const navigate = useNavigate();
  const { theme } = useThemeStore();

  const [epic, setEpic] = useState(null);
  const [features, setFeatures] = useState([]);
  const [storiesByFeature, setStoriesByFeature] = useState({});
  const [loading, setLoading] = useState(true);
  const [expandedFeatures, setExpandedFeatures] = useState({});

  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  const loadData = useCallback(async () => {
    try {
      // Load epic
      const epicRes = await epicAPI.get(epicId);
      setEpic(epicRes.data);

      // Load features
      const featuresRes = await featureAPI.listForEpic(epicId);
      const featuresData = featuresRes.data || [];
      setFeatures(featuresData);

      // Load stories for each feature
      const storiesMap = {};
      for (const feature of featuresData) {
        try {
          const storiesRes = await userStoryAPI.listForFeature(feature.feature_id);
          storiesMap[feature.feature_id] = storiesRes.data || [];
        } catch (err) {
          storiesMap[feature.feature_id] = [];
        }
      }
      setStoriesByFeature(storiesMap);

      // Expand all features by default
      const expanded = {};
      featuresData.forEach(f => { expanded[f.feature_id] = true; });
      setExpandedFeatures(expanded);

    } catch (err) {
      if (err.response?.status === 404) {
        navigate('/dashboard');
      }
    } finally {
      setLoading(false);
    }
  }, [epicId, navigate]);

  useEffect(() => { loadData(); }, [loadData]);

  const toggleFeature = (featureId) => {
    setExpandedFeatures(prev => ({
      ...prev,
      [featureId]: !prev[featureId]
    }));
  };

  const expandAll = () => {
    const expanded = {};
    features.forEach(f => { expanded[f.feature_id] = true; });
    setExpandedFeatures(expanded);
  };

  const collapseAll = () => {
    setExpandedFeatures({});
  };

  // Calculate stats
  const totalFeatures = features.length;
  const approvedFeatures = features.filter(f => f.current_stage === 'approved').length;
  const totalStories = Object.values(storiesByFeature).flat().length;
  const approvedStories = Object.values(storiesByFeature).flat().filter(s => s.current_stage === 'approved').length;
  const totalStoryPoints = Object.values(storiesByFeature).flat().reduce((sum, s) => sum + (s.story_points || 0), 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (!epic) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Epic not found</p>
      </div>
    );
  }

  const isFullyComplete = epic.current_stage === 'epic_locked' && 
    approvedFeatures === totalFeatures && 
    approvedStories === totalStories &&
    totalFeatures > 0 &&
    totalStories > 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-background/95 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => navigate('/dashboard')} 
                className="text-muted-foreground hover:text-foreground"
                data-testid="back-to-dashboard-btn"
              >
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="flex items-center gap-2">
                <img src={logoSrc} alt="JarlPM" className="h-8 w-auto" />
                <span className="text-xl font-bold text-foreground">JarlPM</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isFullyComplete && (
                <Badge className="bg-success text-white" data-testid="completed-badge">
                  <Trophy className="w-3 h-3 mr-1" />
                  Completed
                </Badge>
              )}
              <ThemeToggle />
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => navigate('/settings')}
                className="text-muted-foreground hover:text-foreground"
                data-testid="settings-btn"
              >
                <Settings className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <div className={`border-b ${isFullyComplete ? 'border-success/30 bg-gradient-to-r from-success/10 via-emerald-500/10 to-success/10' : 'border-border bg-muted/30'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${isFullyComplete ? 'bg-success/20' : 'bg-primary/20'}`}>
                {isFullyComplete ? (
                  <Trophy className="w-8 h-8 text-success" />
                ) : (
                  <Layers className="w-8 h-8 text-primary" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="bg-success/10 text-success border-success/30">
                    <Lock className="w-3 h-3 mr-1" />
                    Epic Locked
                  </Badge>
                  {epic.created_at && (
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {new Date(epic.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <h1 className="text-2xl font-bold text-foreground mb-2">{epic.title}</h1>
                {epic.snapshot?.epic_summary && (
                  <p className="text-muted-foreground max-w-2xl">{epic.snapshot.epic_summary}</p>
                )}
              </div>
            </div>
            
            {/* Stats */}
            <div className="flex items-center gap-6 bg-card rounded-xl p-4 border border-border">
              <div className="text-center">
                <p className="text-2xl font-bold text-violet-400">{totalFeatures}</p>
                <p className="text-xs text-muted-foreground">Features</p>
              </div>
              <div className="h-8 w-px bg-border" />
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-400">{totalStories}</p>
                <p className="text-xs text-muted-foreground">Stories</p>
              </div>
              <div className="h-8 w-px bg-border" />
              <div className="text-center">
                <p className="text-2xl font-bold text-amber-400">{totalStoryPoints}</p>
                <p className="text-xs text-muted-foreground">Story Points</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">Epic Breakdown</h2>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={expandAll} data-testid="expand-all-btn">
              Expand All
            </Button>
            <Button variant="outline" size="sm" onClick={collapseAll} data-testid="collapse-all-btn">
              Collapse All
            </Button>
          </div>
        </div>

        {/* Epic Details Card */}
        <Card className="mb-6 border-success/30 bg-success/5" data-testid="epic-details-card">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
                <Layers className="w-5 h-5 text-success" />
              </div>
              <div>
                <CardTitle className="text-base text-foreground flex items-center gap-2">
                  Epic Details
                  <Lock className="w-4 h-4 text-success" />
                </CardTitle>
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">Problem Statement</h4>
              <p className="text-sm text-foreground bg-background/50 p-2 rounded">{epic.snapshot?.problem_statement || 'N/A'}</p>
            </div>
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">Desired Outcome</h4>
              <p className="text-sm text-foreground bg-background/50 p-2 rounded">{epic.snapshot?.desired_outcome || 'N/A'}</p>
            </div>
            {epic.snapshot?.acceptance_criteria?.length > 0 && (
              <div className="md:col-span-2">
                <h4 className="text-xs font-medium text-muted-foreground mb-1">Acceptance Criteria</h4>
                <ul className="text-sm text-foreground bg-background/50 p-2 rounded space-y-1">
                  {epic.snapshot.acceptance_criteria.map((c, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Features Tree */}
        <div className="space-y-4" data-testid="features-tree">
          {features.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="p-8 text-center">
                <p className="text-muted-foreground">No features created yet</p>
                <Button 
                  className="mt-4" 
                  onClick={() => navigate(`/epic/${epicId}`)}
                  data-testid="go-to-feature-planning-btn"
                >
                  Go to Feature Planning
                </Button>
              </CardContent>
            </Card>
          ) : (
            features.map((feature) => {
              const stories = storiesByFeature[feature.feature_id] || [];
              const featureApproved = feature.current_stage === 'approved';
              const allStoriesApproved = stories.length > 0 && stories.every(s => s.current_stage === 'approved');
              const featureComplete = featureApproved && allStoriesApproved;
              const isExpanded = expandedFeatures[feature.feature_id];
              const featureStoryPoints = stories.reduce((sum, s) => sum + (s.story_points || 0), 0);

              return (
                <Collapsible 
                  key={feature.feature_id} 
                  open={isExpanded}
                  onOpenChange={() => toggleFeature(feature.feature_id)}
                >
                  <Card className={`${featureComplete ? 'border-violet-500/30 bg-violet-500/5' : featureApproved ? 'border-success/30 bg-success/5' : 'border-amber-500/30 bg-amber-500/5'}`} data-testid={`feature-tree-${feature.feature_id}`}>
                    <CollapsibleTrigger asChild>
                      <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors pb-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${featureComplete ? 'bg-violet-500/20' : featureApproved ? 'bg-success/20' : 'bg-amber-500/20'}`}>
                              <Puzzle className={`w-5 h-5 ${featureComplete ? 'text-violet-400' : featureApproved ? 'text-success' : 'text-amber-400'}`} />
                            </div>
                            <div>
                              <CardTitle className="text-base text-foreground flex items-center gap-2">
                                {feature.title}
                                {featureApproved && <Lock className="w-4 h-4 text-success" />}
                              </CardTitle>
                              <div className="flex items-center gap-2 mt-1">
                                <Badge variant="outline" className={`text-xs ${featureApproved ? 'bg-success/10 text-success border-success/30' : 'bg-amber-500/10 text-amber-400 border-amber-500/30'}`}>
                                  {featureApproved ? 'Approved' : feature.current_stage}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  {stories.length} {stories.length === 1 ? 'story' : 'stories'}
                                </span>
                                {featureStoryPoints > 0 && (
                                  <span className="text-xs text-blue-400">
                                    {featureStoryPoints} pts
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {!featureApproved && (
                              <Button 
                                variant="outline" 
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); navigate(`/epic/${epicId}`); }}
                                data-testid={`continue-feature-btn-${feature.feature_id}`}
                              >
                                Continue
                              </Button>
                            )}
                            {featureApproved && stories.length === 0 && (
                              <Button 
                                variant="outline" 
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); navigate(`/feature/${feature.feature_id}/stories`); }}
                                data-testid={`create-stories-btn-${feature.feature_id}`}
                              >
                                Create Stories
                              </Button>
                            )}
                            {isExpanded ? (
                              <ChevronDown className="w-5 h-5 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="w-5 h-5 text-muted-foreground" />
                            )}
                          </div>
                        </div>
                      </CardHeader>
                    </CollapsibleTrigger>
                    
                    <CollapsibleContent>
                      <CardContent className="pt-0">
                        {/* Feature Description */}
                        <p className="text-sm text-muted-foreground mb-4">{feature.description}</p>
                        
                        {/* Feature Acceptance Criteria */}
                        {feature.acceptance_criteria?.length > 0 && (
                          <div className="mb-4 bg-background/50 rounded-lg p-3">
                            <p className="text-xs font-medium text-foreground mb-2">Feature Acceptance Criteria:</p>
                            <ul className="text-xs text-muted-foreground space-y-1">
                              {feature.acceptance_criteria.map((c, i) => (
                                <li key={i} className="flex items-start gap-2">
                                  <CheckCircle2 className="w-3 h-3 mt-0.5 text-success flex-shrink-0" />
                                  {c}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* User Stories */}
                        {stories.length > 0 ? (
                          <div className="space-y-3 pl-4 border-l-2 border-blue-500/30">
                            <p className="text-xs font-medium text-foreground mb-2 flex items-center gap-2">
                              <BookOpen className="w-4 h-4 text-blue-400" />
                              User Stories ({stories.length})
                            </p>
                            {stories.map((story) => {
                              const storyApproved = story.current_stage === 'approved';
                              return (
                                <div 
                                  key={story.story_id}
                                  className={`p-3 rounded-lg ${storyApproved ? 'bg-blue-500/10 border border-blue-500/30' : 'bg-amber-500/10 border border-amber-500/30'}`}
                                  data-testid={`story-tree-${story.story_id}`}
                                >
                                  <div className="flex items-start justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <BookOpen className={`w-4 h-4 ${storyApproved ? 'text-blue-400' : 'text-amber-400'}`} />
                                      <Badge variant="outline" className={`text-xs ${storyApproved ? 'bg-success/10 text-success border-success/30' : 'bg-amber-500/10 text-amber-400 border-amber-500/30'}`}>
                                        {storyApproved && <Lock className="w-3 h-3 mr-1" />}
                                        {storyApproved ? 'Approved' : story.current_stage}
                                      </Badge>
                                      {story.story_points && (
                                        <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                                          {story.story_points} pts
                                        </Badge>
                                      )}
                                    </div>
                                    {!storyApproved && (
                                      <Button 
                                        variant="outline" 
                                        size="sm"
                                        onClick={() => navigate(`/feature/${feature.feature_id}/stories`)}
                                        data-testid={`continue-story-btn-${story.story_id}`}
                                      >
                                        Continue
                                      </Button>
                                    )}
                                  </div>
                                  <p className="text-sm text-foreground italic mb-2">&quot;{story.story_text}&quot;</p>
                                  {story.acceptance_criteria?.length > 0 && (
                                    <div className="bg-background/50 rounded p-2">
                                      <p className="text-xs font-medium text-muted-foreground mb-1">Acceptance Criteria:</p>
                                      <ul className="text-xs text-muted-foreground space-y-1">
                                        {story.acceptance_criteria.map((c, i) => (
                                          <li key={i} className="flex items-start gap-1">
                                            {storyApproved ? (
                                              <CheckCircle2 className="w-3 h-3 mt-0.5 text-success flex-shrink-0" />
                                            ) : (
                                              <span className="text-amber-400">•</span>
                                            )}
                                            {c}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : featureApproved ? (
                          <div className="p-4 rounded-lg border-2 border-dashed border-blue-500/30 text-center">
                            <p className="text-sm text-muted-foreground mb-2">No user stories created yet</p>
                            <Button 
                              size="sm"
                              onClick={() => navigate(`/feature/${feature.feature_id}/stories`)}
                              className="bg-blue-500 hover:bg-blue-600"
                              data-testid={`start-stories-btn-${feature.feature_id}`}
                            >
                              <BookOpen className="w-4 h-4 mr-1" />
                              Create User Stories
                            </Button>
                          </div>
                        ) : null}
                      </CardContent>
                    </CollapsibleContent>
                  </Card>
                </Collapsible>
              );
            })
          )}
        </div>

        {/* Completion Message */}
        {isFullyComplete && (
          <Card className="mt-8 border-success/30 bg-gradient-to-r from-success/10 via-emerald-500/10 to-success/10" data-testid="completion-message">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 rounded-full bg-success/20 flex items-center justify-center mx-auto mb-4">
                <Trophy className="w-8 h-8 text-success" />
              </div>
              <h3 className="text-xl font-bold text-foreground mb-2">Epic Complete!</h3>
              <p className="text-muted-foreground mb-4">
                All {totalFeatures} features and {totalStories} user stories have been approved and locked.
                Total estimated effort: {totalStoryPoints} story points.
              </p>
              <p className="text-sm text-muted-foreground italic">
                A Jarl does not reopen settled decisions.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default CompletedEpic;
