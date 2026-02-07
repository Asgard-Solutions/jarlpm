import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  FileText,
  Users,
  Target,
  Check,
  AlertTriangle,
  CheckCircle2,
  BarChart3,
  Lightbulb,
  Shield,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  Copy,
  HelpCircle,
  Layers,
  Activity,
  Lock,
  Eye,
  Clipboard,
  BookOpen,
} from 'lucide-react';
import { toast } from 'sonner';

/**
 * Comprehensive PRD Preview component for structured JSON PRDs.
 * Supports collapsible sections, markdown fallback, and export.
 */
const PRDPreview = ({ content, prdData, format = 'markdown', className = '' }) => {
  // If we have structured JSON PRD data, render that
  if (format === 'json' && prdData) {
    return <StructuredPRDPreview prd={prdData} className={className} />;
  }
  
  // Fallback to legacy markdown parsing
  const parsedPRD = parsePRDContent(content);
  if (!parsedPRD) {
    return (
      <div className={`p-6 text-muted-foreground ${className}`}>
        <p>No PRD content to preview.</p>
      </div>
    );
  }
  
  return <LegacyPRDPreview prd={parsedPRD} className={className} />;
};

/**
 * Collapsible section component
 */
const PRDSection = ({ 
  title, 
  icon: Icon, 
  children, 
  defaultOpen = false,
  badge = null,
  accentColor = 'violet'
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  const colorClasses = {
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/30',
    green: 'text-green-400 bg-green-500/10 border-green-500/30',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    red: 'text-red-400 bg-red-500/10 border-red-500/30',
    slate: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
  };
  
  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 transition-colors">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded ${colorClasses[accentColor]}`}>
              <Icon className="w-4 h-4" />
            </div>
            <span className="font-medium text-slate-100">{title}</span>
            {badge && (
              <Badge variant="outline" className="text-xs border-slate-600 text-slate-400">
                {badge}
              </Badge>
            )}
          </div>
          {isOpen ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 pl-2">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
};

/**
 * Structured PRD Preview for JSON format
 */
const StructuredPRDPreview = ({ prd, className }) => {
  const [copied, setCopied] = useState(false);
  
  const handleCopyMarkdown = () => {
    const markdown = generateMarkdownFromPRD(prd);
    navigator.clipboard.writeText(markdown);
    setCopied(true);
    toast.success('PRD copied as Markdown');
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <ScrollArea className={`h-[600px] ${className}`}>
      <div className="p-6 space-y-4">
        {/* Header with Export */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-violet-400" />
            <h3 className="text-lg font-semibold text-slate-100">
              {prd.summary?.title || 'Product Requirements Document'}
            </h3>
            <Badge variant="outline" className="text-xs border-violet-500/30 text-violet-400">
              v{prd.summary?.version || '1.0'}
            </Badge>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyMarkdown}
            className="gap-1"
          >
            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            {copied ? 'Copied!' : 'Copy as Markdown'}
          </Button>
        </div>

        {/* 1. Summary Section - Always Open */}
        <PRDSection title="Summary" icon={FileText} defaultOpen={true} accentColor="violet">
          <Card className="bg-[#0d0d1a] border-slate-700/50">
            <CardContent className="p-4 space-y-3">
              {prd.summary?.overview && (
                <div>
                  <p className="text-xs font-medium text-slate-400 mb-1">Overview</p>
                  <p className="text-sm text-slate-100">{prd.summary.overview}</p>
                </div>
              )}
              {prd.summary?.problem_statement && (
                <div className="bg-red-500/5 border border-red-500/20 rounded p-3">
                  <p className="text-xs font-medium text-red-400 mb-1">Problem Statement</p>
                  <p className="text-sm text-slate-100">{prd.summary.problem_statement}</p>
                </div>
              )}
              {prd.summary?.goal && (
                <div className="bg-green-500/5 border border-green-500/20 rounded p-3">
                  <p className="text-xs font-medium text-green-400 mb-1">Goal / Desired Outcome</p>
                  <p className="text-sm text-slate-100">{prd.summary.goal}</p>
                </div>
              )}
              {prd.summary?.target_users && (
                <div>
                  <p className="text-xs font-medium text-slate-400 mb-1">Target Users</p>
                  <p className="text-sm text-slate-100">{prd.summary.target_users}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </PRDSection>

        {/* 2. Context & Evidence */}
        {prd.context && (
          <PRDSection title="Context & Evidence" icon={BookOpen} accentColor="blue">
            <Card className="bg-[#0d0d1a] border-slate-700/50">
              <CardContent className="p-4 space-y-3">
                {prd.context.evidence?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 mb-2">Evidence</p>
                    <ul className="space-y-1">
                      {prd.context.evidence.map((item, i) => (
                        <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                          <CheckCircle2 className="w-3 h-3 mt-1 text-blue-400 flex-shrink-0" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {prd.context.current_workflow && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 mb-1">Current Workflow</p>
                    <p className="text-sm text-slate-300">{prd.context.current_workflow}</p>
                  </div>
                )}
                {prd.context.why_now && (
                  <div className="bg-amber-500/5 border border-amber-500/20 rounded p-3">
                    <p className="text-xs font-medium text-amber-400 mb-1">Why Now?</p>
                    <p className="text-sm text-slate-100">{prd.context.why_now}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </PRDSection>
        )}

        {/* 3. Personas / JTBD */}
        {prd.personas?.length > 0 && (
          <PRDSection 
            title="Personas & Jobs-to-be-Done" 
            icon={Users} 
            badge={`${prd.personas.length} personas`}
            accentColor="violet"
          >
            <div className="space-y-3">
              {prd.personas.map((persona, i) => (
                <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center">
                        <Users className="w-4 h-4 text-violet-400" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-100">{persona.name}</p>
                        <p className="text-xs text-slate-400">{persona.context}</p>
                      </div>
                    </div>
                    {persona.jtbd && (
                      <div className="bg-violet-500/5 border border-violet-500/20 rounded p-2 mb-2">
                        <p className="text-xs font-medium text-violet-400 mb-1">Job to be Done</p>
                        <p className="text-sm text-slate-100 italic">&ldquo;{persona.jtbd}&rdquo;</p>
                      </div>
                    )}
                    {persona.pain_points?.length > 0 && (
                      <div className="mb-2">
                        <p className="text-xs font-medium text-red-400 mb-1">Pain Points</p>
                        <ul className="space-y-0.5">
                          {persona.pain_points.map((pain, j) => (
                            <li key={j} className="text-xs text-slate-300 flex items-start gap-1">
                              <AlertTriangle className="w-3 h-3 mt-0.5 text-red-400 flex-shrink-0" />
                              {pain}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {persona.current_workaround && (
                      <div>
                        <p className="text-xs font-medium text-amber-400 mb-1">Current Workaround</p>
                        <p className="text-xs text-slate-300">{persona.current_workaround}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </PRDSection>
        )}

        {/* 4. Scope */}
        {prd.scope && (
          <PRDSection title="Scope" icon={Target} accentColor="green">
            <div className="space-y-3">
              {/* MVP In */}
              {prd.scope.mvp_in?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-400 mb-2 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> MVP Scope (In)
                  </p>
                  <div className="space-y-2">
                    {prd.scope.mvp_in.map((item, i) => (
                      <div key={i} className="bg-green-500/5 border border-green-500/20 rounded p-2">
                        <p className="text-sm font-medium text-slate-100">{item.item}</p>
                        {item.rationale && (
                          <p className="text-xs text-slate-400 mt-1">{item.rationale}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Not Now */}
              {prd.scope.not_now?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-400 mb-2 flex items-center gap-1">
                    <Shield className="w-3 h-3" /> Deferred (Not Now)
                  </p>
                  <div className="space-y-2">
                    {prd.scope.not_now.map((item, i) => (
                      <div key={i} className="bg-slate-700/30 border border-slate-600/30 rounded p-2">
                        <p className="text-sm text-slate-300">{item.item}</p>
                        {item.rationale && (
                          <p className="text-xs text-slate-500 mt-1">Why: {item.rationale}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Assumptions */}
              {prd.scope.assumptions?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-amber-400 mb-2 flex items-center gap-1">
                    <Lightbulb className="w-3 h-3" /> Assumptions to Validate
                  </p>
                  <div className="space-y-2">
                    {prd.scope.assumptions.map((item, i) => (
                      <div key={i} className="bg-amber-500/5 border border-amber-500/20 rounded p-2">
                        <p className="text-sm font-medium text-slate-100">{item.assumption}</p>
                        {item.risk_if_wrong && (
                          <p className="text-xs text-red-400 mt-1">Risk if wrong: {item.risk_if_wrong}</p>
                        )}
                        {item.validation && (
                          <p className="text-xs text-green-400 mt-1">Validation: {item.validation}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </PRDSection>
        )}

        {/* 5. Requirements */}
        {prd.requirements?.features?.length > 0 && (
          <PRDSection 
            title="Requirements" 
            icon={Layers} 
            badge={`${prd.requirements.features.length} features`}
            accentColor="violet"
          >
            <div className="space-y-3">
              {prd.requirements.features.map((feature, i) => (
                <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-medium text-slate-100">{feature.name}</p>
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${
                          feature.priority === 'must-have' 
                            ? 'border-red-500/30 text-red-400'
                            : feature.priority === 'should-have'
                            ? 'border-amber-500/30 text-amber-400'
                            : 'border-slate-500/30 text-slate-400'
                        }`}
                      >
                        {feature.priority}
                      </Badge>
                    </div>
                    {feature.description && (
                      <p className="text-sm text-slate-400 mb-3">{feature.description}</p>
                    )}
                    {feature.stories?.length > 0 && (
                      <div className="space-y-2 pl-3 border-l-2 border-blue-500/30">
                        {feature.stories.map((story, j) => (
                          <div key={j} className="bg-blue-500/5 rounded p-2">
                            <p className="text-sm text-slate-100 italic">&ldquo;{story.story}&rdquo;</p>
                            {story.acceptance_criteria?.length > 0 && (
                              <div className="mt-2">
                                <p className="text-xs font-medium text-slate-400 mb-1">Acceptance Criteria:</p>
                                <ul className="space-y-0.5">
                                  {story.acceptance_criteria.map((ac, k) => (
                                    <li key={k} className="text-xs text-slate-300 flex items-start gap-1">
                                      <Check className="w-3 h-3 mt-0.5 text-green-400 flex-shrink-0" />
                                      {ac}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {story.edge_cases?.length > 0 && (
                              <div className="mt-2">
                                <p className="text-xs font-medium text-amber-400 mb-1">Edge Cases:</p>
                                <ul className="space-y-0.5">
                                  {story.edge_cases.map((ec, k) => (
                                    <li key={k} className="text-xs text-slate-300 flex items-start gap-1">
                                      <AlertTriangle className="w-3 h-3 mt-0.5 text-amber-400 flex-shrink-0" />
                                      {ec}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </PRDSection>
        )}

        {/* 6. NFRs */}
        {prd.nfrs && (
          <PRDSection title="Non-Functional Requirements" icon={Shield} accentColor="blue">
            <Card className="bg-[#0d0d1a] border-slate-700/50">
              <CardContent className="p-4 grid grid-cols-2 gap-4">
                {prd.nfrs.performance?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-blue-400 mb-2 flex items-center gap-1">
                      <Activity className="w-3 h-3" /> Performance
                    </p>
                    <ul className="space-y-1">
                      {prd.nfrs.performance.map((item, i) => (
                        <li key={i} className="text-xs text-slate-300">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {prd.nfrs.reliability?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-green-400 mb-2 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Reliability
                    </p>
                    <ul className="space-y-1">
                      {prd.nfrs.reliability.map((item, i) => (
                        <li key={i} className="text-xs text-slate-300">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {prd.nfrs.security?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-400 mb-2 flex items-center gap-1">
                      <Lock className="w-3 h-3" /> Security
                    </p>
                    <ul className="space-y-1">
                      {prd.nfrs.security.map((item, i) => (
                        <li key={i} className="text-xs text-slate-300">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {prd.nfrs.accessibility?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-violet-400 mb-2 flex items-center gap-1">
                      <Eye className="w-3 h-3" /> Accessibility
                    </p>
                    <ul className="space-y-1">
                      {prd.nfrs.accessibility.map((item, i) => (
                        <li key={i} className="text-xs text-slate-300">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          </PRDSection>
        )}

        {/* 7. Metrics */}
        {prd.metrics && (
          <PRDSection title="Metrics & Analytics" icon={BarChart3} accentColor="green">
            <Card className="bg-[#0d0d1a] border-slate-700/50">
              <CardContent className="p-4 space-y-3">
                {prd.metrics.success_metrics?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-green-400 mb-2">Success Metrics</p>
                    <div className="space-y-2">
                      {prd.metrics.success_metrics.map((m, i) => (
                        <div key={i} className="bg-green-500/5 border border-green-500/20 rounded p-2">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium text-slate-100">{m.metric}</p>
                            <Badge variant="outline" className="text-xs border-green-500/30 text-green-400">
                              {m.target}
                            </Badge>
                          </div>
                          {m.measurement && (
                            <p className="text-xs text-slate-400 mt-1">{m.measurement}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {prd.metrics.guardrails?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-400 mb-2">Guardrail Metrics</p>
                    <ul className="space-y-1">
                      {prd.metrics.guardrails.map((g, i) => (
                        <li key={i} className="text-xs text-slate-300 flex items-start gap-1">
                          <Shield className="w-3 h-3 mt-0.5 text-red-400 flex-shrink-0" />
                          {g}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {prd.metrics.instrumentation?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-blue-400 mb-2">Instrumentation</p>
                    <div className="flex flex-wrap gap-1">
                      {prd.metrics.instrumentation.map((event, i) => (
                        <Badge key={i} variant="outline" className="text-xs border-slate-600 text-slate-400">
                          {event}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {prd.metrics.evaluation_window && (
                  <div className="bg-slate-700/30 rounded p-2">
                    <p className="text-xs font-medium text-slate-400 mb-1">Evaluation Window</p>
                    <p className="text-sm text-slate-300">{prd.metrics.evaluation_window}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </PRDSection>
        )}

        {/* 8. Risks */}
        {prd.risks?.length > 0 && (
          <PRDSection 
            title="Risks" 
            icon={AlertTriangle} 
            badge={`${prd.risks.length} risks`}
            accentColor="red"
          >
            <div className="space-y-2">
              {prd.risks.map((risk, i) => (
                <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between mb-2">
                      <p className="text-sm font-medium text-slate-100">{risk.risk}</p>
                      <div className="flex items-center gap-1">
                        <Badge variant="outline" className="text-xs border-slate-600 text-slate-400">
                          {risk.type}
                        </Badge>
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${
                            risk.impact === 'high' 
                              ? 'border-red-500/30 text-red-400'
                              : risk.impact === 'medium'
                              ? 'border-amber-500/30 text-amber-400'
                              : 'border-slate-500/30 text-slate-400'
                          }`}
                        >
                          {risk.likelihood}/{risk.impact}
                        </Badge>
                      </div>
                    </div>
                    {risk.mitigation && (
                      <div className="bg-green-500/5 border border-green-500/20 rounded p-2">
                        <p className="text-xs font-medium text-green-400 mb-1">Mitigation</p>
                        <p className="text-xs text-slate-300">{risk.mitigation}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </PRDSection>
        )}

        {/* 9. Open Questions */}
        {prd.open_questions?.length > 0 && (
          <PRDSection 
            title="Open Questions" 
            icon={HelpCircle} 
            badge={`${prd.open_questions.filter(q => q.status === 'open').length} open`}
            accentColor="amber"
          >
            <div className="space-y-2">
              {prd.open_questions.map((q, i) => (
                <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between">
                      <p className="text-sm text-slate-100">{q.question}</p>
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${
                          q.status === 'open' 
                            ? 'border-amber-500/30 text-amber-400'
                            : q.status === 'in-progress'
                            ? 'border-blue-500/30 text-blue-400'
                            : 'border-green-500/30 text-green-400'
                        }`}
                      >
                        {q.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                      {q.owner && <span>Owner: {q.owner}</span>}
                      {q.due_date && <span>Due: {q.due_date}</span>}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </PRDSection>
        )}

        {/* 10. Appendix */}
        {prd.appendix && (prd.appendix.alternatives_considered?.length > 0 || prd.appendix.glossary?.length > 0) && (
          <PRDSection title="Appendix" icon={Clipboard} accentColor="slate">
            <Card className="bg-[#0d0d1a] border-slate-700/50">
              <CardContent className="p-4 space-y-3">
                {prd.appendix.alternatives_considered?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 mb-2">Alternatives Considered</p>
                    <ul className="space-y-1">
                      {prd.appendix.alternatives_considered.map((alt, i) => (
                        <li key={i} className="text-xs text-slate-300">{alt}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {prd.appendix.glossary?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-400 mb-2">Glossary</p>
                    <div className="space-y-1">
                      {prd.appendix.glossary.map((item, i) => (
                        <div key={i} className="text-xs">
                          <span className="font-medium text-slate-100">{item.term}:</span>{' '}
                          <span className="text-slate-400">{item.definition}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </PRDSection>
        )}
      </div>
    </ScrollArea>
  );
};

/**
 * Generate Markdown from structured PRD JSON
 */
function generateMarkdownFromPRD(prd) {
  const lines = [];
  
  lines.push(`# ${prd.summary?.title || 'Product Requirements Document'}`);
  lines.push(`**Version:** ${prd.summary?.version || '1.0'}`);
  lines.push(`**Owner:** ${prd.summary?.owner || 'Product Manager'}`);
  lines.push('');
  
  // Summary
  lines.push('## 1. Summary');
  if (prd.summary?.overview) lines.push(`\n${prd.summary.overview}\n`);
  if (prd.summary?.problem_statement) {
    lines.push('### Problem Statement');
    lines.push(prd.summary.problem_statement);
    lines.push('');
  }
  if (prd.summary?.goal) {
    lines.push('### Goal');
    lines.push(prd.summary.goal);
    lines.push('');
  }
  if (prd.summary?.target_users) {
    lines.push('### Target Users');
    lines.push(prd.summary.target_users);
    lines.push('');
  }
  
  // Context
  if (prd.context) {
    lines.push('## 2. Context & Evidence');
    if (prd.context.evidence?.length) {
      lines.push('### Evidence');
      prd.context.evidence.forEach(e => lines.push(`- ${e}`));
      lines.push('');
    }
    if (prd.context.current_workflow) {
      lines.push('### Current Workflow');
      lines.push(prd.context.current_workflow);
      lines.push('');
    }
    if (prd.context.why_now) {
      lines.push('### Why Now');
      lines.push(prd.context.why_now);
      lines.push('');
    }
  }
  
  // Personas
  if (prd.personas?.length) {
    lines.push('## 3. Personas & JTBD');
    prd.personas.forEach(p => {
      lines.push(`### ${p.name}`);
      if (p.context) lines.push(`*${p.context}*`);
      if (p.jtbd) lines.push(`\n**JTBD:** "${p.jtbd}"`);
      if (p.pain_points?.length) {
        lines.push('\n**Pain Points:**');
        p.pain_points.forEach(pain => lines.push(`- ${pain}`));
      }
      if (p.current_workaround) lines.push(`\n**Current Workaround:** ${p.current_workaround}`);
      lines.push('');
    });
  }
  
  // Scope
  if (prd.scope) {
    lines.push('## 4. Scope');
    if (prd.scope.mvp_in?.length) {
      lines.push('### MVP Scope (In)');
      prd.scope.mvp_in.forEach(item => {
        lines.push(`- **${item.item}**: ${item.rationale || ''}`);
      });
      lines.push('');
    }
    if (prd.scope.not_now?.length) {
      lines.push('### Deferred (Not Now)');
      prd.scope.not_now.forEach(item => {
        lines.push(`- **${item.item}**: ${item.rationale || ''}`);
      });
      lines.push('');
    }
    if (prd.scope.assumptions?.length) {
      lines.push('### Assumptions');
      prd.scope.assumptions.forEach(a => {
        lines.push(`- **${a.assumption}**`);
        if (a.risk_if_wrong) lines.push(`  - Risk if wrong: ${a.risk_if_wrong}`);
        if (a.validation) lines.push(`  - Validation: ${a.validation}`);
      });
      lines.push('');
    }
  }
  
  // Requirements
  if (prd.requirements?.features?.length) {
    lines.push('## 5. Requirements');
    prd.requirements.features.forEach(f => {
      lines.push(`### ${f.name} [${f.priority}]`);
      if (f.description) lines.push(f.description);
      if (f.stories?.length) {
        f.stories.forEach(s => {
          lines.push(`\n**User Story:** "${s.story}"`);
          if (s.acceptance_criteria?.length) {
            lines.push('**Acceptance Criteria:**');
            s.acceptance_criteria.forEach(ac => lines.push(`- ${ac}`));
          }
          if (s.edge_cases?.length) {
            lines.push('**Edge Cases:**');
            s.edge_cases.forEach(ec => lines.push(`- ${ec}`));
          }
        });
      }
      lines.push('');
    });
  }
  
  // NFRs
  if (prd.nfrs) {
    lines.push('## 6. Non-Functional Requirements');
    if (prd.nfrs.performance?.length) {
      lines.push('### Performance');
      prd.nfrs.performance.forEach(p => lines.push(`- ${p}`));
    }
    if (prd.nfrs.reliability?.length) {
      lines.push('### Reliability');
      prd.nfrs.reliability.forEach(r => lines.push(`- ${r}`));
    }
    if (prd.nfrs.security?.length) {
      lines.push('### Security');
      prd.nfrs.security.forEach(s => lines.push(`- ${s}`));
    }
    if (prd.nfrs.accessibility?.length) {
      lines.push('### Accessibility');
      prd.nfrs.accessibility.forEach(a => lines.push(`- ${a}`));
    }
    lines.push('');
  }
  
  // Metrics
  if (prd.metrics) {
    lines.push('## 7. Metrics & Analytics');
    if (prd.metrics.success_metrics?.length) {
      lines.push('### Success Metrics');
      prd.metrics.success_metrics.forEach(m => {
        lines.push(`- **${m.metric}**: Target ${m.target} (${m.measurement})`);
      });
    }
    if (prd.metrics.guardrails?.length) {
      lines.push('### Guardrails');
      prd.metrics.guardrails.forEach(g => lines.push(`- ${g}`));
    }
    if (prd.metrics.instrumentation?.length) {
      lines.push('### Instrumentation');
      lines.push(`Events: ${prd.metrics.instrumentation.join(', ')}`);
    }
    if (prd.metrics.evaluation_window) {
      lines.push(`\n**Evaluation:** ${prd.metrics.evaluation_window}`);
    }
    lines.push('');
  }
  
  // Risks
  if (prd.risks?.length) {
    lines.push('## 8. Risks');
    prd.risks.forEach(r => {
      lines.push(`### ${r.risk}`);
      lines.push(`- Type: ${r.type}`);
      lines.push(`- Likelihood: ${r.likelihood}, Impact: ${r.impact}`);
      if (r.mitigation) lines.push(`- Mitigation: ${r.mitigation}`);
      lines.push('');
    });
  }
  
  // Open Questions
  if (prd.open_questions?.length) {
    lines.push('## 9. Open Questions');
    prd.open_questions.forEach(q => {
      lines.push(`- [ ] **${q.question}** (Owner: ${q.owner}, Due: ${q.due_date}) [${q.status}]`);
    });
    lines.push('');
  }
  
  return lines.join('\n');
}

/**
 * Legacy markdown PRD preview (fallback)
 */
const LegacyPRDPreview = ({ prd, className }) => {
  return (
    <ScrollArea className={`h-[600px] ${className}`}>
      <div className="p-6">
        <Card className="bg-[#0d0d1a] border-slate-700/50">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-violet-400" />
              {prd.title || 'PRD Summary'}
            </h3>
            
            <div className="space-y-4">
              {prd.problem && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-1">
                    <Target className="w-4 h-4" /> Problem
                  </div>
                  <p className="text-slate-100">{prd.problem}</p>
                </div>
              )}
              
              {prd.goals && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-1">
                    <Check className="w-4 h-4" /> Goals
                  </div>
                  <p className="text-slate-100">{prd.goals}</p>
                </div>
              )}
              
              {prd.targetUsers?.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                    <Users className="w-4 h-4" /> Target Users
                  </div>
                  <div className="space-y-2">
                    {prd.targetUsers.map((user, i) => (
                      <div key={i} className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                        <p className="font-medium text-slate-100">{user.persona}</p>
                        {user.context && <p className="text-sm text-slate-400">{user.context}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  );
};

/**
 * Parse legacy markdown PRD content (minimal fallback)
 */
function parsePRDContent(content) {
  if (!content) return null;
  
  return {
    title: 'PRD',
    problem: content.substring(0, 500),
    goals: '',
    targetUsers: [],
  };
}

export default PRDPreview;
