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
import { LinkedBugs } from '@/components/LinkedBugs';
import { useAuthStore } from '@/store';
import { userStoryAPI } from '@/api';
import { BookOpen, Plus, Search, ArrowLeft, Settings,
  CheckCircle2, Clock, Edit3, Loader2, Trash2,
  Sparkles, ArrowUpDown, User, Send, Bot, UserIcon,
  Lock, FileText, ChevronRight, History
} from 'lucide-react';
import PokerSessionHistory from '@/components/PokerSessionHistory';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';

// Constants
const STAGE_CONFIG = {
  draft: { label: 'Draft', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30', icon: Edit3 },
  refining: { label: 'Refining', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', icon: Edit3 },
  approved: { label: 'Approved', color: 'bg-green-500/20 text-green-400 border-green-500/30', icon: Lock },
};

const POINTS_CONFIG = {
  1: { label: '1 pt', color: 'text-blue-400' },
  2: { label: '2 pts', color: 'text-blue-400' },
  3: { label: '3 pts', color: 'text-yellow-400' },
  5: { label: '5 pts', color: 'text-orange-400' },
  8: { label: '8 pts', color: 'text-red-400' },
};

const Stories = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [theme, setTheme] = useState('light');
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  // State
  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filters
  const [stageFilter, setStageFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('created_at:desc');
  
  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showAICreateDialog, setShowAICreateDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [showRefineDialog, setShowRefineDialog] = useState(false);
  const [selectedStory, setSelectedStory] = useState(null);
  
  // Create form state
  const [createForm, setCreateForm] = useState({
    title: '',
    persona: '',
    action: '',
    benefit: '',
    acceptance_criteria: [''],
    story_points: null,
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
  
  // Refine chat state
  const [refineMessages, setRefineMessages] = useState([]);
  const [refineInput, setRefineInput] = useState('');
  const [refineSending, setRefineSending] = useState(false);
  const [refineStreamingContent, setRefineStreamingContent] = useState('');
  const refineChatRef = useRef(null);
  
  // Action states
  const [approving, setApproving] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  // Load stories
  const loadStories = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (stageFilter !== 'all') params.stage = stageFilter;
      
      const response = await userStoryAPI.listStandalone(params);
      setStories(response.data || []);
    } catch (err) {
      setError('Failed to load stories');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [stageFilter]);

  useEffect(() => {
    if (user) loadStories();
  }, [user, loadStories]);

  // Filtered and sorted stories (client-side)
  const filteredStories = stories
    .filter(story => 
      !searchQuery || 
      story.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      story.story_text?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      story.persona?.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      const [field, order] = sortBy.split(':');
      const aVal = a[field];
      const bVal = b[field];
      if (order === 'desc') {
        return new Date(bVal) - new Date(aVal);
      }
      return new Date(aVal) - new Date(bVal);
    });

  // Create story manually
  const handleCreate = async () => {
    if (!createForm.title.trim() || !createForm.persona.trim() || 
        !createForm.action.trim() || !createForm.benefit.trim()) return;
    
    try {
      setCreating(true);
      const data = {
        title: createForm.title,
        persona: createForm.persona,
        action: createForm.action,
        benefit: createForm.benefit,
        acceptance_criteria: createForm.acceptance_criteria.filter(c => c.trim()),
        source: 'manual',
      };
      if (createForm.story_points) data.story_points = parseInt(createForm.story_points);
      
      await userStoryAPI.createStandalone(data);
      setShowCreateDialog(false);
      setCreateForm({
        title: '',
        persona: '',
        action: '',
        benefit: '',
        acceptance_criteria: [''],
        story_points: null,
      });
      loadStories();
    } catch (err) {
      setError('Failed to create story');
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  // AI-assisted story creation
  const startAIChat = () => {
    setAiMessages([]);
    setAiInput('');
    setAiProposal(null);
    setAiStreamingContent('');
    setShowAICreateDialog(true);
    
    // Auto-start conversation
    setTimeout(() => {
      sendAIMessage('Hi, I want to create a user story.');
    }, 300);
  };

  const sendAIMessage = async (message = aiInput) => {
    if (!message.trim() || aiSending) return;
    
    const userMessage = { role: 'user', content: message.trim() };
    const newMessages = [...aiMessages, userMessage];
    setAiMessages(newMessages);
    setAiInput('');
    setAiSending(true);
    setAiStreamingContent('');
    
    try {
      const response = await userStoryAPI.aiChat(message.trim(), newMessages.slice(0, -1));
      
      if (!response.ok) {
        throw new Error('Failed to get AI response');
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let proposal = null;
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') {
                fullContent += data.content;
                setAiStreamingContent(fullContent);
              } else if (data.type === 'done') {
                if (data.proposal) {
                  proposal = data.proposal;
                  setAiProposal(data.proposal);
                }
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
      
      // Add assistant message
      setAiMessages(prev => [...prev, { role: 'assistant', content: fullContent }]);
      setAiStreamingContent('');
      
      // Scroll to bottom
      setTimeout(() => {
        aiChatRef.current?.scrollTo({ top: aiChatRef.current.scrollHeight, behavior: 'smooth' });
      }, 100);
      
    } catch (err) {
      console.error('AI chat error:', err);
      setError('Failed to communicate with AI');
    } finally {
      setAiSending(false);
    }
  };

  const createFromAIProposal = async () => {
    if (!aiProposal) return;
    
    try {
      setCreatingFromProposal(true);
      await userStoryAPI.createFromProposal(aiProposal);
      setShowAICreateDialog(false);
      setAiMessages([]);
      setAiProposal(null);
      loadStories();
    } catch (err) {
      setError('Failed to create story from proposal');
      console.error(err);
    } finally {
      setCreatingFromProposal(false);
    }
  };

  // Open refine dialog
  const openRefineDialog = (story) => {
    setSelectedStory(story);
    setRefineMessages([]);
    setRefineInput('');
    setRefineStreamingContent('');
    setShowRefineDialog(true);
  };

  // Send refine message
  const sendRefineMessage = async () => {
    if (!refineInput.trim() || refineSending || !selectedStory) return;
    
    const userMessage = { role: 'user', content: refineInput.trim() };
    const newMessages = [...refineMessages, userMessage];
    setRefineMessages(newMessages);
    setRefineInput('');
    setRefineSending(true);
    setRefineStreamingContent('');
    
    try {
      const response = await userStoryAPI.chatStandalone(selectedStory.story_id, refineInput.trim());
      
      if (!response.ok) {
        throw new Error('Failed to get AI response');
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') {
                fullContent += data.content;
                setRefineStreamingContent(fullContent);
              } else if (data.type === 'story_updated') {
                // Reload story
                const updated = await userStoryAPI.getStandalone(selectedStory.story_id);
                setSelectedStory(updated.data);
                loadStories();
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
      
      // Add assistant message
      setRefineMessages(prev => [...prev, { role: 'assistant', content: fullContent }]);
      setRefineStreamingContent('');
      
      // Scroll to bottom
      setTimeout(() => {
        refineChatRef.current?.scrollTo({ top: refineChatRef.current.scrollHeight, behavior: 'smooth' });
      }, 100);
      
    } catch (err) {
      console.error('Refine chat error:', err);
      setError('Failed to communicate with AI');
    } finally {
      setRefineSending(false);
    }
  };

  // Approve story
  const handleApprove = async (storyId) => {
    try {
      setApproving(true);
      await userStoryAPI.approveStandalone(storyId);
      loadStories();
      if (selectedStory?.story_id === storyId) {
        const response = await userStoryAPI.getStandalone(storyId);
        setSelectedStory(response.data);
      }
      setShowRefineDialog(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve story');
    } finally {
      setApproving(false);
    }
  };

  // Delete story
  const handleDelete = async (storyId) => {
    if (!window.confirm('Are you sure you want to delete this story?')) return;
    
    try {
      setDeleting(true);
      await userStoryAPI.deleteStandalone(storyId);
      setShowDetailDialog(false);
      setSelectedStory(null);
      loadStories();
    } catch (err) {
      setError('Failed to delete story');
    } finally {
      setDeleting(false);
    }
  };

  // View story details
  const openStoryDetail = async (story) => {
    setSelectedStory(story);
    setShowDetailDialog(true);
  };

  // Add acceptance criteria field
  const addAcceptanceCriteria = () => {
    setCreateForm({
      ...createForm,
      acceptance_criteria: [...createForm.acceptance_criteria, '']
    });
  };

  // Update acceptance criteria
  const updateAcceptanceCriteria = (index, value) => {
    const updated = [...createForm.acceptance_criteria];
    updated[index] = value;
    setCreateForm({ ...createForm, acceptance_criteria: updated });
  };

  // Remove acceptance criteria
  const removeAcceptanceCriteria = (index) => {
    const updated = createForm.acceptance_criteria.filter((_, i) => i !== index);
    setCreateForm({ ...createForm, acceptance_criteria: updated.length ? updated : [''] });
  };

  if (!user) {
    navigate('/');
    return null;
  }

  return (
    <div className="flex flex-col overflow-hidden -m-6" style={{ height: 'calc(100vh - 4rem)' }} data-testid="stories-page">
      {/* Page Title Bar */}
      <div className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
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
              <span className="text-lg font-semibold text-foreground">User Stories</span>
            </div>
            <div className="flex items-center gap-2">
              <Button 
                onClick={startAIChat}
                className="bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 text-white"
                data-testid="ai-new-story-btn"
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Create with AI
              </Button>
              <Button 
                variant="outline"
                onClick={() => setShowCreateDialog(true)}
                data-testid="manual-new-story-btn"
              >
                <Plus className="w-4 h-4 mr-2" />
                Manual
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex-shrink-0 border-b border-border bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search stories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="search-input"
              />
            </div>
            
            {/* Stage Filter */}
            <Select value={stageFilter} onValueChange={setStageFilter}>
              <SelectTrigger className="w-[140px]" data-testid="stage-filter">
                <SelectValue placeholder="Stage" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Stages</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="refining">Refining</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort */}
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[160px]" data-testid="sort-select">
                <ArrowUpDown className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="created_at:desc">Recently Created</SelectItem>
                <SelectItem value="updated_at:desc">Recently Updated</SelectItem>
                <SelectItem value="created_at:asc">Oldest First</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Stories List */}
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
          ) : filteredStories.length === 0 ? (
            <EmptyState
              icon={BookOpen}
              title="No standalone stories"
              description={
                searchQuery || stageFilter !== 'all'
                  ? 'No stories match your filters. Try widening your search.'
                  : 'Create your first standalone user story to start tracking work.'
              }
              actionLabel="Create with AI"
              onAction={startAIChat}
              secondaryLabel="Manual"
              onSecondary={() => setShowCreateDialog(true)}
            />
          ) : (
            <div className="space-y-3">
              {filteredStories.map((story) => (
                <StoryCard 
                  key={story.story_id} 
                  story={story} 
                  onClick={() => openStoryDetail(story)}
                  onRefine={() => openRefineDialog(story)}
                  onApprove={() => handleApprove(story.story_id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Manual Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-primary" />
              Create User Story
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                placeholder="Brief descriptive title..."
                value={createForm.title}
                onChange={(e) => setCreateForm({...createForm, title: e.target.value})}
                data-testid="story-title-input"
              />
            </div>
            
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="persona">As a... (Persona) *</Label>
                <Input
                  id="persona"
                  placeholder="e.g., logged-in user"
                  value={createForm.persona}
                  onChange={(e) => setCreateForm({...createForm, persona: e.target.value})}
                  data-testid="story-persona-input"
                />
              </div>
              <div className="col-span-2">
                <Label htmlFor="action">I want to... (Action) *</Label>
                <Input
                  id="action"
                  placeholder="e.g., view my order history"
                  value={createForm.action}
                  onChange={(e) => setCreateForm({...createForm, action: e.target.value})}
                  data-testid="story-action-input"
                />
              </div>
            </div>
            
            <div>
              <Label htmlFor="benefit">So that... (Benefit) *</Label>
              <Input
                id="benefit"
                placeholder="e.g., I can track my past purchases"
                value={createForm.benefit}
                onChange={(e) => setCreateForm({...createForm, benefit: e.target.value})}
                data-testid="story-benefit-input"
              />
            </div>
            
            {createForm.persona && createForm.action && createForm.benefit && (
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-sm text-foreground italic">
                  &quot;As a <strong>{createForm.persona}</strong>, I want to <strong>{createForm.action}</strong> so that <strong>{createForm.benefit}</strong>.&quot;
                </p>
              </div>
            )}
            
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Acceptance Criteria (Given/When/Then)</Label>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={addAcceptanceCriteria}
                  type="button"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add
                </Button>
              </div>
              {createForm.acceptance_criteria.map((criteria, idx) => (
                <div key={idx} className="flex gap-2 mb-2">
                  <Textarea
                    placeholder="Given [context], When [action], Then [expected result]"
                    value={criteria}
                    onChange={(e) => updateAcceptanceCriteria(idx, e.target.value)}
                    rows={2}
                    className="flex-1"
                  />
                  {createForm.acceptance_criteria.length > 1 && (
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => removeAcceptanceCriteria(idx)}
                      type="button"
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            
            <div>
              <Label>Story Points (Optional)</Label>
              <Select 
                value={createForm.story_points?.toString() || ''} 
                onValueChange={(v) => setCreateForm({...createForm, story_points: v ? parseInt(v) : null})}
              >
                <SelectTrigger data-testid="story-points-select">
                  <SelectValue placeholder="Estimate complexity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 - Trivial</SelectItem>
                  <SelectItem value="2">2 - Small</SelectItem>
                  <SelectItem value="3">3 - Medium</SelectItem>
                  <SelectItem value="5">5 - Large</SelectItem>
                  <SelectItem value="8">8 - Complex</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreate}
              disabled={creating || !createForm.title.trim() || !createForm.persona.trim() || !createForm.action.trim() || !createForm.benefit.trim()}
              className="bg-primary hover:bg-primary/90"
              data-testid="create-story-submit-btn"
            >
              {creating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <BookOpen className="w-4 h-4 mr-2" />}
              Create Story
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI-Assisted Story Creation Dialog */}
      <Dialog open={showAICreateDialog} onOpenChange={setShowAICreateDialog}>
        <DialogContent className="max-w-3xl h-[80vh] flex flex-col p-0">
          <DialogHeader className="p-4 pb-2 border-b border-border">
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-500" />
              Create Story with AI Assistant
            </DialogTitle>
            <p className="text-sm text-muted-foreground">
              Describe your user story and I&apos;ll help you structure it properly.
            </p>
          </DialogHeader>
          
          {/* Chat Area */}
          <div 
            ref={aiChatRef}
            className="flex-1 overflow-y-auto p-4 space-y-4"
            data-testid="ai-chat-area"
          >
            {aiMessages.map((msg, idx) => (
              <div 
                key={idx} 
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-violet-400" />
                  </div>
                )}
                <div className={`max-w-[80%] rounded-lg p-3 ${
                  msg.role === 'user' 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-muted text-foreground'
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                </div>
                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                    <UserIcon className="w-4 h-4 text-primary" />
                  </div>
                )}
              </div>
            ))}
            
            {/* Streaming response */}
            {aiStreamingContent && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-violet-400" />
                </div>
                <div className="max-w-[80%] rounded-lg p-3 bg-muted text-foreground">
                  <p className="text-sm whitespace-pre-wrap">{aiStreamingContent}</p>
                </div>
              </div>
            )}
            
            {/* AI typing indicator */}
            {aiSending && !aiStreamingContent && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-violet-400" />
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                  </div>
                </div>
              </div>
            )}
          </div>
          
          {/* Proposal Preview */}
          {aiProposal && (
            <div className="mx-4 mb-2 p-4 bg-success/10 border border-success/30 rounded-lg">
              <h4 className="font-semibold text-foreground flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-4 h-4 text-success" />
                User Story Ready
              </h4>
              <div className="space-y-2 text-sm">
                <p><span className="text-muted-foreground">Title:</span> <span className="text-foreground font-medium">{aiProposal.title}</span></p>
                <p className="italic text-foreground">&quot;As a {aiProposal.persona}, I want to {aiProposal.action} so that {aiProposal.benefit}.&quot;</p>
                {aiProposal.story_points && (
                  <p><span className="text-muted-foreground">Story Points:</span> {aiProposal.story_points}</p>
                )}
              </div>
              <div className="flex gap-2 mt-3">
                <Button 
                  onClick={createFromAIProposal}
                  disabled={creatingFromProposal}
                  className="bg-success hover:bg-success/90"
                  data-testid="create-from-proposal-btn"
                >
                  {creatingFromProposal ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
                  Create Story
                </Button>
                <Button 
                  variant="outline"
                  onClick={() => setAiProposal(null)}
                >
                  Continue Refining
                </Button>
              </div>
            </div>
          )}
          
          {/* Input Area */}
          <div className="p-4 border-t border-border">
            <form 
              onSubmit={(e) => { e.preventDefault(); sendAIMessage(); }}
              className="flex gap-2"
            >
              <Input
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                placeholder="Describe your user story or answer the AI's questions..."
                disabled={aiSending}
                data-testid="ai-chat-input"
                className="flex-1"
              />
              <Button 
                type="submit"
                disabled={!aiInput.trim() || aiSending}
                className="bg-violet-500 hover:bg-violet-600"
                data-testid="ai-send-btn"
              >
                {aiSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </form>
          </div>
        </DialogContent>
      </Dialog>

      {/* Story Detail Dialog */}
      {selectedStory && (
        <StoryDetailDialog
          story={selectedStory}
          open={showDetailDialog}
          onClose={() => {
            setShowDetailDialog(false);
            setSelectedStory(null);
          }}
          onRefine={() => {
            setShowDetailDialog(false);
            openRefineDialog(selectedStory);
          }}
          onApprove={() => handleApprove(selectedStory.story_id)}
          onDelete={() => handleDelete(selectedStory.story_id)}
          approving={approving}
          deleting={deleting}
        />
      )}

      {/* Refine Dialog */}
      {selectedStory && (
        <RefineDialog
          story={selectedStory}
          open={showRefineDialog}
          onClose={() => {
            setShowRefineDialog(false);
            setSelectedStory(null);
            setRefineMessages([]);
          }}
          messages={refineMessages}
          streamingContent={refineStreamingContent}
          input={refineInput}
          setInput={setRefineInput}
          sending={refineSending}
          onSend={sendRefineMessage}
          onApprove={() => handleApprove(selectedStory.story_id)}
          approving={approving}
          chatRef={refineChatRef}
        />
      )}
    </div>
  );
};

// Story Card Component
const StoryCard = ({ story, onClick, onRefine, onApprove }) => {
  const stageConfig = STAGE_CONFIG[story.current_stage] || STAGE_CONFIG.draft;
  const StageIcon = stageConfig.icon;
  const isApproved = story.current_stage === 'approved';

  return (
    <Card 
      className="cursor-pointer hover:border-primary/50 transition-colors"
      onClick={onClick}
      data-testid={`story-card-${story.story_id}`}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Badge variant="outline" className={stageConfig.color}>
                <StageIcon className="w-3 h-3 mr-1" />
                {stageConfig.label}
              </Badge>
              {story.story_points && (
                <Badge variant="outline" className={`bg-muted ${POINTS_CONFIG[story.story_points]?.color || ''}`}>
                  {POINTS_CONFIG[story.story_points]?.label || `${story.story_points} pts`}
                </Badge>
              )}
              <Badge variant="outline" className="bg-muted/50 text-muted-foreground">
                <FileText className="w-3 h-3 mr-1" />
                Standalone
              </Badge>
            </div>
            
            <h3 className="font-medium text-foreground mb-1 truncate">{story.title || 'Untitled Story'}</h3>
            <p className="text-sm text-muted-foreground line-clamp-2 italic">&quot;{story.story_text}&quot;</p>
            
            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(story.updated_at).toLocaleDateString()}
              </span>
              <span className="flex items-center gap-1">
                <User className="w-3 h-3" />
                {story.persona}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
            {!isApproved && (
              <>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={onRefine}
                  data-testid={`refine-story-${story.story_id}`}
                >
                  <Sparkles className="w-4 h-4 mr-1" />
                  Refine
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={onApprove}
                  className="text-green-500 border-green-500/30 hover:bg-green-500/10"
                  data-testid={`approve-story-${story.story_id}`}
                >
                  <Lock className="w-4 h-4 mr-1" />
                  Approve
                </Button>
              </>
            )}
            <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Story Detail Dialog Component
const StoryDetailDialog = ({ story, open, onClose, onRefine, onApprove, onDelete, approving, deleting }) => {
  const stageConfig = STAGE_CONFIG[story.current_stage] || STAGE_CONFIG.draft;
  const isApproved = story.current_stage === 'approved';

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2 text-xl">
                <BookOpen className="w-5 h-5 text-primary" />
                {story.title || 'User Story'}
              </DialogTitle>
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className={stageConfig.color}>
                  {stageConfig.label}
                </Badge>
                {story.story_points && (
                  <Badge variant="outline" className={`bg-muted ${POINTS_CONFIG[story.story_points]?.color || ''}`}>
                    {story.story_points} points
                  </Badge>
                )}
                <PokerSessionHistory 
                  storyId={story.story_id} 
                  storyTitle={story.title}
                />
              </div>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          <div className="p-4 bg-muted/50 rounded-lg">
            <p className="text-foreground italic">
              &quot;As a <strong>{story.persona}</strong>, I want to <strong>{story.action}</strong> so that <strong>{story.benefit}</strong>.&quot;
            </p>
          </div>
          
          {story.acceptance_criteria?.length > 0 && (
            <div>
              <Label className="text-muted-foreground">Acceptance Criteria</Label>
              <ul className="mt-2 space-y-2">
                {story.acceptance_criteria.map((criteria, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-foreground">
                    <CheckCircle2 className="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
                    {criteria}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border">
            <div>
              <Label className="text-muted-foreground">Created</Label>
              <p className="text-foreground mt-1">{new Date(story.created_at).toLocaleString()}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Last Updated</Label>
              <p className="text-foreground mt-1">{new Date(story.updated_at).toLocaleString()}</p>
            </div>
          </div>
          
          {story.approved_at && (
            <div className="pt-2 border-t border-border">
              <Label className="text-muted-foreground">Approved At</Label>
              <p className="text-foreground mt-1">{new Date(story.approved_at).toLocaleString()}</p>
            </div>
          )}
          
          {/* Linked Bugs */}
          <div className="pt-2 border-t border-border">
            <LinkedBugs
              entityType="story"
              entityId={story.story_id}
              entityTitle={story.title || story.story_text?.slice(0, 50)}
              collapsed={false}
            />
          </div>
        </div>

        <DialogFooter className="border-t border-border pt-4">
          <div className="flex items-center justify-between w-full">
            {!isApproved && (
              <Button 
                variant="destructive" 
                size="sm"
                onClick={onDelete}
                disabled={deleting}
                data-testid="delete-story-btn"
              >
                {deleting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
                Delete
              </Button>
            )}
            
            <div className="flex items-center gap-2 ml-auto">
              {!isApproved && (
                <>
                  <Button variant="outline" onClick={onRefine}>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Refine with AI
                  </Button>
                  <Button 
                    onClick={onApprove}
                    disabled={approving}
                    className="bg-success hover:bg-success/90"
                    data-testid="approve-story-dialog-btn"
                  >
                    {approving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Lock className="w-4 h-4 mr-2" />}
                    Approve & Lock
                  </Button>
                </>
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

// Refine Dialog Component
const RefineDialog = ({ story, open, onClose, messages, streamingContent, input, setInput, sending, onSend, onApprove, approving, chatRef }) => {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[85vh] flex flex-col p-0">
        <DialogHeader className="p-4 pb-2 border-b border-border">
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-500" />
            Refine User Story
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            Chat with AI to improve this story. Changes will be applied automatically.
          </p>
        </DialogHeader>
        
        <div className="flex flex-1 overflow-hidden">
          {/* Story Preview Sidebar */}
          <div className="w-80 border-r border-border p-4 overflow-y-auto bg-muted/30">
            <h4 className="font-semibold text-foreground mb-3">Current Story</h4>
            <div className="space-y-3 text-sm">
              <div>
                <Label className="text-muted-foreground text-xs">Title</Label>
                <p className="text-foreground font-medium">{story.title || 'Untitled'}</p>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <p className="text-foreground italic text-xs">
                  &quot;As a <strong>{story.persona}</strong>, I want to <strong>{story.action}</strong> so that <strong>{story.benefit}</strong>.&quot;
                </p>
              </div>
              {story.acceptance_criteria?.length > 0 && (
                <div>
                  <Label className="text-muted-foreground text-xs">Acceptance Criteria</Label>
                  <ul className="mt-1 space-y-1">
                    {story.acceptance_criteria.map((c, i) => (
                      <li key={i} className="text-xs text-foreground flex items-start gap-1">
                        <CheckCircle2 className="w-3 h-3 text-success mt-0.5 flex-shrink-0" />
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {story.story_points && (
                <div>
                  <Label className="text-muted-foreground text-xs">Story Points</Label>
                  <p className="text-foreground">{story.story_points}</p>
                </div>
              )}
            </div>
            
            <div className="mt-6 pt-4 border-t border-border">
              <Button 
                onClick={onApprove}
                disabled={approving}
                className="w-full bg-success hover:bg-success/90"
                data-testid="approve-from-refine-btn"
              >
                {approving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Lock className="w-4 h-4 mr-2" />}
                Approve & Lock
              </Button>
            </div>
          </div>
          
          {/* Chat Area */}
          <div className="flex-1 flex flex-col">
            <div 
              ref={chatRef}
              className="flex-1 overflow-y-auto p-4 space-y-4"
              data-testid="refine-chat-area"
            >
              {messages.length === 0 && !streamingContent && (
                <div className="text-center text-muted-foreground py-8">
                  <Sparkles className="w-8 h-8 mx-auto mb-2 text-violet-400" />
                  <p>Ask the AI to help refine this story.</p>
                  <p className="text-sm mt-1">Try: &quot;Make the acceptance criteria more specific&quot;</p>
                </div>
              )}
              
              {messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                      <Bot className="w-4 h-4 text-violet-400" />
                    </div>
                  )}
                  <div className={`max-w-[80%] rounded-lg p-3 ${
                    msg.role === 'user' 
                      ? 'bg-primary text-primary-foreground' 
                      : 'bg-muted text-foreground'
                  }`}>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                      <UserIcon className="w-4 h-4 text-primary" />
                    </div>
                  )}
                </div>
              ))}
              
              {streamingContent && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-violet-400" />
                  </div>
                  <div className="max-w-[80%] rounded-lg p-3 bg-muted text-foreground">
                    <p className="text-sm whitespace-pre-wrap">{streamingContent}</p>
                  </div>
                </div>
              )}
              
              {sending && !streamingContent && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-violet-400" />
                  </div>
                  <div className="bg-muted rounded-lg p-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Input Area */}
            <div className="p-4 border-t border-border">
              <form 
                onSubmit={(e) => { e.preventDefault(); onSend(); }}
                className="flex gap-2"
              >
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask AI to refine the story..."
                  disabled={sending}
                  data-testid="refine-chat-input"
                  className="flex-1"
                />
                <Button 
                  type="submit"
                  disabled={!input.trim() || sending}
                  className="bg-violet-500 hover:bg-violet-600"
                  data-testid="refine-send-btn"
                >
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </form>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default Stories;
