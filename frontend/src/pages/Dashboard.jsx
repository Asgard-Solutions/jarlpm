import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { epicAPI, subscriptionAPI, llmProviderAPI, authAPI } from '@/api';
import { useAuthStore, useSubscriptionStore, useLLMProviderStore, useThemeStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import ThemeToggle from '@/components/ThemeToggle';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { 
  Plus, Settings, LogOut, Loader2, 
  AlertCircle, FileText, Clock, Lock, Trash2, Bug, BookOpen, Users, Upload
} from 'lucide-react';

const STAGE_COLORS = {
  problem_capture: 'bg-primary/20 text-primary border-primary',
  problem_confirmed: 'bg-success/20 text-success border-success',
  outcome_capture: 'bg-warning/20 text-warning border-warning',
  outcome_confirmed: 'bg-success/20 text-success border-success',
  epic_drafted: 'bg-primary/20 text-primary border-primary',
  epic_locked: 'bg-success/20 text-success border-success',
};

const STAGE_LABELS = {
  problem_capture: 'Problem Capture',
  problem_confirmed: 'Problem Confirmed',
  outcome_capture: 'Outcome Capture',
  outcome_confirmed: 'Outcome Confirmed',
  epic_drafted: 'Epic Draft',
  epic_locked: 'Epic Locked',
};

const Dashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { subscription, isActive, setSubscription } = useSubscriptionStore();
  const { activeProvider, setProviders } = useLLMProviderStore();
  const { theme } = useThemeStore();
  
  const [epics, setEpics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewEpicDialog, setShowNewEpicDialog] = useState(false);
  const [newEpicTitle, setNewEpicTitle] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Select logo based on theme
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Load subscription status
      const subRes = await subscriptionAPI.getStatus();
      setSubscription(subRes.data);

      // Load LLM providers
      const provRes = await llmProviderAPI.list();
      setProviders(provRes.data);

      // Load epics
      const epicsRes = await epicAPI.list();
      setEpics(epicsRes.data.epics);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  }, [setSubscription, setProviders]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateEpic = async () => {
    if (!newEpicTitle.trim()) return;
    
    setCreating(true);
    try {
      const response = await epicAPI.create(newEpicTitle.trim());
      navigate(`/epic/${response.data.epic_id}`);
    } catch (error) {
      console.error('Failed to create epic:', error);
    } finally {
      setCreating(false);
      setShowNewEpicDialog(false);
      setNewEpicTitle('');
    }
  };

  const handleDeleteEpic = async (epicId) => {
    setDeleting(true);
    try {
      await epicAPI.delete(epicId);
      setEpics(epics.filter(e => e.epic_id !== epicId));
    } catch (error) {
      console.error('Failed to delete epic:', error);
    } finally {
      setDeleting(false);
      setDeleteConfirm(null);
    }
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout();
      logout();
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
      logout();
      navigate('/');
    }
  };

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <img 
                src={logoSrc} 
                alt="JarlPM" 
                className="h-9 w-auto"
              />
              <span className="text-xl font-bold text-foreground">JarlPM</span>
            </div>
            <div className="flex items-center gap-4">
              <Button 
                variant="outline"
                size="sm"
                onClick={() => navigate('/personas')}
                className="text-violet-400 border-violet-500/30 hover:bg-violet-500/10"
                data-testid="personas-nav-btn"
              >
                <Users className="w-4 h-4 mr-2" />
                Personas
              </Button>
              <Button 
                variant="outline"
                size="sm"
                onClick={() => navigate('/stories')}
                className="text-primary border-primary/30 hover:bg-primary/10"
                data-testid="stories-nav-btn"
              >
                <BookOpen className="w-4 h-4 mr-2" />
                Stories
              </Button>
              <Button 
                variant="outline"
                size="sm"
                onClick={() => navigate('/bugs')}
                className="text-red-400 border-red-500/30 hover:bg-red-500/10"
                data-testid="bugs-nav-btn"
              >
                <Bug className="w-4 h-4 mr-2" />
                Bugs
              </Button>
              <span className="text-sm text-muted-foreground">{user?.name || user?.email}</span>
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
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={handleLogout}
                className="text-muted-foreground hover:text-foreground"
                data-testid="logout-btn"
              >
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Alerts */}
        {!isActive && (
          <Card className="bg-warning/10 border-warning/30 mb-6">
            <CardContent className="flex items-center gap-4 py-4">
              <AlertCircle className="w-6 h-6 text-warning" />
              <div className="flex-1">
                <p className="text-foreground font-medium">Subscription Required</p>
                <p className="text-muted-foreground text-sm">Subscribe to use AI features</p>
              </div>
              <Button 
                onClick={() => navigate('/settings')}
                className="bg-warning hover:bg-warning/90 text-warning-foreground"
                data-testid="subscribe-cta-btn"
              >
                Subscribe Now
              </Button>
            </CardContent>
          </Card>
        )}

        {!activeProvider && isActive && (
          <Card className="bg-primary/10 border-primary/30 mb-6">
            <CardContent className="flex items-center gap-4 py-4">
              <AlertCircle className="w-6 h-6 text-primary" />
              <div className="flex-1">
                <p className="text-foreground font-medium">No LLM Provider Configured</p>
                <p className="text-muted-foreground text-sm">Add your API key to use AI features</p>
              </div>
              <Button 
                onClick={() => navigate('/settings')}
                variant="outline"
                className="border-primary text-primary hover:bg-primary/10"
                data-testid="add-llm-cta-btn"
              >
                Add API Key
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Title & Actions */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Your Epics</h1>
            <p className="text-muted-foreground mt-1">Create and manage product epics</p>
          </div>
          <Button 
            onClick={() => setShowNewEpicDialog(true)}
            className="bg-primary hover:bg-primary/90 text-primary-foreground"
            data-testid="new-epic-btn"
          >
            <Plus className="w-4 h-4 mr-2" /> New Epic
          </Button>
        </div>

        {/* Epics Grid */}
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        ) : epics.length === 0 ? (
          <Card className="bg-card border-border">
            <CardContent className="py-20 text-center">
              <FileText className="w-16 h-16 text-muted-foreground/50 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-foreground mb-2">No Epics Yet</h3>
              <p className="text-muted-foreground mb-6">Create your first epic to get started</p>
              <Button 
                onClick={() => setShowNewEpicDialog(true)}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
                data-testid="empty-new-epic-btn"
              >
                <Plus className="w-4 h-4 mr-2" /> Create Epic
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {epics.map((epic) => {
              const isLocked = epic.current_stage === 'epic_locked';
              return (
                <Card 
                  key={epic.epic_id} 
                  className="bg-card border-border hover:border-primary/30 transition-all cursor-pointer group"
                  onClick={() => navigate(isLocked ? `/epic/${epic.epic_id}/review` : `/epic/${epic.epic_id}`)}
                  data-testid={`epic-card-${epic.epic_id}`}
                >
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start">
                      <CardTitle className="text-foreground line-clamp-2">{epic.title}</CardTitle>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteConfirm(epic);
                        }}
                        data-testid={`delete-epic-${epic.epic_id}`}
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <Badge 
                        variant="outline" 
                        className={`${STAGE_COLORS[epic.current_stage]} border`}
                      >
                        {epic.current_stage.includes('confirmed') || epic.current_stage === 'epic_locked' ? (
                          <Lock className="w-3 h-3 mr-1" />
                        ) : null}
                        {STAGE_LABELS[epic.current_stage]}
                      </Badge>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(epic.updated_at)}
                      </span>
                    </div>
                    {epic.snapshot?.problem_statement && (
                      <p className="text-sm text-muted-foreground mt-3 line-clamp-2">
                        {epic.snapshot.problem_statement}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </main>

      {/* New Epic Dialog */}
      <Dialog open={showNewEpicDialog} onOpenChange={setShowNewEpicDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-foreground">Create New Epic</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Give your epic a clear, descriptive title
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="e.g., User Authentication System"
            value={newEpicTitle}
            onChange={(e) => setNewEpicTitle(e.target.value)}
            className="bg-background border-border text-foreground"
            onKeyDown={(e) => e.key === 'Enter' && handleCreateEpic()}
            data-testid="new-epic-title-input"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowNewEpicDialog(false)}>Cancel</Button>
            <Button 
              onClick={handleCreateEpic} 
              disabled={!newEpicTitle.trim() || creating}
              className="bg-primary hover:bg-primary/90 text-primary-foreground"
              data-testid="create-epic-confirm-btn"
            >
              {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Create Epic
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <AlertDialogContent className="bg-card border-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground">Delete Epic?</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              This will permanently delete &quot;{deleteConfirm?.title}&quot; and all its data. 
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-border text-foreground">Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={() => handleDeleteEpic(deleteConfirm?.epic_id)}
              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
              disabled={deleting}
              data-testid="confirm-delete-btn"
            >
              {deleting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Dashboard;
