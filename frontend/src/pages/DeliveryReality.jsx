import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { deliveryRealityAPI } from '@/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
} from '@/components/ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Users,
  Calendar,
  Target,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Scissors,
  Download,
  Zap,
  Save,
  RotateCcw,
  Sparkles,
  FileText,
  Shield,
  Lightbulb,
  Copy,
  ExternalLink,
} from 'lucide-react';

const ASSESSMENT_CONFIG = {
  on_track: {
    label: 'On Track',
    color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
    icon: CheckCircle2,
    description: 'Within 2-sprint capacity',
  },
  at_risk: {
    label: 'At Risk',
    color: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
    icon: AlertTriangle,
    description: 'Slightly over capacity (≤25%)',
  },
  overloaded: {
    label: 'Overloaded',
    color: 'bg-red-500/10 text-red-600 border-red-500/20',
    icon: AlertCircle,
    description: 'Significantly over capacity',
  },
};

const PRIORITY_CONFIG = {
  'must-have': { label: 'Must Have', color: 'bg-red-500/10 text-red-600 border-red-500/20' },
  'should-have': { label: 'Should Have', color: 'bg-amber-500/10 text-amber-600 border-amber-500/20' },
  'nice-to-have': { label: 'Nice to Have', color: 'bg-blue-500/10 text-blue-600 border-blue-500/20' },
};

const AssessmentBadge = ({ assessment }) => {
  const config = ASSESSMENT_CONFIG[assessment] || ASSESSMENT_CONFIG.on_track;
  const Icon = config.icon;
  return (
    <Badge variant="outline" className={`${config.color} gap-1`}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
};

const DeliveryReality = () => {
  const navigate = useNavigate();
  const { epicId } = useParams();
  
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [initiatives, setInitiatives] = useState([]);
  const [selectedInitiative, setSelectedInitiative] = useState(null);
  const [initiativeDetail, setInitiativeDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deferredStories, setDeferredStories] = useState(new Set());
  const [scopePlan, setScopePlan] = useState(null);
  const [planNotes, setPlanNotes] = useState('');
  const [savingPlan, setSavingPlan] = useState(false);
  
  // New state for enhanced features
  const [scopeSummary, setScopeSummary] = useState(null);
  const [cutRationale, setCutRationale] = useState(null);
  const [alternativeCuts, setAlternativeCuts] = useState(null);
  const [riskReview, setRiskReview] = useState(null);
  const [aiLoading, setAiLoading] = useState({
    rationale: false,
    alternatives: false,
    risks: false,
  });
  const [showScopeSummary, setShowScopeSummary] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [summaryRes, initiativesRes] = await Promise.all([
        deliveryRealityAPI.getSummary(),
        deliveryRealityAPI.listInitiatives(),
      ]);
      setSummary(summaryRes.data);
      setInitiatives(initiativesRes.data.initiatives);
      
      // If epicId is provided, auto-open that initiative
      if (epicId) {
        const found = initiativesRes.data.initiatives.find(i => i.epic_id === epicId);
        if (found) {
          await fetchInitiativeDetail(epicId);
        }
      }
    } catch (error) {
      console.error('Failed to fetch delivery reality:', error);
      toast.error('Failed to load delivery reality data');
    } finally {
      setLoading(false);
    }
  };

  const fetchInitiativeDetail = async (id) => {
    try {
      setDetailLoading(true);
      setSelectedInitiative(id);
      
      // Reset AI states
      setCutRationale(null);
      setAlternativeCuts(null);
      setRiskReview(null);
      setScopeSummary(null);
      
      const [detailRes, planRes] = await Promise.all([
        deliveryRealityAPI.getInitiative(id),
        deliveryRealityAPI.getScopePlan(id).catch(() => ({ data: null })),
      ]);
      
      setInitiativeDetail(detailRes.data);
      setScopePlan(planRes.data);
      
      // If there's a saved plan, use those deferrals
      // Otherwise, use recommended deferrals
      if (planRes.data) {
        setDeferredStories(new Set(planRes.data.deferred_story_ids || []));
        setPlanNotes(planRes.data.notes || '');
      } else {
        const recommendedIds = new Set(
          detailRes.data.recommended_defer.map(s => s.story_id)
        );
        setDeferredStories(recommendedIds);
        setPlanNotes('');
      }
    } catch (error) {
      console.error('Failed to fetch initiative detail:', error);
      toast.error('Failed to load initiative details');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const closeDetail = () => {
    setSelectedInitiative(null);
    setInitiativeDetail(null);
    setDeferredStories(new Set());
    setScopePlan(null);
    setPlanNotes('');
    setCutRationale(null);
    setAlternativeCuts(null);
    setRiskReview(null);
    setScopeSummary(null);
    // Remove epicId from URL if present
    if (epicId) {
      navigate('/delivery-reality');
    }
  };

  const toggleDefer = (storyId) => {
    setDeferredStories(prev => {
      const next = new Set(prev);
      if (next.has(storyId)) {
        next.delete(storyId);
      } else {
        next.add(storyId);
      }
      return next;
    });
  };

  const saveScopePlan = async () => {
    if (!initiativeDetail) return;
    
    try {
      setSavingPlan(true);
      const response = await deliveryRealityAPI.saveScopePlan(initiativeDetail.epic_id, {
        name: 'Default Plan',
        deferred_story_ids: Array.from(deferredStories),
        notes: planNotes || null,
      });
      setScopePlan(response.data);
      toast.success('Scope plan saved');
    } catch (error) {
      console.error('Failed to save scope plan:', error);
      toast.error('Failed to save scope plan');
    } finally {
      setSavingPlan(false);
    }
  };

  const clearScopePlan = async () => {
    if (!initiativeDetail) return;
    
    try {
      await deliveryRealityAPI.clearScopePlan(initiativeDetail.epic_id);
      setScopePlan(null);
      setPlanNotes('');
      // Reset to recommended deferrals
      const recommendedIds = new Set(
        initiativeDetail.recommended_defer.map(s => s.story_id)
      );
      setDeferredStories(recommendedIds);
      toast.success('Returned to base plan');
    } catch (error) {
      console.error('Failed to clear scope plan:', error);
      toast.error('Failed to clear scope plan');
    }
  };

  // AI Feature handlers
  const generateCutRationale = async () => {
    if (!initiativeDetail) return;
    
    try {
      setAiLoading(prev => ({ ...prev, rationale: true }));
      const response = await deliveryRealityAPI.generateCutRationale(initiativeDetail.epic_id);
      setCutRationale(response.data);
      toast.success('Rationale generated');
    } catch (error) {
      console.error('Failed to generate rationale:', error);
      const msg = error.response?.data?.detail || 'Failed to generate rationale. Make sure you have an LLM provider configured.';
      toast.error(msg);
    } finally {
      setAiLoading(prev => ({ ...prev, rationale: false }));
    }
  };

  const generateAlternatives = async () => {
    if (!initiativeDetail) return;
    
    try {
      setAiLoading(prev => ({ ...prev, alternatives: true }));
      const response = await deliveryRealityAPI.generateAlternativeCuts(initiativeDetail.epic_id);
      setAlternativeCuts(response.data.alternatives);
      toast.success('Alternative cut strategies generated');
    } catch (error) {
      console.error('Failed to generate alternatives:', error);
      const msg = error.response?.data?.detail || 'Failed to generate alternatives. Make sure you have an LLM provider configured.';
      toast.error(msg);
    } finally {
      setAiLoading(prev => ({ ...prev, alternatives: false }));
    }
  };

  const generateRisks = async () => {
    if (!initiativeDetail) return;
    
    try {
      setAiLoading(prev => ({ ...prev, risks: true }));
      const response = await deliveryRealityAPI.generateRiskReview(initiativeDetail.epic_id);
      setRiskReview(response.data);
      toast.success('Risk review generated');
    } catch (error) {
      console.error('Failed to generate risk review:', error);
      const msg = error.response?.data?.detail || 'Failed to generate risk review. Make sure you have an LLM provider configured.';
      toast.error(msg);
    } finally {
      setAiLoading(prev => ({ ...prev, risks: false }));
    }
  };

  const loadScopeSummary = async () => {
    if (!initiativeDetail) return;
    
    try {
      const response = await deliveryRealityAPI.getScopeSummary(initiativeDetail.epic_id);
      setScopeSummary(response.data);
      setShowScopeSummary(true);
    } catch (error) {
      console.error('Failed to load scope summary:', error);
      toast.error('Failed to load scope summary');
    }
  };

  const applyAlternativeCut = (alt) => {
    if (!alt.stories_to_defer) return;
    setDeferredStories(new Set(alt.stories_to_defer));
    toast.success(`Applied "${alt.name}" strategy`);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  // Calculate deferred points based on current selection
  const calculateDeferredPoints = () => {
    if (!initiativeDetail) return 0;
    return initiativeDetail.recommended_defer
      .filter(s => deferredStories.has(s.story_id))
      .reduce((sum, s) => sum + s.points, 0);
  };

  const getCapacityPercentage = (totalPoints, capacity) => {
    if (capacity === 0) return 0;
    return Math.min(Math.round((totalPoints / capacity) * 100), 150);
  };

  // Generate cuts summary text
  const generateCutsSummaryText = () => {
    if (!initiativeDetail) return '';
    
    const deferred = initiativeDetail.recommended_defer.filter(s => deferredStories.has(s.story_id));
    if (deferred.length === 0) return '';
    
    const deferredPoints = deferred.reduce((sum, s) => sum + s.points, 0);
    const titles = deferred.slice(0, 3).map(s => s.title || 'Untitled').join(', ');
    const more = deferred.length > 3 ? ` +${deferred.length - 3} more` : '';
    
    return `To fit capacity, defer ${deferred.length} items totaling ${deferredPoints} pts (${titles}${more}).`;
  };

  // Check MVP feasibility
  const getMvpStatus = () => {
    if (!initiativeDetail) return null;
    
    const mustHavePoints = initiativeDetail.must_have_points;
    const capacity = initiativeDetail.two_sprint_capacity;
    
    if (mustHavePoints <= capacity) {
      return {
        feasible: true,
        buffer: capacity - mustHavePoints,
        message: `Must-haves (${mustHavePoints} pts) fit within capacity with ${capacity - mustHavePoints} pts buffer.`
      };
    } else {
      return {
        feasible: false,
        overBy: mustHavePoints - capacity,
        message: `HARD PROBLEM: Must-haves alone (${mustHavePoints} pts) exceed capacity by ${mustHavePoints - capacity} pts.`
      };
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="delivery-reality-loading">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const ctx = summary?.delivery_context;
  const hasCapacity = ctx?.num_developers > 0;
  const mvpStatus = initiativeDetail ? getMvpStatus() : null;
  const cutsSummary = generateCutsSummaryText();

  return (
    <div className="space-y-6" data-testid="delivery-reality-page">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Target className="h-6 w-6 text-primary" />
            Delivery Reality
          </h1>
          <p className="text-muted-foreground">
            Feasibility analysis and scope recommendations for your initiatives
          </p>
        </div>
        <Button variant="outline" onClick={fetchData} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Delivery Context Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Delivery Context</CardTitle>
          <CardDescription>Your team capacity settings</CardDescription>
        </CardHeader>
        <CardContent>
          {!hasCapacity ? (
            <div className="flex items-center gap-3 p-4 bg-amber-500/10 rounded-lg border border-amber-500/20">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              <div>
                <p className="font-medium text-amber-600">Team capacity not configured</p>
                <p className="text-sm text-muted-foreground">
                  Set your team size in Settings → Delivery Context to enable capacity planning.
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
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Users className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Developers</p>
                  <p className="text-xl font-bold">{ctx.num_developers}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Calendar className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Sprint Length</p>
                  <p className="text-xl font-bold">{ctx.sprint_cycle_length}d</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <Zap className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Points/Dev/Sprint</p>
                  <p className="text-xl font-bold">{ctx.points_per_dev_per_sprint}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <TrendingUp className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Sprint Capacity</p>
                  <p className="text-xl font-bold">{ctx.sprint_capacity} pts</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                  <Target className="h-5 w-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">2-Sprint Capacity</p>
                  <p className="text-xl font-bold">{ctx.two_sprint_capacity} pts</p>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Stats */}
      {hasCapacity && summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Target className="h-4 w-4" />
                Active Initiatives
              </div>
              <div className="text-2xl font-bold mt-1">{summary.total_active_initiatives}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 text-emerald-600 text-sm">
                <CheckCircle2 className="h-4 w-4" />
                On Track
              </div>
              <div className="text-2xl font-bold mt-1">{summary.status_breakdown.on_track}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 text-amber-600 text-sm">
                <AlertTriangle className="h-4 w-4" />
                At Risk
              </div>
              <div className="text-2xl font-bold mt-1">{summary.status_breakdown.at_risk}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertCircle className="h-4 w-4" />
                Overloaded
              </div>
              <div className="text-2xl font-bold mt-1">{summary.status_breakdown.overloaded}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Initiatives Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Initiative Delivery Status</CardTitle>
          <CardDescription>
            {hasCapacity 
              ? 'Click an initiative to view detailed analysis and scope recommendations'
              : 'Configure delivery context to see capacity analysis'
            }
          </CardDescription>
        </CardHeader>
        <CardContent>
          {initiatives.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Target className="h-10 w-10 mx-auto mb-2 opacity-50" />
              <p>No active initiatives found</p>
              <Button 
                variant="link" 
                onClick={() => navigate('/new')}
                className="mt-2"
              >
                Create your first initiative
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[35%]">Initiative</TableHead>
                  <TableHead className="text-center">Stories</TableHead>
                  <TableHead className="text-center">Total Points</TableHead>
                  <TableHead className="text-center">Capacity (2-Sprint)</TableHead>
                  <TableHead className="text-center">Delta</TableHead>
                  <TableHead className="text-center">Status</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {initiatives.map((initiative) => (
                  <TableRow
                    key={initiative.epic_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => fetchInitiativeDetail(initiative.epic_id)}
                    data-testid={`initiative-row-${initiative.epic_id}`}
                  >
                    <TableCell className="font-medium">{initiative.title}</TableCell>
                    <TableCell className="text-center">{initiative.stories_count}</TableCell>
                    <TableCell className="text-center font-mono">{initiative.total_points}</TableCell>
                    <TableCell className="text-center font-mono">{initiative.two_sprint_capacity}</TableCell>
                    <TableCell className="text-center">
                      <span className={`font-mono ${
                        initiative.delta >= 0 
                          ? 'text-emerald-600' 
                          : initiative.delta > -initiative.two_sprint_capacity * 0.25 
                            ? 'text-amber-600' 
                            : 'text-red-600'
                      }`}>
                        {initiative.delta >= 0 ? '+' : ''}{initiative.delta}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <AssessmentBadge assessment={initiative.assessment} />
                    </TableCell>
                    <TableCell>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Initiative Detail Dialog */}
      <Dialog open={!!selectedInitiative} onOpenChange={(open) => !open && closeDetail()}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          {detailLoading ? (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : initiativeDetail ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {initiativeDetail.title}
                  <AssessmentBadge assessment={initiativeDetail.assessment} />
                </DialogTitle>
                <DialogDescription>
                  {ASSESSMENT_CONFIG[initiativeDetail.assessment]?.description}
                </DialogDescription>
              </DialogHeader>

              {/* Capacity Meter */}
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Capacity Usage</span>
                  <span className="font-mono">
                    {initiativeDetail.total_points} / {initiativeDetail.two_sprint_capacity} pts
                  </span>
                </div>
                <Progress 
                  value={getCapacityPercentage(initiativeDetail.total_points, initiativeDetail.two_sprint_capacity)}
                  className={`h-3 ${
                    initiativeDetail.assessment === 'overloaded' 
                      ? '[&>div]:bg-red-500' 
                      : initiativeDetail.assessment === 'at_risk' 
                        ? '[&>div]:bg-amber-500' 
                        : '[&>div]:bg-emerald-500'
                  }`}
                />
                <div className="flex items-center justify-center gap-2 py-2">
                  {initiativeDetail.delta >= 0 ? (
                    <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1">
                      <TrendingDown className="h-3 w-3" />
                      Under by {initiativeDetail.delta} points
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20 gap-1">
                      <TrendingUp className="h-3 w-3" />
                      Over by {Math.abs(initiativeDetail.delta)} points
                    </Badge>
                  )}
                </div>
              </div>

              {/* MVP Feasibility Alert - NEW */}
              {mvpStatus && !mvpStatus.feasible && (
                <Card className="bg-red-500/5 border-red-500/20">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
                      <div>
                        <p className="font-semibold text-red-600">Hard Problem: MVP Exceeds Capacity</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {mvpStatus.message}
                        </p>
                        <p className="text-sm text-muted-foreground mt-2">
                          Consider: reframing scope, extending timeline, or adding resources.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Separator />

              {/* Points Breakdown */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className={`p-3 rounded-lg ${mvpStatus && !mvpStatus.feasible ? 'bg-red-500/10 border border-red-500/20' : 'bg-red-500/5'}`}>
                  <p className="text-sm text-muted-foreground">Must Have</p>
                  <p className="text-xl font-bold">{initiativeDetail.must_have_points} pts</p>
                  {mvpStatus && !mvpStatus.feasible && (
                    <p className="text-xs text-red-500 mt-1">Exceeds capacity!</p>
                  )}
                </div>
                <div className="p-3 bg-amber-500/5 rounded-lg">
                  <p className="text-sm text-muted-foreground">Should Have</p>
                  <p className="text-xl font-bold">{initiativeDetail.should_have_points} pts</p>
                </div>
                <div className="p-3 bg-blue-500/5 rounded-lg">
                  <p className="text-sm text-muted-foreground">Nice to Have</p>
                  <p className="text-xl font-bold">{initiativeDetail.nice_to_have_points} pts</p>
                </div>
              </div>

              {/* Recommended Deferrals */}
              {initiativeDetail.recommended_defer.length > 0 && (
                <>
                  <Separator />
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold flex items-center gap-2">
                        <Scissors className="h-4 w-4" />
                        {scopePlan ? 'Saved Scope Plan' : 'Recommended Scope Cuts'}
                      </h4>
                      <div className="flex items-center gap-2">
                        {scopePlan && (
                          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                            <Save className="h-3 w-3 mr-1" />
                            Plan Saved
                          </Badge>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={loadScopeSummary}
                          className="gap-1"
                        >
                          <FileText className="h-3 w-3" />
                          Export Summary
                        </Button>
                      </div>
                    </div>

                    {/* Why These Cuts - NEW */}
                    {cutsSummary && (
                      <div className="mb-4 p-3 bg-violet-500/5 rounded-lg border border-violet-500/20">
                        <p className="text-sm text-violet-700 dark:text-violet-300">{cutsSummary}</p>
                      </div>
                    )}

                    <p className="text-sm text-muted-foreground mb-4">
                      {scopePlan 
                        ? 'This is your saved deferral plan. Changes are not applied to stories — they remain reversible.'
                        : 'These are AI-recommended deferrals based on priority (lowest first) and size (largest first). Select stories to defer, then save as a plan.'
                      }
                    </p>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[50px]">Defer</TableHead>
                          <TableHead>Story</TableHead>
                          <TableHead>Feature</TableHead>
                          <TableHead className="text-center">Priority</TableHead>
                          <TableHead className="text-center">Points</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {initiativeDetail.recommended_defer.map((story) => (
                          <TableRow key={story.story_id}>
                            <TableCell>
                              <Checkbox
                                checked={deferredStories.has(story.story_id)}
                                onCheckedChange={() => toggleDefer(story.story_id)}
                              />
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <p className="font-medium">{story.title || 'Untitled Story'}</p>
                                <p className="text-xs text-muted-foreground line-clamp-1">
                                  {story.story_text}
                                </p>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {story.feature_title}
                            </TableCell>
                            <TableCell className="text-center">
                              {story.priority && (
                                <Badge 
                                  variant="outline" 
                                  className={PRIORITY_CONFIG[story.priority]?.color || ''}
                                >
                                  {PRIORITY_CONFIG[story.priority]?.label || story.priority}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-center font-mono">
                              {story.points}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>

                    {/* Plan notes */}
                    <div className="mt-4 space-y-2">
                      <label className="text-sm font-medium">Notes (optional)</label>
                      <Textarea
                        placeholder="Add notes about this scope plan..."
                        value={planNotes}
                        onChange={(e) => setPlanNotes(e.target.value)}
                        className="h-20"
                      />
                    </div>

                    {/* New totals after deferral */}
                    <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="text-sm text-muted-foreground">
                            {scopePlan ? 'With saved plan:' : 'After deferring selected stories:'}
                          </p>
                          <p className="font-medium">
                            New total: <span className="font-mono">{initiativeDetail.total_points - calculateDeferredPoints()}</span> pts
                            {' '}
                            <span className={`${
                              initiativeDetail.two_sprint_capacity - (initiativeDetail.total_points - calculateDeferredPoints()) >= 0
                                ? 'text-emerald-600'
                                : 'text-red-600'
                            }`}>
                              ({initiativeDetail.two_sprint_capacity - (initiativeDetail.total_points - calculateDeferredPoints()) >= 0 ? '+' : ''}
                              {initiativeDetail.two_sprint_capacity - (initiativeDetail.total_points - calculateDeferredPoints())} delta)
                            </span>
                          </p>
                        </div>
                        <Badge variant="secondary">
                          -{calculateDeferredPoints()} pts deferred
                        </Badge>
                      </div>
                    </div>
                  </div>
                </>
              )}

              <Separator />

              {/* AI Features Section - NEW */}
              <div className="space-y-4">
                <h4 className="font-semibold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-violet-500" />
                  AI-Powered Insights
                  <Badge variant="outline" className="text-xs">Uses your LLM</Badge>
                </h4>
                
                <Tabs defaultValue="rationale" className="w-full">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="rationale" className="gap-1">
                      <Lightbulb className="h-3 w-3" />
                      Rationale
                    </TabsTrigger>
                    <TabsTrigger value="alternatives" className="gap-1">
                      <Scissors className="h-3 w-3" />
                      Alternatives
                    </TabsTrigger>
                    <TabsTrigger value="risks" className="gap-1">
                      <Shield className="h-3 w-3" />
                      Risk Review
                    </TabsTrigger>
                  </TabsList>
                  
                  {/* Rationale Tab */}
                  <TabsContent value="rationale" className="space-y-3 mt-4">
                    {cutRationale ? (
                      <div className="space-y-3">
                        <div className="p-3 bg-violet-500/5 rounded-lg border border-violet-500/20">
                          <p className="text-xs font-medium text-violet-600 mb-1">Rationale</p>
                          <p className="text-sm">{cutRationale.rationale}</p>
                        </div>
                        <div className="p-3 bg-amber-500/5 rounded-lg border border-amber-500/20">
                          <p className="text-xs font-medium text-amber-600 mb-1">User Impact Tradeoff</p>
                          <p className="text-sm">{cutRationale.user_impact_tradeoff}</p>
                        </div>
                        <div className="p-3 bg-blue-500/5 rounded-lg border border-blue-500/20">
                          <p className="text-xs font-medium text-blue-600 mb-1">Validate First</p>
                          <p className="text-sm">{cutRationale.what_to_validate_first}</p>
                        </div>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => copyToClipboard(`Rationale: ${cutRationale.rationale}\n\nUser Impact: ${cutRationale.user_impact_tradeoff}\n\nValidate First: ${cutRationale.what_to_validate_first}`)}
                          className="gap-1"
                        >
                          <Copy className="h-3 w-3" />
                          Copy
                        </Button>
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <Lightbulb className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                        <p className="text-sm text-muted-foreground mb-3">
                          Generate PM-quality explanation for your scope decisions
                        </p>
                        <Button 
                          onClick={generateCutRationale}
                          disabled={aiLoading.rationale}
                          className="gap-2"
                        >
                          {aiLoading.rationale ? (
                            <RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <Sparkles className="h-4 w-4" />
                          )}
                          Generate Rationale
                        </Button>
                      </div>
                    )}
                  </TabsContent>
                  
                  {/* Alternatives Tab */}
                  <TabsContent value="alternatives" className="space-y-3 mt-4">
                    {alternativeCuts && alternativeCuts.length > 0 ? (
                      <div className="space-y-3">
                        {alternativeCuts.map((alt, i) => (
                          <Card key={i} className="bg-muted/30">
                            <CardContent className="p-4">
                              <div className="flex items-start justify-between">
                                <div>
                                  <p className="font-medium">{alt.name}</p>
                                  <p className="text-sm text-muted-foreground mt-1">{alt.description}</p>
                                  <Badge variant="secondary" className="mt-2">
                                    -{alt.total_deferred_points} pts
                                  </Badge>
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => applyAlternativeCut(alt)}
                                >
                                  Apply
                                </Button>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <Scissors className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                        <p className="text-sm text-muted-foreground mb-3">
                          Get 2-3 alternative ways to cut scope
                        </p>
                        <Button 
                          onClick={generateAlternatives}
                          disabled={aiLoading.alternatives || initiativeDetail.delta >= 0}
                          className="gap-2"
                        >
                          {aiLoading.alternatives ? (
                            <RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <Sparkles className="h-4 w-4" />
                          )}
                          Generate Alternatives
                        </Button>
                        {initiativeDetail.delta >= 0 && (
                          <p className="text-xs text-muted-foreground mt-2">
                            No cuts needed - you&apos;re under capacity
                          </p>
                        )}
                      </div>
                    )}
                  </TabsContent>
                  
                  {/* Risks Tab */}
                  <TabsContent value="risks" className="space-y-3 mt-4">
                    {riskReview ? (
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs font-medium text-red-600 mb-2">Top Delivery Risks</p>
                          <ul className="space-y-1">
                            {riskReview.top_delivery_risks.map((risk, i) => (
                              <li key={i} className="text-sm flex items-start gap-2">
                                <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                                {risk}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-amber-600 mb-2">Assumptions to Validate</p>
                          <ul className="space-y-1">
                            {riskReview.top_assumptions.map((assumption, i) => (
                              <li key={i} className="text-sm flex items-start gap-2">
                                <Lightbulb className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                                {assumption}
                              </li>
                            ))}
                          </ul>
                        </div>
                        {riskReview.suggested_spike && (
                          <Card className="bg-blue-500/5 border-blue-500/20">
                            <CardContent className="p-3">
                              <p className="text-xs font-medium text-blue-600 mb-1">Suggested Spike Story</p>
                              <p className="font-medium">{riskReview.suggested_spike.title}</p>
                              <p className="text-sm text-muted-foreground">{riskReview.suggested_spike.description}</p>
                              <Badge variant="outline" className="mt-2">
                                {riskReview.suggested_spike.points} pts
                              </Badge>
                            </CardContent>
                          </Card>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <Shield className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                        <p className="text-sm text-muted-foreground mb-3">
                          Identify risks and assumptions for your plan
                        </p>
                        <Button 
                          onClick={generateRisks}
                          disabled={aiLoading.risks}
                          className="gap-2"
                        >
                          {aiLoading.risks ? (
                            <RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <Sparkles className="h-4 w-4" />
                          )}
                          Generate Risk Review
                        </Button>
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </div>

              {/* Actions */}
              <div className="flex justify-between pt-4">
                <Button variant="outline" onClick={closeDetail}>
                  Close
                </Button>
                <div className="flex gap-2">
                  {scopePlan && (
                    <Button 
                      variant="outline"
                      onClick={clearScopePlan}
                      className="gap-2"
                    >
                      <RotateCcw className="h-4 w-4" />
                      Reset to Base
                    </Button>
                  )}
                  {initiativeDetail.recommended_defer.length > 0 && (
                    <Button 
                      onClick={saveScopePlan}
                      disabled={savingPlan}
                      className="gap-2"
                    >
                      {savingPlan ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      {scopePlan ? 'Update Plan' : 'Save Plan'}
                    </Button>
                  )}
                  <Button 
                    variant="outline" 
                    onClick={() => navigate(`/epic/${initiativeDetail.epic_id}`)}
                  >
                    View Initiative
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Scope Summary Dialog - NEW */}
      <Dialog open={showScopeSummary} onOpenChange={setShowScopeSummary}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Scope Decision Summary
            </DialogTitle>
            <DialogDescription>
              Shareable artifact for stakeholders
            </DialogDescription>
          </DialogHeader>
          
          {scopeSummary && (
            <div className="space-y-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">{scopeSummary.title}</CardTitle>
                  <CardDescription>
                    Generated: {new Date(scopeSummary.generated_at).toLocaleString()}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* MVP Analysis */}
                  <div className={`p-3 rounded-lg ${scopeSummary.mvp_analysis.mvp_feasible ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                    <p className="text-sm font-medium">
                      {scopeSummary.mvp_analysis.mvp_feasible ? '✓ MVP Feasible' : '⚠ MVP Problem'}
                    </p>
                    <p className="text-sm text-muted-foreground">{scopeSummary.mvp_analysis.message}</p>
                  </div>
                  
                  {/* Sprint 1 */}
                  <div>
                    <p className="font-medium mb-2">Sprint 1 ({scopeSummary.sprint_1_points} pts)</p>
                    <ul className="text-sm space-y-1">
                      {scopeSummary.sprint_1_scope.slice(0, 5).map((s, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                          {s.title} ({s.points} pts)
                        </li>
                      ))}
                      {scopeSummary.sprint_1_scope.length > 5 && (
                        <li className="text-muted-foreground">+{scopeSummary.sprint_1_scope.length - 5} more</li>
                      )}
                    </ul>
                  </div>
                  
                  {/* Sprint 2 */}
                  <div>
                    <p className="font-medium mb-2">Sprint 2 ({scopeSummary.sprint_2_points} pts)</p>
                    <ul className="text-sm space-y-1">
                      {scopeSummary.sprint_2_scope.slice(0, 5).map((s, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <CheckCircle2 className="h-3 w-3 text-blue-500" />
                          {s.title} ({s.points} pts)
                        </li>
                      ))}
                      {scopeSummary.sprint_2_scope.length > 5 && (
                        <li className="text-muted-foreground">+{scopeSummary.sprint_2_scope.length - 5} more</li>
                      )}
                    </ul>
                  </div>
                  
                  {/* Deferred */}
                  {scopeSummary.deferred_scope.length > 0 && (
                    <div>
                      <p className="font-medium mb-2 text-amber-600">Deferred ({scopeSummary.deferred_points} pts)</p>
                      <ul className="text-sm space-y-1">
                        {scopeSummary.deferred_scope.map((s, i) => (
                          <li key={i} className="flex items-center gap-2 text-muted-foreground">
                            <Minus className="h-3 w-3" />
                            {s.title} ({s.points} pts)
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {/* Cuts Summary */}
                  {scopeSummary.cuts_summary && (
                    <div className="p-3 bg-violet-500/5 rounded-lg">
                      <p className="text-sm">{scopeSummary.cuts_summary}</p>
                    </div>
                  )}
                  
                  {/* Notes */}
                  {scopeSummary.notes && (
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-xs font-medium mb-1">Notes</p>
                      <p className="text-sm">{scopeSummary.notes}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
              
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    const text = `# Scope Decision: ${scopeSummary.title}\n\n` +
                      `**Capacity:** ${scopeSummary.capacity} pts\n` +
                      `**Total Scope:** ${scopeSummary.total_points} pts\n\n` +
                      `## Sprint 1 (${scopeSummary.sprint_1_points} pts)\n` +
                      scopeSummary.sprint_1_scope.map(s => `- ${s.title} (${s.points} pts)`).join('\n') + '\n\n' +
                      `## Sprint 2 (${scopeSummary.sprint_2_points} pts)\n` +
                      scopeSummary.sprint_2_scope.map(s => `- ${s.title} (${s.points} pts)`).join('\n') + '\n\n' +
                      (scopeSummary.deferred_scope.length > 0 ? 
                        `## Deferred (${scopeSummary.deferred_points} pts)\n` +
                        scopeSummary.deferred_scope.map(s => `- ${s.title} (${s.points} pts)`).join('\n') : '') +
                      (scopeSummary.cuts_summary ? `\n\n**Summary:** ${scopeSummary.cuts_summary}` : '');
                    copyToClipboard(text);
                  }}
                  className="gap-2"
                >
                  <Copy className="h-4 w-4" />
                  Copy as Markdown
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DeliveryReality;
