import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { 
  Loader2, LayoutGrid, Save, Download, Plus, Trash2, 
  Users, Lightbulb, DollarSign, Target, Gift, BarChart3,
  Zap, TrendingUp, ShieldCheck, Sparkles
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
  const [loadingCanvas, setLoadingCanvas] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [epics, setEpics] = useState([]);
  const [selectedEpic, setSelectedEpic] = useState('');
  const [canvas, setCanvas] = useState({});
  const [canvasSource, setCanvasSource] = useState('manual');
  const [hasExistingCanvas, setHasExistingCanvas] = useState(false);

  useEffect(() => {
    loadEpics();
  }, []);

  useEffect(() => {
    if (selectedEpic) {
      loadCanvasForEpic();
    }
  }, [selectedEpic]);

  const loadEpics = async () => {
    try {
      const response = await epicAPI.list();
      setEpics(response.data?.epics || []);
    } catch (error) {
      console.error('Failed to load epics:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCanvasForEpic = async () => {
    setLoadingCanvas(true);
    try {
      const response = await leanCanvasAPI.get(selectedEpic);
      const data = response.data;
      
      if (data.exists && data.canvas) {
        // Load saved canvas from database
        setCanvas(data.canvas);
        setCanvasSource(data.source || 'manual');
        setHasExistingCanvas(true);
      } else {
        // Pre-populate from epic data
        const epic = epics.find(e => e.epic_id === selectedEpic);
        if (epic) {
          setCanvas({
            problem: epic.problem_statement || '',
            solution: epic.vision || '',
            unique_value: epic.desired_outcome || '',
            customer_segments: epic.target_users || '',
            key_metrics: epic.success_metrics || '',
            unfair_advantage: '',
            channels: '',
            cost_structure: '',
            revenue_streams: '',
          });
        } else {
          setCanvas({});
        }
        setCanvasSource('manual');
        setHasExistingCanvas(false);
      }
    } catch (error) {
      console.error('Failed to load canvas:', error);
      // Fallback to empty canvas
      setCanvas({});
      setHasExistingCanvas(false);
    } finally {
      setLoadingCanvas(false);
    }
  };

  const handleSectionChange = (sectionId, value) => {
    setCanvas(prev => ({
      ...prev,
      [sectionId]: value
    }));
  };

  const handleSave = async () => {
    if (!selectedEpic) return;
    
    setSaving(true);
    try {
      await leanCanvasAPI.save(selectedEpic, canvas, canvasSource);
      setHasExistingCanvas(true);
      toast.success('Lean Canvas saved to database!');
    } catch (error) {
      console.error('Failed to save canvas:', error);
      toast.error('Failed to save Lean Canvas');
    } finally {
      setSaving(false);
    }
  };

  const handleExport = () => {
    const epic = epics.find(e => e.epic_id === selectedEpic);
    const content = CANVAS_SECTIONS.map(section => 
      `## ${section.title}\n${canvas[section.id] || '_Not defined_'}\n`
    ).join('\n');
    
    const fullContent = `# Lean Canvas: ${epic?.title || 'Untitled'}\n\n${content}\n\n---\n*Generated by JarlPM*`;
    
    const blob = new Blob([fullContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `LeanCanvas_${epic?.title?.replace(/\s+/g, '_') || 'canvas'}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleAIGenerate = async () => {
    if (!selectedEpic) {
      toast.error('Please select an epic first');
      return;
    }
    
    setGenerating(true);
    try {
      const response = await leanCanvasAPI.generate(selectedEpic);
      const generatedCanvas = response.data.canvas;
      
      // Update canvas with generated data
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
      
      toast.success('Lean Canvas generated successfully!');
    } catch (error) {
      console.error('Failed to generate lean canvas:', error);
      const message = error.response?.data?.detail || 'Failed to generate Lean Canvas';
      toast.error(message);
    } finally {
      setGenerating(false);
    }
  };

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
          <h1 className="text-3xl font-bold text-foreground">Lean Canvas</h1>
          <p className="text-muted-foreground mt-1">Build your business model canvas</p>
        </div>
      </div>

      {/* Epic Selector & Actions */}
      <Card className="bg-card border-border">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1">
              <Select value={selectedEpic} onValueChange={setSelectedEpic}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select an epic for this canvas" />
                </SelectTrigger>
                <SelectContent>
                  {epics.map((epic) => (
                    <SelectItem key={epic.epic_id} value={epic.epic_id}>
                      {epic.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedEpic && (
              <div className="flex gap-2">
                <Button 
                  onClick={handleAIGenerate} 
                  disabled={generating}
                  className="bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 text-white"
                >
                  {generating ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  {generating ? 'Generating...' : 'AI Generate'}
                </Button>
                <Button variant="outline" onClick={handleExport}>
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Save
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Canvas Grid */}
      {selectedEpic ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Row 1: Problem, Solution, UVP, Unfair Advantage, Customer Segments */}
          <div className="lg:col-span-2 lg:row-span-2 space-y-4">
            {/* Problem */}
            <CanvasSection
              section={CANVAS_SECTIONS[0]}
              value={canvas.problem || ''}
              onChange={(v) => handleSectionChange('problem', v)}
            />
            {/* Solution */}
            <CanvasSection
              section={CANVAS_SECTIONS[1]}
              value={canvas.solution || ''}
              onChange={(v) => handleSectionChange('solution', v)}
            />
          </div>
          
          {/* UVP - Center */}
          <div className="lg:row-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[2]}
              value={canvas.unique_value || ''}
              onChange={(v) => handleSectionChange('unique_value', v)}
              tall
            />
          </div>
          
          <div className="lg:col-span-2 lg:row-span-2 space-y-4">
            {/* Unfair Advantage */}
            <CanvasSection
              section={CANVAS_SECTIONS[3]}
              value={canvas.unfair_advantage || ''}
              onChange={(v) => handleSectionChange('unfair_advantage', v)}
            />
            {/* Customer Segments */}
            <CanvasSection
              section={CANVAS_SECTIONS[4]}
              value={canvas.customer_segments || ''}
              onChange={(v) => handleSectionChange('customer_segments', v)}
            />
          </div>

          {/* Row 2: Key Metrics, Channels */}
          <div className="lg:col-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[5]}
              value={canvas.key_metrics || ''}
              onChange={(v) => handleSectionChange('key_metrics', v)}
            />
          </div>
          
          <div className="lg:col-span-1">
            {/* Spacer for layout */}
          </div>
          
          <div className="lg:col-span-2">
            <CanvasSection
              section={CANVAS_SECTIONS[6]}
              value={canvas.channels || ''}
              onChange={(v) => handleSectionChange('channels', v)}
            />
          </div>

          {/* Row 3: Cost Structure, Revenue Streams */}
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
      ) : (
        <Card className="bg-card border-border">
          <CardContent className="p-12 text-center">
            <LayoutGrid className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-xl font-medium text-foreground mb-2">
              Select an Epic to Start
            </h3>
            <p className="text-muted-foreground mb-6 max-w-md mx-auto">
              Choose an epic from the dropdown above to create or edit its Lean Canvas.
            </p>
            {epics.length === 0 && (
              <Button onClick={() => navigate('/dashboard')}>
                Create Your First Epic
              </Button>
            )}
          </CardContent>
        </Card>
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
          className={`bg-background border-border text-sm resize-none ${tall ? 'min-h-[200px]' : 'min-h-[100px]'}`}
        />
      </CardContent>
    </Card>
  );
};

export default LeanCanvas;
