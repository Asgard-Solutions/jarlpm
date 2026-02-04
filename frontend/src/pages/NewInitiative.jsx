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
  Target, Users, AlertTriangle, BarChart3
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
                  // New pass starting
                  setProgress(data.message);
                  setProgressPercent(data.pass * 25); // 25%, 50%, 75%
                  break;
                case 'progress':
                  setProgress(data.message);
                  setProgressPercent(prev => Math.min(prev + 8, 95));
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
                <div className="space-y-3">
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
                                <div key={si} className="bg-nordic-bg-primary rounded p-3">
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="font-medium text-sm text-nordic-text-primary">
                                      {story.title}
                                    </span>
                                    <Badge variant="outline" className="text-xs">
                                      {story.points} pts
                                    </Badge>
                                  </div>
                                  <p className="text-xs text-nordic-text-muted mb-2">
                                    As {story.persona}, I want to {story.action} so that {story.benefit}
                                  </p>
                                  <div className="text-xs text-nordic-text-muted">
                                    <span className="font-medium">AC:</span>
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
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NewInitiative;
