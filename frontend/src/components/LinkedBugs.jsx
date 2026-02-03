import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { bugAPI } from '@/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { 
  Bug, Plus, Link2, Unlink, ExternalLink, AlertCircle, 
  Loader2, ChevronRight, AlertTriangle, CheckCircle2
} from 'lucide-react';

const SEVERITY_CONFIG = {
  critical: { label: 'Critical', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
  high: { label: 'High', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300' },
  medium: { label: 'Medium', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
  low: { label: 'Low', color: 'bg-slate-100 text-slate-600 dark:bg-slate-900/30 dark:text-slate-400' },
};

const STATUS_CONFIG = {
  draft: { label: 'Draft', color: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300' },
  confirmed: { label: 'Confirmed', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' },
  in_progress: { label: 'In Progress', color: 'bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300' },
  resolved: { label: 'Resolved', color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
  closed: { label: 'Closed', color: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300' },
};

// Compact bug card for display in entity pages
const BugCard = ({ bug, onUnlink, onView, showUnlink = true }) => {
  const severityConfig = SEVERITY_CONFIG[bug.severity] || SEVERITY_CONFIG.medium;
  const statusConfig = STATUS_CONFIG[bug.status] || STATUS_CONFIG.draft;

  return (
    <div 
      className="flex items-center justify-between p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors"
      data-testid={`linked-bug-${bug.bug_id}`}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <Bug className="w-4 h-4 text-red-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{bug.title}</p>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline" className={`text-xs ${severityConfig.color}`}>
              {severityConfig.label}
            </Badge>
            <Badge variant="outline" className={`text-xs ${statusConfig.color}`}>
              {statusConfig.label}
            </Badge>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onView(bug.bug_id)}
          className="text-muted-foreground hover:text-foreground"
          data-testid={`view-bug-${bug.bug_id}`}
        >
          <ExternalLink className="w-4 h-4" />
        </Button>
        {showUnlink && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onUnlink(bug)}
            className="text-muted-foreground hover:text-destructive"
            data-testid={`unlink-bug-${bug.bug_id}`}
          >
            <Unlink className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
};

// Create/Link Bug Dialog
const CreateLinkBugDialog = ({ 
  open, 
  onOpenChange, 
  entityType, 
  entityId, 
  entityTitle,
  onBugCreated,
  onBugLinked 
}) => {
  const [mode, setMode] = useState('create'); // 'create' or 'link'
  const [loading, setLoading] = useState(false);
  const [existingBugs, setExistingBugs] = useState([]);
  const [selectedBugId, setSelectedBugId] = useState('');
  
  // New bug form
  const [newBug, setNewBug] = useState({
    title: '',
    description: '',
    severity: 'medium',
    steps_to_reproduce: '',
    expected_behavior: '',
    actual_behavior: '',
  });

  useEffect(() => {
    if (open && mode === 'link') {
      loadExistingBugs();
    }
  }, [open, mode]);

  const loadExistingBugs = async () => {
    try {
      const { data } = await bugAPI.list({ linked: 'false' }); // Get unlinked bugs
      setExistingBugs(data || []);
    } catch (err) {
      console.error('Failed to load bugs:', err);
    }
  };

  const handleCreateBug = async () => {
    if (!newBug.title.trim() || !newBug.description.trim()) {
      toast.error('Please fill in title and description');
      return;
    }

    setLoading(true);
    try {
      const { data } = await bugAPI.create({
        ...newBug,
        links: [{ entity_type: entityType, entity_id: entityId }]
      });
      toast.success('Bug created and linked');
      onBugCreated?.(data);
      onOpenChange(false);
      resetForm();
    } catch (err) {
      toast.error('Failed to create bug');
    } finally {
      setLoading(false);
    }
  };

  const handleLinkBug = async () => {
    if (!selectedBugId) {
      toast.error('Please select a bug');
      return;
    }

    setLoading(true);
    try {
      await bugAPI.addLinks(selectedBugId, [{ entity_type: entityType, entity_id: entityId }]);
      toast.success('Bug linked successfully');
      onBugLinked?.(selectedBugId);
      onOpenChange(false);
      setSelectedBugId('');
    } catch (err) {
      toast.error('Failed to link bug');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setNewBug({
      title: '',
      description: '',
      severity: 'medium',
      steps_to_reproduce: '',
      expected_behavior: '',
      actual_behavior: '',
    });
    setSelectedBugId('');
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) resetForm(); }}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bug className="w-5 h-5 text-red-400" />
            {mode === 'create' ? 'Report Bug' : 'Link Existing Bug'}
          </DialogTitle>
          <DialogDescription>
            {mode === 'create' 
              ? `Create a new bug linked to "${entityTitle}"`
              : `Link an existing bug to "${entityTitle}"`
            }
          </DialogDescription>
        </DialogHeader>

        {/* Mode Toggle */}
        <div className="flex gap-2 p-1 rounded-lg bg-muted">
          <Button
            variant={mode === 'create' ? 'default' : 'ghost'}
            size="sm"
            className="flex-1"
            onClick={() => setMode('create')}
          >
            <Plus className="w-4 h-4 mr-1" />
            Create New
          </Button>
          <Button
            variant={mode === 'link' ? 'default' : 'ghost'}
            size="sm"
            className="flex-1"
            onClick={() => setMode('link')}
          >
            <Link2 className="w-4 h-4 mr-1" />
            Link Existing
          </Button>
        </div>

        <Separator />

        {mode === 'create' ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="bug-title">Title *</Label>
              <Input
                id="bug-title"
                placeholder="Brief description of the bug"
                value={newBug.title}
                onChange={(e) => setNewBug({ ...newBug, title: e.target.value })}
                data-testid="new-bug-title"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="bug-description">Description *</Label>
              <Textarea
                id="bug-description"
                placeholder="Detailed description of the bug"
                value={newBug.description}
                onChange={(e) => setNewBug({ ...newBug, description: e.target.value })}
                rows={3}
                data-testid="new-bug-description"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="bug-severity">Severity</Label>
              <Select 
                value={newBug.severity} 
                onValueChange={(v) => setNewBug({ ...newBug, severity: v })}
              >
                <SelectTrigger data-testid="new-bug-severity">
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

            <div className="space-y-2">
              <Label htmlFor="bug-steps">Steps to Reproduce</Label>
              <Textarea
                id="bug-steps"
                placeholder="1. Go to...\n2. Click on...\n3. See error"
                value={newBug.steps_to_reproduce}
                onChange={(e) => setNewBug({ ...newBug, steps_to_reproduce: e.target.value })}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bug-expected">Expected Behavior</Label>
                <Textarea
                  id="bug-expected"
                  placeholder="What should happen"
                  value={newBug.expected_behavior}
                  onChange={(e) => setNewBug({ ...newBug, expected_behavior: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bug-actual">Actual Behavior</Label>
                <Textarea
                  id="bug-actual"
                  placeholder="What actually happens"
                  value={newBug.actual_behavior}
                  onChange={(e) => setNewBug({ ...newBug, actual_behavior: e.target.value })}
                  rows={2}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Select Bug to Link</Label>
              <Select value={selectedBugId} onValueChange={setSelectedBugId}>
                <SelectTrigger data-testid="select-existing-bug">
                  <SelectValue placeholder="Choose a bug..." />
                </SelectTrigger>
                <SelectContent>
                  {existingBugs.length === 0 ? (
                    <div className="p-2 text-sm text-muted-foreground text-center">
                      No unlinked bugs available
                    </div>
                  ) : (
                    existingBugs.map((bug) => (
                      <SelectItem key={bug.bug_id} value={bug.bug_id}>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={`text-xs ${SEVERITY_CONFIG[bug.severity]?.color}`}>
                            {bug.severity}
                          </Badge>
                          <span className="truncate">{bug.title}</span>
                        </div>
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            {selectedBugId && existingBugs.find(b => b.bug_id === selectedBugId) && (
              <Card className="bg-muted/50">
                <CardContent className="p-4">
                  <p className="text-sm font-medium">
                    {existingBugs.find(b => b.bug_id === selectedBugId)?.title}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {existingBugs.find(b => b.bug_id === selectedBugId)?.description?.slice(0, 100)}...
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={mode === 'create' ? handleCreateBug : handleLinkBug}
            disabled={loading || (mode === 'create' ? !newBug.title.trim() : !selectedBugId)}
            data-testid="submit-bug-link"
          >
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {mode === 'create' ? 'Create & Link' : 'Link Bug'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Main LinkedBugs component to embed in entity pages
export const LinkedBugs = ({ 
  entityType, // 'epic', 'feature', 'story'
  entityId,
  entityTitle,
  collapsed = false,
  onBugChange 
}) => {
  const navigate = useNavigate();
  const [bugs, setBugs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [expanded, setExpanded] = useState(!collapsed);

  const loadBugs = useCallback(async () => {
    if (!entityId) return;
    
    setLoading(true);
    try {
      const { data } = await bugAPI.getForEntity(entityType, entityId);
      setBugs(data || []);
    } catch (err) {
      console.error('Failed to load linked bugs:', err);
    } finally {
      setLoading(false);
    }
  }, [entityType, entityId]);

  useEffect(() => {
    loadBugs();
  }, [loadBugs]);

  const handleUnlink = async (bug) => {
    // Find the link for this entity
    try {
      const { data: links } = await bugAPI.getLinks(bug.bug_id);
      const link = links.find(l => l.entity_type === entityType && l.entity_id === entityId);
      
      if (link) {
        await bugAPI.removeLink(bug.bug_id, link.link_id);
        toast.success('Bug unlinked');
        loadBugs();
        onBugChange?.();
      }
    } catch (err) {
      toast.error('Failed to unlink bug');
    }
  };

  const handleViewBug = (bugId) => {
    navigate(`/bugs?highlight=${bugId}`);
  };

  const handleBugCreated = () => {
    loadBugs();
    onBugChange?.();
  };

  const handleBugLinked = () => {
    loadBugs();
    onBugChange?.();
  };

  // Count by severity
  const criticalCount = bugs.filter(b => b.severity === 'critical').length;
  const majorCount = bugs.filter(b => b.severity === 'major').length;
  const openCount = bugs.filter(b => !['resolved', 'closed'].includes(b.status)).length;

  return (
    <Card className="border-red-500/20" data-testid={`linked-bugs-${entityType}-${entityId}`}>
      <CardHeader className="pb-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center">
              <Bug className="w-4 h-4 text-red-400" />
            </div>
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                Linked Bugs
                {bugs.length > 0 && (
                  <Badge variant="outline" className="text-xs">
                    {bugs.length}
                  </Badge>
                )}
              </CardTitle>
              {bugs.length > 0 && openCount > 0 && (
                <CardDescription className="text-xs flex items-center gap-2 mt-0.5">
                  {criticalCount > 0 && (
                    <span className="text-red-400">{criticalCount} critical</span>
                  )}
                  {majorCount > 0 && (
                    <span className="text-orange-400">{majorCount} major</span>
                  )}
                  <span className="text-muted-foreground">{openCount} open</span>
                </CardDescription>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => { e.stopPropagation(); setShowCreateDialog(true); }}
              className="text-red-400 border-red-500/30 hover:bg-red-500/10"
              data-testid="add-bug-link-btn"
            >
              <Plus className="w-4 h-4 mr-1" />
              Report Bug
            </Button>
            <ChevronRight className={`w-4 h-4 text-muted-foreground transition-transform ${expanded ? 'rotate-90' : ''}`} />
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="pt-0">
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : bugs.length === 0 ? (
            <div className="text-center py-6 text-muted-foreground">
              <Bug className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No bugs linked to this {entityType}</p>
              <Button
                variant="link"
                size="sm"
                onClick={() => setShowCreateDialog(true)}
                className="text-red-400 mt-1"
              >
                Report a bug
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {bugs.map((bug) => (
                <BugCard
                  key={bug.bug_id}
                  bug={bug}
                  onUnlink={handleUnlink}
                  onView={handleViewBug}
                />
              ))}
            </div>
          )}
        </CardContent>
      )}

      <CreateLinkBugDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        entityType={entityType}
        entityId={entityId}
        entityTitle={entityTitle}
        onBugCreated={handleBugCreated}
        onBugLinked={handleBugLinked}
      />
    </Card>
  );
};

export default LinkedBugs;
