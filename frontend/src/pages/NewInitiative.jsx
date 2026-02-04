import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Sparkles, Rocket, FileText, Layers, BookOpen, 
  Calendar, Check, ArrowRight, Loader2, Save,
  Target, Users, AlertTriangle, BarChart3,
  Shield, Lightbulb, CheckCircle2, TrendingUp
} from 'lucide-react';

const API = import.meta.env.VITE_BACKEND_URL;

const NewInitiative = () => {
  const navigate = useNavigate();
  const [idea, setIdea] = useState('');
  const [productName, setProductName] = useState('');
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressPercent, setProgressPercent] = useState(0);
  const [initiative, setInitiative] = useState(null);
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    if (!idea.trim()) return;
    
    setGenerating(true);
    setError('');
    setInitiative(null);
    setProgressPercent(10);
    
    try {
      const response = await fetch(`${API}/api/initiative/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          idea: idea.trim(),
          product_name: productName.trim() || null
        }),
        credentials: 'include',
      });
      
      if (!response.ok) {
        const err = await response.json();
        // Handle specific error codes with actionable CTAs
        if (response.status === 402) {
          setError('subscription_required');
        } else if (response.status === 400 && err.detail?.includes('LLM provider')) {
          setError('llm_not_configured');
        } else {
          setError(err.detail || 'Failed to generate initiative');
        }
        return;
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ''; // SSE buffer for handling split chunks
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'pass':
                  // New pass starting (4 passes: 20%, 40%, 60%, 80%)
                  setProgress(data.message);
                  setProgressPercent(data.pass * 20);
                  break;
                case 'progress':
                  setProgress(data.message);
                  setProgressPercent(prev => Math.min(prev + 5, 95));
                  break;
                case 'initiative':
                  setInitiative(data.data);
                  setProgressPercent(100);
                  break;
                case 'error':
                  setError(data.message);
                  break;
                case 'done':
                  setProgress('');
                  break;
              }
            } catch (e) {
              // Ignore parse errors - incomplete JSON will be caught next iteration
            }
          }
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!initiative) return;
    
    setSaving(true);
    try {
      const response = await fetch(`${API}/api/initiative/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(initiative),
        credentials: 'include',
      });
      
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save');
      }
      
      const result = await response.json();
      navigate(`/epic/${result.epic_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const totalPoints = initiative?.total_points || 0;
  const totalStories = initiative?.features?.reduce((acc, f) => acc + (f.stories?.length || 0), 0) || 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-nordic-bg-primary to-nordic-bg-secondary">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-nordic-accent/10 rounded-full text-nordic-accent mb-4">
            <Sparkles className="w-4 h-4" />
            <span className="text-sm font-medium">Turn idea into plan</span>
          </div>
          <h1 className="text-4xl font-bold text-nordic-text-primary mb-3">
            New Initiative
          </h1>
          <p className="text-lg text-nordic-text-muted max-w-xl mx-auto">
            Paste your messy idea. Get a clean PRD, features, stories, and a 2-sprint plan in seconds.
          </p>
        </div>

        {/* Input Section */}
        {!initiative && (
          <Card className="bg-nordic-bg-secondary border-nordic-border mb-8">
            <CardContent className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-nordic-text-primary mb-2">
                  Product Name <span className="text-nordic-text-muted">(optional)</span>
                </label>
                <Input
                  placeholder="e.g., TaskFlow, BudgetBuddy, FitTrack..."
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  className="bg-nordic-bg-primary border-nordic-border text-nordic-text-primary"
                  disabled={generating}
                  data-testid="product-name-input"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-nordic-text-primary mb-2">
                  Your Idea / Problem <span className="text-red-400">*</span>
                </label>
                <Textarea
                  placeholder={`Paste your messy idea here...

Example:
"We need an app for freelancers to track time and invoice clients. 
They currently use spreadsheets which is error-prone. 
Should work on mobile, integrate with Stripe for payments, 
and send automatic payment reminders. Target: solo freelancers 
and small agencies (2-5 people)."`}
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                  className="bg-nordic-bg-primary border-nordic-border text-nordic-text-primary min-h-[200px] resize-none"
                  disabled={generating}
                  data-testid="idea-input"
                />
                <p className="text-xs text-nordic-text-muted mt-2">
                  Include: the problem, who has it, any constraints, nice-to-haves
                </p>
              </div>

              {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  {error === 'subscription_required' ? (
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div>
                        <p className="font-medium text-red-400">Active subscription required</p>
                        <p className="text-sm text-nordic-text-muted mt-1">
                          Upgrade to JarlPM Pro to use AI-powered features.
                        </p>
                      </div>
                      <Button
                        onClick={() => navigate('/settings?tab=subscription')}
                        className="bg-nordic-accent hover:bg-nordic-accent/90 text-white shrink-0"
                        data-testid="upgrade-cta"
                      >
                        <Sparkles className="w-4 h-4 mr-2" />
                        Upgrade Now
                      </Button>
                    </div>
                  ) : error === 'llm_not_configured' ? (
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div>
                        <p className="font-medium text-red-400">No LLM provider configured</p>
                        <p className="text-sm text-nordic-text-muted mt-1">
                          Add your OpenAI or Anthropic API key to enable AI features.
                        </p>
                      </div>
                      <Button
                        onClick={() => navigate('/settings?tab=llm')}
                        variant="outline"
                        className="border-nordic-accent text-nordic-accent hover:bg-nordic-accent/10 shrink-0"
                        data-testid="configure-llm-cta"
                      >
                        Configure LLM
                      </Button>
                    </div>
                  ) : (
                    <p className="text-red-400 text-sm">{error}</p>
                  )}
                </div>
              )}

              {generating && (
                <div className="space-y-4">
                  {/* 3-Pass Pipeline Indicator */}
                  <div className="flex items-center justify-between text-xs text-nordic-text-muted mb-2">
                    <div className={`flex items-center gap-1 ${progressPercent >= 25 ? 'text-nordic-accent' : ''}`}>
                      <div className={`w-2 h-2 rounded-full ${progressPercent >= 25 ? 'bg-nordic-accent' : 'bg-nordic-text-muted/30'}`} />
                      PRD
                    </div>
                    <div className={`flex items-center gap-1 ${progressPercent >= 50 ? 'text-nordic-accent' : ''}`}>
                      <div className={`w-2 h-2 rounded-full ${progressPercent >= 50 ? 'bg-nordic-accent' : 'bg-nordic-text-muted/30'}`} />
                      Features
                    </div>
                    <div className={`flex items-center gap-1 ${progressPercent >= 60 ? 'text-nordic-accent' : ''}`}>
                      <div className={`w-2 h-2 rounded-full ${progressPercent >= 60 ? 'bg-nordic-accent' : 'bg-nordic-text-muted/30'}`} />
                      Planning
                    </div>
                    <div className={`flex items-center gap-1 ${progressPercent >= 80 ? 'text-nordic-accent' : ''}`}>
                      <div className={`w-2 h-2 rounded-full ${progressPercent >= 80 ? 'bg-nordic-accent' : 'bg-nordic-text-muted/30'}`} />
                      Review
                    </div>
                    <div className={`flex items-center gap-1 ${progressPercent >= 100 ? 'text-nordic-green' : ''}`}>
                      <div className={`w-2 h-2 rounded-full ${progressPercent >= 100 ? 'bg-nordic-green' : 'bg-nordic-text-muted/30'}`} />
                      Done
                    </div>
                  </div>
                  <Progress value={progressPercent} className="h-2" />
                  <div className="flex items-center justify-center gap-2 text-nordic-accent">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">{progress || 'Processing...'}</span>
                  </div>
                </div>
              )}

              <Button
                onClick={handleGenerate}
                disabled={!idea.trim() || generating}
                className="w-full bg-nordic-accent hover:bg-nordic-accent/90 text-white py-6 text-lg"
                data-testid="generate-button"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Generating your initiative...
                  </>
                ) : (
                  <>
                    <Rocket className="w-5 h-5 mr-2" />
                    Generate Initiative
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Results Section */}
        {initiative && (
          <div className="space-y-6">
            {/* Quality Summary & Warnings */}
            {(initiative.warnings?.length > 0 || initiative.quality_summary) && (
              <Card className={`border ${
                initiative.quality_summary?.scope_assessment === 'overloaded' 
                  ? 'bg-red-500/10 border-red-500/30' 
                  : initiative.quality_summary?.scope_assessment === 'at_risk'
                  ? 'bg-amber-500/10 border-amber-500/30'
                  : 'bg-nordic-green/10 border-nordic-green/30'
              }`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className={`w-4 h-4 ${
                          initiative.quality_summary?.scope_assessment === 'overloaded' ? 'text-red-500' :
                          initiative.quality_summary?.scope_assessment === 'at_risk' ? 'text-amber-500' :
                          'text-nordic-green'
                        }`} />
                        <span className="font-medium text-nordic-text-primary">
                          PM Quality Check
                        </span>
                        {initiative.quality_summary?.auto_fixed > 0 && (
                          <Badge variant="outline" className="text-xs border-nordic-green text-nordic-green">
                            {initiative.quality_summary.auto_fixed} auto-fixed
                          </Badge>
                        )}
                      </div>
                      {initiative.quality_summary?.recommendation && (
                        <p className="text-sm text-nordic-text-muted mb-2">
                          {initiative.quality_summary.recommendation}
                        </p>
                      )}
                      {initiative.warnings?.length > 0 && (
                        <div className="space-y-1">
                          {initiative.warnings.slice(0, 3).map((w, i) => (
                            <div key={i} className="text-xs text-nordic-text-muted flex items-start gap-2">
                              <span className="text-amber-500">⚠</span>
                              <span><strong>{w.location}:</strong> {w.problem}</span>
                            </div>
                          ))}
                          {initiative.warnings.length > 3 && (
                            <div className="text-xs text-nordic-text-muted">
                              +{initiative.warnings.length - 3} more warnings
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <Badge className={
                      initiative.quality_summary?.scope_assessment === 'overloaded' 
                        ? 'bg-red-500 text-white' 
                        : initiative.quality_summary?.scope_assessment === 'at_risk'
                        ? 'bg-amber-500 text-white'
                        : 'bg-nordic-green text-white'
                    }>
                      {initiative.quality_summary?.scope_assessment === 'on_track' ? 'On Track' :
                       initiative.quality_summary?.scope_assessment === 'at_risk' ? 'At Risk' :
                       initiative.quality_summary?.scope_assessment === 'overloaded' ? 'Overloaded' :
                       'Reviewed'}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Confidence & Risks Panel - PM Premium Feature */}
            {initiative.confidence_assessment && (
              <Card className="bg-nordic-bg-secondary border-nordic-border">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-nordic-text-primary flex items-center gap-2">
                      <Shield className="w-5 h-5 text-nordic-accent" />
                      Confidence & Risks
                    </h3>
                    {initiative.confidence_assessment.confidence_score && (
                      <div className="flex items-center gap-2">
                        <div className={`text-2xl font-bold ${
                          initiative.confidence_assessment.confidence_score >= 70 ? 'text-nordic-green' :
                          initiative.confidence_assessment.confidence_score >= 50 ? 'text-amber-500' :
                          'text-red-500'
                        }`}>
                          {initiative.confidence_assessment.confidence_score}%
                        </div>
                        <span className="text-xs text-nordic-text-muted">confidence</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Top Risks */}
                    {initiative.confidence_assessment.top_risks?.length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-red-400 mb-2">
                          <AlertTriangle className="w-4 h-4" />
                          Top Risks
                        </div>
                        <ul className="space-y-2">
                          {initiative.confidence_assessment.top_risks.slice(0, 3).map((risk, i) => (
                            <li key={i} className="text-sm text-nordic-text-muted flex items-start gap-2">
                              <span className="text-red-400 font-mono text-xs mt-0.5">{i + 1}.</span>
                              {risk}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {/* Key Assumptions */}
                    {initiative.confidence_assessment.key_assumptions?.length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-amber-400 mb-2">
                          <Lightbulb className="w-4 h-4" />
                          Key Assumptions
                        </div>
                        <ul className="space-y-2">
                          {initiative.confidence_assessment.key_assumptions.slice(0, 3).map((assumption, i) => (
                            <li key={i} className="text-sm text-nordic-text-muted flex items-start gap-2">
                              <span className="text-amber-400 font-mono text-xs mt-0.5">{i + 1}.</span>
                              {assumption}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Validate First - Most important */}
                  {initiative.confidence_assessment.validate_first?.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-nordic-border">
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-accent mb-2">
                        <CheckCircle2 className="w-4 h-4" />
                        Validate First (Before Heavy Development)
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {initiative.confidence_assessment.validate_first.slice(0, 3).map((item, i) => (
                          <Badge 
                            key={i} 
                            variant="outline" 
                            className="text-xs border-nordic-accent/50 text-nordic-accent bg-nordic-accent/5"
                          >
                            {i + 1}. {item}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Success Factors */}
                  {initiative.confidence_assessment.success_factors?.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-nordic-border">
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-green mb-2">
                        <TrendingUp className="w-4 h-4" />
                        Critical Success Factors
                      </div>
                      <ul className="flex flex-wrap gap-2">
                        {initiative.confidence_assessment.success_factors.map((factor, i) => (
                          <li key={i} className="text-sm text-nordic-text-muted bg-nordic-green/10 px-2 py-1 rounded">
                            {factor}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Summary Header */}
            <Card className="bg-gradient-to-r from-nordic-accent/20 to-nordic-green/20 border-nordic-accent/30">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-nordic-text-primary">
                      {initiative.product_name}
                    </h2>
                    <p className="text-nordic-text-muted">{initiative.tagline}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-nordic-accent">{initiative.features?.length || 0}</div>
                      <div className="text-xs text-nordic-text-muted">Features</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-nordic-green">{totalStories}</div>
                      <div className="text-xs text-nordic-text-muted">Stories</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-nordic-text-primary">{totalPoints}</div>
                      <div className="text-xs text-nordic-text-muted">Points</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* PRD Column */}
              <div className="lg:col-span-2 space-y-6">
                {/* PRD Section */}
                <Card className="bg-nordic-bg-secondary border-nordic-border">
                  <CardContent className="p-6">
                    <h3 className="text-lg font-semibold text-nordic-text-primary flex items-center gap-2 mb-4">
                      <FileText className="w-5 h-5 text-nordic-accent" />
                      PRD Summary
                    </h3>
                    
                    <div className="space-y-4">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                          <Target className="w-4 h-4" /> Problem
                        </div>
                        <p className="text-nordic-text-primary">{initiative.prd?.problem_statement}</p>
                      </div>
                      
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                          <Users className="w-4 h-4" /> Target Users
                        </div>
                        <p className="text-nordic-text-primary">{initiative.prd?.target_users}</p>
                      </div>
                      
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                          <Check className="w-4 h-4" /> Desired Outcome
                        </div>
                        <p className="text-nordic-text-primary">{initiative.prd?.desired_outcome}</p>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                            <BarChart3 className="w-4 h-4" /> Key Metrics
                          </div>
                          <div className="space-y-1">
                            {initiative.prd?.key_metrics?.map((m, i) => (
                              <Badge key={i} variant="outline" className="mr-1 mb-1 text-nordic-text-primary border-nordic-border">
                                {m}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div>
                          <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                            <AlertTriangle className="w-4 h-4" /> Risks
                          </div>
                          <div className="space-y-1">
                            {initiative.prd?.risks?.map((r, i) => (
                              <Badge key={i} variant="outline" className="mr-1 mb-1 text-amber-500 border-amber-500/30">
                                {r}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Features & Stories */}
                <Card className="bg-nordic-bg-secondary border-nordic-border">
                  <CardContent className="p-6">
                    <h3 className="text-lg font-semibold text-nordic-text-primary flex items-center gap-2 mb-4">
                      <Layers className="w-5 h-5 text-nordic-accent" />
                      Features & Stories
                    </h3>
                    
                    <ScrollArea className="h-[500px] pr-4">
                      <div className="space-y-6">
                        {initiative.features?.map((feature, fi) => (
                          <div key={fi} className="border border-nordic-border rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="font-medium text-nordic-text-primary">{feature.name}</h4>
                              <Badge 
                                className={
                                  feature.priority === 'must-have' 
                                    ? 'bg-red-500/20 text-red-400 border-red-500/30'
                                    : feature.priority === 'should-have'
                                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                                    : 'bg-nordic-text-muted/20 text-nordic-text-muted'
                                }
                                variant="outline"
                              >
                                {feature.priority}
                              </Badge>
                            </div>
                            <p className="text-sm text-nordic-text-muted mb-3">{feature.description}</p>
                            
                            <div className="space-y-2">
                              {feature.stories?.map((story, si) => (
                                <div key={si} className="bg-nordic-bg-primary rounded p-3" data-testid={`story-card-${story.id || si}`}>
                                  {/* Story Header: Title + Points + Priority */}
                                  <div className="flex items-center justify-between mb-2">
                                    <span className="font-medium text-sm text-nordic-text-primary">
                                      {story.title}
                                    </span>
                                    <div className="flex items-center gap-2">
                                      <Badge 
                                        variant="outline" 
                                        className={`text-xs ${
                                          story.priority === 'must-have' 
                                            ? 'border-red-500/50 text-red-400'
                                            : story.priority === 'should-have'
                                            ? 'border-amber-500/50 text-amber-400'
                                            : 'border-nordic-text-muted/50'
                                        }`}
                                      >
                                        {story.priority}
                                      </Badge>
                                      <Badge variant="outline" className="text-xs">
                                        {story.points} pts
                                      </Badge>
                                    </div>
                                  </div>
                                  
                                  {/* User Story Format */}
                                  <p className="text-xs text-nordic-text-muted mb-2">
                                    As {story.persona}, I want to {story.action} so that {story.benefit}
                                  </p>
                                  
                                  {/* Labels */}
                                  {story.labels?.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mb-2">
                                      {story.labels.map((label, li) => (
                                        <Badge 
                                          key={li} 
                                          variant="secondary" 
                                          className="text-[10px] px-1.5 py-0 bg-nordic-accent/10 text-nordic-accent"
                                        >
                                          {label}
                                        </Badge>
                                      ))}
                                    </div>
                                  )}
                                  
                                  {/* Acceptance Criteria (Gherkin) */}
                                  <div className="text-xs text-nordic-text-muted">
                                    <span className="font-medium">Acceptance Criteria:</span>
                                    <ul className="ml-3 mt-1 space-y-0.5">
                                      {story.acceptance_criteria?.slice(0, 2).map((ac, ai) => (
                                        <li key={ai} className="flex items-start gap-1">
                                          <Check className="w-3 h-3 mt-0.5 text-nordic-green flex-shrink-0" />
                                          <span className="line-clamp-1">{ac}</span>
                                        </li>
                                      ))}
                                      {story.acceptance_criteria?.length > 2 && (
                                        <li className="text-nordic-accent">
                                          +{story.acceptance_criteria.length - 2} more
                                        </li>
                                      )}
                                    </ul>
                                  </div>
                                  
                                  {/* Dependencies & Risks (collapsible) */}
                                  {(story.dependencies?.length > 0 || story.risks?.length > 0) && (
                                    <div className="mt-2 pt-2 border-t border-nordic-border/50 grid grid-cols-2 gap-2">
                                      {story.dependencies?.length > 0 && (
                                        <div className="text-[10px]">
                                          <span className="text-nordic-text-muted font-medium">Dependencies:</span>
                                          <ul className="mt-0.5 text-nordic-text-muted/70">
                                            {story.dependencies.slice(0, 2).map((dep, di) => (
                                              <li key={di} className="truncate">→ {dep}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                      {story.risks?.length > 0 && (
                                        <div className="text-[10px]">
                                          <span className="text-amber-500 font-medium">Risks:</span>
                                          <ul className="mt-0.5 text-amber-500/70">
                                            {story.risks.slice(0, 2).map((risk, ri) => (
                                              <li key={ri} className="truncate">⚠ {risk}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>

              {/* Sprint Plan Column */}
              <div className="space-y-6">
                <Card className="bg-nordic-bg-secondary border-nordic-border">
                  <CardContent className="p-6">
                    <h3 className="text-lg font-semibold text-nordic-text-primary flex items-center gap-2 mb-4">
                      <Calendar className="w-5 h-5 text-nordic-accent" />
                      2-Sprint Plan
                    </h3>
                    
                    <div className="space-y-4">
                      {/* Sprint 1 */}
                      <div className="border border-nordic-accent/30 bg-nordic-accent/5 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-nordic-accent">Sprint 1</span>
                          <Badge className="bg-nordic-accent text-white">
                            {initiative.sprint_plan?.sprint_1?.total_points || 0} pts
                          </Badge>
                        </div>
                        <p className="text-sm text-nordic-text-primary mb-3">
                          {initiative.sprint_plan?.sprint_1?.goal}
                        </p>
                        <div className="space-y-1">
                          {initiative.sprint_plan?.sprint_1?.stories?.map((s, i) => (
                            <div key={i} className="text-xs text-nordic-text-muted flex items-center gap-2">
                              <BookOpen className="w-3 h-3" />
                              <span className="line-clamp-1">{s}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {/* Sprint 2 */}
                      <div className="border border-nordic-green/30 bg-nordic-green/5 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-nordic-green">Sprint 2</span>
                          <Badge className="bg-nordic-green text-white">
                            {initiative.sprint_plan?.sprint_2?.total_points || 0} pts
                          </Badge>
                        </div>
                        <p className="text-sm text-nordic-text-primary mb-3">
                          {initiative.sprint_plan?.sprint_2?.goal}
                        </p>
                        <div className="space-y-1">
                          {initiative.sprint_plan?.sprint_2?.stories?.map((s, i) => (
                            <div key={i} className="text-xs text-nordic-text-muted flex items-center gap-2">
                              <BookOpen className="w-3 h-3" />
                              <span className="line-clamp-1">{s}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Actions */}
                <div className="space-y-3">
                  <Button
                    onClick={handleSave}
                    disabled={saving}
                    className="w-full bg-nordic-green hover:bg-nordic-green/90 text-white py-6"
                    data-testid="save-initiative-button"
                  >
                    {saving ? (
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    ) : (
                      <Save className="w-5 h-5 mr-2" />
                    )}
                    Save & Start Working
                  </Button>
                  
                  <Button
                    variant="outline"
                    onClick={() => {
                      setInitiative(null);
                      setProgressPercent(0);
                    }}
                    className="w-full border-nordic-border text-nordic-text-muted hover:text-nordic-text-primary"
                  >
                    <ArrowRight className="w-4 h-4 mr-2 rotate-180" />
                    Start Over
                  </Button>
                </div>

                {/* Out of Scope */}
                {initiative.prd?.out_of_scope?.length > 0 && (
                  <Card className="bg-nordic-bg-secondary border-nordic-border">
                    <CardContent className="p-4">
                      <h4 className="text-sm font-medium text-nordic-text-muted mb-2">
                        Out of Scope (v1)
                      </h4>
                      <ul className="space-y-1">
                        {initiative.prd.out_of_scope.map((item, i) => (
                          <li key={i} className="text-xs text-nordic-text-muted flex items-start gap-2">
                            <span className="text-red-400">✕</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Delivery Context - shows personalization */}
                {initiative.delivery_context && (
                  <Card className="bg-nordic-bg-secondary border-nordic-border">
                    <CardContent className="p-4">
                      <h4 className="text-sm font-medium text-nordic-text-primary mb-3 flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        Tailored For Your Team
                      </h4>
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-nordic-text-muted">Industry</span>
                          <span className="text-nordic-text-primary capitalize">{initiative.delivery_context.industry}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-nordic-text-muted">Methodology</span>
                          <span className="text-nordic-text-primary capitalize">{initiative.delivery_context.methodology}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-nordic-text-muted">Sprint Length</span>
                          <span className="text-nordic-text-primary">{initiative.delivery_context.sprint_length} days</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-nordic-text-muted">Team Velocity</span>
                          <span className="text-nordic-text-primary">~{initiative.delivery_context.team_velocity} pts/sprint</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-nordic-text-muted">Platform</span>
                          <span className="text-nordic-text-primary capitalize">{initiative.delivery_context.platform?.replace('_', ' ')}</span>
                        </div>
                      </div>
                      {initiative.delivery_context.definition_of_done?.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-nordic-border">
                          <h5 className="text-xs font-medium text-nordic-text-muted mb-2">Definition of Done</h5>
                          <ul className="space-y-1">
                            {initiative.delivery_context.definition_of_done.slice(0, 4).map((d, i) => (
                              <li key={i} className="text-xs text-nordic-text-muted flex items-start gap-1">
                                <Check className="w-3 h-3 mt-0.5 text-nordic-green flex-shrink-0" />
                                {d}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NewInitiative;
