import React, { useState, useRef, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
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
  Download,
  Edit3,
  Save,
  X,
  Plus,
  Trash2,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import jsPDF from 'jspdf';

/**
 * Comprehensive PRD Preview component with inline editing and PDF export.
 * Supports structured JSON PRDs with collapsible sections.
 */
const PRDPreview = ({ 
  content, 
  prdData, 
  format = 'markdown', 
  className = '',
  onSave = null, // Callback to save PRD changes
  readOnly = false, // If true, disable editing
}) => {
  // If we have structured JSON PRD data, render that
  if (format === 'json' && prdData) {
    return (
      <StructuredPRDPreview 
        prd={prdData} 
        className={className} 
        onSave={onSave}
        readOnly={readOnly}
      />
    );
  }
  
  // Fallback to legacy markdown preview (read-only)
  return <LegacyPRDPreview content={content} className={className} />;
};

/**
 * Inline editable text field
 */
const EditableText = ({ value, onChange, multiline = false, placeholder = '', className = '' }) => {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value);
  const inputRef = useRef(null);

  const handleEdit = () => {
    setTempValue(value);
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleSave = () => {
    onChange(tempValue);
    setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value);
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !multiline) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (editing) {
    return (
      <div className="flex items-start gap-2">
        {multiline ? (
          <Textarea
            ref={inputRef}
            value={tempValue}
            onChange={(e) => setTempValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="min-h-[60px] bg-slate-800 border-slate-600 text-slate-100"
            placeholder={placeholder}
          />
        ) : (
          <Input
            ref={inputRef}
            value={tempValue}
            onChange={(e) => setTempValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="bg-slate-800 border-slate-600 text-slate-100"
            placeholder={placeholder}
          />
        )}
        <Button size="sm" variant="ghost" onClick={handleSave} className="text-green-400 hover:text-green-300">
          <Check className="w-4 h-4" />
        </Button>
        <Button size="sm" variant="ghost" onClick={handleCancel} className="text-red-400 hover:text-red-300">
          <X className="w-4 h-4" />
        </Button>
      </div>
    );
  }

  return (
    <div 
      onClick={handleEdit}
      className={`cursor-pointer hover:bg-slate-700/30 rounded px-1 -mx-1 transition-colors ${className}`}
      title="Click to edit"
    >
      {value || <span className="text-slate-500 italic">{placeholder || 'Click to add...'}</span>}
    </div>
  );
};

/**
 * Editable list component
 */
const EditableList = ({ items, onChange, itemPlaceholder = 'Add item...' }) => {
  const [newItem, setNewItem] = useState('');

  const handleAdd = () => {
    if (newItem.trim()) {
      onChange([...items, newItem.trim()]);
      setNewItem('');
    }
  };

  const handleRemove = (index) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const handleUpdate = (index, value) => {
    const updated = [...items];
    updated[index] = value;
    onChange(updated);
  };

  return (
    <div className="space-y-1">
      {items.map((item, i) => (
        <div key={i} className="flex items-start gap-2 group">
          <EditableText
            value={item}
            onChange={(v) => handleUpdate(i, v)}
            className="flex-1 text-sm text-slate-300"
          />
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleRemove(i)}
            className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 h-6 w-6 p-0"
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      ))}
      <div className="flex items-center gap-2 mt-2">
        <Input
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder={itemPlaceholder}
          className="h-8 text-sm bg-slate-800/50 border-slate-700 text-slate-300"
        />
        <Button size="sm" variant="ghost" onClick={handleAdd} className="text-green-400 h-8">
          <Plus className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
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
 * Generate PDF from PRD data
 */
const generatePDF = (prd) => {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  const contentWidth = pageWidth - 2 * margin;
  let y = 20;

  const addText = (text, fontSize = 10, isBold = false, color = [0, 0, 0]) => {
    doc.setFontSize(fontSize);
    doc.setFont('helvetica', isBold ? 'bold' : 'normal');
    doc.setTextColor(...color);
    const lines = doc.splitTextToSize(text, contentWidth);
    
    // Check if we need a new page
    const lineHeight = fontSize * 0.4;
    if (y + lines.length * lineHeight > doc.internal.pageSize.getHeight() - margin) {
      doc.addPage();
      y = margin;
    }
    
    doc.text(lines, margin, y);
    y += lines.length * lineHeight + 2;
  };

  const addSection = (title, content) => {
    if (y > doc.internal.pageSize.getHeight() - 40) {
      doc.addPage();
      y = margin;
    }
    addText(title, 14, true, [75, 85, 99]);
    y += 2;
    if (typeof content === 'string' && content) {
      addText(content, 10, false);
    }
    y += 4;
  };

  const addBulletList = (items) => {
    items.forEach(item => {
      if (item) {
        addText(`• ${item}`, 10, false);
      }
    });
    y += 2;
  };

  // Title
  addText(prd.summary?.title || 'Product Requirements Document', 20, true, [88, 28, 135]);
  addText(`Version ${prd.summary?.version || '1.0'} | ${prd.summary?.owner || 'Product Manager'}`, 10, false, [100, 100, 100]);
  y += 8;

  // Summary
  addSection('1. Summary', '');
  if (prd.summary?.overview) {
    addText('Overview', 11, true);
    addText(prd.summary.overview, 10);
    y += 2;
  }
  if (prd.summary?.problem_statement) {
    addText('Problem Statement', 11, true);
    addText(prd.summary.problem_statement, 10);
    y += 2;
  }
  if (prd.summary?.goal) {
    addText('Goal / Desired Outcome', 11, true);
    addText(prd.summary.goal, 10);
    y += 2;
  }
  if (prd.summary?.target_users) {
    addText('Target Users', 11, true);
    addText(prd.summary.target_users, 10);
  }
  y += 6;

  // Context & Evidence
  if (prd.context) {
    addSection('2. Context & Evidence', '');
    if (prd.context.evidence?.length > 0) {
      addText('Evidence:', 11, true);
      addBulletList(prd.context.evidence);
    }
    if (prd.context.current_workflow) {
      addText('Current Workflow', 11, true);
      addText(prd.context.current_workflow, 10);
      y += 2;
    }
    if (prd.context.why_now) {
      addText('Why Now', 11, true);
      addText(prd.context.why_now, 10);
    }
    y += 6;
  }

  // Personas
  if (prd.personas?.length > 0) {
    addSection('3. Personas & Jobs-to-be-Done', '');
    prd.personas.forEach((persona, i) => {
      addText(`${persona.name}`, 11, true);
      if (persona.context) addText(persona.context, 10, false, [100, 100, 100]);
      if (persona.jtbd) addText(`JTBD: "${persona.jtbd}"`, 10, false);
      if (persona.pain_points?.length > 0) {
        addText('Pain Points:', 10, true);
        addBulletList(persona.pain_points);
      }
      if (persona.current_workaround) {
        addText(`Workaround: ${persona.current_workaround}`, 10);
      }
      y += 4;
    });
  }

  // Scope
  if (prd.scope) {
    addSection('4. Scope', '');
    if (prd.scope.mvp_in?.length > 0) {
      addText('MVP Scope (In):', 11, true, [34, 139, 34]);
      prd.scope.mvp_in.forEach(item => {
        addText(`• ${item.item}`, 10);
        if (item.rationale) addText(`  Rationale: ${item.rationale}`, 9, false, [100, 100, 100]);
      });
      y += 2;
    }
    if (prd.scope.not_now?.length > 0) {
      addText('Deferred (Not Now):', 11, true, [100, 100, 100]);
      prd.scope.not_now.forEach(item => {
        addText(`• ${item.item}`, 10);
        if (item.rationale) addText(`  Why: ${item.rationale}`, 9, false, [100, 100, 100]);
      });
      y += 2;
    }
    if (prd.scope.assumptions?.length > 0) {
      addText('Assumptions to Validate:', 11, true, [218, 165, 32]);
      prd.scope.assumptions.forEach(item => {
        addText(`• ${item.assumption}`, 10);
        if (item.risk_if_wrong) addText(`  Risk if wrong: ${item.risk_if_wrong}`, 9, false, [178, 34, 34]);
        if (item.validation) addText(`  Validation: ${item.validation}`, 9, false, [34, 139, 34]);
      });
    }
    y += 6;
  }

  // Requirements
  if (prd.requirements?.features?.length > 0) {
    addSection('5. Requirements', '');
    prd.requirements.features.forEach((feature, i) => {
      addText(`${feature.name} [${feature.priority}]`, 11, true);
      if (feature.description) addText(feature.description, 10);
      if (feature.stories?.length > 0) {
        feature.stories.forEach(story => {
          addText(`User Story: "${story.story}"`, 10, false);
          if (story.acceptance_criteria?.length > 0) {
            addText('Acceptance Criteria:', 9, true);
            addBulletList(story.acceptance_criteria);
          }
          if (story.edge_cases?.length > 0) {
            addText('Edge Cases:', 9, true, [218, 165, 32]);
            addBulletList(story.edge_cases);
          }
        });
      }
      y += 4;
    });
  }

  // NFRs
  if (prd.nfrs) {
    addSection('6. Non-Functional Requirements', '');
    if (prd.nfrs.performance?.length > 0) {
      addText('Performance:', 11, true);
      addBulletList(prd.nfrs.performance);
    }
    if (prd.nfrs.reliability?.length > 0) {
      addText('Reliability:', 11, true);
      addBulletList(prd.nfrs.reliability);
    }
    if (prd.nfrs.security?.length > 0) {
      addText('Security:', 11, true);
      addBulletList(prd.nfrs.security);
    }
    if (prd.nfrs.accessibility?.length > 0) {
      addText('Accessibility:', 11, true);
      addBulletList(prd.nfrs.accessibility);
    }
    y += 6;
  }

  // Metrics
  if (prd.metrics) {
    addSection('7. Metrics & Analytics', '');
    if (prd.metrics.success_metrics?.length > 0) {
      addText('Success Metrics:', 11, true);
      prd.metrics.success_metrics.forEach(m => {
        addText(`• ${m.metric}: ${m.target}`, 10);
        if (m.measurement) addText(`  Measurement: ${m.measurement}`, 9, false, [100, 100, 100]);
      });
      y += 2;
    }
    if (prd.metrics.guardrails?.length > 0) {
      addText('Guardrail Metrics:', 11, true, [178, 34, 34]);
      addBulletList(prd.metrics.guardrails);
    }
    if (prd.metrics.instrumentation?.length > 0) {
      addText('Instrumentation:', 11, true);
      addText(prd.metrics.instrumentation.join(', '), 10);
      y += 2;
    }
    if (prd.metrics.evaluation_window) {
      addText(`Evaluation: ${prd.metrics.evaluation_window}`, 10);
    }
    y += 6;
  }

  // Risks
  if (prd.risks?.length > 0) {
    addSection('8. Risks', '');
    prd.risks.forEach(risk => {
      addText(`• ${risk.risk}`, 10, true);
      addText(`  Type: ${risk.type} | Likelihood: ${risk.likelihood} | Impact: ${risk.impact}`, 9, false, [100, 100, 100]);
      if (risk.mitigation) addText(`  Mitigation: ${risk.mitigation}`, 9, false, [34, 139, 34]);
      y += 2;
    });
    y += 4;
  }

  // Open Questions
  if (prd.open_questions?.length > 0) {
    addSection('9. Open Questions', '');
    prd.open_questions.forEach(q => {
      addText(`• ${q.question}`, 10);
      addText(`  Owner: ${q.owner} | Due: ${q.due_date} | Status: ${q.status}`, 9, false, [100, 100, 100]);
    });
    y += 4;
  }

  // Appendix
  if (prd.appendix && (prd.appendix.alternatives_considered?.length > 0 || prd.appendix.glossary?.length > 0)) {
    addSection('10. Appendix', '');
    if (prd.appendix.alternatives_considered?.length > 0) {
      addText('Alternatives Considered:', 11, true);
      addBulletList(prd.appendix.alternatives_considered);
    }
    if (prd.appendix.glossary?.length > 0) {
      addText('Glossary:', 11, true);
      prd.appendix.glossary.forEach(item => {
        addText(`• ${item.term}: ${item.definition}`, 10);
      });
    }
  }

  // Footer on all pages
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(150, 150, 150);
    doc.text(
      `Generated by JarlPM | Page ${i} of ${pageCount}`,
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 10,
      { align: 'center' }
    );
  }

  return doc;
};

/**
 * Structured PRD Preview with inline editing
 */
const StructuredPRDPreview = ({ prd: initialPrd, className, onSave, readOnly }) => {
  const [prd, setPrd] = useState(initialPrd);
  const [hasChanges, setHasChanges] = useState(false);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Deep update helper
  const updatePrd = useCallback((path, value) => {
    setPrd(prev => {
      const updated = JSON.parse(JSON.stringify(prev));
      const parts = path.split('.');
      let current = updated;
      for (let i = 0; i < parts.length - 1; i++) {
        if (parts[i].includes('[')) {
          const [key, indexStr] = parts[i].split('[');
          const index = parseInt(indexStr);
          current = current[key][index];
        } else {
          current = current[parts[i]];
        }
      }
      const lastPart = parts[parts.length - 1];
      if (lastPart.includes('[')) {
        const [key, indexStr] = lastPart.split('[');
        const index = parseInt(indexStr);
        current[key][index] = value;
      } else {
        current[lastPart] = value;
      }
      return updated;
    });
    setHasChanges(true);
  }, []);

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(prd);
      setHasChanges(false);
      toast.success('PRD saved successfully');
    } catch (error) {
      toast.error('Failed to save PRD');
    } finally {
      setSaving(false);
    }
  };

  const handleCopyMarkdown = () => {
    const markdown = generateMarkdownFromPRD(prd);
    navigator.clipboard.writeText(markdown);
    setCopied(true);
    toast.success('PRD copied as Markdown');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExportPDF = () => {
    setExporting(true);
    try {
      const doc = generatePDF(prd);
      const filename = `${prd.summary?.title || 'PRD'}_v${prd.summary?.version || '1.0'}.pdf`;
      doc.save(filename.replace(/[^a-z0-9_.-]/gi, '_'));
      toast.success('PDF exported successfully');
    } catch (error) {
      console.error('PDF export error:', error);
      toast.error('Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  // Render editable or read-only text
  const renderText = (value, path, multiline = false, placeholder = '') => {
    if (readOnly) {
      return <span>{value || <span className="text-slate-500 italic">{placeholder}</span>}</span>;
    }
    return (
      <EditableText
        value={value}
        onChange={(v) => updatePrd(path, v)}
        multiline={multiline}
        placeholder={placeholder}
      />
    );
  };

  // Render editable or read-only list
  const renderList = (items, path, placeholder = 'Add item...') => {
    if (readOnly) {
      return (
        <ul className="space-y-1">
          {items?.map((item, i) => (
            <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
              <CheckCircle2 className="w-3 h-3 mt-1 text-blue-400 flex-shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      );
    }
    return (
      <EditableList
        items={items || []}
        onChange={(v) => updatePrd(path, v)}
        itemPlaceholder={placeholder}
      />
    );
  };

  return (
    <ScrollArea className={`h-[600px] ${className}`}>
      <div className="p-6 space-y-4">
        {/* Header with Actions */}
        <div className="flex items-center justify-between mb-4 sticky top-0 bg-background/95 backdrop-blur z-10 py-2">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-violet-400" />
            <h3 className="text-lg font-semibold text-slate-100">
              {readOnly ? (prd.summary?.title || 'PRD') : renderText(prd.summary?.title, 'summary.title', false, 'PRD Title')}
            </h3>
            <Badge variant="outline" className="text-xs border-violet-500/30 text-violet-400">
              v{prd.summary?.version || '1.0'}
            </Badge>
            {hasChanges && !readOnly && (
              <Badge variant="outline" className="text-xs border-amber-500/30 text-amber-400">
                Unsaved changes
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {hasChanges && !readOnly && onSave && (
              <Button
                variant="default"
                size="sm"
                onClick={handleSave}
                disabled={saving}
                className="gap-1"
              >
                {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                Save
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyMarkdown}
              className="gap-1"
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copied!' : 'Copy MD'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportPDF}
              disabled={exporting}
              className="gap-1"
            >
              {exporting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
              Export PDF
            </Button>
          </div>
        </div>

        {/* 1. Summary Section - Always Open */}
        <PRDSection title="Summary" icon={FileText} defaultOpen={true} accentColor="violet">
          <Card className="bg-[#0d0d1a] border-slate-700/50">
            <CardContent className="p-4 space-y-3">
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">Overview</p>
                <div className="text-sm text-slate-100">
                  {renderText(prd.summary?.overview, 'summary.overview', true, 'Add overview...')}
                </div>
              </div>
              <div className="bg-red-500/5 border border-red-500/20 rounded p-3">
                <p className="text-xs font-medium text-red-400 mb-1">Problem Statement</p>
                <div className="text-sm text-slate-100">
                  {renderText(prd.summary?.problem_statement, 'summary.problem_statement', true, 'Describe the problem...')}
                </div>
              </div>
              <div className="bg-green-500/5 border border-green-500/20 rounded p-3">
                <p className="text-xs font-medium text-green-400 mb-1">Goal / Desired Outcome</p>
                <div className="text-sm text-slate-100">
                  {renderText(prd.summary?.goal, 'summary.goal', true, 'Define the goal...')}
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">Target Users</p>
                <div className="text-sm text-slate-100">
                  {renderText(prd.summary?.target_users, 'summary.target_users', true, 'Who are the target users?')}
                </div>
              </div>
            </CardContent>
          </Card>
        </PRDSection>

        {/* 2. Context & Evidence */}
        <PRDSection title="Context & Evidence" icon={BookOpen} accentColor="blue">
          <Card className="bg-[#0d0d1a] border-slate-700/50">
            <CardContent className="p-4 space-y-3">
              <div>
                <p className="text-xs font-medium text-slate-400 mb-2">Evidence</p>
                {renderList(prd.context?.evidence, 'context.evidence', 'Add evidence point...')}
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">Current Workflow</p>
                <div className="text-sm text-slate-300">
                  {renderText(prd.context?.current_workflow, 'context.current_workflow', true, 'Describe current workflow...')}
                </div>
              </div>
              <div className="bg-amber-500/5 border border-amber-500/20 rounded p-3">
                <p className="text-xs font-medium text-amber-400 mb-1">Why Now?</p>
                <div className="text-sm text-slate-100">
                  {renderText(prd.context?.why_now, 'context.why_now', true, 'Why is this urgent?')}
                </div>
              </div>
            </CardContent>
          </Card>
        </PRDSection>

        {/* 3. Personas */}
        <PRDSection 
          title="Personas & Jobs-to-be-Done" 
          icon={Users} 
          badge={`${prd.personas?.length || 0} personas`}
          accentColor="violet"
        >
          <div className="space-y-3">
            {(prd.personas || []).map((persona, i) => (
              <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center">
                      <Users className="w-4 h-4 text-violet-400" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-slate-100">
                        {renderText(persona.name, `personas[${i}].name`, false, 'Persona name')}
                      </div>
                      <div className="text-xs text-slate-400">
                        {renderText(persona.context, `personas[${i}].context`, false, 'Context/role')}
                      </div>
                    </div>
                  </div>
                  <div className="bg-violet-500/5 border border-violet-500/20 rounded p-2 mb-2">
                    <p className="text-xs font-medium text-violet-400 mb-1">Job to be Done</p>
                    <div className="text-sm text-slate-100 italic">
                      {renderText(persona.jtbd, `personas[${i}].jtbd`, true, '"When I..., I want to..., So that..."')}
                    </div>
                  </div>
                  <div className="mb-2">
                    <p className="text-xs font-medium text-red-400 mb-1">Pain Points</p>
                    {renderList(persona.pain_points, `personas[${i}].pain_points`, 'Add pain point...')}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-amber-400 mb-1">Current Workaround</p>
                    <div className="text-xs text-slate-300">
                      {renderText(persona.current_workaround, `personas[${i}].current_workaround`, false, 'How do they solve it today?')}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {!readOnly && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => updatePrd('personas', [...(prd.personas || []), { name: '', context: '', jtbd: '', pain_points: [], current_workaround: '' }])}
                className="w-full text-violet-400 border-violet-500/30"
              >
                <Plus className="w-4 h-4 mr-2" /> Add Persona
              </Button>
            )}
          </div>
        </PRDSection>

        {/* 4. Scope */}
        <PRDSection title="Scope" icon={Target} accentColor="green">
          <div className="space-y-3">
            {/* MVP In */}
            <div>
              <p className="text-xs font-medium text-green-400 mb-2 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> MVP Scope (In)
              </p>
              <div className="space-y-2">
                {(prd.scope?.mvp_in || []).map((item, i) => (
                  <div key={i} className="bg-green-500/5 border border-green-500/20 rounded p-2">
                    <div className="text-sm font-medium text-slate-100">
                      {renderText(item.item, `scope.mvp_in[${i}].item`, false, 'Scope item')}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      {renderText(item.rationale, `scope.mvp_in[${i}].rationale`, false, 'Rationale')}
                    </div>
                  </div>
                ))}
                {!readOnly && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => updatePrd('scope.mvp_in', [...(prd.scope?.mvp_in || []), { item: '', rationale: '' }])}
                    className="text-green-400"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Add MVP item
                  </Button>
                )}
              </div>
            </div>
            
            {/* Not Now */}
            <div>
              <p className="text-xs font-medium text-slate-400 mb-2 flex items-center gap-1">
                <Shield className="w-3 h-3" /> Deferred (Not Now)
              </p>
              <div className="space-y-2">
                {(prd.scope?.not_now || []).map((item, i) => (
                  <div key={i} className="bg-slate-700/30 border border-slate-600/30 rounded p-2">
                    <div className="text-sm text-slate-300">
                      {renderText(item.item, `scope.not_now[${i}].item`, false, 'Deferred item')}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Why: {renderText(item.rationale, `scope.not_now[${i}].rationale`, false, 'Why deferred')}
                    </div>
                  </div>
                ))}
                {!readOnly && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => updatePrd('scope.not_now', [...(prd.scope?.not_now || []), { item: '', rationale: '' }])}
                    className="text-slate-400"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Add deferred item
                  </Button>
                )}
              </div>
            </div>
            
            {/* Assumptions */}
            <div>
              <p className="text-xs font-medium text-amber-400 mb-2 flex items-center gap-1">
                <Lightbulb className="w-3 h-3" /> Assumptions to Validate
              </p>
              <div className="space-y-2">
                {(prd.scope?.assumptions || []).map((item, i) => (
                  <div key={i} className="bg-amber-500/5 border border-amber-500/20 rounded p-2">
                    <div className="text-sm font-medium text-slate-100">
                      {renderText(item.assumption, `scope.assumptions[${i}].assumption`, false, 'Assumption')}
                    </div>
                    <div className="text-xs text-red-400 mt-1">
                      Risk if wrong: {renderText(item.risk_if_wrong, `scope.assumptions[${i}].risk_if_wrong`, false, 'What happens if wrong?')}
                    </div>
                    <div className="text-xs text-green-400 mt-1">
                      Validation: {renderText(item.validation, `scope.assumptions[${i}].validation`, false, 'How to validate')}
                    </div>
                  </div>
                ))}
                {!readOnly && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => updatePrd('scope.assumptions', [...(prd.scope?.assumptions || []), { assumption: '', risk_if_wrong: '', validation: '' }])}
                    className="text-amber-400"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Add assumption
                  </Button>
                )}
              </div>
            </div>
          </div>
        </PRDSection>

        {/* 5. Requirements - simplified for space */}
        <PRDSection 
          title="Requirements" 
          icon={Layers} 
          badge={`${prd.requirements?.features?.length || 0} features`}
          accentColor="violet"
        >
          <div className="space-y-3">
            {(prd.requirements?.features || []).map((feature, i) => (
              <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-medium text-slate-100">
                      {renderText(feature.name, `requirements.features[${i}].name`, false, 'Feature name')}
                    </div>
                    <Badge 
                      variant="outline" 
                      className={`text-xs cursor-pointer ${
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
                  <div className="text-sm text-slate-400 mb-3">
                    {renderText(feature.description, `requirements.features[${i}].description`, true, 'Feature description')}
                  </div>
                </CardContent>
              </Card>
            ))}
            {!readOnly && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => updatePrd('requirements.features', [...(prd.requirements?.features || []), { name: '', description: '', priority: 'should-have', stories: [] }])}
                className="w-full text-violet-400 border-violet-500/30"
              >
                <Plus className="w-4 h-4 mr-2" /> Add Feature
              </Button>
            )}
          </div>
        </PRDSection>

        {/* 6. NFRs */}
        <PRDSection title="Non-Functional Requirements" icon={Shield} accentColor="blue">
          <Card className="bg-[#0d0d1a] border-slate-700/50">
            <CardContent className="p-4 grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-blue-400 mb-2">Performance</p>
                {renderList(prd.nfrs?.performance, 'nfrs.performance', 'Add performance target...')}
              </div>
              <div>
                <p className="text-xs font-medium text-green-400 mb-2">Reliability</p>
                {renderList(prd.nfrs?.reliability, 'nfrs.reliability', 'Add reliability target...')}
              </div>
              <div>
                <p className="text-xs font-medium text-red-400 mb-2">Security</p>
                {renderList(prd.nfrs?.security, 'nfrs.security', 'Add security requirement...')}
              </div>
              <div>
                <p className="text-xs font-medium text-violet-400 mb-2">Accessibility</p>
                {renderList(prd.nfrs?.accessibility, 'nfrs.accessibility', 'Add accessibility requirement...')}
              </div>
            </CardContent>
          </Card>
        </PRDSection>

        {/* 7. Metrics */}
        <PRDSection title="Metrics & Analytics" icon={BarChart3} accentColor="green">
          <Card className="bg-[#0d0d1a] border-slate-700/50">
            <CardContent className="p-4 space-y-3">
              <div>
                <p className="text-xs font-medium text-green-400 mb-2">Success Metrics</p>
                {renderList(
                  prd.metrics?.success_metrics?.map(m => `${m.metric}: ${m.target}`),
                  'metrics.success_metrics',
                  'Add success metric...'
                )}
              </div>
              <div>
                <p className="text-xs font-medium text-red-400 mb-2">Guardrail Metrics</p>
                {renderList(prd.metrics?.guardrails, 'metrics.guardrails', 'Add guardrail...')}
              </div>
              <div>
                <p className="text-xs font-medium text-blue-400 mb-2">Instrumentation</p>
                {renderList(prd.metrics?.instrumentation, 'metrics.instrumentation', 'Add event...')}
              </div>
            </CardContent>
          </Card>
        </PRDSection>

        {/* 8. Risks */}
        <PRDSection 
          title="Risks" 
          icon={AlertTriangle} 
          badge={`${prd.risks?.length || 0} risks`}
          accentColor="red"
        >
          <div className="space-y-2">
            {(prd.risks || []).map((risk, i) => (
              <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                <CardContent className="p-3">
                  <div className="flex items-start justify-between mb-2">
                    <div className="text-sm font-medium text-slate-100 flex-1">
                      {renderText(risk.risk, `risks[${i}].risk`, false, 'Risk description')}
                    </div>
                    <Badge variant="outline" className="text-xs border-slate-600 text-slate-400 ml-2">
                      {risk.type}
                    </Badge>
                  </div>
                  <div className="bg-green-500/5 border border-green-500/20 rounded p-2">
                    <p className="text-xs font-medium text-green-400 mb-1">Mitigation</p>
                    <div className="text-xs text-slate-300">
                      {renderText(risk.mitigation, `risks[${i}].mitigation`, false, 'How to mitigate')}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {!readOnly && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => updatePrd('risks', [...(prd.risks || []), { risk: '', type: 'product', likelihood: 'medium', impact: 'medium', mitigation: '' }])}
                className="w-full text-red-400 border-red-500/30"
              >
                <Plus className="w-4 h-4 mr-2" /> Add Risk
              </Button>
            )}
          </div>
        </PRDSection>

        {/* 9. Open Questions */}
        <PRDSection 
          title="Open Questions" 
          icon={HelpCircle} 
          badge={`${prd.open_questions?.filter(q => q.status === 'open').length || 0} open`}
          accentColor="amber"
        >
          <div className="space-y-2">
            {(prd.open_questions || []).map((q, i) => (
              <Card key={i} className="bg-[#0d0d1a] border-slate-700/50">
                <CardContent className="p-3">
                  <div className="flex items-start justify-between">
                    <div className="text-sm text-slate-100 flex-1">
                      {renderText(q.question, `open_questions[${i}].question`, false, 'Question')}
                    </div>
                    <Badge 
                      variant="outline" 
                      className={`text-xs ml-2 ${
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
                    <span>Owner: {renderText(q.owner, `open_questions[${i}].owner`, false, 'Owner')}</span>
                    <span>Due: {renderText(q.due_date, `open_questions[${i}].due_date`, false, 'Due date')}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
            {!readOnly && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => updatePrd('open_questions', [...(prd.open_questions || []), { question: '', owner: 'TBD', due_date: 'TBD', status: 'open' }])}
                className="w-full text-amber-400 border-amber-500/30"
              >
                <Plus className="w-4 h-4 mr-2" /> Add Question
              </Button>
            )}
          </div>
        </PRDSection>

        {/* 10. Appendix */}
        <PRDSection title="Appendix" icon={Clipboard} accentColor="slate">
          <Card className="bg-[#0d0d1a] border-slate-700/50">
            <CardContent className="p-4 space-y-3">
              <div>
                <p className="text-xs font-medium text-slate-400 mb-2">Alternatives Considered</p>
                {renderList(prd.appendix?.alternatives_considered, 'appendix.alternatives_considered', 'Add alternative...')}
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400 mb-2">Glossary</p>
                {renderList(
                  prd.appendix?.glossary?.map(g => `${g.term}: ${g.definition}`),
                  'appendix.glossary',
                  'Add term (format: term: definition)'
                )}
              </div>
            </CardContent>
          </Card>
        </PRDSection>
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
 * Legacy markdown PRD preview (read-only fallback)
 */
const LegacyPRDPreview = ({ content, className }) => {
  return (
    <ScrollArea className={`h-[600px] ${className}`}>
      <div className="p-6">
        <Card className="bg-[#0d0d1a] border-slate-700/50">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-violet-400" />
              PRD (Legacy Format)
            </h3>
            <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono">
              {content || 'No content available'}
            </pre>
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  );
};

export default PRDPreview;
