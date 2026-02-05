import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, Gauge, ArrowUpDown, Filter, ExternalLink, Sparkles, Check } from 'lucide-react';
import { MoSCoWBadge, RICEBadge } from '@/components/ScoringComponents';
import { epicAPI, featureAPI, storyAPI, scoringAPI } from '@/api';
import { toast } from 'sonner';

const Scoring = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [allSuggestions, setAllSuggestions] = useState(null);
  const [epics, setEpics] = useState([]);
  const [features, setFeatures] = useState([]);
  const [stories, setStories] = useState([]);
  const [selectedEpic, setSelectedEpic] = useState('all');
  const [sortBy, setSortBy] = useState('rice_desc');
  const [filterMoscow, setFilterMoscow] = useState('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [epicsRes, storiesRes] = await Promise.all([
        epicAPI.list(),
        storyAPI.getAllStories(),
      ]);
      
      setEpics(epicsRes.data?.epics || epicsRes.data || []);
      setStories(storiesRes.data || []);
      
      // Load features for all epics
      const allFeatures = [];
      const epicsList = epicsRes.data?.epics || epicsRes.data || [];
      for (const epic of epicsList) {
        try {
          const featuresRes = await featureAPI.getFeatures(epic.epic_id);
          allFeatures.push(...(featuresRes.data || []));
        } catch (e) {
          console.error(`Failed to load features for epic ${epic.epic_id}`);
        }
      }
      setFeatures(allFeatures);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAIGenerate = async () => {
    if (selectedEpic === 'all') {
      toast.error('Please select a specific epic to generate scores');
      return;
    }
    
    setGenerating(true);
    setAllSuggestions(null);
    try {
      const response = await scoringAPI.bulkScoreAll(selectedEpic);
      setAllSuggestions(response.data);
      const total = (response.data.feature_suggestions?.length || 0) + 
                    (response.data.story_suggestions?.length || 0) + 
                    (response.data.bug_suggestions?.length || 0);
      toast.success(`Generated scores for ${total} items (${response.data.feature_suggestions?.length || 0} features, ${response.data.story_suggestions?.length || 0} stories, ${response.data.bug_suggestions?.length || 0} bugs)`);
    } catch (error) {
      console.error('Failed to generate scores:', error);
      const message = error.response?.data?.detail || 'Failed to generate scores';
      toast.error(message);
    } finally {
      setGenerating(false);
    }
  };

  const handleApplyScores = async () => {
    if (!allSuggestions) return;
    
    setApplying(true);
    try {
      const response = await scoringAPI.applyAllScores(selectedEpic, allSuggestions);
      toast.success(`Applied scores: ${response.data.applied.features} features, ${response.data.applied.stories} stories, ${response.data.applied.bugs} bugs`);
      setAllSuggestions(null);
      await loadData(); // Reload to show updated scores
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

  const filterAndSort = (items) => {
    let filtered = items;
    
    // Filter by epic
    if (selectedEpic !== 'all') {
      filtered = filtered.filter(item => item.epic_id === selectedEpic);
    }
    
    // Filter by MoSCoW
    if (filterMoscow !== 'all') {
      filtered = filtered.filter(item => item.moscow_score === filterMoscow);
    }
    
    // Sort
    return filtered.sort((a, b) => {
      switch (sortBy) {
        case 'rice_desc':
          return (b.rice_total || 0) - (a.rice_total || 0);
        case 'rice_asc':
          return (a.rice_total || 0) - (b.rice_total || 0);
        case 'moscow':
          const moscowOrder = { must_have: 0, should_have: 1, could_have: 2, wont_have: 3 };
          return (moscowOrder[a.moscow_score] ?? 4) - (moscowOrder[b.moscow_score] ?? 4);
        default:
          return 0;
      }
    });
  };

  const getEpicTitle = (epicId) => {
    const epic = epics.find(e => e.epic_id === epicId);
    return epic?.title || 'Unknown Epic';
  };

  const renderScoringTable = (items, type) => {
    const sorted = filterAndSort(items);
    
    if (sorted.length === 0) {
      return (
        <div className="text-center py-12 text-muted-foreground">
          No {type} found with scoring data
        </div>
      );
    }

    return (
      <div className="space-y-3">
        {sorted.map((item) => (
          <Card 
            key={item.feature_id || item.story_id} 
            className="bg-card border-border hover:border-primary/30 transition-colors cursor-pointer"
            onClick={() => {
              if (type === 'features') {
                navigate(`/epic/${item.epic_id}`);
              } else {
                navigate(`/stories`);
              }
            }}
          >
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium text-foreground truncate">
                      {item.title}
                    </h3>
                    <ExternalLink className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                  </div>
                  <p className="text-sm text-muted-foreground truncate">
                    {getEpicTitle(item.epic_id)}
                  </p>
                </div>
                <div className="flex items-center gap-3 ml-4">
                  {item.moscow_score && (
                    <MoSCoWBadge score={item.moscow_score} />
                  )}
                  {item.rice_total !== null && item.rice_total !== undefined && (
                    <RICEBadge score={item.rice_total} />
                  )}
                  {!item.moscow_score && !item.rice_total && (
                    <Badge variant="outline" className="text-muted-foreground">
                      Not scored
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  const scoredFeatures = features.filter(f => f.moscow_score || f.rice_total);
  const scoredStories = stories.filter(s => s.moscow_score || s.rice_total);
  const unscoredFeatures = features.filter(f => !f.moscow_score && !f.rice_total);
  const unscoredStories = stories.filter(s => !s.moscow_score && !s.rice_total);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Scoring</h1>
          <p className="text-muted-foreground mt-1">MoSCoW prioritization and RICE scoring</p>
        </div>
        <div className="flex gap-2">
          {getTotalSuggestions() > 0 && (
            <Button 
              onClick={handleApplyScores} 
              disabled={applying}
              variant="outline"
              className="border-green-500 text-green-500 hover:bg-green-500/10"
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
            onClick={handleAIGenerate} 
            disabled={generating || selectedEpic === 'all'}
            className="bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 text-white"
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

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/10 rounded-lg">
                <Gauge className="h-5 w-5 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{scoredFeatures.length}</p>
                <p className="text-sm text-muted-foreground">Scored Features</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <Gauge className="h-5 w-5 text-blue-500" />
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
              <div className="p-2 bg-yellow-500/10 rounded-lg">
                <Gauge className="h-5 w-5 text-yellow-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{unscoredFeatures.length}</p>
                <p className="text-sm text-muted-foreground">Unscored Features</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-500/10 rounded-lg">
                <Gauge className="h-5 w-5 text-orange-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">{unscoredStories.length}</p>
                <p className="text-sm text-muted-foreground">Unscored Stories</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-card border-border">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-foreground">Filters:</span>
            </div>
            <Select value={selectedEpic} onValueChange={setSelectedEpic}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="All Epics" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Epics</SelectItem>
                {epics.map((epic) => (
                  <SelectItem key={epic.epic_id} value={epic.epic_id}>
                    {epic.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterMoscow} onValueChange={setFilterMoscow}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="All MoSCoW" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All MoSCoW</SelectItem>
                <SelectItem value="must_have">Must Have</SelectItem>
                <SelectItem value="should_have">Should Have</SelectItem>
                <SelectItem value="could_have">Could Have</SelectItem>
                <SelectItem value="wont_have">Won't Have</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="rice_desc">RICE (High → Low)</SelectItem>
                <SelectItem value="rice_asc">RICE (Low → High)</SelectItem>
                <SelectItem value="moscow">MoSCoW Priority</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* AI Suggestions Preview */}
      {suggestions.length > 0 && (
        <Card className="bg-violet-500/5 border-violet-500/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-violet-500" />
              AI-Generated Scores (Review before applying)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {suggestions.map((s) => (
                <div key={s.feature_id} className="flex items-center justify-between p-3 bg-background rounded-lg border">
                  <span className="font-medium">{s.title}</span>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="bg-red-500/10 text-red-400 border-red-500/30">
                      {s.moscow?.score?.replace('_', ' ')}
                    </Badge>
                    <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30">
                      RICE: {s.rice?.reach && s.rice?.impact && s.rice?.confidence && s.rice?.effort 
                        ? ((s.rice.reach * s.rice.impact * s.rice.confidence) / s.rice.effort).toFixed(1)
                        : 'N/A'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
        </div>
      ) : (
        <Tabs defaultValue="features" className="space-y-4">
          <TabsList>
            <TabsTrigger value="features">
              Features ({features.length})
            </TabsTrigger>
            <TabsTrigger value="stories">
              Stories ({stories.length})
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="features">
            {renderScoringTable(features, 'features')}
          </TabsContent>
          
          <TabsContent value="stories">
            {renderScoringTable(stories, 'stories')}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
};

export default Scoring;
