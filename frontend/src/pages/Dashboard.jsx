import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { epicAPI, subscriptionAPI, llmProviderAPI, authAPI } from '@/api';
import { useAuthStore, useSubscriptionStore, useLLMProviderStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
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
  Layers, Plus, Settings, LogOut, Loader2, 
  AlertCircle, FileText, Clock, Lock, Trash2 
} from 'lucide-react';

const STAGE_COLORS = {
  problem_capture: 'bg-blue-500/20 text-blue-400 border-blue-500',
  problem_confirmed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500',
  outcome_capture: 'bg-amber-500/20 text-amber-400 border-amber-500',
  outcome_confirmed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500',
  epic_drafted: 'bg-purple-500/20 text-purple-400 border-purple-500',
  epic_locked: 'bg-emerald-500/20 text-emerald-400 border-emerald-500',
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
  
  const [epics, setEpics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewEpicDialog, setShowNewEpicDialog] = useState(false);
  const [newEpicTitle, setNewEpicTitle] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
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
  };

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
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Layers className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">JarlPM</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-400">{user?.name || user?.email}</span>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => navigate('/settings')}
                data-testid="settings-btn"
              >
                <Settings className="w-5 h-5 text-slate-400" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={handleLogout}
                data-testid="logout-btn"
              >
                <LogOut className="w-5 h-5 text-slate-400" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Alerts */}
        {!isActive && (
          <Card className="bg-amber-500/10 border-amber-500/50 mb-6">
            <CardContent className="flex items-center gap-4 py-4">
              <AlertCircle className="w-6 h-6 text-amber-400" />
              <div className="flex-1">
                <p className="text-amber-200 font-medium">Subscription Required</p>
                <p className="text-amber-300/70 text-sm">Subscribe to use AI features</p>
              </div>
              <Button 
                onClick={() => navigate('/settings')}
                className="bg-amber-500 hover:bg-amber-600 text-black"
                data-testid="subscribe-cta-btn"
              >
                Subscribe Now
              </Button>
            </CardContent>
          </Card>
        )}

        {!activeProvider && isActive && (
          <Card className="bg-blue-500/10 border-blue-500/50 mb-6">
            <CardContent className="flex items-center gap-4 py-4">
              <AlertCircle className="w-6 h-6 text-blue-400" />
              <div className="flex-1">
                <p className="text-blue-200 font-medium">No LLM Provider Configured</p>
                <p className="text-blue-300/70 text-sm">Add your API key to use AI features</p>
              </div>
              <Button 
                onClick={() => navigate('/settings')}
                variant="outline"
                className="border-blue-500 text-blue-400 hover:bg-blue-500/20"
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
            <h1 className="text-3xl font-bold text-white">Your Epics</h1>
            <p className="text-slate-400 mt-1">Create and manage product epics</p>
          </div>
          <Button 
            onClick={() => setShowNewEpicDialog(true)}
            className="bg-indigo-600 hover:bg-indigo-700"
            data-testid="new-epic-btn"
          >
            <Plus className="w-4 h-4 mr-2" /> New Epic
          </Button>
        </div>

        {/* Epics Grid */}
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          </div>
        ) : epics.length === 0 ? (
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="py-20 text-center">
              <FileText className="w-16 h-16 text-slate-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">No Epics Yet</h3>
              <p className="text-slate-400 mb-6">Create your first epic to get started</p>
              <Button 
                onClick={() => setShowNewEpicDialog(true)}
                className="bg-indigo-600 hover:bg-indigo-700"
                data-testid="empty-new-epic-btn"
              >
                <Plus className="w-4 h-4 mr-2" /> Create Epic
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {epics.map((epic) => (
              <Card 
                key={epic.epic_id} 
                className="bg-slate-900/50 border-slate-800 hover:border-indigo-500/50 transition-all cursor-pointer group"
                onClick={() => navigate(`/epic/${epic.epic_id}`)}
                data-testid={`epic-card-${epic.epic_id}`}
              >
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-white line-clamp-2">{epic.title}</CardTitle>
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
                      <Trash2 className="w-4 h-4 text-red-400" />
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
                    <span className="text-xs text-slate-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDate(epic.updated_at)}
                    </span>
                  </div>
                  {epic.snapshot?.problem_statement && (
                    <p className="text-sm text-slate-400 mt-3 line-clamp-2">
                      {epic.snapshot.problem_statement}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>

      {/* New Epic Dialog */}
      <Dialog open={showNewEpicDialog} onOpenChange={setShowNewEpicDialog}>
        <DialogContent className="bg-slate-900 border-slate-800">
          <DialogHeader>
            <DialogTitle className="text-white">Create New Epic</DialogTitle>
            <DialogDescription className="text-slate-400">
              Give your epic a clear, descriptive title
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="e.g., User Authentication System"
            value={newEpicTitle}
            onChange={(e) => setNewEpicTitle(e.target.value)}
            className="bg-slate-800 border-slate-700 text-white"
            onKeyDown={(e) => e.key === 'Enter' && handleCreateEpic()}
            data-testid="new-epic-title-input"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowNewEpicDialog(false)}>Cancel</Button>
            <Button 
              onClick={handleCreateEpic} 
              disabled={!newEpicTitle.trim() || creating}
              className="bg-indigo-600 hover:bg-indigo-700"
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
        <AlertDialogContent className="bg-slate-900 border-slate-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">Delete Epic?</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              This will permanently delete "{deleteConfirm?.title}" and all its data. 
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-slate-700 text-slate-300">Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={() => handleDeleteEpic(deleteConfirm?.epic_id)}
              className="bg-red-600 hover:bg-red-700"
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
