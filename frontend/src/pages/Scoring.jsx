import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Loader2, Gauge, Plus, Layers, BookOpen, Bug, ExternalLink, Sparkles, Check, ChevronRight, ArrowLeft, Target, AlertCircle, Filter } from 'lucide-react';
import { MoSCoWBadge, RICEBadge } from '@/components/ScoringComponents';
import { scoringAPI, epicAPI, userStoryAPI, bugAPI } from '@/api';
import { toast } from 'sonner';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';

const Scoring = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const epicIdFromUrl = searchParams.get('epic');
  
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  
  // Scored items (list-first view)
  const [scoredItems, setScoredItems] = useState([]);
  
  // Items available for scoring
  const [itemsForScoring, setItemsForScoring] = useState({ epics: [], standalone_stories: [], standalone_bugs: [] });
  
  // AI suggestions
  const [allSuggestions, setAllSuggestions] = useState(null);
  
  // Dialog state
  const [showInitiateDialog, setShowInitiateDialog] = useState(false);
  const [selectedItemType, setSelectedItemType] = useState('epic');
  const [selectedItemId, setSelectedItemId] = useState('');
  
  // View mode
  const [viewMode, setViewMode] = useState('list'); // 'list' | 'detail'
  const [selectedEpicDetail, setSelectedEpicDetail] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  // If epic ID is in URL, auto-open scoring for that epic
  useEffect(() => {
    if (epicIdFromUrl && itemsForScoring.epics.length > 0) {
      const epic = itemsForScoring.epics.find(e => e.epic_id === epicIdFromUrl);
      if (epic) {
        handleViewEpicScores(epicIdFromUrl);
      }
    }
  }, [epicIdFromUrl, itemsForScoring.epics]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [scoredRes, itemsRes] = await Promise.all([
        scoringAPI.getScoredItems(),
        scoringAPI.getItemsForScoring(),
      ]);
      
      setScoredItems(scoredRes.data?.items || []);
      setItemsForScoring(itemsRes.data || { epics: [], standalone_stories: [], standalone_bugs: [] });
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load scoring data');
    } finally {
      setLoading(false);
    }
  };

  const handleViewEpicScores = async (epicId) => {
    try {
      const response = await scoringAPI.getEpicScores(epicId);
      setSelectedEpicDetail(response.data);
      setViewMode('detail');
    } catch (error) {
      console.error('Failed to load epic scores:', error);
      toast.error('Failed to load epic scores');
    }
  };

  const handleInitiateScoring = () => {
    if (!selectedItemId) {
      toast.error('Please select an item to score');
      return;
    }
    
    setShowInitiateDialog(false);
    
    if (selectedItemType === 'epic') {
      handleAIGenerateForEpic(selectedItemId);
    } else if (selectedItemType === 'standalone_story') {
      // For standalone stories, navigate to a scoring interface or show inline
      toast.info('Standalone story scoring - use AI suggest');
    } else if (selectedItemType === 'standalone_bug') {
      toast.info('Standalone bug scoring - use AI suggest');
    }
  };

  const handleAIGenerateForEpic = async (epicId) => {
    setGenerating(true);
    setAllSuggestions(null);
    
    // First, view the epic scores to show detail view
    await handleViewEpicScores(epicId);
    
    try {
      const response = await scoringAPI.bulkScoreAll(epicId);
      setAllSuggestions(response.data);
      const total = (response.data.feature_suggestions?.length || 0) + 
                    (response.data.story_suggestions?.length || 0) + 
                    (response.data.bug_suggestions?.length || 0);
      toast.success(`Generated scores for ${total} items`);
    } catch (error) {
      console.error('Failed to generate scores:', error);
      const message = error.response?.data?.detail || 'Failed to generate scores';
      toast.error(message);
    } finally {
      setGenerating(false);
    }
  };

  const handleApplyScores = async () => {
    if (!allSuggestions || !selectedEpicDetail) return;
    
    setApplying(true);
    try {
      const response = await scoringAPI.applyAllScores(selectedEpicDetail.epic_id, allSuggestions);
      toast.success(`Applied scores: ${response.data.applied.features} features, ${response.data.applied.stories} stories, ${response.data.applied.bugs} bugs`);
      setAllSuggestions(null);
      // Reload the detail view
      await handleViewEpicScores(selectedEpicDetail.epic_id);
      // Also reload the main list
      await loadData();
    } catch (error) {
      console.error('Failed to apply scores:', error);
      toast.error('Failed to apply scores');
    } finally {
      setApplying(false);
    }
  };

  const getTotalSuggestions = () => {
    if (!allSuggestions) return 0;
    return (allSuggestions.feature_suggestions?.length || 0) + 
           (allSuggestions.story_suggestions?.length || 0) + 
           (allSuggestions.bug_suggestions?.length || 0);
  };

  const scoredEpics = scoredItems.filter(i => i.item_type === 'epic');
  const scoredStories = scoredItems.filter(i => i.item_type === 'standalone_story');
  const scoredBugs = scoredItems.filter(i => i.item_type === 'standalone_bug');

  // ============================================
  // DETAIL VIEW - Epic Scores
  // ============================================
  if (viewMode === 'detail' && selectedEpicDetail) {
    return (
      <div className="space-y-6" data-testid="scoring-detail-view">
        {/* Page Header */}
        <div className="flex items-center gap-4">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => {
              setViewMode('list');
              setSelectedEpicDetail(null);
              setAllSuggestions(null);
            }}
            className="text-muted-foreground hover:text-foreground"
            data-testid="back-to-list-btn"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-foreground">{selectedEpicDetail.title}</h1>
            <p className="text-sm text-muted-foreground">Epic Scoring Details</p>
          </div>
          <div className="flex items-center gap-2">
            {getTotalSuggestions() > 0 && (
              <Button
                onClick={handleApplyScores}
                disabled={applying}
                variant="outline"
                className="border-green-500 text-green-500 hover:bg-green-500/10"
                data-testid="apply-scores-btn"
              >
                {applying ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Apply {getTotalSuggestions()} Scores
              </Button>
            )}
            <Button
              onClick={() => handleAIGenerateForEpic(selectedEpicDetail.epic_id)}
              disabled={generating}
              className="bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 text-white"
              data-testid="ai-score-btn"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              {generating ? 'Generating...' : 'AI Score All'}
            </Button>
          </div>
        </div>

        {/* Epic MoSCoW Score */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                  <Layers className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-base">Epic Priority</CardTitle>
                  <CardDescription>MoSCoW prioritization for this epic</CardDescription>
                </div>
              </div>
              {selectedEpicDetail.moscow_score ? (
                <MoSCoWBadge score={selectedEpicDetail.moscow_score} />
              ) : (
                <Badge variant="outline" className="text-muted-foreground">Not scored</Badge>
              )}
            </div>
          </CardHeader>
        </Card>

        {/* AI Suggestions Preview */}
        {allSuggestions && getTotalSuggestions() > 0 && (
          <Card className="bg-violet-500/5 border-violet-500/30" data-testid="ai-suggestions-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-violet-500" />
                AI-Generated Scores (Review before applying)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Features */}
              {allSuggestions.feature_suggestions?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Features ({allSuggestions.feature_suggestions.length})</h4>
                  <div className="space-y-2">
                    {allSuggestions.feature_suggestions.map((s) => (
                      <div key={s.item_id} className="flex items-center justify-between p-3 bg-background rounded-lg border">
                        <span className="font-medium truncate max-w-[300px]">{s.title}</span>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="bg-red-500/10 text-red-400 border-red-500/30 text-xs">
                            {s.moscow?.score?.replace('_', ' ')}
                          </Badge>
                          <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30 text-xs">
                            RICE: {s.rice?.reach && s.rice?.impact && s.rice?.confidence && s.rice?.effort 
                              ? ((s.rice.reach * s.rice.impact * s.rice.confidence) / s.rice.effort).toFixed(1)
                              : 'N/A'}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Stories */}
              {allSuggestions.story_suggestions?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">User Stories ({allSuggestions.story_suggestions.length})</h4>
                  <div className="space-y-2">
                    {allSuggestions.story_suggestions.map((s) => (
                      <div key={s.item_id} className="flex items-center justify-between p-3 bg-background rounded-lg border">
                        <span className="font-medium truncate max-w-[300px]">{s.title}</span>
                        <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30 text-xs">
                          RICE: {s.rice?.reach && s.rice?.impact && s.rice?.confidence && s.rice?.effort 
                            ? ((s.rice.reach * s.rice.impact * s.rice.confidence) / s.rice.effort).toFixed(1)
                            : 'N/A'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Bugs */}
              {allSuggestions.bug_suggestions?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Bugs ({allSuggestions.bug_suggestions.length})</h4>
                  <div className="space-y-2">
                    {allSuggestions.bug_suggestions.map((s) => (
                      <div key={s.item_id} className="flex items-center justify-between p-3 bg-background rounded-lg border">
                        <span className="font-medium truncate max-w-[300px]">{s.title}</span>
                        <Badge variant="outline" className="bg-orange-500/10 text-orange-400 border-orange-500/30 text-xs">
                          RICE: {s.rice?.reach && s.rice?.impact && s.rice?.confidence && s.rice?.effort 
                            ? ((s.rice.reach * s.rice.impact * s.rice.confidence) / s.rice.effort).toFixed(1)
                            : 'N/A'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Features Section */}
        <div>
          <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            Features ({selectedEpicDetail.features?.length || 0})
            <Badge variant="outline" className="text-xs">MoSCoW + RICE</Badge>
          </h3>
          {selectedEpicDetail.features?.length > 0 ? (
            <div className="space-y-3">
              {selectedEpicDetail.features.map((feature) => (
                <Card key={feature.feature_id} className="bg-card border-border hover:border-primary/30 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-foreground truncate">{feature.title}</h4>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {feature.moscow_score ? (
                          <MoSCoWBadge score={feature.moscow_score} />
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground text-xs">No MoSCoW</Badge>
                        )}
                        {feature.rice_total !== null && feature.rice_total !== undefined ? (
                          <RICEBadge score={feature.rice_total} />
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground text-xs">No RICE</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="border-dashed">
              <CardContent className="p-6 text-center text-muted-foreground">
                No features found for this epic
              </CardContent>
            </Card>
          )}
        </div>

        {/* Stories Section */}
        <div>
          <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            User Stories ({selectedEpicDetail.stories?.length || 0})
            <Badge variant="outline" className="text-xs">RICE only</Badge>
          </h3>
          {selectedEpicDetail.stories?.length > 0 ? (
            <div className="space-y-3">
              {selectedEpicDetail.stories.map((story) => (
                <Card key={story.story_id} className="bg-card border-border hover:border-blue-500/30 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <BookOpen className="w-4 h-4 text-blue-400" />
                          <h4 className="font-medium text-foreground truncate">{story.title}</h4>
                        </div>
                        {story.story_points && (
                          <p className="text-xs text-muted-foreground mt-1">{story.story_points} story points</p>
                        )}
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {story.rice_total !== null && story.rice_total !== undefined ? (
                          <RICEBadge score={story.rice_total} />
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground text-xs">Not scored</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="border-dashed">
              <CardContent className="p-6 text-center text-muted-foreground">
                No user stories found for this epic
              </CardContent>
            </Card>
          )}
        </div>

        {/* Bugs Section */}
        {selectedEpicDetail.bugs?.length > 0 && (
          <div>
            <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              Linked Bugs ({selectedEpicDetail.bugs.length})
              <Badge variant="outline" className="text-xs">RICE only</Badge>
            </h3>
            <div className="space-y-3">
              {selectedEpicDetail.bugs.map((bug) => (
                <Card key={bug.bug_id} className="bg-card border-border hover:border-orange-500/30 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Bug className="w-4 h-4 text-orange-400" />
                          <h4 className="font-medium text-foreground truncate">{bug.title}</h4>
                          <Badge variant="outline" className={`text-xs ${
                            bug.severity === 'critical' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                            bug.severity === 'high' ? 'bg-orange-500/10 text-orange-400 border-orange-500/30' :
                            bug.severity === 'medium' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30' :
                            'bg-gray-500/10 text-gray-400 border-gray-500/30'
                          }`}>
                            {bug.severity}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {bug.rice_total !== null && bug.rice_total !== undefined ? (
                          <RICEBadge score={bug.rice_total} />
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground text-xs">Not scored</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ============================================
  // LIST VIEW - Main Page
  // ============================================
  return (
    <div className="space-y-6" data-testid="scoring-list-view">
      {/* Page Header */}
      <PageHeader
        title="Scoring"
        description="MoSCoW prioritization and RICE scoring for your work items"
        actions={
          <Button
            onClick={() => setShowInitiateDialog(true)}
            className="bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 text-white"
            data-testid="initiate-scoring-btn"
          >
            <Plus className="h-4 w-4 mr-2" />
            Initiate Scoring
          </Button>
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-violet-500/10 rounded-lg">
                <Layers className="h-5 w-5 text-violet-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{scoredEpics.length}</p>
                <p className="text-sm text-muted-foreground">Scored Epics</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <BookOpen className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{scoredStories.length}</p>
                <p className="text-sm text-muted-foreground">Scored Stories</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-500/10 rounded-lg">
                <Bug className="h-5 w-5 text-orange-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{scoredBugs.length}</p>
                <p className="text-sm text-muted-foreground">Scored Bugs</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/10 rounded-lg">
                <Gauge className="h-5 w-5 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{scoredItems.length}</p>
                <p className="text-sm text-muted-foreground">Total Scored</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
        </div>
      ) : scoredItems.length === 0 ? (
        <Card className="border-2 border-dashed border-violet-500/30 bg-violet-500/5" data-testid="empty-state">
          <CardContent className="p-8 text-center">
            <div className="w-16 h-16 rounded-2xl bg-violet-500/20 flex items-center justify-center mx-auto mb-4">
              <Gauge className="w-8 h-8 text-violet-400" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">No Scored Items Yet</h3>
            <p className="text-muted-foreground mb-6 max-w-md mx-auto">
              Start by selecting an Epic, Standalone User Story, or Standalone Bug to score using MoSCoW and RICE frameworks.
            </p>
            <Button 
              onClick={() => setShowInitiateDialog(true)}
              className="bg-violet-500 hover:bg-violet-600 text-white"
              data-testid="start-scoring-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Start Scoring
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="epics" className="space-y-4">
          <TabsList>
            <TabsTrigger value="epics" data-testid="tab-epics">
              <Layers className="w-4 h-4 mr-2" />
              Epics ({scoredEpics.length})
            </TabsTrigger>
            <TabsTrigger value="stories" data-testid="tab-stories">
              <BookOpen className="w-4 h-4 mr-2" />
              Standalone Stories ({scoredStories.length})
            </TabsTrigger>
            <TabsTrigger value="bugs" data-testid="tab-bugs">
              <Bug className="w-4 h-4 mr-2" />
              Standalone Bugs ({scoredBugs.length})
            </TabsTrigger>
          </TabsList>
          
          {/* Epics Tab */}
          <TabsContent value="epics" className="space-y-3">
            {scoredEpics.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="p-8 text-center text-muted-foreground">
                  No scored epics yet. Click "Initiate Scoring" to get started.
                </CardContent>
              </Card>
            ) : (
              scoredEpics.map((item) => (
                <Card 
                  key={item.item_id} 
                  className="bg-card border-border hover:border-primary/30 transition-colors cursor-pointer"
                  onClick={() => handleViewEpicScores(item.item_id)}
                  data-testid={`epic-card-${item.item_id}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Layers className="w-4 h-4 text-violet-400" />
                          <h3 className="font-medium text-foreground truncate">{item.title}</h3>
                        </div>
                        <p className="text-sm text-muted-foreground truncate">{item.description}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge variant="outline" className="text-xs">
                            {item.children_scored}/{item.children_total} items scored
                          </Badge>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {item.moscow_score && <MoSCoWBadge score={item.moscow_score} />}
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>
          
          {/* Standalone Stories Tab */}
          <TabsContent value="stories" className="space-y-3">
            {scoredStories.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="p-8 text-center text-muted-foreground">
                  No scored standalone stories yet.
                </CardContent>
              </Card>
            ) : (
              scoredStories.map((item) => (
                <Card 
                  key={item.item_id} 
                  className="bg-card border-border hover:border-blue-500/30 transition-colors"
                  data-testid={`story-card-${item.item_id}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <BookOpen className="w-4 h-4 text-blue-400" />
                          <h3 className="font-medium text-foreground truncate">{item.title}</h3>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">{item.description}</p>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {item.rice_total !== null && item.rice_total !== undefined ? (
                          <RICEBadge score={item.rice_total} />
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground">Not scored</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>
          
          {/* Standalone Bugs Tab */}
          <TabsContent value="bugs" className="space-y-3">
            {scoredBugs.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="p-8 text-center text-muted-foreground">
                  No scored standalone bugs yet.
                </CardContent>
              </Card>
            ) : (
              scoredBugs.map((item) => (
                <Card 
                  key={item.item_id} 
                  className="bg-card border-border hover:border-orange-500/30 transition-colors"
                  data-testid={`bug-card-${item.item_id}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Bug className="w-4 h-4 text-orange-400" />
                          <h3 className="font-medium text-foreground truncate">{item.title}</h3>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">{item.description}</p>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        {item.rice_total !== null && item.rice_total !== undefined ? (
                          <RICEBadge score={item.rice_total} />
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground">Not scored</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>
        </Tabs>
      )}

      {/* Initiate Scoring Dialog */}
      <Dialog open={showInitiateDialog} onOpenChange={setShowInitiateDialog}>
        <DialogContent className="bg-card border-border max-w-md" data-testid="initiate-scoring-dialog">
          <DialogHeader>
            <DialogTitle className="text-foreground flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              Initiate Scoring
            </DialogTitle>
            <DialogDescription>
              Select an item type and choose what you want to score
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Item Type Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Item Type</label>
              <Select value={selectedItemType} onValueChange={setSelectedItemType}>
                <SelectTrigger data-testid="item-type-select">
                  <SelectValue placeholder="Select item type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="epic">
                    <div className="flex items-center gap-2">
                      <Layers className="w-4 h-4 text-violet-400" />
                      Epic (scores Epic + Features + Stories + Bugs)
                    </div>
                  </SelectItem>
                  <SelectItem value="standalone_story">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-blue-400" />
                      Standalone User Story (RICE only)
                    </div>
                  </SelectItem>
                  <SelectItem value="standalone_bug">
                    <div className="flex items-center gap-2">
                      <Bug className="w-4 h-4 text-orange-400" />
                      Standalone Bug (RICE only)
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Item Selection based on type */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Select {selectedItemType === 'epic' ? 'Epic' : selectedItemType === 'standalone_story' ? 'Story' : 'Bug'}
              </label>
              <Select value={selectedItemId} onValueChange={setSelectedItemId}>
                <SelectTrigger data-testid="item-select">
                  <SelectValue placeholder={`Select ${selectedItemType === 'epic' ? 'an epic' : selectedItemType === 'standalone_story' ? 'a story' : 'a bug'}`} />
                </SelectTrigger>
                <SelectContent>
                  {selectedItemType === 'epic' && itemsForScoring.epics.map((epic) => (
                    <SelectItem key={epic.epic_id} value={epic.epic_id}>
                      <div className="flex items-center justify-between w-full">
                        <span className="truncate max-w-[200px]">{epic.title}</span>
                        {epic.has_moscow && <Badge variant="outline" className="ml-2 text-xs">Has MoSCoW</Badge>}
                      </div>
                    </SelectItem>
                  ))}
                  {selectedItemType === 'standalone_story' && itemsForScoring.standalone_stories.map((story) => (
                    <SelectItem key={story.story_id} value={story.story_id}>
                      <div className="flex items-center justify-between w-full">
                        <span className="truncate max-w-[200px]">{story.title}</span>
                        {story.has_rice && <Badge variant="outline" className="ml-2 text-xs">Scored</Badge>}
                      </div>
                    </SelectItem>
                  ))}
                  {selectedItemType === 'standalone_bug' && itemsForScoring.standalone_bugs.map((bug) => (
                    <SelectItem key={bug.bug_id} value={bug.bug_id}>
                      <div className="flex items-center justify-between w-full">
                        <span className="truncate max-w-[200px]">{bug.title}</span>
                        {bug.has_rice && <Badge variant="outline" className="ml-2 text-xs">Scored</Badge>}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {/* Empty state for each type */}
              {selectedItemType === 'epic' && itemsForScoring.epics.length === 0 && (
                <p className="text-sm text-muted-foreground mt-2">
                  No locked epics available. Create and lock an epic first.
                </p>
              )}
              {selectedItemType === 'standalone_story' && itemsForScoring.standalone_stories.length === 0 && (
                <p className="text-sm text-muted-foreground mt-2">
                  No standalone stories available. Create a standalone story first.
                </p>
              )}
              {selectedItemType === 'standalone_bug' && itemsForScoring.standalone_bugs.length === 0 && (
                <p className="text-sm text-muted-foreground mt-2">
                  No standalone bugs available. Create a standalone bug first.
                </p>
              )}
            </div>

            {/* Info about scoring */}
            <Card className="bg-muted/50 border-0">
              <CardContent className="p-3">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-muted-foreground">
                    {selectedItemType === 'epic' ? (
                      <>
                        <strong>Epic scoring includes:</strong>
                        <ul className="mt-1 space-y-0.5">
                          <li>• Epic: MoSCoW prioritization</li>
                          <li>• Features: MoSCoW + RICE</li>
                          <li>• User Stories: RICE only</li>
                          <li>• Bugs: RICE only</li>
                        </ul>
                      </>
                    ) : (
                      <>
                        <strong>Standalone items use RICE scoring:</strong>
                        <ul className="mt-1 space-y-0.5">
                          <li>• Reach: Users affected (1-10)</li>
                          <li>• Impact: Per-user impact (0.25-3)</li>
                          <li>• Confidence: Estimate certainty (0.5-1.0)</li>
                          <li>• Effort: Person-months (0.5-10)</li>
                        </ul>
                      </>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInitiateDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleInitiateScoring}
              disabled={!selectedItemId}
              className="bg-violet-500 hover:bg-violet-600"
              data-testid="start-scoring-dialog-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Start AI Scoring
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Scoring;
