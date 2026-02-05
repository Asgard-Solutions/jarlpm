import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { 
  Loader2, Calendar, Play, CheckCircle2, Clock, AlertCircle,
  ChevronRight, Plus, ArrowRight
} from 'lucide-react';
import { epicAPI, storyAPI, deliveryContextAPI } from '@/api';

const STATUS_COLORS = {
  draft: 'bg-gray-500/10 text-gray-500 border-gray-500/30',
  ready: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
  in_progress: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30',
  done: 'bg-green-500/10 text-green-500 border-green-500/30',
  blocked: 'bg-red-500/10 text-red-500 border-red-500/30',
};

const Sprints = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [stories, setStories] = useState([]);
  const [epics, setEpics] = useState([]);
  const [deliveryContext, setDeliveryContext] = useState(null);
  const [selectedSprint, setSelectedSprint] = useState('current');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [storiesRes, epicsRes, contextRes] = await Promise.all([
        storyAPI.getAllStories(),
        epicAPI.list(),
        deliveryContextAPI.get(),
      ]);
      
      setStories(storiesRes.data || []);
      setEpics(epicsRes.data || []);
      setDeliveryContext(contextRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSprintInfo = () => {
    if (!deliveryContext?.sprint_cycle_length || !deliveryContext?.sprint_start_date) {
      return null;
    }
    
    const startDate = new Date(deliveryContext.sprint_start_date);
    const cycleLength = deliveryContext.sprint_cycle_length;
    const today = new Date();
    
    // Calculate current sprint number
    const daysSinceStart = Math.floor((today - startDate) / (1000 * 60 * 60 * 24));
    const currentSprintNum = Math.floor(daysSinceStart / cycleLength) + 1;
    
    // Calculate current sprint dates
    const currentSprintStart = new Date(startDate);
    currentSprintStart.setDate(startDate.getDate() + (currentSprintNum - 1) * cycleLength);
    const currentSprintEnd = new Date(currentSprintStart);
    currentSprintEnd.setDate(currentSprintStart.getDate() + cycleLength - 1);
    
    // Days remaining
    const daysRemaining = Math.ceil((currentSprintEnd - today) / (1000 * 60 * 60 * 24));
    const progress = Math.round(((cycleLength - daysRemaining) / cycleLength) * 100);
    
    return {
      sprintNumber: currentSprintNum,
      startDate: currentSprintStart,
      endDate: currentSprintEnd,
      daysRemaining: Math.max(0, daysRemaining),
      progress: Math.min(100, Math.max(0, progress)),
      cycleLength,
    };
  };

  const sprintInfo = getSprintInfo();

  const formatDate = (date) => {
    return new Date(date).toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric' 
    });
  };

  const getEpicTitle = (epicId) => {
    const epic = epics.find(e => e.epic_id === epicId);
    return epic?.title || 'Unknown Epic';
  };

  // Group stories by status
  const groupedStories = {
    backlog: stories.filter(s => s.status === 'draft' || !s.status),
    ready: stories.filter(s => s.status === 'ready'),
    in_progress: stories.filter(s => s.status === 'in_progress'),
    done: stories.filter(s => s.status === 'done'),
  };

  const totalPoints = stories.reduce((sum, s) => sum + (s.story_points || 0), 0);
  const completedPoints = groupedStories.done.reduce((sum, s) => sum + (s.story_points || 0), 0);

  if (loading) {
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
          <h1 className="text-3xl font-bold text-foreground">Sprints</h1>
          <p className="text-muted-foreground mt-1">Plan and track sprint progress</p>
        </div>
        <Button onClick={() => navigate('/settings')} variant="outline">
          <Calendar className="h-4 w-4 mr-2" />
          Configure Sprints
        </Button>
      </div>

      {/* Sprint Info Card */}
      {sprintInfo ? (
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-foreground">
                  Sprint {sprintInfo.sprintNumber}
                </h2>
                <p className="text-muted-foreground">
                  {formatDate(sprintInfo.startDate)} - {formatDate(sprintInfo.endDate)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-primary">{sprintInfo.daysRemaining}</p>
                <p className="text-sm text-muted-foreground">days remaining</p>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Sprint Progress</span>
                <span className="text-foreground font-medium">{sprintInfo.progress}%</span>
              </div>
              <Progress value={sprintInfo.progress} className="h-2" />
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-card border-border">
          <CardContent className="p-6 text-center">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">Sprint Not Configured</h3>
            <p className="text-muted-foreground mb-4">
              Set up your sprint cycle in Settings to enable sprint tracking.
            </p>
            <Button onClick={() => navigate('/settings')}>
              Configure Sprint Settings
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="bg-card border-border">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-foreground">{stories.length}</p>
            <p className="text-sm text-muted-foreground">Total Stories</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-gray-500">{groupedStories.backlog.length}</p>
            <p className="text-sm text-muted-foreground">Backlog</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-blue-500">{groupedStories.ready.length}</p>
            <p className="text-sm text-muted-foreground">Ready</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-yellow-500">{groupedStories.in_progress.length}</p>
            <p className="text-sm text-muted-foreground">In Progress</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-green-500">{groupedStories.done.length}</p>
            <p className="text-sm text-muted-foreground">Done</p>
          </CardContent>
        </Card>
      </div>

      {/* Story Points Progress */}
      {totalPoints > 0 && (
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-foreground">Story Points Completed</span>
              <span className="text-sm text-muted-foreground">
                {completedPoints} / {totalPoints} points
              </span>
            </div>
            <Progress value={(completedPoints / totalPoints) * 100} className="h-2" />
          </CardContent>
        </Card>
      )}

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Backlog Column */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-muted-foreground flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Backlog
            </h3>
            <Badge variant="outline">{groupedStories.backlog.length}</Badge>
          </div>
          <div className="space-y-2 min-h-[200px] p-2 bg-muted/30 rounded-lg">
            {groupedStories.backlog.slice(0, 5).map((story) => (
              <Card 
                key={story.story_id} 
                className="bg-card border-border cursor-pointer hover:border-primary/30"
                onClick={() => navigate('/stories')}
              >
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-foreground line-clamp-2">{story.title}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-muted-foreground truncate max-w-[100px]">
                      {getEpicTitle(story.epic_id)}
                    </span>
                    {story.story_points && (
                      <Badge variant="outline" className="text-xs">
                        {story.story_points} pts
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
            {groupedStories.backlog.length > 5 && (
              <p className="text-xs text-center text-muted-foreground py-2">
                +{groupedStories.backlog.length - 5} more
              </p>
            )}
          </div>
        </div>

        {/* Ready Column */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-blue-500 flex items-center gap-2">
              <Play className="h-4 w-4" />
              Ready
            </h3>
            <Badge variant="outline" className="border-blue-500/30 text-blue-500">
              {groupedStories.ready.length}
            </Badge>
          </div>
          <div className="space-y-2 min-h-[200px] p-2 bg-blue-500/5 rounded-lg">
            {groupedStories.ready.map((story) => (
              <Card 
                key={story.story_id} 
                className="bg-card border-blue-500/20 cursor-pointer hover:border-blue-500/40"
                onClick={() => navigate('/stories')}
              >
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-foreground line-clamp-2">{story.title}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-muted-foreground truncate max-w-[100px]">
                      {getEpicTitle(story.epic_id)}
                    </span>
                    {story.story_points && (
                      <Badge variant="outline" className="text-xs border-blue-500/30">
                        {story.story_points} pts
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* In Progress Column */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-yellow-500 flex items-center gap-2">
              <Loader2 className="h-4 w-4" />
              In Progress
            </h3>
            <Badge variant="outline" className="border-yellow-500/30 text-yellow-500">
              {groupedStories.in_progress.length}
            </Badge>
          </div>
          <div className="space-y-2 min-h-[200px] p-2 bg-yellow-500/5 rounded-lg">
            {groupedStories.in_progress.map((story) => (
              <Card 
                key={story.story_id} 
                className="bg-card border-yellow-500/20 cursor-pointer hover:border-yellow-500/40"
                onClick={() => navigate('/stories')}
              >
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-foreground line-clamp-2">{story.title}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-muted-foreground truncate max-w-[100px]">
                      {getEpicTitle(story.epic_id)}
                    </span>
                    {story.story_points && (
                      <Badge variant="outline" className="text-xs border-yellow-500/30">
                        {story.story_points} pts
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Done Column */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-green-500 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Done
            </h3>
            <Badge variant="outline" className="border-green-500/30 text-green-500">
              {groupedStories.done.length}
            </Badge>
          </div>
          <div className="space-y-2 min-h-[200px] p-2 bg-green-500/5 rounded-lg">
            {groupedStories.done.slice(0, 5).map((story) => (
              <Card 
                key={story.story_id} 
                className="bg-card border-green-500/20 cursor-pointer hover:border-green-500/40"
                onClick={() => navigate('/stories')}
              >
                <CardContent className="p-3">
                  <p className="text-sm font-medium text-foreground line-clamp-2">{story.title}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-muted-foreground truncate max-w-[100px]">
                      {getEpicTitle(story.epic_id)}
                    </span>
                    {story.story_points && (
                      <Badge variant="outline" className="text-xs border-green-500/30">
                        {story.story_points} pts
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
            {groupedStories.done.length > 5 && (
              <p className="text-xs text-center text-muted-foreground py-2">
                +{groupedStories.done.length - 5} more
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sprints;
