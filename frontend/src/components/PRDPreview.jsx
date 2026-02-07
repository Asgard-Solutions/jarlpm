import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
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
} from 'lucide-react';

/**
 * Styled PRD Preview component that matches the Example Output modal styling.
 * Parses markdown PRD content and renders it in a visually appealing format.
 */
const PRDPreview = ({ content, className = '' }) => {
  // Parse the markdown content into structured sections
  const parsedPRD = parsePRDContent(content);

  if (!parsedPRD) {
    return (
      <div className={`p-6 text-nordic-text-muted ${className}`}>
        <p>No PRD content to preview.</p>
      </div>
    );
  }

  return (
    <ScrollArea className={`h-[600px] ${className}`}>
      <div className="p-6">
        <Card className="bg-[#0d0d1a] border-nordic-border">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-nordic-text-primary flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-nordic-accent" />
              {parsedPRD.title || 'PRD Summary'}
            </h3>
            
            <div className="space-y-4">
              {/* Executive Summary / Problem */}
              {parsedPRD.problem && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                    <Target className="w-4 h-4" /> Problem
                  </div>
                  <p className="text-nordic-text-primary">{parsedPRD.problem}</p>
                  {parsedPRD.evidence && (
                    <p className="text-sm text-nordic-text-muted mt-2 italic bg-[#1a1a2e] p-2 rounded">
                      Evidence: {parsedPRD.evidence}
                    </p>
                  )}
                </div>
              )}

              {/* Vision */}
              {parsedPRD.vision && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                    <TrendingUp className="w-4 h-4" /> Vision
                  </div>
                  <p className="text-nordic-text-primary">{parsedPRD.vision}</p>
                </div>
              )}
              
              {/* Target Users */}
              {parsedPRD.targetUsers && parsedPRD.targetUsers.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                    <Users className="w-4 h-4" /> Target Users
                  </div>
                  <div className="space-y-3">
                    {parsedPRD.targetUsers.map((user, i) => (
                      <div key={i} className="bg-[#1a1a2e] p-3 rounded-lg border border-nordic-border">
                        <div className="font-medium text-nordic-text-primary mb-1">{user.persona}</div>
                        {user.context && <p className="text-sm text-nordic-text-muted mb-2">{user.context}</p>}
                        {user.painPoints && user.painPoints.length > 0 && (
                          <div className="mb-2">
                            <span className="text-xs font-medium text-red-400">Pain Points: </span>
                            <span className="text-sm text-nordic-text-muted">{user.painPoints.join(', ')}</span>
                          </div>
                        )}
                        {user.currentWorkaround && (
                          <div className="mb-2">
                            <span className="text-xs font-medium text-amber-400">Current Workaround: </span>
                            <span className="text-sm text-nordic-text-muted">{user.currentWorkaround}</span>
                          </div>
                        )}
                        {user.jtbd && (
                          <div className="text-sm text-nordic-accent italic">&ldquo;{user.jtbd}&rdquo;</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Goals / Desired Outcome */}
              {parsedPRD.goals && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                    <Check className="w-4 h-4" /> Goals & Objectives
                  </div>
                  <p className="text-nordic-text-primary">{parsedPRD.goals}</p>
                </div>
              )}

              {/* Positioning */}
              {parsedPRD.positioning && (
                <div className="bg-gradient-to-r from-nordic-accent/10 to-transparent p-3 rounded-lg border border-nordic-accent/20">
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-accent mb-2">
                    <TrendingUp className="w-4 h-4" /> Positioning
                  </div>
                  <p className="text-sm text-nordic-text-primary">{parsedPRD.positioning}</p>
                </div>
              )}
              
              {/* Key Metrics & Risks */}
              {(parsedPRD.metrics || parsedPRD.risks) && (
                <div className="grid grid-cols-2 gap-4">
                  {parsedPRD.metrics && parsedPRD.metrics.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                        <BarChart3 className="w-4 h-4" /> Key Metrics
                      </div>
                      <div className="space-y-1">
                        {parsedPRD.metrics.map((m, i) => (
                          <Badge key={i} variant="outline" className="mr-1 mb-1 text-nordic-text-primary border-nordic-border block w-fit">
                            {m}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {parsedPRD.risks && parsedPRD.risks.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                        <AlertTriangle className="w-4 h-4" /> Risks
                      </div>
                      <div className="space-y-1">
                        {parsedPRD.risks.map((r, i) => (
                          <p key={i} className="text-sm text-amber-400">{r}</p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {/* Scope - In */}
              {parsedPRD.scopeIn && parsedPRD.scopeIn.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-green-400 mb-2">
                    <CheckCircle2 className="w-4 h-4" /> In Scope
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.scopeIn.map((item, i) => (
                      <div key={i} className="bg-green-500/5 border border-green-500/20 p-2 rounded">
                        <span className="text-nordic-text-primary">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Scope - Out */}
              {parsedPRD.scopeOut && parsedPRD.scopeOut.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                    <Shield className="w-4 h-4" /> Out of Scope
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.scopeOut.map((item, i) => (
                      <div key={i} className="bg-[#1a1a2e] p-2 rounded border border-nordic-border">
                        <span className="text-nordic-text-muted">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Assumptions */}
              {parsedPRD.assumptions && parsedPRD.assumptions.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-2">
                    <Lightbulb className="w-4 h-4" /> Assumptions
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.assumptions.map((a, i) => (
                      <div key={i} className="bg-amber-500/5 border border-amber-500/20 p-2 rounded">
                        <span className="text-nordic-text-primary">{a}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Features */}
              {parsedPRD.features && parsedPRD.features.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-accent mb-2">
                    <CheckCircle2 className="w-4 h-4" /> Features
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.features.map((feature, i) => (
                      <div key={i} className="bg-nordic-accent/5 border border-nordic-accent/20 p-2 rounded">
                        <span className="font-medium text-nordic-text-primary">{feature.name}</span>
                        {feature.description && (
                          <p className="text-xs text-nordic-text-muted mt-1">{feature.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Acceptance Criteria */}
              {parsedPRD.acceptanceCriteria && parsedPRD.acceptanceCriteria.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-green-400 mb-2">
                    <CheckCircle2 className="w-4 h-4" /> Acceptance Criteria
                  </div>
                  <ul className="space-y-1">
                    {parsedPRD.acceptanceCriteria.map((ac, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <Check className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                        <span className="text-nordic-text-primary">{ac}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Timeline */}
              {parsedPRD.timeline && (
                <div className="bg-[#1a1a2e] p-3 rounded-lg border border-nordic-border">
                  <div className="flex items-center gap-2 text-sm font-medium text-nordic-text-muted mb-1">
                    Timeline
                  </div>
                  <p className="text-sm text-nordic-text-primary">{parsedPRD.timeline}</p>
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
 * Parse markdown PRD content into structured data
 */
function parsePRDContent(content) {
  if (!content) return null;

  const prd = {
    title: '',
    problem: '',
    evidence: '',
    vision: '',
    goals: '',
    positioning: '',
    targetUsers: [],
    metrics: [],
    risks: [],
    scopeIn: [],
    scopeOut: [],
    assumptions: [],
    features: [],
    acceptanceCriteria: [],
    timeline: '',
  };

  // Split content into sections
  const lines = content.split('\n');
  let currentSection = '';
  let currentUser = null;
  let buffer = [];

  const flushBuffer = () => {
    const text = buffer.join('\n').trim();
    buffer = [];
    return text;
  };

  const extractListItems = (text) => {
    return text.split('\n')
      .map(line => line.replace(/^[-*]\s*/, '').trim())
      .filter(line => line.length > 0);
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmedLine = line.trim();

    // Detect section headers
    if (trimmedLine.startsWith('# ')) {
      prd.title = trimmedLine.replace('# ', '').replace('Product Requirements Document (PRD)', '').trim();
      continue;
    }

    if (trimmedLine.startsWith('## ')) {
      // Save previous section
      if (currentSection && buffer.length > 0) {
        const text = flushBuffer();
        assignToSection(prd, currentSection, text, currentUser);
      }
      currentSection = trimmedLine.replace('## ', '').toLowerCase();
      currentUser = null;
      continue;
    }

    if (trimmedLine.startsWith('### ')) {
      // Sub-section (often user personas)
      if (buffer.length > 0) {
        const text = flushBuffer();
        assignToSection(prd, currentSection, text, currentUser);
      }
      const subSection = trimmedLine.replace('### ', '');
      if (currentSection.includes('target') || currentSection.includes('user')) {
        currentUser = { persona: subSection, painPoints: [] };
        prd.targetUsers.push(currentUser);
      }
      continue;
    }

    // Collect content
    if (trimmedLine.length > 0 && !trimmedLine.startsWith('---')) {
      // Parse special fields within user sections
      if (currentUser) {
        if (trimmedLine.toLowerCase().startsWith('context:')) {
          currentUser.context = trimmedLine.replace(/^context:\s*/i, '');
        } else if (trimmedLine.toLowerCase().startsWith('pain points:')) {
          currentUser.painPoints = trimmedLine.replace(/^pain points:\s*/i, '').split(',').map(p => p.trim());
        } else if (trimmedLine.toLowerCase().startsWith('current workaround:')) {
          currentUser.currentWorkaround = trimmedLine.replace(/^current workaround:\s*/i, '');
        } else if (trimmedLine.toLowerCase().startsWith('job to be done:') || trimmedLine.toLowerCase().startsWith('jtbd:')) {
          currentUser.jtbd = trimmedLine.replace(/^(job to be done|jtbd):\s*/i, '');
        } else {
          buffer.push(line);
        }
      } else {
        buffer.push(line);
      }
    }
  }

  // Flush remaining buffer
  if (currentSection && buffer.length > 0) {
    const text = flushBuffer();
    assignToSection(prd, currentSection, text, currentUser);
  }

  return prd;
}

function assignToSection(prd, section, text, currentUser) {
  const cleanText = text.replace(/^\*\*[^*]+\*\*:\s*/gm, '').trim();
  const listItems = text.split('\n')
    .map(line => line.replace(/^[-*]\s*/, '').replace(/^\*\*[^*]+\*\*:\s*/, '').trim())
    .filter(line => line.length > 0 && !line.startsWith('**'));

  if (section.includes('problem') || section.includes('executive summary')) {
    if (!prd.problem) {
      prd.problem = cleanText.split('\n')[0];
      // Look for evidence
      const evidenceMatch = text.match(/evidence[:\s]+(.+)/i);
      if (evidenceMatch) {
        prd.evidence = evidenceMatch[1].trim();
      }
    }
  } else if (section.includes('vision')) {
    prd.vision = cleanText;
  } else if (section.includes('goal') || section.includes('objective')) {
    prd.goals = cleanText;
  } else if (section.includes('metric') || section.includes('success')) {
    prd.metrics = listItems.length > 0 ? listItems : [cleanText];
  } else if (section.includes('risk')) {
    prd.risks = listItems.length > 0 ? listItems : [cleanText];
  } else if (section.includes('scope')) {
    if (section.includes('out')) {
      prd.scopeOut = listItems.length > 0 ? listItems : [cleanText];
    } else {
      prd.scopeIn = listItems.length > 0 ? listItems : [cleanText];
    }
  } else if (section.includes('assumption')) {
    prd.assumptions = listItems.length > 0 ? listItems : [cleanText];
  } else if (section.includes('feature')) {
    prd.features = listItems.map(item => ({ name: item, description: '' }));
  } else if (section.includes('acceptance') || section.includes('criteria')) {
    prd.acceptanceCriteria = listItems;
  } else if (section.includes('timeline') || section.includes('milestone')) {
    prd.timeline = cleanText;
  } else if (section.includes('position')) {
    prd.positioning = cleanText;
  }
}

export default PRDPreview;
