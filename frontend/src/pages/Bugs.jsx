import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ThemeToggle from '@/components/ThemeToggle';
import { useAuthStore } from '@/store';
import { bugAPI } from '@/api';
import { 
  Bug, Plus, Search, ArrowLeft, Settings, 
  AlertTriangle, AlertCircle, Info, CheckCircle2,
  Clock, Play, CheckCheck, Archive, Link2, Unlink,
  ChevronRight, Loader2, Trash2, Edit3, Sparkles,
  ArrowUpDown, Calendar, User, Send, Bot, UserIcon, MessageSquare
} from 'lucide-react';

// Constants
const SEVERITY_CONFIG = {
  critical: { label: 'Critical', color: 'bg-red-500/20 text-red-400 border-red-500/30', icon: AlertTriangle },
  high: { label: 'High', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', icon: AlertCircle },
  medium: { label: 'Medium', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', icon: Info },
  low: { label: 'Low', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: Info },
};

const STATUS_CONFIG = {
  draft: { label: 'Draft', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30', icon: Edit3 },
  confirmed: { label: 'Confirmed', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', icon: CheckCircle2 },
  in_progress: { label: 'In Progress', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: Play },
  resolved: { label: 'Resolved', color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: CheckCheck },
  closed: { label: 'Closed', color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', icon: Archive },
};

const PRIORITY_CONFIG = {
  p0: { label: 'P0 - Urgent', color: 'text-red-400' },
  p1: { label: 'P1 - High', color: 'text-orange-400' },
  p2: { label: 'P2 - Medium', color: 'text-yellow-400' },
  p3: { label: 'P3 - Low', color: 'text-blue-400' },
};

const Bugs = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [theme, setTheme] = useState('light');
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  // State
  const [bugs, setBugs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [linkedFilter, setLinkedFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('updated_at');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showAICreateDialog, setShowAICreateDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [selectedBug, setSelectedBug] = useState(null);
  
  // Create form state
  const [createForm, setCreateForm] = useState({
    title: '',
    description: '',
    severity: 'medium',
    priority: '',
    steps_to_reproduce: '',
    expected_behavior: '',
    actual_behavior: '',
    environment: '',
  });
  const [creating, setCreating] = useState(false);
  
  // AI chat state
  const [aiMessages, setAiMessages] = useState([]);
  const [aiInput, setAiInput] = useState('');
  const [aiSending, setAiSending] = useState(false);
  const [aiStreamingContent, setAiStreamingContent] = useState('');
  const [aiProposal, setAiProposal] = useState(null);
  const [creatingFromProposal, setCreatingFromProposal] = useState(false);
  const aiChatRef = useRef(null);
  
  // Transition state
  const [transitioning, setTransitioning] = useState(false);

  // Theme detection
  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setTheme(root.classList.contains('dark') ? 'dark' : 'light');
    });
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    setTheme(root.classList.contains('dark') ? 'dark' : 'light');
    return () => observer.disconnect();
  }, []);

  // Load bugs
  const loadBugs = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (severityFilter !== 'all') params.severity = severityFilter;
      if (linkedFilter !== 'all') params.linked = linkedFilter;
      params.sort_by = sortBy;
      params.sort_order = sortOrder;
      
      const response = await bugAPI.list(params);
      setBugs(response.data || []);
    } catch (err) {
      setError('Failed to load bugs');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter, linkedFilter, sortBy, sortOrder]);

  useEffect(() => {
    if (user) loadBugs();
  }, [user, loadBugs]);

  // Filtered bugs (client-side search)
  const filteredBugs = bugs.filter(bug => 
    !searchQuery || 
    bug.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    bug.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Create bug
  const handleCreate = async () => {
    if (!createForm.title.trim() || !createForm.description.trim()) return;
    
    try {
      setCreating(true);
      const data = {
        title: createForm.title,
        description: createForm.description,
        severity: createForm.severity,
      };
      if (createForm.priority) data.priority = createForm.priority;
      if (createForm.steps_to_reproduce) data.steps_to_reproduce = createForm.steps_to_reproduce;
      if (createForm.expected_behavior) data.expected_behavior = createForm.expected_behavior;
      if (createForm.actual_behavior) data.actual_behavior = createForm.actual_behavior;
      if (createForm.environment) data.environment = createForm.environment;
      
      await bugAPI.create(data);
      setShowCreateDialog(false);
      setCreateForm({
        title: '',
        description: '',
        severity: 'medium',
        priority: '',
        steps_to_reproduce: '',
        expected_behavior: '',
        actual_behavior: '',
        environment: '',
      });
      loadBugs();
    } catch (err) {
      setError('Failed to create bug');
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  // Transition status
  const handleTransition = async (bugId, newStatus, notes = null) => {
    try {
      setTransitioning(true);
      await bugAPI.transition(bugId, newStatus, notes);
      loadBugs();
      if (selectedBug?.bug_id === bugId) {
        const response = await bugAPI.get(bugId);
        setSelectedBug(response.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to transition status');
    } finally {
      setTransitioning(false);
    }
  };

  // Delete bug
  const handleDelete = async (bugId) => {
    if (!window.confirm('Are you sure you want to delete this bug?')) return;
    
    try {
      await bugAPI.delete(bugId);
      setShowDetailDialog(false);
      setSelectedBug(null);
      loadBugs();
    } catch (err) {
      setError('Failed to delete bug');
    }
  };

  // View bug details
  const openBugDetail = async (bug) => {
    try {
      const response = await bugAPI.get(bug.bug_id);
      setSelectedBug(response.data);
      setShowDetailDialog(true);
    } catch (err) {
      setError('Failed to load bug details');
    }
  };

  if (!user) {
    navigate('/');
    return null;
  }

  return (
    <div className="h-screen bg-background flex flex-col overflow-hidden" data-testid="bugs-page">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => navigate('/dashboard')} 
                className="text-muted-foreground hover:text-foreground"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="flex items-center gap-2">
                <img src={logoSrc} alt="JarlPM" className="h-8 w-auto" />
                <span className="text-lg font-semibold text-foreground">Bug Tracker</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button 
                onClick={() => setShowCreateDialog(true)}
                className="bg-red-500 hover:bg-red-600 text-white"
                data-testid="new-bug-btn"
              >
                <Plus className="w-4 h-4 mr-2" />
                New Bug
              </Button>
              <ThemeToggle />
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => navigate('/settings')} 
                className="text-muted-foreground hover:text-foreground"
              >
                <Settings className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Filters Bar */}
      <div className="flex-shrink-0 border-b border-border bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search bugs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="search-input"
              />
            </div>
            
            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px]" data-testid="status-filter">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="confirmed">Confirmed</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            
            {/* Severity Filter */}
            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger className="w-[140px]" data-testid="severity-filter">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severity</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
            
            {/* Linked Filter */}
            <Select value={linkedFilter} onValueChange={setLinkedFilter}>
              <SelectTrigger className="w-[140px]" data-testid="linked-filter">
                <SelectValue placeholder="Links" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Bugs</SelectItem>
                <SelectItem value="true">Linked</SelectItem>
                <SelectItem value="false">Standalone</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort */}
            <Select value={`${sortBy}:${sortOrder}`} onValueChange={(v) => {
              const [by, order] = v.split(':');
              setSortBy(by);
              setSortOrder(order);
            }}>
              <SelectTrigger className="w-[160px]" data-testid="sort-select">
                <ArrowUpDown className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="updated_at:desc">Recently Updated</SelectItem>
                <SelectItem value="created_at:desc">Recently Created</SelectItem>
                <SelectItem value="severity:desc">Severity (High→Low)</SelectItem>
                <SelectItem value="severity:asc">Severity (Low→High)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Bug List */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-destructive text-sm">
              {error}
              <Button variant="ghost" size="sm" onClick={() => setError(null)} className="ml-2">
                Dismiss
              </Button>
            </div>
          )}
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredBugs.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center">
                <Bug className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold text-foreground mb-2">No bugs found</h3>
                <p className="text-muted-foreground mb-4">
                  {searchQuery || statusFilter !== 'all' || severityFilter !== 'all' || linkedFilter !== 'all'
                    ? 'Try adjusting your filters'
                    : 'Create your first bug to start tracking issues'}
                </p>
                <Button onClick={() => setShowCreateDialog(true)} data-testid="create-first-bug-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Bug
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {filteredBugs.map((bug) => (
                <BugCard 
                  key={bug.bug_id} 
                  bug={bug} 
                  onClick={() => openBugDetail(bug)}
                  onTransition={handleTransition}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Bug Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bug className="w-5 h-5 text-red-500" />
              Create New Bug
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                placeholder="Brief summary of the bug..."
                value={createForm.title}
                onChange={(e) => setCreateForm({...createForm, title: e.target.value})}
                data-testid="bug-title-input"
              />
            </div>
            
            <div>
              <Label htmlFor="description">Description *</Label>
              <Textarea
                id="description"
                placeholder="Detailed description of the bug..."
                value={createForm.description}
                onChange={(e) => setCreateForm({...createForm, description: e.target.value})}
                rows={3}
                data-testid="bug-description-input"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Severity</Label>
                <Select 
                  value={createForm.severity} 
                  onValueChange={(v) => setCreateForm({...createForm, severity: v})}
                >
                  <SelectTrigger data-testid="bug-severity-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">Critical</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label>Priority (Optional)</Label>
                <Select 
                  value={createForm.priority} 
                  onValueChange={(v) => setCreateForm({...createForm, priority: v})}
                >
                  <SelectTrigger data-testid="bug-priority-select">
                    <SelectValue placeholder="Select priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="p0">P0 - Urgent</SelectItem>
                    <SelectItem value="p1">P1 - High</SelectItem>
                    <SelectItem value="p2">P2 - Medium</SelectItem>
                    <SelectItem value="p3">P3 - Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div>
              <Label htmlFor="steps">Steps to Reproduce (Optional)</Label>
              <Textarea
                id="steps"
                placeholder="1. Go to...\n2. Click on...\n3. Observe..."
                value={createForm.steps_to_reproduce}
                onChange={(e) => setCreateForm({...createForm, steps_to_reproduce: e.target.value})}
                rows={3}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="expected">Expected Behavior (Optional)</Label>
                <Textarea
                  id="expected"
                  placeholder="What should happen..."
                  value={createForm.expected_behavior}
                  onChange={(e) => setCreateForm({...createForm, expected_behavior: e.target.value})}
                  rows={2}
                />
              </div>
              <div>
                <Label htmlFor="actual">Actual Behavior (Optional)</Label>
                <Textarea
                  id="actual"
                  placeholder="What actually happens..."
                  value={createForm.actual_behavior}
                  onChange={(e) => setCreateForm({...createForm, actual_behavior: e.target.value})}
                  rows={2}
                />
              </div>
            </div>
            
            <div>
              <Label htmlFor="environment">Environment (Optional)</Label>
              <Input
                id="environment"
                placeholder="e.g., Chrome 120, macOS 14, Production"
                value={createForm.environment}
                onChange={(e) => setCreateForm({...createForm, environment: e.target.value})}
              />
            </div>
            
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Link2 className="w-3 h-3" />
              Links to Epics, Features, or Stories can be added after creation
            </p>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreate}
              disabled={creating || !createForm.title.trim() || !createForm.description.trim()}
              className="bg-red-500 hover:bg-red-600"
              data-testid="create-bug-submit-btn"
            >
              {creating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Bug className="w-4 h-4 mr-2" />}
              Create Bug
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bug Detail Dialog */}
      {selectedBug && (
        <BugDetailDialog
          bug={selectedBug}
          open={showDetailDialog}
          onClose={() => {
            setShowDetailDialog(false);
            setSelectedBug(null);
          }}
          onTransition={handleTransition}
          onDelete={handleDelete}
          transitioning={transitioning}
        />
      )}
    </div>
  );
};

// Bug Card Component
const BugCard = ({ bug, onClick, onTransition }) => {
  const severityConfig = SEVERITY_CONFIG[bug.severity] || SEVERITY_CONFIG.medium;
  const statusConfig = STATUS_CONFIG[bug.status] || STATUS_CONFIG.draft;
  const SeverityIcon = severityConfig.icon;
  const StatusIcon = statusConfig.icon;

  return (
    <Card 
      className="cursor-pointer hover:border-primary/50 transition-colors"
      onClick={onClick}
      data-testid={`bug-card-${bug.bug_id}`}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Badge variant="outline" className={severityConfig.color}>
                <SeverityIcon className="w-3 h-3 mr-1" />
                {severityConfig.label}
              </Badge>
              <Badge variant="outline" className={statusConfig.color}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {statusConfig.label}
              </Badge>
              {bug.priority && (
                <Badge variant="outline" className={`bg-muted ${PRIORITY_CONFIG[bug.priority]?.color || ''}`}>
                  {PRIORITY_CONFIG[bug.priority]?.label || bug.priority}
                </Badge>
              )}
              {bug.link_count > 0 ? (
                <Badge variant="outline" className="bg-muted text-muted-foreground">
                  <Link2 className="w-3 h-3 mr-1" />
                  {bug.link_count} link{bug.link_count > 1 ? 's' : ''}
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-muted/50 text-muted-foreground">
                  <Unlink className="w-3 h-3 mr-1" />
                  Standalone
                </Badge>
              )}
            </div>
            
            <h3 className="font-medium text-foreground mb-1 truncate">{bug.title}</h3>
            <p className="text-sm text-muted-foreground line-clamp-2">{bug.description}</p>
            
            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(bug.updated_at).toLocaleDateString()}
              </span>
              {bug.assignee_id && (
                <span className="flex items-center gap-1">
                  <User className="w-3 h-3" />
                  Assigned
                </span>
              )}
              {bug.due_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Due {new Date(bug.due_date).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
          
          <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0" />
        </div>
      </CardContent>
    </Card>
  );
};

// Bug Detail Dialog Component
const BugDetailDialog = ({ bug, open, onClose, onTransition, onDelete, transitioning }) => {
  const [activeTab, setActiveTab] = useState('details');
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const severityConfig = SEVERITY_CONFIG[bug.severity] || SEVERITY_CONFIG.medium;
  const statusConfig = STATUS_CONFIG[bug.status] || STATUS_CONFIG.draft;

  const loadHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const response = await bugAPI.getHistory(bug.bug_id);
      setHistory(response.data || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setLoadingHistory(false);
    }
  }, [bug.bug_id]);

  // Load history when tab changes
  useEffect(() => {
    if (activeTab === 'history' && history.length === 0) {
      loadHistory();
    }
  }, [activeTab, history.length, loadHistory]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2 text-xl">
                <Bug className="w-5 h-5 text-red-500" />
                {bug.title}
              </DialogTitle>
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className={severityConfig.color}>
                  {severityConfig.label}
                </Badge>
                <Badge variant="outline" className={statusConfig.color}>
                  {statusConfig.label}
                </Badge>
                {bug.priority && (
                  <Badge variant="outline" className={`bg-muted ${PRIORITY_CONFIG[bug.priority]?.color || ''}`}>
                    {PRIORITY_CONFIG[bug.priority]?.label}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="links">Links ({bug.link_count})</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>
          
          <TabsContent value="details" className="flex-1 overflow-y-auto">
            <div className="space-y-4 py-4">
              <div>
                <Label className="text-muted-foreground">Description</Label>
                <p className="text-foreground mt-1 whitespace-pre-wrap">{bug.description}</p>
              </div>
              
              {bug.steps_to_reproduce && (
                <div>
                  <Label className="text-muted-foreground">Steps to Reproduce</Label>
                  <p className="text-foreground mt-1 whitespace-pre-wrap">{bug.steps_to_reproduce}</p>
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4">
                {bug.expected_behavior && (
                  <div>
                    <Label className="text-muted-foreground">Expected Behavior</Label>
                    <p className="text-foreground mt-1 whitespace-pre-wrap">{bug.expected_behavior}</p>
                  </div>
                )}
                {bug.actual_behavior && (
                  <div>
                    <Label className="text-muted-foreground">Actual Behavior</Label>
                    <p className="text-foreground mt-1 whitespace-pre-wrap">{bug.actual_behavior}</p>
                  </div>
                )}
              </div>
              
              {bug.environment && (
                <div>
                  <Label className="text-muted-foreground">Environment</Label>
                  <p className="text-foreground mt-1">{bug.environment}</p>
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border">
                <div>
                  <Label className="text-muted-foreground">Created</Label>
                  <p className="text-foreground mt-1">{new Date(bug.created_at).toLocaleString()}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Last Updated</Label>
                  <p className="text-foreground mt-1">{new Date(bug.updated_at).toLocaleString()}</p>
                </div>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="links" className="flex-1 overflow-y-auto">
            <div className="py-4">
              {bug.links?.length > 0 ? (
                <div className="space-y-2">
                  {bug.links.map((link) => (
                    <div 
                      key={link.link_id}
                      className="flex items-center justify-between p-3 bg-muted rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="capitalize">{link.entity_type}</Badge>
                        <span className="text-sm text-foreground">{link.entity_id}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(link.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Unlink className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No links (standalone bug)</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    This bug is not linked to any Epics, Features, or Stories
                  </p>
                </div>
              )}
            </div>
          </TabsContent>
          
          <TabsContent value="history" className="flex-1 overflow-y-auto">
            <div className="py-4">
              {loadingHistory ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : history.length > 0 ? (
                <div className="space-y-3">
                  {history.map((item, idx) => (
                    <div 
                      key={item.history_id}
                      className="flex gap-3 p-3 bg-muted/50 rounded-lg"
                    >
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                        <span className="text-xs font-medium text-primary">{history.length - idx}</span>
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-foreground">
                          {item.from_status ? (
                            <>
                              <span className="capitalize">{item.from_status.replace('_', ' ')}</span>
                              {' → '}
                              <span className="capitalize font-medium">{item.to_status.replace('_', ' ')}</span>
                            </>
                          ) : (
                            <span className="font-medium">Bug created</span>
                          )}
                        </p>
                        {item.notes && (
                          <p className="text-xs text-muted-foreground mt-1">{item.notes}</p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          {new Date(item.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">No history available</p>
              )}
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter className="border-t border-border pt-4">
          <div className="flex items-center justify-between w-full">
            <Button 
              variant="destructive" 
              size="sm"
              onClick={() => onDelete(bug.bug_id)}
              data-testid="delete-bug-btn"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
            
            <div className="flex items-center gap-2">
              {bug.allowed_transitions?.length > 0 && (
                <Select 
                  onValueChange={(status) => onTransition(bug.bug_id, status)}
                  disabled={transitioning}
                >
                  <SelectTrigger className="w-[180px]" data-testid="transition-select">
                    {transitioning ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <SelectValue placeholder="Transition to..." />
                    )}
                  </SelectTrigger>
                  <SelectContent>
                    {bug.allowed_transitions.map((status) => (
                      <SelectItem key={status} value={status}>
                        {STATUS_CONFIG[status]?.label || status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button variant="outline" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default Bugs;
