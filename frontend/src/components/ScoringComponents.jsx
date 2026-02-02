import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Slider } from './ui/slider';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Sparkles, Calculator, TrendingUp, Users, Target, Shield, Clock, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { scoringAPI } from '../api';

// MoSCoW Badge Colors
const MOSCOW_COLORS = {
  must_have: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 border-red-300',
  should_have: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 border-orange-300',
  could_have: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 border-blue-300',
  wont_have: 'bg-slate-100 text-slate-600 dark:bg-slate-900/30 dark:text-slate-400 border-slate-300',
};

const MOSCOW_LABELS = {
  must_have: 'Must Have',
  should_have: 'Should Have',
  could_have: 'Could Have',
  wont_have: "Won't Have",
};

const IMPACT_OPTIONS = [
  { value: 0.25, label: 'Minimal (0.25)' },
  { value: 0.5, label: 'Low (0.5)' },
  { value: 1, label: 'Medium (1)' },
  { value: 2, label: 'High (2)' },
  { value: 3, label: 'Massive (3)' },
];

const CONFIDENCE_OPTIONS = [
  { value: 0.5, label: 'Low (50%)' },
  { value: 0.8, label: 'Medium (80%)' },
  { value: 1.0, label: 'High (100%)' },
];

// MoSCoW Badge Component
export const MoSCoWBadge = ({ score, size = 'default' }) => {
  if (!score) return null;
  const colorClass = MOSCOW_COLORS[score] || MOSCOW_COLORS.wont_have;
  const label = MOSCOW_LABELS[score] || score;
  return (
    <Badge variant="outline" className={`${colorClass} ${size === 'sm' ? 'text-xs px-1.5 py-0' : ''}`}>
      {label}
    </Badge>
  );
};

// RICE Score Badge Component
export const RICEBadge = ({ score, size = 'default' }) => {
  if (!score && score !== 0) return null;
  let colorClass = 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
  if (score >= 10) colorClass = 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
  else if (score >= 5) colorClass = 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
  else if (score >= 2) colorClass = 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300';
  
  return (
    <Badge variant="outline" className={`${colorClass} ${size === 'sm' ? 'text-xs px-1.5 py-0' : ''}`}>
      <Calculator className="w-3 h-3 mr-1" />
      RICE: {score.toFixed(1)}
    </Badge>
  );
};

// Combined Scoring Display Component
export const ScoringDisplay = ({ moscow, rice, showLabels = true, size = 'default' }) => {
  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      {moscow && <MoSCoWBadge score={moscow} size={size} />}
      {rice !== null && rice !== undefined && <RICEBadge score={rice} size={size} />}
    </div>
  );
};

// MoSCoW Editor Component
export const MoSCoWEditor = ({ value, onChange, onSuggest, loading = false, disabled = false }) => {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-foreground">MoSCoW Priority</label>
        {onSuggest && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onSuggest}
            disabled={loading || disabled}
            className="text-violet-600 hover:text-violet-700 hover:bg-violet-50 dark:hover:bg-violet-900/20"
          >
            {loading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}
            AI Suggest
          </Button>
        )}
      </div>
      <Select value={value || ''} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select priority..." />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="must_have">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              Must Have
            </span>
          </SelectItem>
          <SelectItem value="should_have">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              Should Have
            </span>
          </SelectItem>
          <SelectItem value="could_have">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              Could Have
            </span>
          </SelectItem>
          <SelectItem value="wont_have">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-slate-400" />
              Won&apos;t Have
            </span>
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
};

// RICE Editor Component
export const RICEEditor = ({ 
  reach, impact, confidence, effort, total,
  onReachChange, onImpactChange, onConfidenceChange, onEffortChange,
  onSuggest, loading = false, disabled = false 
}) => {
  const calculateTotal = () => {
    if (reach && impact && confidence && effort && effort > 0) {
      return ((reach * impact * confidence) / effort).toFixed(2);
    }
    return null;
  };

  const displayTotal = total ?? calculateTotal();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-foreground">RICE Score</label>
        {onSuggest && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onSuggest}
            disabled={loading || disabled}
            className="text-violet-600 hover:text-violet-700 hover:bg-violet-50 dark:hover:bg-violet-900/20"
          >
            {loading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}
            AI Suggest
          </Button>
        )}
      </div>

      {/* RICE Formula Display */}
      <div className="bg-muted/50 rounded-lg p-3 text-center text-sm">
        <span className="font-mono">
          ({reach || '?'} × {impact || '?'} × {confidence || '?'}) / {effort || '?'} = 
          <span className="font-bold text-primary ml-2">{displayTotal || '?'}</span>
        </span>
      </div>

      {/* Reach */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm flex items-center gap-1.5">
            <Users className="w-4 h-4 text-muted-foreground" />
            Reach (1-10)
          </label>
          <span className="text-sm font-medium">{reach || '-'}</span>
        </div>
        <Slider
          value={[reach || 1]}
          min={1}
          max={10}
          step={1}
          onValueChange={(v) => onReachChange(v[0])}
          disabled={disabled}
          className="py-1"
        />
        <p className="text-xs text-muted-foreground">Users affected per time period</p>
      </div>

      {/* Impact */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <Target className="w-4 h-4 text-muted-foreground" />
          <label className="text-sm">Impact</label>
        </div>
        <Select value={impact?.toString() || ''} onValueChange={(v) => onImpactChange(parseFloat(v))} disabled={disabled}>
          <SelectTrigger>
            <SelectValue placeholder="Select impact..." />
          </SelectTrigger>
          <SelectContent>
            {IMPACT_OPTIONS.map(opt => (
              <SelectItem key={opt.value} value={opt.value.toString()}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Confidence */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <Shield className="w-4 h-4 text-muted-foreground" />
          <label className="text-sm">Confidence</label>
        </div>
        <Select value={confidence?.toString() || ''} onValueChange={(v) => onConfidenceChange(parseFloat(v))} disabled={disabled}>
          <SelectTrigger>
            <SelectValue placeholder="Select confidence..." />
          </SelectTrigger>
          <SelectContent>
            {CONFIDENCE_OPTIONS.map(opt => (
              <SelectItem key={opt.value} value={opt.value.toString()}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Effort */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-muted-foreground" />
            Effort (person-months)
          </label>
          <span className="text-sm font-medium">{effort || '-'}</span>
        </div>
        <Slider
          value={[effort || 0.5]}
          min={0.5}
          max={10}
          step={0.5}
          onValueChange={(v) => onEffortChange(v[0])}
          disabled={disabled}
          className="py-1"
        />
        <p className="text-xs text-muted-foreground">0.5 = 2 weeks, 1 = 1 month</p>
      </div>
    </div>
  );
};

// Full Scoring Dialog for Features (MoSCoW + RICE)
export const FeatureScoringDialog = ({ open, onOpenChange, featureId, featureTitle, onUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [scores, setScores] = useState({
    moscow_score: null,
    rice_reach: null,
    rice_impact: null,
    rice_confidence: null,
    rice_effort: null,
    rice_total: null,
  });

  useEffect(() => {
    if (open && featureId) {
      loadScores();
    }
  }, [open, featureId]);

  const loadScores = async () => {
    try {
      const { data } = await scoringAPI.getFeatureScores(featureId);
      setScores({
        moscow_score: data.moscow_score,
        rice_reach: data.rice_reach,
        rice_impact: data.rice_impact,
        rice_confidence: data.rice_confidence,
        rice_effort: data.rice_effort,
        rice_total: data.rice_total,
      });
    } catch (err) {
      console.error('Failed to load scores:', err);
    }
  };

  const handleMoSCoWChange = async (value) => {
    try {
      setLoading(true);
      await scoringAPI.updateFeatureMoSCoW(featureId, value);
      setScores(prev => ({ ...prev, moscow_score: value }));
      toast.success('MoSCoW score updated');
      onUpdate?.();
    } catch (err) {
      toast.error('Failed to update MoSCoW score');
    } finally {
      setLoading(false);
    }
  };

  const handleRICEChange = async (field, value) => {
    const newScores = { ...scores, [field]: value };
    setScores(newScores);
    
    // Auto-save when all RICE fields are filled
    if (newScores.rice_reach && newScores.rice_impact && newScores.rice_confidence && newScores.rice_effort) {
      try {
        setLoading(true);
        await scoringAPI.updateFeatureRICE(featureId, {
          reach: newScores.rice_reach,
          impact: newScores.rice_impact,
          confidence: newScores.rice_confidence,
          effort: newScores.rice_effort,
        });
        const total = ((newScores.rice_reach * newScores.rice_impact * newScores.rice_confidence) / newScores.rice_effort);
        setScores(prev => ({ ...prev, rice_total: total }));
        toast.success('RICE score updated');
        onUpdate?.();
      } catch (err) {
        toast.error('Failed to update RICE score');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleAISuggest = async () => {
    setAiLoading(true);
    try {
      const response = await scoringAPI.suggestFeatureScores(featureId);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        const lines = text.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'suggestion' && data.suggestion) {
                const { moscow, rice } = data.suggestion;
                if (moscow?.score) {
                  await scoringAPI.updateFeatureMoSCoW(featureId, moscow.score);
                  setScores(prev => ({ ...prev, moscow_score: moscow.score }));
                }
                if (rice) {
                  await scoringAPI.updateFeatureRICE(featureId, {
                    reach: rice.reach,
                    impact: rice.impact,
                    confidence: rice.confidence,
                    effort: rice.effort,
                  });
                  const total = ((rice.reach * rice.impact * rice.confidence) / rice.effort);
                  setScores(prev => ({
                    ...prev,
                    rice_reach: rice.reach,
                    rice_impact: rice.impact,
                    rice_confidence: rice.confidence,
                    rice_effort: rice.effort,
                    rice_total: total,
                  }));
                }
                toast.success('AI suggestions applied');
                onUpdate?.();
              } else if (data.type === 'error') {
                toast.error(data.message);
              }
            } catch (e) {}
          }
        }
      }
    } catch (err) {
      toast.error('Failed to get AI suggestions');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-violet-500" />
            Prioritize Feature
          </DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">{featureTitle}</p>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* AI Suggest All Button */}
          <Button
            variant="outline"
            className="w-full border-violet-200 text-violet-600 hover:bg-violet-50 dark:border-violet-800 dark:hover:bg-violet-900/20"
            onClick={handleAISuggest}
            disabled={aiLoading || loading}
          >
            {aiLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            Get AI Suggestions for All Scores
          </Button>

          {/* MoSCoW Section */}
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">MoSCoW Priority</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <MoSCoWEditor
                value={scores.moscow_score}
                onChange={handleMoSCoWChange}
                loading={loading}
                disabled={loading || aiLoading}
              />
            </CardContent>
          </Card>

          {/* RICE Section */}
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">RICE Score</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <RICEEditor
                reach={scores.rice_reach}
                impact={scores.rice_impact}
                confidence={scores.rice_confidence}
                effort={scores.rice_effort}
                total={scores.rice_total}
                onReachChange={(v) => handleRICEChange('rice_reach', v)}
                onImpactChange={(v) => handleRICEChange('rice_impact', v)}
                onConfidenceChange={(v) => handleRICEChange('rice_confidence', v)}
                onEffortChange={(v) => handleRICEChange('rice_effort', v)}
                loading={loading}
                disabled={loading || aiLoading}
              />
            </CardContent>
          </Card>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// RICE-only Dialog for Stories and Bugs
export const RICEScoringDialog = ({ 
  open, onOpenChange, entityId, entityType, entityTitle, onUpdate 
}) => {
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [scores, setScores] = useState({
    rice_reach: null,
    rice_impact: null,
    rice_confidence: null,
    rice_effort: null,
    rice_total: null,
  });

  useEffect(() => {
    if (open && entityId) {
      loadScores();
    }
  }, [open, entityId]);

  const loadScores = async () => {
    try {
      const api = entityType === 'story' ? scoringAPI.getStoryRICE : scoringAPI.getBugRICE;
      const { data } = await api(entityId);
      setScores({
        rice_reach: data.rice_reach,
        rice_impact: data.rice_impact,
        rice_confidence: data.rice_confidence,
        rice_effort: data.rice_effort,
        rice_total: data.rice_total,
      });
    } catch (err) {
      console.error('Failed to load scores:', err);
    }
  };

  const handleRICEChange = async (field, value) => {
    const newScores = { ...scores, [field]: value };
    setScores(newScores);
    
    if (newScores.rice_reach && newScores.rice_impact && newScores.rice_confidence && newScores.rice_effort) {
      try {
        setLoading(true);
        const api = entityType === 'story' ? scoringAPI.updateStoryRICE : scoringAPI.updateBugRICE;
        await api(entityId, {
          reach: newScores.rice_reach,
          impact: newScores.rice_impact,
          confidence: newScores.rice_confidence,
          effort: newScores.rice_effort,
        });
        const total = ((newScores.rice_reach * newScores.rice_impact * newScores.rice_confidence) / newScores.rice_effort);
        setScores(prev => ({ ...prev, rice_total: total }));
        toast.success('RICE score updated');
        onUpdate?.();
      } catch (err) {
        toast.error('Failed to update RICE score');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleAISuggest = async () => {
    setAiLoading(true);
    try {
      const suggestApi = entityType === 'story' ? scoringAPI.suggestStoryRICE : scoringAPI.suggestBugRICE;
      const response = await suggestApi(entityId);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        const lines = text.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'suggestion' && data.suggestion) {
                const { reach, impact, confidence, effort } = data.suggestion;
                const updateApi = entityType === 'story' ? scoringAPI.updateStoryRICE : scoringAPI.updateBugRICE;
                await updateApi(entityId, { reach, impact, confidence, effort });
                const total = ((reach * impact * confidence) / effort);
                setScores({
                  rice_reach: reach,
                  rice_impact: impact,
                  rice_confidence: confidence,
                  rice_effort: effort,
                  rice_total: total,
                });
                toast.success('AI suggestion applied');
                onUpdate?.();
              } else if (data.type === 'error') {
                toast.error(data.message);
              }
            } catch (e) {}
          }
        }
      }
    } catch (err) {
      toast.error('Failed to get AI suggestion');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calculator className="w-5 h-5 text-violet-500" />
            RICE Score
          </DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">{entityTitle}</p>
        </DialogHeader>

        <div className="py-4">
          <RICEEditor
            reach={scores.rice_reach}
            impact={scores.rice_impact}
            confidence={scores.rice_confidence}
            effort={scores.rice_effort}
            total={scores.rice_total}
            onReachChange={(v) => handleRICEChange('rice_reach', v)}
            onImpactChange={(v) => handleRICEChange('rice_impact', v)}
            onConfidenceChange={(v) => handleRICEChange('rice_confidence', v)}
            onEffortChange={(v) => handleRICEChange('rice_effort', v)}
            onSuggest={handleAISuggest}
            loading={loading}
            disabled={loading || aiLoading}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Epic MoSCoW Dialog
export const EpicMoSCoWDialog = ({ open, onOpenChange, epicId, epicTitle, onUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [score, setScore] = useState(null);

  useEffect(() => {
    if (open && epicId) {
      loadScore();
    }
  }, [open, epicId]);

  const loadScore = async () => {
    try {
      const { data } = await scoringAPI.getEpicMoSCoW(epicId);
      setScore(data.moscow_score);
    } catch (err) {
      console.error('Failed to load score:', err);
    }
  };

  const handleChange = async (value) => {
    try {
      setLoading(true);
      await scoringAPI.updateEpicMoSCoW(epicId, value);
      setScore(value);
      toast.success('MoSCoW score updated');
      onUpdate?.();
    } catch (err) {
      toast.error('Failed to update score');
    } finally {
      setLoading(false);
    }
  };

  const handleAISuggest = async () => {
    setAiLoading(true);
    try {
      const response = await scoringAPI.suggestEpicMoSCoW(epicId);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        const lines = text.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'suggestion' && data.suggestion?.score) {
                await scoringAPI.updateEpicMoSCoW(epicId, data.suggestion.score);
                setScore(data.suggestion.score);
                toast.success('AI suggestion applied');
                onUpdate?.();
              } else if (data.type === 'error') {
                toast.error(data.message);
              }
            } catch (e) {}
          }
        }
      }
    } catch (err) {
      toast.error('Failed to get AI suggestion');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-violet-500" />
            Epic Priority
          </DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">{epicTitle}</p>
        </DialogHeader>

        <div className="py-4">
          <MoSCoWEditor
            value={score}
            onChange={handleChange}
            onSuggest={handleAISuggest}
            loading={loading || aiLoading}
            disabled={loading || aiLoading}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
