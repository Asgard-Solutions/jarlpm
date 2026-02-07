import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAuthStore } from '@/store';
import {
  trackPreviewTabChange,
  trackGenerateMyOwnClick,
  trackCopyPRDClick,
} from '@/utils/analytics';
import {
  ArrowRight,
  Copy,
  Check,
  FileText,
  Layers,
  Calendar,
  Users,
  Target,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  BarChart3,
  Lightbulb,
  Shield,
  TrendingUp,
  Puzzle,
  BookOpen,
  Lock,
  ChevronDown,
  Clock,
  ListChecks,
  Flag,
  Play,
  Ban,
} from 'lucide-react';

import exampleData from '@/content/exampleInitiative.json';

const ExampleOutputModal = ({ open, onOpenChange }) => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('prd');
  const [copied, setCopied] = useState(false);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    trackPreviewTabChange(tab);
  };

  const handleGenerateMyOwn = () => {
    trackGenerateMyOwnClick(!!user);
    onOpenChange(false);
    if (user) {
      navigate('/new');
    } else {
      navigate('/signup?next=/new');
    }
  };

  const handleCopyPRD = async () => {
    const prdText = formatPRDForCopy(exampleData.prd);
    try {
      await navigator.clipboard.writeText(prdText);
      setCopied(true);
      trackCopyPRDClick('full');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const formatPRDForCopy = (prd) => {
    return `# ${exampleData.product_name}

## Problem Statement
${prd.problem_statement}

## Evidence
${prd.problem_evidence}

## Target Users
${prd.target_users.map(u => `### ${u.persona}\n${u.context}\n\nPain Points:\n${u.pain_points.map(p => `- ${p}`).join('\n')}\n\nJTBD: ${u.jtbd}`).join('\n\n')}

## Desired Outcome
${prd.desired_outcome}

## Key Metrics
${prd.key_metrics.map(m => `- ${m}`).join('\n')}

## MVP Scope
${prd.mvp_scope.map(s => `- ${s.item}: ${s.rationale}`).join('\n')}

## Assumptions
${prd.assumptions.map(a => `- ${a.assumption}\n  Risk: ${a.risk_if_wrong}\n  Validation: ${a.validation_approach}`).join('\n')}

## Riskiest Unknown
${prd.riskiest_unknown}

## Validation Plan
${prd.validation_plan}
`;
  };

  // Calculate totals
  const totalStories = exampleData.features.reduce((acc, f) => acc + f.stories.length, 0);
  const totalPoints = exampleData.total_points;

  // Get capacity status for sprint plan
  const getCapacityStatus = (points, capacity = 16) => {
    const ratio = points / capacity;
    if (ratio <= 0.9) return { status: 'on-track', className: 'bg-green-500/20 text-green-400 border-green-500/30', label: 'On Track' };
    if (ratio <= 1.1) return { status: 'at-risk', className: 'bg-amber-500/20 text-amber-400 border-amber-500/30', label: 'At Risk' };
    return { status: 'overloaded', className: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'Overloaded' };
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] p-0 gap-0 bg-[#1a1a2e] border-nordic-border shadow-2xl">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-nordic-border">
          <div className="flex items-center justify-between">
            <div>
              <Badge variant="outline" className="mb-2 text-xs border-nordic-accent/50 text-nordic-accent">
                <Sparkles className="w-3 h-3 mr-1" />
                Example Output
              </Badge>
              <DialogTitle className="text-xl text-nordic-text-primary">
                {exampleData.epic.title}
              </DialogTitle>
              <p className="text-sm text-nordic-text-muted mt-1">
                {exampleData.epic.vision}
              </p>
            </div>
            <Button
              onClick={handleGenerateMyOwn}
              className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
              data-testid="modal-generate-my-own-btn"
            >
              Generate My Own <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1">
          <div className="px-6 pt-4 border-b border-nordic-border">
            <TabsList className="grid w-full grid-cols-3 bg-[#0d0d1a]">
              <TabsTrigger value="prd" className="flex items-center gap-2 data-[state=active]:bg-nordic-accent data-[state=active]:text-white" data-testid="tab-prd">
                <FileText className="w-4 h-4" />
                PRD
              </TabsTrigger>
              <TabsTrigger value="stories" className="flex items-center gap-2 data-[state=active]:bg-nordic-accent data-[state=active]:text-white" data-testid="tab-stories">
                <Layers className="w-4 h-4" />
                Stories
              </TabsTrigger>
              <TabsTrigger value="sprint" className="flex items-center gap-2 data-[state=active]:bg-nordic-accent data-[state=active]:text-white" data-testid="tab-sprint">
                <Calendar className="w-4 h-4" />
                Sprint Plan
              </TabsTrigger>
            </TabsList>
          </div>

          <ScrollArea className="h-[60vh]">
            {/* PRD Tab - Matches NewInitiative.jsx PRD Section */}
            <TabsContent value="prd" className="p-6 mt-0">
              <div className="flex justify-end mb-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyPRD}
                  className="border-nordic-border text-nordic-text-primary hover:bg-[#1a1a2e]"
                  data-testid="copy-prd-btn"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 mr-2 text-nordic-green" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4 mr-2" />
                      Copy PRD
                    </>
                  )}
                </Button>
              </div>

              <Card className="bg-[#0d0d1a] border-nordic-border">
                <CardContent className="p-6">
                  <h3 className="text-lg font-semibold text-nordic-text-primary flex items-center gap-2 mb-4">
                    <FileText className="w-5 h-5 text-nordic-accent" />
                    PRD Summary
                  </h3>
                  
                  <div className="space-y-4">
                    {/* Problem Statement */}
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                        <Target className="w-4 h-4" /> Problem
                      </div>
                      <p className="text-nordic-text-primary">{exampleData.prd.problem_statement}</p>
                      <p className="text-sm text-nordic-text-muted mt-2 italic bg-[#0d0d1a] p-2 rounded">
                        Evidence: {exampleData.prd.problem_evidence}
                      </p>
                    </div>
                    
                    {/* Target Users */}
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                        <Users className="w-4 h-4" /> Target Users
                      </div>
                      <div className="space-y-3">
                        {exampleData.prd.target_users.map((user, i) => (
                          <div key={i} className="bg-[#0d0d1a] p-3 rounded-lg border border-nordic-border">
                            <div className="font-medium text-nordic-text-primary mb-1">{user.persona}</div>
                            <p className="text-sm text-nordic-text-muted mb-2">{user.context}</p>
                            <div className="mb-2">
                              <span className="text-xs font-medium text-red-400">Pain Points: </span>
                              <span className="text-sm text-nordic-text-muted">{user.pain_points.join(', ')}</span>
                            </div>
                            <div className="mb-2">
                              <span className="text-xs font-medium text-amber-400">Current Workaround: </span>
                              <span className="text-sm text-nordic-text-muted">{user.current_workaround}</span>
                            </div>
                            <div className="text-sm text-nordic-accent italic">&ldquo;{user.jtbd}&rdquo;</div>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    {/* Desired Outcome */}
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                        <Check className="w-4 h-4" /> Desired Outcome
                      </div>
                      <p className="text-nordic-text-primary">{exampleData.prd.desired_outcome}</p>
                    </div>

                    {/* Positioning */}
                    <div className="bg-gradient-to-r from-nordic-accent/10 to-transparent p-3 rounded-lg border border-nordic-accent/20">
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-accent mb-2">
                        <TrendingUp className="w-4 h-4" /> Positioning
                      </div>
                      <p className="text-sm text-nordic-text-primary">
                        For <span className="font-medium">{exampleData.prd.positioning.for_who}</span>, 
                        who struggle with <span className="font-medium">{exampleData.prd.positioning.who_struggle_with}</span>, 
                        our <span className="font-medium">{exampleData.prd.positioning.our_solution}</span> is unlike 
                        <span className="font-medium"> {exampleData.prd.positioning.unlike}</span> because 
                        <span className="font-medium text-nordic-accent"> {exampleData.prd.positioning.key_benefit}</span>.
                      </p>
                    </div>
                    
                    {/* Key Metrics & Riskiest Unknown */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                          <BarChart3 className="w-4 h-4" /> Key Metrics
                        </div>
                        <div className="space-y-1">
                          {exampleData.prd.key_metrics.map((m, i) => (
                            <Badge key={i} variant="outline" className="mr-1 mb-1 text-nordic-text-primary border-nordic-border">
                              {m}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                          <AlertTriangle className="w-4 h-4" /> Riskiest Unknown
                        </div>
                        <p className="text-sm text-amber-400">{exampleData.prd.riskiest_unknown}</p>
                      </div>
                    </div>
                    
                    {/* MVP Scope */}
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-green-400 mb-2">
                        <CheckCircle2 className="w-4 h-4" /> MVP Scope (In)
                      </div>
                      <div className="space-y-2">
                        {exampleData.prd.mvp_scope.map((item, i) => (
                          <div key={i} className="bg-green-500/5 border border-green-500/20 p-2 rounded">
                            <span className="font-medium text-nordic-text-primary">{item.item}</span>
                            <p className="text-xs text-nordic-text-muted mt-1">{item.rationale}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Not Now */}
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                        <Shield className="w-4 h-4" /> Deferred (Not Now)
                      </div>
                      <div className="space-y-2">
                        {exampleData.prd.not_now.map((item, i) => (
                          <div key={i} className="bg-[#0d0d1a] p-2 rounded border border-nordic-border">
                            <span className="text-nordic-text-muted">{item.item}</span>
                            <p className="text-xs text-nordic-text-muted/70 mt-1">Why: {item.rationale}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    {/* Assumptions */}
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                        <Lightbulb className="w-4 h-4" /> Assumptions to Validate
                      </div>
                      <div className="space-y-2">
                        {exampleData.prd.assumptions.slice(0, 2).map((a, i) => (
                          <div key={i} className="bg-amber-500/5 border border-amber-500/20 p-2 rounded">
                            <span className="font-medium text-nordic-text-primary">{a.assumption}</span>
                            <p className="text-xs text-red-400 mt-1">Risk if wrong: {a.risk_if_wrong}</p>
                            <p className="text-xs text-green-400 mt-1">Validation: {a.validation_approach}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    {/* Validation Plan */}
                    <div className="bg-green-500/5 border border-green-500/20 p-3 rounded-lg">
                      <div className="flex items-center gap-2 text-sm font-medium text-green-400 mb-1">
                        <CheckCircle2 className="w-4 h-4" /> Validation Plan
                      </div>
                      <p className="text-sm text-nordic-text-primary">{exampleData.prd.validation_plan}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Stories Tab - Matches CompletedEpic.jsx Feature & Story Cards */}
            <TabsContent value="stories" className="p-6 mt-0">
              <div className="space-y-4">
                {exampleData.features.map((feature, fi) => {
                  const featureStoryPoints = feature.stories.reduce((sum, s) => sum + (s.points || 0), 0);
                  const moscowClass = feature.priority === 'must-have' 
                    ? 'bg-red-500/20 text-red-400 border-red-500/30'
                    : feature.priority === 'should-have'
                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                    : 'bg-slate-500/20 text-slate-400 border-slate-500/30';
                  
                  return (
                    <Card 
                      key={fi} 
                      className="border-violet-500/30 bg-violet-500/5"
                    >
                      {/* Feature Header */}
                      <div className="p-4 pb-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-violet-500/20">
                              <Puzzle className="w-5 h-5 text-violet-400" />
                            </div>
                            <div>
                              <div className="text-base font-semibold text-nordic-text-primary flex items-center gap-2">
                                {feature.name}
                                <Lock className="w-4 h-4 text-green-400" />
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <Badge variant="outline" className="text-xs bg-green-500/10 text-green-400 border-green-500/30">
                                  Approved
                                </Badge>
                                <span className="text-xs text-nordic-text-muted">
                                  {feature.stories.length} {feature.stories.length === 1 ? 'story' : 'stories'}
                                </span>
                                {featureStoryPoints > 0 && (
                                  <span className="text-xs text-blue-400">
                                    {featureStoryPoints} pts
                                  </span>
                                )}
                                {/* MoSCoW Badge */}
                                <Badge variant="outline" className={`text-xs ${moscowClass}`}>
                                  {feature.priority === 'must-have' ? 'Must Have' : 
                                   feature.priority === 'should-have' ? 'Should Have' : 'Nice to Have'}
                                </Badge>
                                {/* RICE Badge */}
                                {feature.rice_score && (
                                  <Badge variant="outline" className="text-xs bg-teal-500/10 text-teal-400 border-teal-500/30">
                                    RICE: {feature.rice_score}
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </div>
                          <ChevronDown className="w-5 h-5 text-nordic-text-muted" />
                        </div>
                      </div>
                      
                      {/* Feature Content */}
                      <CardContent className="pt-0">
                        {/* Feature Description */}
                        <p className="text-sm text-nordic-text-muted mb-4">{feature.description}</p>
                        
                        {/* User Stories */}
                        <div className="space-y-3 pl-4 border-l-2 border-blue-500/30">
                          <p className="text-xs font-medium text-nordic-text-primary mb-2 flex items-center gap-2">
                            <BookOpen className="w-4 h-4 text-blue-400" />
                            User Stories ({feature.stories.length})
                          </p>
                          
                          {feature.stories.map((story, si) => (
                            <div 
                              key={si}
                              className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30"
                            >
                              {/* Story Header with Badges */}
                              <div className="flex items-start justify-between mb-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <BookOpen className="w-4 h-4 text-blue-400" />
                                  <Badge variant="outline" className="text-xs bg-green-500/10 text-green-400 border-green-500/30">
                                    <Lock className="w-3 h-3 mr-1" />
                                    Approved
                                  </Badge>
                                  {story.points && (
                                    <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                                      {story.points} pts
                                    </Badge>
                                  )}
                                  {/* RICE Score for Stories */}
                                  {story.rice_score && (
                                    <Badge variant="outline" className="text-xs bg-teal-500/10 text-teal-400 border-teal-500/30">
                                      RICE: {story.rice_score}
                                    </Badge>
                                  )}
                                </div>
                              </div>
                              
                              {/* Story Text (italic, quoted) */}
                              <p className="text-sm text-nordic-text-primary italic mb-2">&quot;{story.description}&quot;</p>
                              
                              {/* Acceptance Criteria */}
                              {story.acceptance_criteria?.length > 0 && (
                                <div className="bg-[#0d0d1a]/50 rounded p-2">
                                  <p className="text-xs font-medium text-nordic-text-muted mb-1">Acceptance Criteria:</p>
                                  <ul className="text-xs text-nordic-text-muted space-y-1">
                                    {story.acceptance_criteria.map((ac, ai) => (
                                      <li key={ai} className="flex items-start gap-1">
                                        <CheckCircle2 className="w-3 h-3 mt-0.5 text-green-400 flex-shrink-0" />
                                        {ac}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              
                              {/* Edge Cases */}
                              {story.edge_cases?.length > 0 && (
                                <div className="mt-2 bg-amber-500/5 border border-amber-500/20 rounded p-2">
                                  <p className="text-xs font-medium text-amber-400 mb-1">Edge Cases:</p>
                                  <ul className="text-xs text-nordic-text-muted space-y-0.5">
                                    {story.edge_cases.map((ec, ei) => (
                                      <li key={ei} className="flex items-start gap-1">
                                        <AlertTriangle className="w-3 h-3 mt-0.5 text-amber-400 flex-shrink-0" />
                                        {ec}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              
                              {/* Notes for Engineering */}
                              {story.notes_for_engineering && (
                                <div className="mt-2 bg-violet-500/5 border border-violet-500/20 rounded p-2">
                                  <p className="text-xs font-medium text-violet-400 mb-1">Notes for Engineering:</p>
                                  <p className="text-xs text-nordic-text-muted">{story.notes_for_engineering}</p>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </TabsContent>

            {/* Sprint Plan Tab */}
            <TabsContent value="sprint" className="p-6 mt-0">
              {/* Summary Header - Matches NewInitiative.jsx */}
              <Card className="bg-gradient-to-r from-nordic-accent/20 to-nordic-green/20 border-nordic-accent/30 mb-6">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-bold text-nordic-text-primary">
                        {exampleData.product_name}
                      </h2>
                      <p className="text-nordic-text-muted">{exampleData.tagline}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-nordic-accent">{exampleData.features.length}</div>
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

              <div className="space-y-4">
                {/* Sprint 1 */}
                <Card className="bg-[#0d0d1a] border-nordic-border">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold text-nordic-text-primary">Sprint 1</h4>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="border-nordic-border">
                          {exampleData.sprint_plan.sprint_1.total_points} pts
                        </Badge>
                        {(() => {
                          const status = getCapacityStatus(exampleData.sprint_plan.sprint_1.total_points);
                          return (
                            <Badge variant="outline" className={status.className}>
                              {status.label}
                            </Badge>
                          );
                        })()}
                      </div>
                    </div>
                    <p className="text-sm text-nordic-text-muted mb-3">{exampleData.sprint_plan.sprint_1.goal}</p>
                    <div className="space-y-2">
                      {exampleData.sprint_plan.sprint_1.story_ids.map((storyId) => {
                        const story = exampleData.features
                          .flatMap(f => f.stories)
                          .find(s => s.id === storyId);
                        return story ? (
                          <div key={storyId} className="flex items-center justify-between p-2 bg-[#0d0d1a] rounded">
                            <span className="text-sm text-nordic-text-primary">{story.title}</span>
                            <Badge variant="outline" className="text-xs border-nordic-border">{story.points} pts</Badge>
                          </div>
                        ) : null;
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Sprint 2 */}
                <Card className="bg-[#0d0d1a] border-nordic-border">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold text-nordic-text-primary">Sprint 2</h4>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="border-nordic-border">
                          {exampleData.sprint_plan.sprint_2.total_points} pts
                        </Badge>
                        {(() => {
                          const status = getCapacityStatus(exampleData.sprint_plan.sprint_2.total_points);
                          return (
                            <Badge variant="outline" className={status.className}>
                              {status.label}
                            </Badge>
                          );
                        })()}
                      </div>
                    </div>
                    <p className="text-sm text-nordic-text-muted mb-3">{exampleData.sprint_plan.sprint_2.goal}</p>
                    <div className="space-y-2">
                      {exampleData.sprint_plan.sprint_2.story_ids.map((storyId) => {
                        const story = exampleData.features
                          .flatMap(f => f.stories)
                          .find(s => s.id === storyId);
                        return story ? (
                          <div key={storyId} className="flex items-center justify-between p-2 bg-[#0d0d1a] rounded">
                            <span className="text-sm text-nordic-text-primary">{story.title}</span>
                            <Badge variant="outline" className="text-xs border-nordic-border">{story.points} pts</Badge>
                          </div>
                        ) : null;
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Capacity Note */}
                <div className="text-center p-4 bg-[#0d0d1a] rounded-lg border border-nordic-border">
                  <p className="text-sm text-nordic-text-muted">
                    Based on a team velocity of ~16 points/sprint
                  </p>
                  <p className="text-xs text-nordic-text-muted/70 mt-1">
                    JarlPM adapts to your actual delivery context and capacity settings
                  </p>
                </div>
              </div>
            </TabsContent>
          </ScrollArea>
        </Tabs>

        {/* Footer CTA */}
        <div className="px-6 py-4 border-t border-nordic-border bg-[#0d0d1a] flex items-center justify-between">
          <p className="text-sm text-nordic-text-muted">
            Ready to turn your idea into a plan?
          </p>
          <Button
            onClick={handleGenerateMyOwn}
            className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
            data-testid="modal-footer-generate-btn"
          >
            Generate My Own <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ExampleOutputModal;
