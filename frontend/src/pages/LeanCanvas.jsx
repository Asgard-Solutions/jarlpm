import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { 
  Loader2, LayoutGrid, Save, Download, Plus, ArrowLeft,
  Users, Lightbulb, DollarSign, Target, Gift, BarChart3,
  Zap, TrendingUp, ShieldCheck, Sparkles, Calendar, Edit3
} from 'lucide-react';
import { epicAPI, leanCanvasAPI } from '@/api';

const CANVAS_SECTIONS = [
  { 
    id: 'problem', 
    title: 'Problem', 
    icon: Target,
    placeholder: 'Top 3 problems you are solving',
    color: 'text-red-500',
    bgColor: 'bg-red-500/10'
  },
  { 
    id: 'solution', 
    title: 'Solution', 
    icon: Lightbulb,
    placeholder: 'Top 3 features that solve the problems',
    color: 'text-green-500',
    bgColor: 'bg-green-500/10'
  },
  { 
    id: 'unique_value', 
    title: 'Unique Value Proposition', 
    icon: Gift,
    placeholder: 'Single, clear, compelling message that states why you are different',
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10'
  },
  { 
    id: 'unfair_advantage', 
    title: 'Unfair Advantage', 
    icon: ShieldCheck,
    placeholder: 'Something that cannot be easily copied or bought',
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10'
  },
  { 
    id: 'customer_segments', 
    title: 'Customer Segments', 
    icon: Users,
    placeholder: 'Target customers and users',
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10'
  },
  { 
    id: 'key_metrics', 
    title: 'Key Metrics', 
    icon: BarChart3,
    placeholder: 'Key activities you measure',
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-500/10'
  },
  { 
    id: 'channels', 
    title: 'Channels', 
    icon: Zap,
    placeholder: 'Path to customers',
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10'
  },
  { 
    id: 'cost_structure', 
    title: 'Cost Structure', 
    icon: DollarSign,
    placeholder: 'Customer acquisition costs, distribution costs, hosting, people, etc.',
    color: 'text-pink-500',
    bgColor: 'bg-pink-500/10'
  },
  { 
    id: 'revenue_streams', 
    title: 'Revenue Streams', 
    icon: TrendingUp,
    placeholder: 'Revenue model, lifetime value, revenue, gross margin',
    color: 'text-emerald-500',
    bgColor: 'bg-emerald-500/10'
  },
];

const LeanCanvas = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [canvasList, setCanvasList] = useState([]);
  const [availableEpics, setAvailableEpics] = useState([]);
  
  // Editor state
  const [view, setView] = useState('list'); // list | editor
  const [selectedEpicId, setSelectedEpicId] = useState('');
  const [selectedEpicTitle, setSelectedEpicTitle] = useState('');
  const [canvas, setCanvas] = useState({});
  const [canvasSource, setCanvasSource] = useState('manual');
  const [hasExistingCanvas, setHasExistingCanvas] = useState(false);
  const [loadingCanvas, setLoadingCanvas] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  
  // Create new dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newCanvasEpic, setNewCanvasEpic] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [canvasRes, epicsRes] = await Promise.all([
        leanCanvasAPI.list(),
        leanCanvasAPI.getEpicsWithoutCanvas()
      ]);
      setCanvasList(canvasRes.data?.canvases || []);
      setAvailableEpics(epicsRes.data?.epics || []);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load Lean Canvases');
    } finally {
      setLoading(false);
    }
  };

  const openCanvas = async (epicId, epicTitle) => {
    setSelectedEpicId(epicId);
    setSelectedEpicTitle(epicTitle);
    setLoadingCanvas(true);
    setView('editor');
    
    try {
      const response = await leanCanvasAPI.get(epicId);
      const data = response.data;
      
      if (data.exists && data.canvas) {
        setCanvas(data.canvas);
        setCanvasSource(data.source || 'manual');
        setHasExistingCanvas(true);
      } else {
        // Pre-populate from epic if available
        const epicRes = await epicAPI.get(epicId);
        const epic = epicRes.data;
        setCanvas({
          problem: epic?.problem_statement || '',
          solution: epic?.vision || '',
          unique_value: epic?.desired_outcome || '',
          customer_segments: epic?.target_users || '',
          key_metrics: epic?.success_metrics || '',
          unfair_advantage: '',
          channels: '',
          cost_structure: '',
          revenue_streams: '',
        });
        setCanvasSource('manual');
        setHasExistingCanvas(false);
      }
    } catch (error) {
      console.error('Failed to load canvas:', error);
      setCanvas({});
      setHasExistingCanvas(false);
    } finally {
      setLoadingCanvas(false);
    }
  };

  const createNewCanvas = async () => {
    if (!newCanvasEpic) {
      toast.error('Please select an epic');
      return;
    }
    
    const epic = availableEpics.find(e => e.epic_id === newCanvasEpic);
    setShowCreateDialog(false);
    setNewCanvasEpic('');
    
    await openCanvas(newCanvasEpic, epic?.title || 'New Canvas');
  };

  const backToList = () => {
    setView('list');
    setSelectedEpicId('');
    setSelectedEpicTitle('');
    setCanvas({});
    setHasExistingCanvas(false);
    loadData(); // Refresh list
  };

  const handleSectionChange = (sectionId, value) => {
    setCanvas(prev => ({
      ...prev,
      [sectionId]: value
    }));
  };

  const handleSave = async () => {
    if (!selectedEpicId) return;
    
    setSaving(true);
    try {
      await leanCanvasAPI.save(selectedEpicId, canvas, canvasSource);
      setHasExistingCanvas(true);
      toast.success('Lean Canvas saved!');
    } catch (error) {
      console.error('Failed to save canvas:', error);
      toast.error('Failed to save Lean Canvas');
    } finally {
      setSaving(false);
    }
  };

  const handleAIGenerate = async () => {
    if (!selectedEpicId) return;
    
    setGenerating(true);
    try {
      const response = await leanCanvasAPI.generate(selectedEpicId);
      const generatedCanvas = response.data.canvas;
      
      setCanvas({
        problem: generatedCanvas.problem || '',
        solution: generatedCanvas.solution || '',
        unique_value: generatedCanvas.unique_value || '',
        unfair_advantage: generatedCanvas.unfair_advantage || '',
        customer_segments: generatedCanvas.customer_segments || '',
        key_metrics: generatedCanvas.key_metrics || '',
        channels: generatedCanvas.channels || '',
        cost_structure: generatedCanvas.cost_structure || '',
        revenue_streams: generatedCanvas.revenue_streams || '',
      });
      
      setCanvasSource('ai_generated');
      toast.success('Lean Canvas generated! Click Save to persist.');
    } catch (error) {
      console.error('Failed to generate:', error);
      toast.error(error.response?.data?.detail || 'Failed to generate');
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = () => {
    const fullContent = `# Lean Canvas: ${selectedEpicTitle}\n\n${CANVAS_SECTIONS.map(section => 
      `## ${section.title}\n${canvas[section.id] || '_Not defined_'}\n`
    ).join('\n')}`;
    
    const blob = new Blob([fullContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lean-canvas-${selectedEpicTitle.replace(/\s+/g, '-').toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  };

  // LIST VIEW
  if (view === 'list') {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Lean Canvas</h1>
            <p className="text-muted-foreground mt-1">Business model canvases for your epics</p>
          </div>
          
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button disabled={availableEpics.length === 0} data-testid="create-new-canvas">
                <Plus className="h-4 w-4 mr-2" />
                Create New
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Lean Canvas</DialogTitle>
                <DialogDescription>
                  Select an epic to create a Lean Canvas for.
                </DialogDescription>
              </DialogHeader>
              <div className="py-4">
                <Select value={newCanvasEpic} onValueChange={setNewCanvasEpic}>
                  <SelectTrigger data-testid="select-epic-for-canvas">
                    <SelectValue placeholder="Select an epic..." />
                  </SelectTrigger>
                  <SelectContent>
                    {availableEpics.map((epic) => (
                      <SelectItem key={epic.epic_id} value={epic.epic_id}>
                        {epic.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {availableEpics.length === 0 && (
                  <p className="text-sm text-muted-foreground mt-2">
                    All epics already have a Lean Canvas.
                  </p>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
                <Button onClick={createNewCanvas} disabled={!newCanvasEpic}>Create</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
          </div>
        ) : canvasList.length === 0 ? (
          <Card className="bg-card border-border">
            <CardContent className="p-12 text-center">
              <LayoutGrid className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-xl font-medium text-foreground mb-2">
                No Lean Canvases Yet
              </h3>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                Create your first Lean Canvas to map out your business model.
              </p>
              {availableEpics.length > 0 ? (
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Canvas
                </Button>
              ) : (
                <Button onClick={() => navigate('/dashboard')}>
                  Create an Epic First
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {canvasList.map((item) => (
              <Card 
                key={item.canvas_id} 
                className="bg-card border-border hover:border-primary/50 cursor-pointer transition-colors"
                onClick={() => openCanvas(item.epic_id, item.epic_title)}
                data-testid={`canvas-card-${item.epic_id}`}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-lg">{item.epic_title}</CardTitle>
                    <Badge variant="outline" className={item.source === 'ai_generated' ? 'bg-purple-500/10 text-purple-500' : ''}>
                      {item.source === 'ai_generated' ? 'AI Generated' : 'Manual'}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Calendar className="h-4 w-4" />
                      {formatDate(item.updated_at)}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  // EDITOR VIEW
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={backToList}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{selectedEpicTitle}</h1>
            <p className="text-muted-foreground">Lean Canvas</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            onClick={handleAIGenerate}
            disabled={generating}
          >
            {generating ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4 mr-2" />
            )}
            AI Generate
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button onClick={handleSave} disabled={saving || loadingCanvas}>
            {saving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            {hasExistingCanvas ? 'Update' : 'Save'}
          </Button>
          {hasExistingCanvas && (
            <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30">
              Saved
            </Badge>
          )}
        </div>
      </div>

      {/* Canvas Grid */}
      {loadingCanvas ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Row 1: Problem, Solution, UVP, Unfair Advantage, Customer Segments */}
          <div className="lg:col-span-2 lg:row-span-2 space-y-4">
            <CanvasSection
              section={CANVAS_SECTIONS[0]}
              value={canvas.problem || ''}
              onChange={(v) => handleSectionChange('problem', v)}
            />
            <CanvasSection
              section={CANVAS_SECTIONS[1]}
              value={canvas.solution || ''}
              onChange={(v) => handleSectionChange('solution', v)}
            />
          </div>
          
          <div className="lg:row-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[2]}
              value={canvas.unique_value || ''}
              onChange={(v) => handleSectionChange('unique_value', v)}
              tall
            />
          </div>
          
          <div className="lg:col-span-2 lg:row-span-2 space-y-4">
            <CanvasSection
              section={CANVAS_SECTIONS[3]}
              value={canvas.unfair_advantage || ''}
              onChange={(v) => handleSectionChange('unfair_advantage', v)}
            />
            <CanvasSection
              section={CANVAS_SECTIONS[4]}
              value={canvas.customer_segments || ''}
              onChange={(v) => handleSectionChange('customer_segments', v)}
            />
          </div>
          
          {/* Row 2: Key Metrics, Channels, Cost Structure, Revenue */}
          <div className="lg:col-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[5]}
              value={canvas.key_metrics || ''}
              onChange={(v) => handleSectionChange('key_metrics', v)}
            />
          </div>
          
          <div className="lg:col-span-1">
            {/* Spacer */}
          </div>
          
          <div className="lg:col-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[6]}
              value={canvas.channels || ''}
              onChange={(v) => handleSectionChange('channels', v)}
            />
          </div>
          
          <div className="lg:col-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[7]}
              value={canvas.cost_structure || ''}
              onChange={(v) => handleSectionChange('cost_structure', v)}
            />
          </div>
          
          <div className="lg:col-span-1">
            {/* Spacer */}
          </div>
          
          <div className="lg:col-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[8]}
              value={canvas.revenue_streams || ''}
              onChange={(v) => handleSectionChange('revenue_streams', v)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

const CanvasSection = ({ section, value, onChange, tall = false }) => {
  const Icon = section.icon;
  
  return (
    <Card className={`bg-card border-border ${tall ? 'h-full' : ''}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <div className={`p-1.5 rounded ${section.bgColor}`}>
            <Icon className={`h-3.5 w-3.5 ${section.color}`} />
          </div>
          {section.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={section.placeholder}
          className={`resize-none ${tall ? 'min-h-[200px]' : 'min-h-[100px]'}`}
        />
      </CardContent>
    </Card>
  );
};

export default LeanCanvas;
