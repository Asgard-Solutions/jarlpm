import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { integrationsAPI } from '@/api';
import {
  Loader2, ExternalLink, AlertCircle, CheckCircle, 
  ArrowRight, Link2, ChevronDown, ChevronRight, FileText
} from 'lucide-react';

const PushToLinearModal = ({ isOpen, onClose, epicId, epicTitle }) => {
  const [loading, setLoading] = useState(false);
  const [integrationStatus, setIntegrationStatus] = useState(null);
  const [teams, setTeams] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState('');
  const [selectedProject, setSelectedProject] = useState('');
  const [pushScope, setPushScope] = useState('epic_features_stories');
  const [includeBugs, setIncludeBugs] = useState(false);
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushResults, setPushResults] = useState(null);

  // Load integration status and teams on mount
  useEffect(() => {
    if (isOpen) {
      loadIntegrationData();
    }
  }, [isOpen]);

  // Load projects when team changes
  useEffect(() => {
    if (selectedTeam) {
      loadProjects(selectedTeam);
    } else {
      setProjects([]);
      setSelectedProject('');
    }
  }, [selectedTeam]);

  // Load preview when options change
  useEffect(() => {
    if (selectedTeam && isOpen && !pushResults) {
      loadPreview();
    }
  }, [selectedTeam, pushScope, includeBugs, isOpen, pushResults]);

  const loadIntegrationData = async () => {
    setLoading(true);
    try {
      const [statusRes, teamsRes] = await Promise.all([
        integrationsAPI.getProviderStatus('linear'),
        integrationsAPI.getLinearTeams().catch(() => ({ data: { teams: [] } }))
      ]);
      
      setIntegrationStatus(statusRes.data);
      setTeams(teamsRes.data.teams || []);
      
      // Auto-select default team if set
      if (statusRes.data?.default_team?.id) {
        setSelectedTeam(statusRes.data.default_team.id);
      }
      if (statusRes.data?.default_project?.id) {
        setSelectedProject(statusRes.data.default_project.id);
      }
    } catch (error) {
      console.error('Failed to load integration data:', error);
      if (error.response?.status === 402) {
        toast.error('Active subscription required for integrations');
      } else if (error.response?.status === 400) {
        setIntegrationStatus({ connected: false });
      }
    } finally {
      setLoading(false);
    }
  };

  const loadProjects = async (teamId) => {
    try {
      const res = await integrationsAPI.getLinearProjects(teamId);
      setProjects(res.data.projects || []);
    } catch (error) {
      console.error('Failed to load projects:', error);
    }
  };

  const loadPreview = async () => {
    if (!selectedTeam) return;
    
    setLoadingPreview(true);
    try {
      const res = await integrationsAPI.previewPush('linear', {
        epic_id: epicId,
        push_scope: pushScope,
        include_bugs: includeBugs
      });
      setPreview(res.data);
    } catch (error) {
      console.error('Failed to load preview:', error);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handlePush = async () => {
    if (!selectedTeam) {
      toast.error('Please select a team');
      return;
    }

    setPushing(true);
    try {
      const res = await integrationsAPI.push('linear', {
        epic_id: epicId,
        team_id: selectedTeam,
        project_id: selectedProject || null,
        push_scope: pushScope,
        include_bugs: includeBugs,
        dry_run: false
      });
      
      setPushResults(res.data);
      
      const created = res.data.created?.length || 0;
      const updated = res.data.updated?.length || 0;
      const errors = res.data.errors?.length || 0;
      
      if (errors === 0) {
        toast.success(`Successfully pushed ${created + updated} items to Linear`);
      } else {
        toast.warning(`Pushed with ${errors} errors. ${created} created, ${updated} updated.`);
      }
    } catch (error) {
      console.error('Push failed:', error);
      toast.error(error.response?.data?.detail || 'Failed to push to Linear');
    } finally {
      setPushing(false);
    }
  };

  const handleClose = () => {
    setPreview(null);
    setPushResults(null);
    onClose();
  };

  const scopeOptions = [
    { value: 'epic_only', label: 'Epic Only', description: 'Just the epic itself' },
    { value: 'epic_features', label: 'Epic + Features', description: 'Epic and its features' },
    { value: 'epic_features_stories', label: 'Full Hierarchy', description: 'Epic, features, and stories' },
  ];

  if (loading) {
    return (
      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className="bg-nordic-bg-secondary border-nordic-border">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-nordic-accent" />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  if (!integrationStatus?.connected) {
    return (
      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className="bg-nordic-bg-secondary border-nordic-border">
          <DialogHeader>
            <DialogTitle className="text-nordic-text-primary">Push to Linear</DialogTitle>
          </DialogHeader>
          <div className="py-6 text-center">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 text-amber-500" />
            <h3 className="text-lg font-medium text-nordic-text-primary mb-2">Linear Not Connected</h3>
            <p className="text-sm text-nordic-text-muted mb-4">
              Connect your Linear workspace in Settings to push items.
            </p>
            <Button
              onClick={() => {
                handleClose();
                window.location.href = '/settings?tab=integrations';
              }}
              className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
            >
              Go to Settings
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="bg-nordic-bg-secondary border-nordic-border max-w-2xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="text-nordic-text-primary flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-[#5E6AD2] flex items-center justify-center">
              <svg viewBox="0 0 100 100" className="w-4 h-4 text-white" fill="currentColor">
                <path d="M1.22541 61.5228c-.2225-.9485.90748-1.5459 1.59638-.857L39.3342 97.1782c.6889.6889.0915 1.8189-.857 1.5765C20.8 94.1102 5.95513 79.2002 1.22541 61.5228ZM.0222626 45.9876C-.077182 46.6422.387617 47.2239 1.04521 47.3005c16.9076 1.9666 31.9987 11.4328 41.0064 25.1052 1.0186 1.5445 3.302.8691 3.3451-.9911.0423-1.8237.0638-3.6541.0638-5.4903 0-36.8177-29.8487-66.6665-66.66657-66.6665-1.83593 0-3.66607.02185-5.49023.0645-1.86018.04289-2.53569 2.32647-.99128 3.34495C86.3328 12.9984 95.799 28.0895 97.7657 45.0064c.0766.6576.6583 1.1224 1.3129 1.0228 36.3254-5.5188 64.2133-35.9725 64.6528-73.2026.0024-.2045-.1662-.3716-.3707-.3692C28.9325 76.4257 0 47.4911.0222626 45.9876Z"/>
              </svg>
            </div>
            Push to Linear
          </DialogTitle>
          <DialogDescription className="text-nordic-text-muted">
            Push &quot;{epicTitle}&quot; to Linear
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh]">
          {pushResults ? (
            // Results View
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-2 text-lg font-medium text-nordic-text-primary">
                <CheckCircle className="w-6 h-6 text-nordic-green" />
                Push Complete
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-nordic-bg-primary rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-nordic-green">{pushResults.created?.length || 0}</div>
                  <div className="text-sm text-nordic-text-muted">Created</div>
                </div>
                <div className="bg-nordic-bg-primary rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-nordic-accent">{pushResults.updated?.length || 0}</div>
                  <div className="text-sm text-nordic-text-muted">Updated</div>
                </div>
                <div className="bg-nordic-bg-primary rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-red-500">{pushResults.errors?.length || 0}</div>
                  <div className="text-sm text-nordic-text-muted">Errors</div>
                </div>
              </div>

              {/* Links to created/updated items */}
              {pushResults.links && pushResults.links.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Created Issues</Label>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {[...pushResults.created, ...pushResults.updated].map((item, idx) => (
                      <a
                        key={idx}
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 p-2 bg-nordic-bg-primary rounded text-sm hover:bg-nordic-accent/10 transition-colors"
                      >
                        <FileText className="w-4 h-4 text-nordic-text-muted" />
                        <span className="text-nordic-accent font-mono">{item.external_key}</span>
                        <span className="text-nordic-text-muted capitalize">{item.type}</span>
                        <ExternalLink className="w-3 h-3 ml-auto text-nordic-text-muted" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Errors */}
              {pushResults.errors && pushResults.errors.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-red-500">Errors</Label>
                  <div className="space-y-1">
                    {pushResults.errors.map((error, idx) => (
                      <div key={idx} className="p-2 bg-red-500/10 border border-red-500/30 rounded text-sm">
                        <span className="font-medium capitalize">{error.type}</span>: {error.error}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            // Configuration View
            <div className="space-y-4 py-4">
              {/* Team Selection */}
              <div className="space-y-2">
                <Label className="text-nordic-text-secondary">Target Team *</Label>
                <Select value={selectedTeam} onValueChange={setSelectedTeam}>
                  <SelectTrigger className="bg-background border-border text-foreground">
                    <SelectValue placeholder="Select a Linear team" />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border shadow-lg">
                    {teams.map((team) => (
                      <SelectItem key={team.id} value={team.id}>
                        <span className="font-mono text-nordic-accent mr-2">{team.key}</span>
                        {team.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Project Selection (Optional) */}
              {projects.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Project (Optional)</Label>
                  <Select value={selectedProject || '_none_'} onValueChange={(v) => setSelectedProject(v === '_none_' ? '' : v)}>
                    <SelectTrigger className="bg-background border-border text-foreground">
                      <SelectValue placeholder="No project" />
                    </SelectTrigger>
                    <SelectContent className="bg-popover border-border shadow-lg">
                      <SelectItem value="_none_">No project</SelectItem>
                      {projects.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Push Scope */}
              <div className="space-y-2">
                <Label className="text-nordic-text-secondary">Push Scope</Label>
                <div className="grid grid-cols-3 gap-2">
                  {scopeOptions.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => setPushScope(option.value)}
                      className={`p-3 rounded-lg border-2 transition-all text-left ${
                        pushScope === option.value
                          ? 'border-nordic-accent bg-nordic-accent/10'
                          : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
                      }`}
                    >
                      <div className="font-medium text-sm text-nordic-text-primary">{option.label}</div>
                      <div className="text-xs text-nordic-text-muted">{option.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Include Bugs */}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="include-bugs"
                  checked={includeBugs}
                  onCheckedChange={setIncludeBugs}
                />
                <Label htmlFor="include-bugs" className="text-nordic-text-secondary cursor-pointer">
                  Include linked bugs
                </Label>
              </div>

              {/* Preview */}
              {selectedTeam && (
                <div className="space-y-2 border-t border-nordic-border pt-4">
                  <div className="flex items-center justify-between">
                    <Label className="text-nordic-text-secondary">Preview</Label>
                    {loadingPreview && <Loader2 className="w-4 h-4 animate-spin text-nordic-accent" />}
                  </div>
                  
                  {preview && (
                    <div className="space-y-3">
                      <div className="flex gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <Badge className="bg-nordic-green text-white">{preview.totals?.create || 0}</Badge>
                          <span className="text-nordic-text-muted">to create</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Badge className="bg-nordic-accent text-white">{preview.totals?.update || 0}</Badge>
                          <span className="text-nordic-text-muted">to update</span>
                        </div>
                      </div>
                      
                      {/* Preview Items */}
                      <div className="bg-nordic-bg-primary rounded-lg p-3 max-h-48 overflow-y-auto space-y-2">
                        {/* Epic */}
                        {preview.epic && (
                          <div className="flex items-center gap-2 text-sm">
                            <Badge variant="outline" className="text-xs">Epic</Badge>
                            <span className="text-nordic-text-primary truncate">{preview.epic.title}</span>
                            <Badge className={preview.epic.action === 'create' ? 'bg-nordic-green' : 'bg-nordic-accent'}>
                              {preview.epic.action}
                            </Badge>
                          </div>
                        )}
                        
                        {/* Features */}
                        {preview.features?.map((feature, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm pl-4">
                            <ChevronRight className="w-3 h-3 text-nordic-text-muted" />
                            <Badge variant="outline" className="text-xs">Feature</Badge>
                            <span className="text-nordic-text-primary truncate flex-1">{feature.title}</span>
                            <Badge className={feature.action === 'create' ? 'bg-nordic-green' : 'bg-nordic-accent'}>
                              {feature.action}
                            </Badge>
                          </div>
                        ))}
                        
                        {/* Stories count */}
                        {preview.stories?.length > 0 && (
                          <div className="text-xs text-nordic-text-muted pl-8">
                            + {preview.stories.length} stories
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </ScrollArea>

        <DialogFooter className="border-t border-nordic-border pt-4">
          <Button
            variant="outline"
            onClick={handleClose}
            className="border-nordic-border text-nordic-text-secondary"
          >
            {pushResults ? 'Close' : 'Cancel'}
          </Button>
          
          {!pushResults && (
            <Button
              onClick={handlePush}
              disabled={!selectedTeam || pushing}
              className="bg-[#5E6AD2] hover:bg-[#5E6AD2]/90 text-white"
              data-testid="push-to-linear-btn"
            >
              {pushing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Pushing...
                </>
              ) : (
                <>
                  <ArrowRight className="w-4 h-4 mr-2" />
                  Push to Linear
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PushToLinearModal;
