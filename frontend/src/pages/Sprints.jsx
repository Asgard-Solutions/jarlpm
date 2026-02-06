import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { sprintAPI, deliveryRealityAPI, storyAPI } from '@/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  Calendar,
  Clock,
  Target,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Play,
  Pause,
  MoreVertical,
  RefreshCw,
  Sparkles,
  Zap,
  TrendingUp,
  TrendingDown,
  ListChecks,
  Users,
  Flag,
  MessageSquare,
  Lightbulb,
  ArrowRight,
  Plus,
  Ban,
  ChevronRight,
  Copy,
} from 'lucide-react';

const STATUS_CONFIG = {
  backlog: {
    label: 'Backlog',
    color: 'bg-gray-500/10 text-gray-600 border-gray-500/20',
    bgColor: 'bg-gray-500/5',
    icon: ListChecks,
  },
  ready: {
    label: 'Ready',
    color: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    bgColor: 'bg-blue-500/5',
    icon: Flag,
  },
  in_progress: {
    label: 'In Progress',
    color: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
    bgColor: 'bg-amber-500/5',
    icon: Play,
  },
  done: {
    label: 'Done',
    color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
    bgColor: 'bg-emerald-500/5',
    icon: CheckCircle2,
  },
  blocked: {
    label: 'Blocked',
    color: 'bg-red-500/10 text-red-600 border-red-500/20',
    bgColor: 'bg-red-500/5',
    icon: Ban,
  },
};

const Sprints = () => {
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [sprintData, setSprintData] = useState(null);
  
  // Dialog states
  const [showBlockedDialog, setShowBlockedDialog] = useState(false);
  const [selectedStory, setSelectedStory] = useState(null);
  const [blockedReason, setBlockedReason] = useState('');
  const [statusUpdating, setStatusUpdating] = useState(false);
  
  // AI states
  const [kickoffPlan, setKickoffPlan] = useState(null);
  const [standupSummary, setStandupSummary] = useState(null);
  const [wipSuggestions, setWipSuggestions] = useState(null);
  const [aiLoading, setAiLoading] = useState({
    kickoff: false,
    standup: false,
    wip: false,
  });

  const fetchSprintData = async () => {
    try {
      setLoading(true);
      const response = await sprintAPI.getCurrentSprint();
      setSprintData(response.data);
      
      // Also load any saved AI insights
      try {
        const insightsResponse = await sprintAPI.getSavedInsights();
        const insights = insightsResponse.data;
        
        // Load saved insights into state
        if (insights.kickoff_plan?.content) {
          setKickoffPlan(insights.kickoff_plan.content);
        }
        if (insights.standup_summary?.content) {
          setStandupSummary(insights.standup_summary.content);
        }
        if (insights.wip_suggestions?.content) {
          setWipSuggestions(insights.wip_suggestions.content);
        }
      } catch (insightError) {
        // Insights are optional - don't fail if they're not available
        console.log('No saved insights found:', insightError);
      }
    } catch (error) {
      console.error('Failed to fetch sprint data:', error);
      toast.error('Failed to load sprint data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSprintData();
  }, []);

  const updateStoryStatus = async (storyId, newStatus, reason = null) => {
    try {
      setStatusUpdating(true);
      await sprintAPI.updateStoryStatus(storyId, newStatus, reason);
      toast.success(`Story moved to ${STATUS_CONFIG[newStatus]?.label || newStatus}`);
      await fetchSprintData();
    } catch (error) {
      console.error('Failed to update status:', error);
      toast.error('Failed to update story status');
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleStatusChange = (story, newStatus) => {
    if (newStatus === 'blocked') {
      setSelectedStory(story);
      setBlockedReason(story.blocked_reason || '');
      setShowBlockedDialog(true);
    } else {
      updateStoryStatus(story.story_id, newStatus);
    }
  };

  const confirmBlocked = () => {
    if (selectedStory) {
      updateStoryStatus(selectedStory.story_id, 'blocked', blockedReason);
      setShowBlockedDialog(false);
      setSelectedStory(null);
      setBlockedReason('');
    }
  };

  // AI handlers
  const generateKickoff = async () => {
    try {
      setAiLoading(prev => ({ ...prev, kickoff: true }));
      const response = await sprintAPI.generateKickoffPlan();
      setKickoffPlan(response.data);
      toast.success('Kickoff plan generated');
    } catch (error) {
      console.error('Failed to generate kickoff:', error);
      const msg = error.response?.data?.detail || 'Failed to generate kickoff plan';
      toast.error(msg);
    } finally {
      setAiLoading(prev => ({ ...prev, kickoff: false }));
    }
  };

  const generateStandup = async () => {
    try {
      setAiLoading(prev => ({ ...prev, standup: true }));
      const response = await sprintAPI.generateStandupSummary();
      setStandupSummary(response.data);
      toast.success('Standup summary generated');
    } catch (error) {
      console.error('Failed to generate standup:', error);
      const msg = error.response?.data?.detail || 'Failed to generate standup summary';
      toast.error(msg);
    } finally {
      setAiLoading(prev => ({ ...prev, standup: false }));
    }
  };

  const generateWip = async () => {
    try {
      setAiLoading(prev => ({ ...prev, wip: true }));
      const response = await sprintAPI.generateWipSuggestions();
      setWipSuggestions(response.data);
      toast.success('WIP suggestions generated');
    } catch (error) {
      console.error('Failed to generate WIP suggestions:', error);
      const msg = error.response?.data?.detail || 'Failed to generate WIP suggestions';
      toast.error(msg);
    } finally {
      setAiLoading(prev => ({ ...prev, wip: false }));
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="sprints-loading">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const sprintInfo = sprintData?.sprint_info;
  const capacity = sprintData?.capacity;
  const storiesByStatus = sprintData?.stories_by_status || {};
  const blockedStories = sprintData?.blocked_stories || [];

  const totalStories = Object.values(storiesByStatus).flat().length;
  const inProgressCount = storiesByStatus.in_progress?.length || 0;
  const wipLimit = capacity ? Math.floor(capacity.sprint_capacity / 5) + 1 : 3;
  const isWipHigh = inProgressCount > wipLimit;

  return (
    <div className="space-y-6" data-testid="sprints-page">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Calendar className="h-6 w-6 text-primary" />
            Sprints
          </h1>
          <p className="text-muted-foreground">
            Track sprint progress and manage your team&apos;s work
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={fetchSprintData} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button 
            variant="outline" 
            onClick={() => navigate('/delivery-reality')}
            className="gap-2"
          >
            <Target className="h-4 w-4" />
            Delivery Reality
          </Button>
        </div>
      </div>

      {/* Sprint Info */}
      {!sprintInfo ? (
        <Card className="bg-amber-500/5 border-amber-500/20">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-amber-600" />
              <div>
                <p className="font-medium text-amber-600">Sprint not configured</p>
                <p className="text-sm text-muted-foreground">
                  Set your sprint start date in Settings → Delivery Context to enable sprint tracking.
                </p>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => navigate('/settings')}
                className="ml-auto"
              >
                Configure
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Sprint Header Card */}
          <Card>
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="h-14 w-14 rounded-xl bg-primary/10 flex items-center justify-center">
                    <span className="text-2xl font-bold text-primary">{sprintInfo.sprint_number}</span>
                  </div>
                  <div>
                    <h2 className="text-xl font-bold">Sprint {sprintInfo.sprint_number}</h2>
                    <p className="text-sm text-muted-foreground">
                      {new Date(sprintInfo.start_date).toLocaleDateString()} - {new Date(sprintInfo.end_date).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="h-4 w-4" />
                      <span className="text-sm">Days Left</span>
                    </div>
                    <p className="text-2xl font-bold">{sprintInfo.days_remaining}</p>
                  </div>
                  
                  <div className="w-32">
                    <p className="text-sm text-muted-foreground mb-1">Progress</p>
                    <Progress value={sprintInfo.progress} className="h-2" />
                    <p className="text-xs text-right text-muted-foreground mt-1">{sprintInfo.progress}%</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Capacity + Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {/* Capacity Meter */}
            {capacity && (
              <Card className={capacity.is_overloaded ? 'border-red-500/30 bg-red-500/5' : ''}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                    <Target className="h-4 w-4" />
                    Capacity
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold">{capacity.committed_points}</span>
                    <span className="text-muted-foreground">/ {capacity.sprint_capacity}</span>
                  </div>
                  <Badge 
                    variant="outline" 
                    className={`mt-2 ${capacity.is_overloaded 
                      ? 'bg-red-500/10 text-red-600 border-red-500/30' 
                      : 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'}`}
                  >
                    {capacity.is_overloaded ? (
                      <><TrendingUp className="h-3 w-3 mr-1" /> Over by {Math.abs(capacity.delta)}</>
                    ) : (
                      <><TrendingDown className="h-3 w-3 mr-1" /> {capacity.delta} buffer</>
                    )}
                  </Badge>
                </CardContent>
              </Card>
            )}
            
            {/* Story Counts */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-gray-600 text-sm">
                  <ListChecks className="h-4 w-4" />
                  Backlog
                </div>
                <div className="text-2xl font-bold mt-1">{storiesByStatus.backlog?.length || 0}</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-blue-600 text-sm">
                  <Flag className="h-4 w-4" />
                  Ready
                </div>
                <div className="text-2xl font-bold mt-1">{storiesByStatus.ready?.length || 0}</div>
              </CardContent>
            </Card>
            
            <Card className={isWipHigh ? 'border-amber-500/30 bg-amber-500/5' : ''}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-amber-600 text-sm">
                  <Play className="h-4 w-4" />
                  In Progress
                </div>
                <div className="text-2xl font-bold mt-1">{inProgressCount}</div>
                {isWipHigh && (
                  <Badge variant="outline" className="mt-1 bg-amber-500/10 text-amber-600 border-amber-500/30 text-xs">
                    High WIP
                  </Badge>
                )}
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-emerald-600 text-sm">
                  <CheckCircle2 className="h-4 w-4" />
                  Done
                </div>
                <div className="text-2xl font-bold mt-1">{storiesByStatus.done?.length || 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {sprintData?.completed_points || 0} / {sprintData?.total_points || 0} pts
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Blocked Stories Alert */}
          {blockedStories.length > 0 && (
            <Card className="border-red-500/30 bg-red-500/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-5 w-5" />
                  Blocked Stories ({blockedStories.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {blockedStories.map((story) => (
                    <div 
                      key={story.story_id}
                      className="flex items-center justify-between p-3 bg-background rounded-lg"
                    >
                      <div>
                        <p className="font-medium">{story.title}</p>
                        <p className="text-sm text-red-600">{story.blocked_reason || 'No reason provided'}</p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleStatusChange(story, 'in_progress')}
                      >
                        Unblock
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Kanban Board */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {['ready', 'in_progress', 'blocked', 'done'].map((status) => {
              const config = STATUS_CONFIG[status];
              const stories = storiesByStatus[status] || [];
              const Icon = config.icon;
              
              return (
                <Card key={status} className={config.bgColor}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Icon className={`h-4 w-4 ${config.color.split(' ')[1]}`} />
                        {config.label}
                      </span>
                      <Badge variant="secondary">{stories.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {stories.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">No stories</p>
                    ) : (
                      stories.map((story) => (
                        <Card 
                          key={story.story_id}
                          className="bg-background cursor-pointer hover:border-primary/30 transition-colors"
                        >
                          <CardContent className="p-3">
                            <div className="flex items-start justify-between">
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-sm truncate">{story.title}</p>
                                <div className="flex items-center gap-2 mt-1">
                                  {story.story_points && (
                                    <Badge variant="outline" className="text-xs">
                                      {story.story_points} pts
                                    </Badge>
                                  )}
                                  {story.blocked_reason && status === 'blocked' && (
                                    <Badge variant="outline" className="text-xs bg-red-500/10 text-red-600 border-red-500/30">
                                      Blocked
                                    </Badge>
                                  )}
                                </div>
                              </div>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreVertical className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  {status !== 'ready' && (
                                    <DropdownMenuItem onClick={() => handleStatusChange(story, 'ready')}>
                                      <Flag className="h-4 w-4 mr-2" />
                                      Move to Ready
                                    </DropdownMenuItem>
                                  )}
                                  {status !== 'in_progress' && (
                                    <DropdownMenuItem onClick={() => handleStatusChange(story, 'in_progress')}>
                                      <Play className="h-4 w-4 mr-2" />
                                      Move to In Progress
                                    </DropdownMenuItem>
                                  )}
                                  {status !== 'blocked' && (
                                    <DropdownMenuItem onClick={() => handleStatusChange(story, 'blocked')}>
                                      <Ban className="h-4 w-4 mr-2" />
                                      Mark Blocked
                                    </DropdownMenuItem>
                                  )}
                                  {status !== 'done' && (
                                    <DropdownMenuItem onClick={() => handleStatusChange(story, 'done')}>
                                      <CheckCircle2 className="h-4 w-4 mr-2" />
                                      Mark Done
                                    </DropdownMenuItem>
                                  )}
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </CardContent>
                        </Card>
                      ))
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* AI Features Section */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-violet-500" />
                AI-Powered Sprint Insights
                <Badge variant="outline" className="text-xs">Uses your LLM</Badge>
              </CardTitle>
              <CardDescription>
                Get AI help with sprint planning, standups, and WIP management
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="kickoff" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="kickoff" className="gap-1">
                    <Zap className="h-3 w-3" />
                    Kickoff
                  </TabsTrigger>
                  <TabsTrigger value="standup" className="gap-1">
                    <MessageSquare className="h-3 w-3" />
                    Standup
                  </TabsTrigger>
                  <TabsTrigger value="wip" className="gap-1">
                    <Lightbulb className="h-3 w-3" />
                    WIP Tips
                  </TabsTrigger>
                </TabsList>
                
                {/* Kickoff Tab */}
                <TabsContent value="kickoff" className="space-y-4 mt-4">
                  {kickoffPlan ? (
                    <div className="space-y-4">
                      <div className="p-4 bg-violet-500/5 rounded-lg border border-violet-500/20">
                        <p className="text-xs font-medium text-violet-600 mb-1">Sprint Goal</p>
                        <p className="font-medium">{kickoffPlan.sprint_goal}</p>
                      </div>
                      
                      <div>
                        <p className="text-sm font-medium mb-2">Top Priority Stories</p>
                        <div className="space-y-2">
                          {kickoffPlan.top_stories?.map((story, i) => (
                            <div key={i} className="flex items-start gap-2 p-2 bg-muted/50 rounded">
                              <span className="font-bold text-primary">{i + 1}.</span>
                              <div>
                                <p className="font-medium">{story.title}</p>
                                <p className="text-xs text-muted-foreground">{story.reason}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      <div>
                        <p className="text-sm font-medium mb-2">Sequencing</p>
                        <ul className="space-y-1">
                          {kickoffPlan.sequencing?.map((step, i) => (
                            <li key={i} className="text-sm flex items-start gap-2">
                              <ArrowRight className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                              {step}
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      <div>
                        <p className="text-sm font-medium mb-2">Risks</p>
                        <ul className="space-y-1">
                          {kickoffPlan.risks?.map((risk, i) => (
                            <li key={i} className="text-sm flex items-start gap-2">
                              <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                              {risk}
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => copyToClipboard(
                          `Sprint Goal: ${kickoffPlan.sprint_goal}\n\n` +
                          `Top Stories:\n${kickoffPlan.top_stories?.map((s, i) => `${i+1}. ${s.title}`).join('\n')}\n\n` +
                          `Sequencing:\n${kickoffPlan.sequencing?.map(s => `- ${s}`).join('\n')}`
                        )}
                        className="gap-1"
                      >
                        <Copy className="h-3 w-3" />
                        Copy
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Zap className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                      <p className="text-muted-foreground mb-4">
                        Generate a sprint kickoff plan with goal, priorities, and sequencing
                      </p>
                      <Button 
                        onClick={generateKickoff}
                        disabled={aiLoading.kickoff || totalStories === 0}
                        className="gap-2"
                      >
                        {aiLoading.kickoff ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Generate Kickoff Plan
                      </Button>
                      {totalStories === 0 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          No stories committed to this sprint
                        </p>
                      )}
                    </div>
                  )}
                </TabsContent>
                
                {/* Standup Tab */}
                <TabsContent value="standup" className="space-y-4 mt-4">
                  {standupSummary ? (
                    <div className="space-y-4">
                      <div className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/20">
                        <p className="font-medium">{standupSummary.summary}</p>
                      </div>
                      
                      <div>
                        <p className="text-sm font-medium mb-2 text-emerald-600">What Changed</p>
                        <ul className="space-y-1">
                          {standupSummary.what_changed?.map((item, i) => (
                            <li key={i} className="text-sm flex items-start gap-2">
                              <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      {standupSummary.whats_blocked?.length > 0 && (
                        <div>
                          <p className="text-sm font-medium mb-2 text-red-600">Blocked</p>
                          <ul className="space-y-1">
                            {standupSummary.whats_blocked.map((item, i) => (
                              <li key={i} className="text-sm flex items-start gap-2">
                                <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      <div>
                        <p className="text-sm font-medium mb-2 text-blue-600">Next Actions</p>
                        <ul className="space-y-1">
                          {standupSummary.what_to_do_next?.map((item, i) => (
                            <li key={i} className="text-sm flex items-start gap-2">
                              <ArrowRight className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => copyToClipboard(
                          `${standupSummary.summary}\n\n` +
                          `✓ What Changed:\n${standupSummary.what_changed?.map(s => `- ${s}`).join('\n')}\n\n` +
                          `🚫 Blocked:\n${standupSummary.whats_blocked?.map(s => `- ${s}`).join('\n') || 'None'}\n\n` +
                          `→ Next:\n${standupSummary.what_to_do_next?.map(s => `- ${s}`).join('\n')}`
                        )}
                        className="gap-1"
                      >
                        <Copy className="h-3 w-3" />
                        Copy for Slack
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <MessageSquare className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                      <p className="text-muted-foreground mb-4">
                        Generate a quick standup summary: what changed, blocked, next steps
                      </p>
                      <Button 
                        onClick={generateStandup}
                        disabled={aiLoading.standup || totalStories === 0}
                        className="gap-2"
                      >
                        {aiLoading.standup ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Generate Standup Summary
                      </Button>
                    </div>
                  )}
                </TabsContent>
                
                {/* WIP Tab */}
                <TabsContent value="wip" className="space-y-4 mt-4">
                  {wipSuggestions ? (
                    <div className="space-y-4">
                      <div className="p-3 bg-muted rounded-lg">
                        <p className="text-sm">{wipSuggestions.reasoning}</p>
                      </div>
                      
                      {wipSuggestions.finish_first?.length > 0 && (
                        <div>
                          <p className="text-sm font-medium mb-2 text-emerald-600">Finish First</p>
                          {wipSuggestions.finish_first.map((item, i) => (
                            <div key={i} className="p-2 bg-emerald-500/5 rounded mb-2">
                              <p className="font-medium text-sm">{item.title}</p>
                              <p className="text-xs text-muted-foreground">{item.reason}</p>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {wipSuggestions.consider_pausing?.length > 0 && (
                        <div>
                          <p className="text-sm font-medium mb-2 text-amber-600">Consider Pausing</p>
                          {wipSuggestions.consider_pausing.map((item, i) => (
                            <div key={i} className="p-2 bg-amber-500/5 rounded mb-2">
                              <p className="font-medium text-sm">{item.title}</p>
                              <p className="text-xs text-muted-foreground">{item.reason}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Lightbulb className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                      <p className="text-muted-foreground mb-4">
                        Get suggestions on what to focus on when WIP is high
                      </p>
                      <Button 
                        onClick={generateWip}
                        disabled={aiLoading.wip || inProgressCount < 2}
                        className="gap-2"
                      >
                        {aiLoading.wip ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Get WIP Suggestions
                      </Button>
                      {inProgressCount < 2 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          WIP is healthy - less than 2 stories in progress
                        </p>
                      )}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </>
      )}

      {/* Blocked Dialog */}
      <Dialog open={showBlockedDialog} onOpenChange={setShowBlockedDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Ban className="h-5 w-5 text-red-500" />
              Mark Story as Blocked
            </DialogTitle>
            <DialogDescription>
              {selectedStory?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">What&apos;s blocking this story?</label>
              <Textarea
                placeholder="Describe the blocker..."
                value={blockedReason}
                onChange={(e) => setBlockedReason(e.target.value)}
                className="mt-2"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBlockedDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={confirmBlocked}
              disabled={statusUpdating}
              className="bg-red-500 hover:bg-red-600"
            >
              {statusUpdating ? (
                <RefreshCw className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Mark Blocked
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Sprints;
