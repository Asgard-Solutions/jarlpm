import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI, epicAPI } from '@/api';
import { useAuthStore, useThemeStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import {
  AlertTriangle,
  AlertCircle,
  Target,
  TrendingUp,
  CheckCircle2,
  Clock,
  Sparkles,
  ArrowRight,
  Settings,
  Zap,
  Activity,
  FileText,
  Save,
  Lock,
  Plus,
  Archive,
  RotateCcw,
  Loader2,
  ChevronRight,
  Wrench,
} from 'lucide-react';

const STAGE_LABELS = {
  problem_capture: 'Problem Capture',
  problem_confirmed: 'Problem Confirmed',
  outcome_capture: 'Outcome Capture',
  outcome_confirmed: 'Outcome Confirmed',
  epic_drafted: 'Epic Draft',
  epic_locked: 'Locked',
};

const EVENT_CONFIG = {
  created: { icon: Plus, label: 'Created', color: 'text-blue-600' },
  archived: { icon: Archive, label: 'Archived', color: 'text-muted-foreground' },
  restored: { icon: RotateCcw, label: 'Restored', color: 'text-emerald-600' },
  scope_plan_saved: { icon: Save, label: 'Scope plan saved', color: 'text-purple-600' },
  epic_locked: { icon: Lock, label: 'Locked', color: 'text-emerald-600' },
};

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { theme } = useThemeStore();
  
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [problemInput, setProblemInput] = useState('');
  const [generating, setGenerating] = useState(false);

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const response = await dashboardAPI.getData();
      setData(response.data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const handleCreateEpic = async () => {
    try {
      const response = await epicAPI.create('New Epic');
      navigate(`/epic/${response.data.epic_id}`);
    } catch (error) {
      console.error('Failed to create epic:', error);
      toast.error('Failed to create epic');
    }
  };

  const handleQuickGenerate = async () => {
    if (!problemInput.trim()) {
      toast.error('Please enter a problem statement');
      return;
    }
    
    // Navigate to new initiative page with the problem pre-filled
    navigate('/new', { state: { initialProblem: problemInput.trim() } });
  };

  const formatTimeAgo = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="dashboard-loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const { at_risk_initiatives, focus_list, kpis, recent_activity, has_llm_configured, has_capacity_configured } = data || {};

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Welcome back{user?.name ? `, ${user.name.split(' ')[0]}` : ''}
          </h1>
          <p className="text-muted-foreground">
            Here's what needs your attention today
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCreateEpic} className="gap-2">
            <Plus className="h-4 w-4" />
            Create Epic
          </Button>
          <Button onClick={() => navigate('/new')} className="gap-2">
            <Sparkles className="h-4 w-4" />
            AI Initiative
          </Button>
        </div>
      </div>

      {/* Setup Alerts */}
      {(!has_llm_configured || !has_capacity_configured) && (
        <div className="space-y-3">
          {!has_llm_configured && (
            <Card className="border-amber-500/30 bg-amber-500/5">
              <CardContent className="flex items-center gap-4 py-4">
                <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0" />
                <div className="flex-1">
                  <p className="font-medium">No LLM Provider Configured</p>
                  <p className="text-sm text-muted-foreground">Add your API key to use AI features</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => navigate('/settings')}>
                  <Settings className="h-4 w-4 mr-2" />
                  Configure
                </Button>
              </CardContent>
            </Card>
          )}
          {!has_capacity_configured && (
            <Card className="border-blue-500/30 bg-blue-500/5">
              <CardContent className="flex items-center gap-4 py-4">
                <Target className="h-5 w-5 text-blue-600 flex-shrink-0" />
                <div className="flex-1">
                  <p className="font-medium">Team Capacity Not Set</p>
                  <p className="text-sm text-muted-foreground">Configure your team size for delivery planning</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => navigate('/settings')}>
                  <Settings className="h-4 w-4 mr-2" />
                  Configure
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* At Risk / Overloaded Inbox */}
      {at_risk_initiatives && at_risk_initiatives.length > 0 && (
        <Card className="border-red-500/30">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <CardTitle className="text-lg">Needs Attention</CardTitle>
              <Badge variant="destructive" className="ml-auto">
                {at_risk_initiatives.length}
              </Badge>
            </div>
            <CardDescription>
              Initiatives over capacity — review scope or adjust team
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {at_risk_initiatives.slice(0, 5).map((initiative) => (
              <div 
                key={initiative.epic_id}
                className="flex items-center gap-4 p-3 rounded-lg bg-muted/50 hover:bg-muted cursor-pointer transition-colors"
                onClick={() => navigate(`/delivery-reality/${initiative.epic_id}`)}
                data-testid={`at-risk-${initiative.epic_id}`}
              >
                <div className={`h-10 w-10 rounded-full flex items-center justify-center ${
                  initiative.assessment === 'overloaded' 
                    ? 'bg-red-500/10 text-red-600' 
                    : 'bg-amber-500/10 text-amber-600'
                }`}>
                  {initiative.assessment === 'overloaded' 
                    ? <AlertCircle className="h-5 w-5" />
                    : <AlertTriangle className="h-5 w-5" />
                  }
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{initiative.title}</p>
                  <p className="text-sm text-muted-foreground">
                    {initiative.total_points} pts / {initiative.two_sprint_capacity} capacity
                  </p>
                </div>
                <div className="text-right">
                  <Badge variant={initiative.assessment === 'overloaded' ? 'destructive' : 'outline'} className={
                    initiative.assessment === 'at_risk' ? 'border-amber-500 text-amber-600' : ''
                  }>
                    {initiative.delta > 0 ? '+' : ''}{initiative.delta} pts
                  </Badge>
                </div>
                <Button variant="outline" size="sm" className="gap-1">
                  <Wrench className="h-3 w-3" />
                  Fix
                </Button>
              </div>
            ))}
            {at_risk_initiatives.length > 5 && (
              <Button variant="link" className="w-full" onClick={() => navigate('/delivery-reality')}>
                View all {at_risk_initiatives.length} initiatives
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Main Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left Column: Focus List + Quick Entry */}
        <div className="lg:col-span-2 space-y-6">
          {/* Magic Moment: Quick Entry */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Quick Start
              </CardTitle>
              <CardDescription>
                What problem are you trying to solve?
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-3">
                <Input
                  placeholder="e.g., Users can't find relevant products in search results..."
                  value={problemInput}
                  onChange={(e) => setProblemInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleQuickGenerate()}
                  className="flex-1"
                  data-testid="quick-problem-input"
                />
                <Button 
                  onClick={handleQuickGenerate}
                  disabled={!problemInput.trim() || generating}
                  className="gap-2"
                  data-testid="quick-generate-btn"
                >
                  {generating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Zap className="h-4 w-4" />
                  )}
                  Generate
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Focus List */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                Focus List
              </CardTitle>
              <CardDescription>
                Top initiatives by must-have scope
              </CardDescription>
            </CardHeader>
            <CardContent>
              {focus_list && focus_list.length > 0 ? (
                <div className="space-y-3">
                  {focus_list.map((initiative, idx) => (
                    <div 
                      key={initiative.epic_id}
                      className="flex items-center gap-4 p-3 rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                      onClick={() => navigate(`/epic/${initiative.epic_id}`)}
                      data-testid={`focus-${initiative.epic_id}`}
                    >
                      <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-sm">
                        {idx + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{initiative.title}</p>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span>{initiative.must_have_points} must-have pts</span>
                          <span>•</span>
                          <span>{initiative.total_points} total</span>
                        </div>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {STAGE_LABELS[initiative.current_stage] || initiative.current_stage}
                      </Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="h-10 w-10 mx-auto mb-2 opacity-50" />
                  <p>No initiatives in progress</p>
                  <Button variant="link" onClick={() => navigate('/new')} className="mt-2">
                    Create your first initiative
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: KPIs + Activity */}
        <div className="space-y-6">
          {/* Portfolio KPIs */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Portfolio
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Active */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Active Initiatives</span>
                <span className="text-xl font-bold">{kpis?.active_initiatives || 0}</span>
              </div>
              
              {/* Completed */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Completed (30d)</span>
                <span className="text-xl font-bold text-emerald-600">{kpis?.completed_30d || 0}</span>
              </div>
              
              <Separator />
              
              {/* Points in Flight */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Points in Flight</span>
                <span className="text-xl font-bold">{kpis?.total_points_in_flight || 0}</span>
              </div>
              
              {/* Capacity Utilization */}
              {has_capacity_configured && kpis?.two_sprint_capacity > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Capacity (2-Sprint)</span>
                    <span className={`text-lg font-bold ${
                      kpis.capacity_utilization_pct > 100 
                        ? 'text-red-600' 
                        : kpis.capacity_utilization_pct > 80 
                          ? 'text-amber-600' 
                          : 'text-emerald-600'
                    }`}>
                      {kpis.capacity_utilization_pct}%
                    </span>
                  </div>
                  <Progress 
                    value={Math.min(kpis.capacity_utilization_pct, 150)} 
                    max={150}
                    className={`h-2 ${
                      kpis.capacity_utilization_pct > 100 
                        ? '[&>div]:bg-red-500' 
                        : kpis.capacity_utilization_pct > 80 
                          ? '[&>div]:bg-amber-500' 
                          : '[&>div]:bg-emerald-500'
                    }`}
                  />
                  <p className="text-xs text-muted-foreground text-right">
                    {kpis.total_points_in_flight} / {kpis.two_sprint_capacity} pts
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Activity className="h-5 w-5 text-primary" />
                Recent Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              {recent_activity && recent_activity.length > 0 ? (
                <div className="space-y-3">
                  {recent_activity.slice(0, 8).map((event, idx) => {
                    const config = EVENT_CONFIG[event.event_type] || EVENT_CONFIG.created;
                    const Icon = config.icon;
                    return (
                      <div 
                        key={`${event.epic_id}-${event.event_type}-${idx}`}
                        className="flex items-start gap-3 text-sm cursor-pointer hover:bg-muted/50 p-2 rounded -mx-2"
                        onClick={() => navigate(`/epic/${event.epic_id}`)}
                      >
                        <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${config.color}`} />
                        <div className="flex-1 min-w-0">
                          <p className="truncate">
                            <span className="font-medium">{event.title}</span>
                          </p>
                          <p className="text-muted-foreground text-xs">
                            {config.label}
                            {event.details && ` • ${event.details}`}
                          </p>
                        </div>
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatTimeAgo(event.timestamp)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-center py-4 text-muted-foreground text-sm">
                  No recent activity
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
