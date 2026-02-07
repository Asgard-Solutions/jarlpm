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
      <div className={`p-6 text-muted-foreground ${className}`}>
        <p>No PRD content to preview.</p>
      </div>
    );
  }

  return (
    <ScrollArea className={`h-[600px] ${className}`}>
      <div className="p-6">
        <Card className="bg-[#0d0d1a] border-slate-700/50">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-violet-400" />
              {parsedPRD.title || 'PRD Summary'}
            </h3>
            
            <div className="space-y-4">
              {/* Problem Statement */}
              {parsedPRD.problem && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-1">
                    <Target className="w-4 h-4" /> Problem
                  </div>
                  <p className="text-slate-100">{parsedPRD.problem}</p>
                  {parsedPRD.evidence && (
                    <p className="text-sm text-slate-400 mt-2 italic bg-slate-800/50 p-2 rounded">
                      Evidence: {parsedPRD.evidence}
                    </p>
                  )}
                </div>
              )}

              {/* Target Users */}
              {parsedPRD.targetUsers && parsedPRD.targetUsers.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                    <Users className="w-4 h-4" /> Target Users
                  </div>
                  <div className="space-y-3">
                    {parsedPRD.targetUsers.map((user, i) => (
                      <div key={i} className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                        <div className="font-medium text-slate-100 mb-1">{user.persona}</div>
                        {user.context && <p className="text-sm text-slate-400 mb-2">{user.context}</p>}
                        {user.painPoints && user.painPoints.length > 0 && (
                          <div className="mb-2">
                            <span className="text-xs font-medium text-red-400">Pain Points: </span>
                            <span className="text-sm text-slate-400">{user.painPoints.join(', ')}</span>
                          </div>
                        )}
                        {user.currentWorkaround && (
                          <div className="mb-2">
                            <span className="text-xs font-medium text-amber-400">Current Workaround: </span>
                            <span className="text-sm text-slate-400">{user.currentWorkaround}</span>
                          </div>
                        )}
                        {user.jtbd && (
                          <div className="text-sm text-violet-400 italic">&ldquo;{user.jtbd}&rdquo;</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Desired Outcome / Goals */}
              {parsedPRD.goals && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-1">
                    <Check className="w-4 h-4" /> Desired Outcome
                  </div>
                  <p className="text-slate-100">{parsedPRD.goals}</p>
                </div>
              )}

              {/* Positioning */}
              {parsedPRD.positioning && (
                <div className="bg-gradient-to-r from-violet-500/10 to-transparent p-3 rounded-lg border border-violet-500/20">
                  <div className="flex items-center gap-2 text-sm font-medium text-violet-400 mb-2">
                    <TrendingUp className="w-4 h-4" /> Positioning
                  </div>
                  <p className="text-sm text-slate-100">{parsedPRD.positioning}</p>
                </div>
              )}
              
              {/* Key Metrics & Riskiest Unknown */}
              {(parsedPRD.metrics.length > 0 || parsedPRD.riskiestUnknown) && (
                <div className="grid grid-cols-2 gap-4">
                  {parsedPRD.metrics.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                        <BarChart3 className="w-4 h-4" /> Key Metrics
                      </div>
                      <div className="space-y-1">
                        {parsedPRD.metrics.map((m, i) => (
                          <Badge key={i} variant="outline" className="mr-1 mb-1 text-slate-100 border-slate-700 block w-fit">
                            {m}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {parsedPRD.riskiestUnknown && (
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                        <AlertTriangle className="w-4 h-4" /> Riskiest Unknown
                      </div>
                      <p className="text-sm text-amber-400">{parsedPRD.riskiestUnknown}</p>
                    </div>
                  )}
                </div>
              )}
              
              {/* MVP Scope (In) */}
              {parsedPRD.scopeIn.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-green-400 mb-2">
                    <CheckCircle2 className="w-4 h-4" /> MVP Scope (In)
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.scopeIn.map((item, i) => (
                      <div key={i} className="bg-green-500/5 border border-green-500/20 p-2 rounded">
                        <span className="font-medium text-slate-100">{item.name || item}</span>
                        {item.rationale && (
                          <p className="text-xs text-slate-400 mt-1">{item.rationale}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Out of Scope / Deferred */}
              {parsedPRD.scopeOut.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                    <Shield className="w-4 h-4" /> Deferred (Not Now)
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.scopeOut.map((item, i) => (
                      <div key={i} className="bg-slate-800/50 p-2 rounded border border-slate-700/50">
                        <span className="text-slate-300">{item.name || item}</span>
                        {item.rationale && (
                          <p className="text-xs text-slate-500 mt-1">Why: {item.rationale}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Assumptions to Validate */}
              {parsedPRD.assumptions.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                    <Lightbulb className="w-4 h-4" /> Assumptions to Validate
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.assumptions.map((a, i) => (
                      <div key={i} className="bg-amber-500/5 border border-amber-500/20 p-2 rounded">
                        <span className="font-medium text-slate-100">{a.assumption || a}</span>
                        {a.risk && (
                          <p className="text-xs text-red-400 mt-1">Risk if wrong: {a.risk}</p>
                        )}
                        {a.validation && (
                          <p className="text-xs text-green-400 mt-1">Validation: {a.validation}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks */}
              {parsedPRD.risks.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-2">
                    <AlertTriangle className="w-4 h-4" /> Risks & Mitigations
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.risks.map((r, i) => (
                      <div key={i} className="bg-red-500/5 border border-red-500/20 p-2 rounded">
                        <span className="text-slate-100">{r}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Validation Plan */}
              {parsedPRD.validationPlan && (
                <div className="bg-green-500/5 border border-green-500/20 p-3 rounded-lg">
                  <div className="flex items-center gap-2 text-sm font-medium text-green-400 mb-1">
                    <CheckCircle2 className="w-4 h-4" /> Validation Plan
                  </div>
                  <p className="text-sm text-slate-100">{parsedPRD.validationPlan}</p>
                </div>
              )}

              {/* Features */}
              {parsedPRD.features.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-violet-400 mb-2">
                    <CheckCircle2 className="w-4 h-4" /> Features
                  </div>
                  <div className="space-y-2">
                    {parsedPRD.features.map((feature, i) => (
                      <div key={i} className="bg-violet-500/5 border border-violet-500/20 p-2 rounded">
                        <span className="font-medium text-slate-100">{feature.name}</span>
                        {feature.description && (
                          <p className="text-xs text-slate-400 mt-1">{feature.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Timeline */}
              {parsedPRD.timeline && (
                <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mb-1">
                    Timeline
                  </div>
                  <p className="text-sm text-slate-100">{parsedPRD.timeline}</p>
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
    riskiestUnknown: '',
    risks: [],
    scopeIn: [],
    scopeOut: [],
    assumptions: [],
    features: [],
    validationPlan: '',
    timeline: '',
  };

  // Split content into lines
  const lines = content.split('\n');
  let currentSection = '';
  let currentSubsection = '';
  let currentUser = null;
  let buffer = [];

  const flushBuffer = () => {
    const text = buffer.join('\n').trim();
    buffer = [];
    return text;
  };

  const extractListItems = (text) => {
    return text.split('\n')
      .map(line => line.replace(/^[-*•]\s*/, '').replace(/^\d+\.\s*/, '').trim())
      .filter(line => line.length > 0 && !line.startsWith('#') && !line.startsWith('**'));
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmedLine = line.trim();

    // Skip empty lines and separators
    if (trimmedLine === '' || trimmedLine === '---') {
      continue;
    }

    // Detect main title
    if (trimmedLine.startsWith('# ')) {
      const title = trimmedLine.replace('# ', '').replace(/Product Requirements Document.*$/i, '').replace(/\(PRD\)/i, '').trim();
      if (title) prd.title = title;
      continue;
    }

    // Detect section headers
    if (trimmedLine.startsWith('## ')) {
      // Save previous section
      if (currentSection && buffer.length > 0) {
        assignToSection(prd, currentSection, currentSubsection, flushBuffer(), currentUser);
      }
      currentSection = trimmedLine.replace('## ', '').replace(/^\d+\.\s*/, '').toLowerCase();
      currentSubsection = '';
      currentUser = null;
      continue;
    }

    // Detect subsection headers
    if (trimmedLine.startsWith('### ')) {
      // Save previous subsection
      if (buffer.length > 0) {
        assignToSection(prd, currentSection, currentSubsection, flushBuffer(), currentUser);
      }
      currentSubsection = trimmedLine.replace('### ', '').replace(/^\d+\.\d+\s*/, '').toLowerCase();
      
      // Check if this is a user persona
      if (currentSection.includes('user') || currentSection.includes('persona') || currentSection.includes('target')) {
        const personaName = trimmedLine.replace('### ', '').replace(/^\d+\.\d+\s*/, '');
        currentUser = { persona: personaName, painPoints: [], context: '', jtbd: '', currentWorkaround: '' };
        prd.targetUsers.push(currentUser);
      } else {
        currentUser = null;
      }
      continue;
    }

    // Handle inline formatting and collect content
    let cleanLine = trimmedLine;
    
    // Parse special inline fields
    if (currentUser) {
      if (trimmedLine.match(/^[-*•]?\s*(context|background|description):/i)) {
        currentUser.context = trimmedLine.replace(/^[-*•]?\s*(context|background|description):\s*/i, '');
        continue;
      }
      if (trimmedLine.match(/^[-*•]?\s*(pain points?|frustrations?):/i)) {
        currentUser.painPoints = trimmedLine.replace(/^[-*•]?\s*(pain points?|frustrations?):\s*/i, '').split(',').map(p => p.trim());
        continue;
      }
      if (trimmedLine.match(/^[-*•]?\s*(current workaround|workaround|today):/i)) {
        currentUser.currentWorkaround = trimmedLine.replace(/^[-*•]?\s*(current workaround|workaround|today):\s*/i, '');
        continue;
      }
      if (trimmedLine.match(/^[-*•]?\s*(jtbd|job to be done|goal):/i)) {
        currentUser.jtbd = trimmedLine.replace(/^[-*•]?\s*(jtbd|job to be done|goal):\s*/i, '');
        continue;
      }
    }

    // Remove bold markers for cleaner text
    cleanLine = cleanLine.replace(/\*\*([^*]+)\*\*/g, '$1').trim();
    
    buffer.push(cleanLine);
  }

  // Flush remaining buffer
  if (currentSection && buffer.length > 0) {
    assignToSection(prd, currentSection, currentSubsection, flushBuffer(), currentUser);
  }

  return prd;
}

function assignToSection(prd, section, subsection, text, currentUser) {
  const listItems = text.split('\n')
    .map(line => line.replace(/^[-*•]\s*/, '').replace(/^\d+\.\s*/, '').trim())
    .filter(line => line.length > 0 && !line.startsWith('#'));
  
  const cleanText = listItems.join(' ').trim();
  const sectionLower = section.toLowerCase();
  const subsectionLower = subsection.toLowerCase();

  // Problem / Executive Summary
  if (sectionLower.includes('problem') || sectionLower.includes('executive')) {
    if (subsectionLower.includes('evidence')) {
      prd.evidence = cleanText;
    } else if (!prd.problem) {
      prd.problem = cleanText;
    }
  }
  // Vision
  else if (sectionLower.includes('vision') || subsectionLower.includes('vision')) {
    prd.vision = cleanText;
  }
  // Goals / Objectives / Desired Outcome
  else if (sectionLower.includes('goal') || sectionLower.includes('objective') || 
           sectionLower.includes('outcome') || subsectionLower.includes('outcome') ||
           subsectionLower.includes('goal')) {
    if (!prd.goals) prd.goals = cleanText;
  }
  // Success Metrics / Key Metrics
  else if (sectionLower.includes('metric') || sectionLower.includes('success') ||
           subsectionLower.includes('metric') || subsectionLower.includes('success')) {
    prd.metrics = listItems.length > 0 ? listItems.slice(0, 5) : [cleanText];
  }
  // Risks
  else if (sectionLower.includes('risk') && !sectionLower.includes('unknown')) {
    if (subsectionLower.includes('unknown') || subsectionLower.includes('riskiest')) {
      prd.riskiestUnknown = cleanText;
    } else {
      prd.risks = listItems.length > 0 ? listItems.slice(0, 5) : [cleanText];
    }
  }
  // Scope
  else if (sectionLower.includes('scope')) {
    if (subsectionLower.includes('out') || subsectionLower.includes('not') || subsectionLower.includes('defer')) {
      prd.scopeOut = listItems.map(item => ({ name: item, rationale: '' }));
    } else if (subsectionLower.includes('in') || subsectionLower.includes('mvp')) {
      prd.scopeIn = listItems.map(item => ({ name: item, rationale: '' }));
    } else if (listItems.length > 0) {
      prd.scopeIn = listItems.map(item => ({ name: item, rationale: '' }));
    }
  }
  // MVP Scope
  else if (sectionLower.includes('mvp')) {
    prd.scopeIn = listItems.map(item => ({ name: item, rationale: '' }));
  }
  // Assumptions
  else if (sectionLower.includes('assumption') || subsectionLower.includes('assumption')) {
    prd.assumptions = listItems.map(item => ({ assumption: item, risk: '', validation: '' }));
  }
  // Features
  else if (sectionLower.includes('feature') || sectionLower.includes('requirement')) {
    prd.features = listItems.map(item => ({ name: item, description: '' }));
  }
  // Validation Plan
  else if (sectionLower.includes('validation') || subsectionLower.includes('validation')) {
    prd.validationPlan = cleanText;
  }
  // Timeline
  else if (sectionLower.includes('timeline') || sectionLower.includes('milestone') ||
           subsectionLower.includes('timeline') || subsectionLower.includes('milestone')) {
    prd.timeline = cleanText;
  }
  // Positioning
  else if (sectionLower.includes('position') || subsectionLower.includes('position')) {
    prd.positioning = cleanText;
  }
  // Target Users - handle text that wasn't parsed as a user card
  else if ((sectionLower.includes('user') || sectionLower.includes('persona') || sectionLower.includes('target')) && !currentUser) {
    if (prd.targetUsers.length === 0 && cleanText) {
      prd.targetUsers.push({ persona: cleanText, painPoints: [], context: '', jtbd: '', currentWorkaround: '' });
    }
  }
}

export default PRDPreview;
