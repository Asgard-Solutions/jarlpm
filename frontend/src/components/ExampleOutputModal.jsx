import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
  ListChecks,
  Calendar,
  Users,
  Target,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
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

  // Calculate capacity status for sprint plan
  const getCapacityStatus = (points, capacity = 16) => {
    const ratio = points / capacity;
    if (ratio <= 0.9) return { status: 'on-track', color: 'text-green-600 bg-green-100', label: 'On Track' };
    if (ratio <= 1.1) return { status: 'at-risk', color: 'text-yellow-600 bg-yellow-100', label: 'At Risk' };
    return { status: 'overloaded', color: 'text-red-600 bg-red-100', label: 'Overloaded' };
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <div className="flex items-center justify-between">
            <div>
              <Badge variant="outline" className="mb-2 text-xs">
                <Sparkles className="w-3 h-3 mr-1" />
                Example Output
              </Badge>
              <DialogTitle className="text-xl">
                {exampleData.epic.title}
              </DialogTitle>
              <p className="text-sm text-muted-foreground mt-1">
                {exampleData.epic.vision}
              </p>
            </div>
            <Button
              onClick={handleGenerateMyOwn}
              className="bg-primary hover:bg-primary/90"
              data-testid="modal-generate-my-own-btn"
            >
              Generate My Own <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1">
          <div className="px-6 pt-4 border-b">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="prd" className="flex items-center gap-2" data-testid="tab-prd">
                <FileText className="w-4 h-4" />
                PRD
              </TabsTrigger>
              <TabsTrigger value="stories" className="flex items-center gap-2" data-testid="tab-stories">
                <ListChecks className="w-4 h-4" />
                Stories
              </TabsTrigger>
              <TabsTrigger value="sprint" className="flex items-center gap-2" data-testid="tab-sprint">
                <Calendar className="w-4 h-4" />
                Sprint Plan
              </TabsTrigger>
            </TabsList>
          </div>

          <ScrollArea className="h-[60vh]">
            {/* PRD Tab */}
            <TabsContent value="prd" className="p-6 mt-0">
              <div className="flex justify-end mb-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyPRD}
                  data-testid="copy-prd-btn"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 mr-2" />
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

              <div className="space-y-6">
                {/* Problem Statement */}
                <div>
                  <h3 className="font-semibold text-lg mb-2 flex items-center gap-2">
                    <Target className="w-5 h-5 text-primary" />
                    Problem Statement
                  </h3>
                  <p className="text-muted-foreground">{exampleData.prd.problem_statement}</p>
                  <p className="text-sm text-muted-foreground/80 mt-2 italic">
                    {exampleData.prd.problem_evidence}
                  </p>
                </div>

                {/* Target Users */}
                <div>
                  <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                    <Users className="w-5 h-5 text-primary" />
                    Target Users
                  </h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {exampleData.prd.target_users.map((user, i) => (
                      <Card key={i} className="bg-muted/30">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base">{user.persona}</CardTitle>
                          <p className="text-sm text-muted-foreground">{user.context}</p>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          <div>
                            <p className="text-xs font-medium text-muted-foreground uppercase">Pain Points</p>
                            <ul className="text-sm space-y-1 mt-1">
                              {user.pain_points.map((p, j) => (
                                <li key={j} className="flex items-start gap-2">
                                  <span className="text-destructive">•</span>
                                  <span>{p}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div className="pt-2 border-t">
                            <p className="text-xs font-medium text-muted-foreground uppercase">Job to Be Done</p>
                            <p className="text-sm mt-1 italic">"{user.jtbd}"</p>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>

                {/* Key Metrics */}
                <div>
                  <h3 className="font-semibold text-lg mb-2">Key Metrics</h3>
                  <ul className="space-y-2">
                    {exampleData.prd.key_metrics.map((metric, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                        <span>{metric}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Assumptions & Risks */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="font-semibold text-lg mb-2 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5 text-yellow-600" />
                      Riskiest Unknown
                    </h3>
                    <p className="text-sm text-muted-foreground p-3 bg-yellow-50 dark:bg-yellow-950/20 rounded-lg border border-yellow-200 dark:border-yellow-900">
                      {exampleData.prd.riskiest_unknown}
                    </p>
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg mb-2">Validation Plan</h3>
                    <p className="text-sm text-muted-foreground p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-900">
                      {exampleData.prd.validation_plan}
                    </p>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Stories Tab */}
            <TabsContent value="stories" className="p-6 mt-0">
              <div className="space-y-6">
                {exampleData.features.slice(0, 2).map((feature) => (
                  <div key={feature.id}>
                    <div className="flex items-center gap-2 mb-3">
                      <Badge variant={feature.priority === 'must-have' ? 'default' : 'secondary'}>
                        {feature.priority}
                      </Badge>
                      <h3 className="font-semibold">{feature.name}</h3>
                    </div>
                    <p className="text-sm text-muted-foreground mb-4">{feature.description}</p>
                    
                    <div className="space-y-3">
                      {feature.stories.slice(0, 2).map((story) => (
                        <Card key={story.id} className="bg-card border">
                          <CardHeader className="pb-2">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <CardTitle className="text-sm font-medium">{story.title}</CardTitle>
                                <p className="text-xs text-muted-foreground mt-1">{story.description}</p>
                              </div>
                              <Badge variant="outline" className="ml-2 shrink-0">
                                {story.points} pts
                              </Badge>
                            </div>
                          </CardHeader>
                          <CardContent className="space-y-3">
                            {/* Acceptance Criteria */}
                            <div>
                              <p className="text-xs font-medium text-muted-foreground uppercase mb-1">
                                Acceptance Criteria
                              </p>
                              <ul className="text-xs space-y-1">
                                {story.acceptance_criteria.slice(0, 2).map((ac, i) => (
                                  <li key={i} className="flex items-start gap-2 bg-muted/50 p-2 rounded">
                                    <CheckCircle2 className="w-3 h-3 text-green-600 mt-0.5 flex-shrink-0" />
                                    <span className="font-mono">{ac}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>

                            {/* Edge Cases */}
                            {story.edge_cases && story.edge_cases.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-muted-foreground uppercase mb-1">
                                  Edge Cases
                                </p>
                                <ul className="text-xs space-y-1">
                                  {story.edge_cases.slice(0, 2).map((ec, i) => (
                                    <li key={i} className="flex items-start gap-2">
                                      <AlertTriangle className="w-3 h-3 text-yellow-600 mt-0.5 flex-shrink-0" />
                                      <span>{ec}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* Engineering Notes */}
                            {story.notes_for_engineering && (
                              <div className="pt-2 border-t">
                                <p className="text-xs font-medium text-muted-foreground uppercase mb-1">
                                  Notes for Engineering
                                </p>
                                <p className="text-xs text-muted-foreground bg-muted/50 p-2 rounded">
                                  {story.notes_for_engineering}
                                </p>
                              </div>
                            )}

                            {/* Labels */}
                            <div className="flex flex-wrap gap-1 pt-2">
                              {story.labels.map((label) => (
                                <Badge key={label} variant="outline" className="text-xs px-1.5 py-0">
                                  {label}
                                </Badge>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                ))}

                <p className="text-sm text-muted-foreground text-center italic">
                  + {exampleData.features.reduce((acc, f) => acc + f.stories.length, 0) - 4} more stories across {exampleData.features.length} features
                </p>
              </div>
            </TabsContent>

            {/* Sprint Plan Tab */}
            <TabsContent value="sprint" className="p-6 mt-0">
              <div className="space-y-6">
                {/* Summary Stats */}
                <div className="grid grid-cols-3 gap-4">
                  <Card className="bg-muted/30">
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold text-primary">{exampleData.total_points}</p>
                      <p className="text-sm text-muted-foreground">Total Points</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-muted/30">
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold">{exampleData.features.length}</p>
                      <p className="text-sm text-muted-foreground">Features</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-muted/30">
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold">{exampleData.features.reduce((acc, f) => acc + f.stories.length, 0)}</p>
                      <p className="text-sm text-muted-foreground">Stories</p>
                    </CardContent>
                  </Card>
                </div>

                {/* Sprint 1 */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Sprint 1</CardTitle>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{exampleData.sprint_plan.sprint_1.total_points} pts</Badge>
                        {(() => {
                          const status = getCapacityStatus(exampleData.sprint_plan.sprint_1.total_points);
                          return (
                            <Badge className={status.color}>
                              {status.label}
                            </Badge>
                          );
                        })()}
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">{exampleData.sprint_plan.sprint_1.goal}</p>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {exampleData.sprint_plan.sprint_1.story_ids.map((storyId) => {
                        const story = exampleData.features
                          .flatMap(f => f.stories)
                          .find(s => s.id === storyId);
                        return story ? (
                          <li key={storyId} className="flex items-center justify-between p-2 bg-muted/30 rounded">
                            <span className="text-sm">{story.title}</span>
                            <Badge variant="outline" className="text-xs">{story.points} pts</Badge>
                          </li>
                        ) : null;
                      })}
                    </ul>
                  </CardContent>
                </Card>

                {/* Sprint 2 */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Sprint 2</CardTitle>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{exampleData.sprint_plan.sprint_2.total_points} pts</Badge>
                        {(() => {
                          const status = getCapacityStatus(exampleData.sprint_plan.sprint_2.total_points);
                          return (
                            <Badge className={status.color}>
                              {status.label}
                            </Badge>
                          );
                        })()}
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">{exampleData.sprint_plan.sprint_2.goal}</p>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {exampleData.sprint_plan.sprint_2.story_ids.map((storyId) => {
                        const story = exampleData.features
                          .flatMap(f => f.stories)
                          .find(s => s.id === storyId);
                        return story ? (
                          <li key={storyId} className="flex items-center justify-between p-2 bg-muted/30 rounded">
                            <span className="text-sm">{story.title}</span>
                            <Badge variant="outline" className="text-xs">{story.points} pts</Badge>
                          </li>
                        ) : null;
                      })}
                    </ul>
                  </CardContent>
                </Card>

                {/* Capacity Note */}
                <div className="text-center p-4 bg-muted/30 rounded-lg">
                  <p className="text-sm text-muted-foreground">
                    Based on a team velocity of ~16 points/sprint
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1">
                    JarlPM adapts to your actual delivery context and capacity settings
                  </p>
                </div>
              </div>
            </TabsContent>
          </ScrollArea>
        </Tabs>

        {/* Footer CTA */}
        <div className="px-6 py-4 border-t bg-muted/30 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Ready to turn your idea into a plan?
          </p>
          <Button
            onClick={handleGenerateMyOwn}
            className="bg-primary hover:bg-primary/90"
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
