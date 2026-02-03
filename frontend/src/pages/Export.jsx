import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { epicAPI } from '@/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import ThemeToggle from '@/components/ThemeToggle';
import {
  ArrowLeft, Download, Upload, FileJson, FileText, FileSpreadsheet,
  ExternalLink, Loader2, CheckCircle2, XCircle, AlertTriangle,
  Layers, BookOpen, Bug, Settings, Info
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const Export = () => {
  const navigate = useNavigate();
  const [epics, setEpics] = useState([]);
  const [selectedEpic, setSelectedEpic] = useState('');
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [includeBugs, setIncludeBugs] = useState(true);
  const [exportResults, setExportResults] = useState(null);
  const [showResultsDialog, setShowResultsDialog] = useState(false);
  
  // Jira config
  const [jiraConfig, setJiraConfig] = useState({
    base_url: '',
    email: '',
    api_token: '',
    project_key: ''
  });
  
  // Azure DevOps config
  const [azureConfig, setAzureConfig] = useState({
    organization: '',
    project: '',
    pat: ''
  });

  const loadEpics = async () => {
    try {
      const { data } = await epicAPI.list();
      setEpics(data.epics || []);
    } catch (err) {
      toast.error('Failed to load epics');
    }
  };

  const loadPreview = React.useCallback(async () => {
    if (!selectedEpic) return;
    
    setPreviewLoading(true);
    try {
      const response = await fetch(
        `${API}/api/export/preview/${selectedEpic}?include_bugs=${includeBugs}`,
        { credentials: 'include' }
      );
      if (!response.ok) throw new Error('Failed to load preview');
      const data = await response.json();
      setPreview(data);
    } catch (err) {
      toast.error('Failed to load export preview');
    } finally {
      setPreviewLoading(false);
    }
  }, [selectedEpic, includeBugs]);

  useEffect(() => {
    loadEpics();
  }, []);

  useEffect(() => {
    if (selectedEpic) {
      loadPreview();
    }
  }, [selectedEpic, includeBugs, loadPreview]);

  const handleFileExport = async (format) => {
    if (!selectedEpic) {
      toast.error('Please select an epic first');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/export/file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          epic_id: selectedEpic,
          format,
          include_bugs: includeBugs
        })
      });
      
      if (!response.ok) throw new Error('Export failed');
      
      // Get filename from Content-Disposition header
      const contentDisposition = response.headers.get('Content-Disposition');
      const filenameMatch = contentDisposition?.match(/filename=(.+)/);
      const filename = filenameMatch ? filenameMatch[1] : `export.${format.includes('csv') ? 'csv' : format === 'json' ? 'json' : 'md'}`;
      
      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast.success(`Exported to ${filename}`);
    } catch (err) {
      toast.error('Export failed');
    } finally {
      setLoading(false);
    }
  };

  const handleJiraExport = async () => {
    if (!selectedEpic) {
      toast.error('Please select an epic first');
      return;
    }
    
    if (!jiraConfig.base_url || !jiraConfig.email || !jiraConfig.api_token || !jiraConfig.project_key) {
      toast.error('Please fill in all Jira configuration fields');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/export/jira`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          epic_id: selectedEpic,
          include_bugs: includeBugs,
          jira_base_url: jiraConfig.base_url,
          jira_email: jiraConfig.email,
          jira_api_token: jiraConfig.api_token,
          jira_project_key: jiraConfig.project_key
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Export failed');
      }
      
      const results = await response.json();
      setExportResults(results);
      setShowResultsDialog(true);
      
      if (results.success) {
        toast.success(`Successfully exported ${results.created_count} items to Jira`);
      } else {
        toast.warning(`Exported with ${results.error_count} errors`);
      }
    } catch (err) {
      toast.error(err.message || 'Jira export failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAzureExport = async () => {
    if (!selectedEpic) {
      toast.error('Please select an epic first');
      return;
    }
    
    if (!azureConfig.organization || !azureConfig.project || !azureConfig.pat) {
      toast.error('Please fill in all Azure DevOps configuration fields');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/export/azure-devops`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          epic_id: selectedEpic,
          include_bugs: includeBugs,
          organization: azureConfig.organization,
          project: azureConfig.project,
          pat: azureConfig.pat
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Export failed');
      }
      
      const results = await response.json();
      setExportResults(results);
      setShowResultsDialog(true);
      
      if (results.success) {
        toast.success(`Successfully exported ${results.created_count} items to Azure DevOps`);
      } else {
        toast.warning(`Exported with ${results.error_count} errors`);
      }
    } catch (err) {
      toast.error(err.message || 'Azure DevOps export failed');
    } finally {
      setLoading(false);
    }
  };

  const getItemIcon = (type) => {
    switch (type) {
      case 'Epic': return <Layers className="w-4 h-4 text-violet-400" />;
      case 'Feature': return <BookOpen className="w-4 h-4 text-blue-400" />;
      case 'User Story': return <FileText className="w-4 h-4 text-green-400" />;
      case 'Bug': return <Bug className="w-4 h-4 text-red-400" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-background" data-testid="export-page">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} data-testid="back-btn">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div>
                <h1 className="text-xl font-bold text-foreground">Export to Jira / Azure DevOps</h1>
                <p className="text-sm text-muted-foreground">Export your epics, features, stories, and bugs</p>
              </div>
            </div>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Epic Selection & Preview */}
          <div className="lg:col-span-1 space-y-6">
            {/* Epic Selection */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Select Epic</CardTitle>
                <CardDescription>Choose an epic to export</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select value={selectedEpic} onValueChange={setSelectedEpic}>
                  <SelectTrigger data-testid="epic-selector">
                    <SelectValue placeholder="Select an epic..." />
                  </SelectTrigger>
                  <SelectContent>
                    {epics.map((epic) => (
                      <SelectItem key={epic.epic_id} value={epic.epic_id}>
                        {epic.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="include-bugs"
                    checked={includeBugs}
                    onCheckedChange={setIncludeBugs}
                  />
                  <Label htmlFor="include-bugs" className="text-sm">Include bugs in export</Label>
                </div>
              </CardContent>
            </Card>

            {/* Export Preview */}
            {selectedEpic && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Export Preview</CardTitle>
                  <CardDescription>Items that will be exported</CardDescription>
                </CardHeader>
                <CardContent>
                  {previewLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : preview ? (
                    <div className="space-y-4">
                      {/* Summary */}
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="flex items-center gap-2">
                          <Layers className="w-4 h-4 text-violet-400" />
                          <span>1 Epic</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <BookOpen className="w-4 h-4 text-blue-400" />
                          <span>{preview.feature_count} Features</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-green-400" />
                          <span>{preview.story_count} Stories</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Bug className="w-4 h-4 text-red-400" />
                          <span>{preview.bug_count} Bugs</span>
                        </div>
                      </div>

                      <Separator />

                      {/* Items List */}
                      <div className="max-h-64 overflow-y-auto space-y-1">
                        {preview.items.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-muted/50">
                            {getItemIcon(item.type)}
                            <span className="truncate flex-1">{item.title}</span>
                            {item.moscow && (
                              <Badge variant="outline" className="text-xs">{item.moscow.replace('_', ' ')}</Badge>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">Select an epic to see preview</p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Export Options */}
          <div className="lg:col-span-2">
            <Tabs defaultValue="file" className="space-y-6">
              <TabsList className="grid grid-cols-3 w-full">
                <TabsTrigger value="file" data-testid="file-export-tab">
                  <Download className="w-4 h-4 mr-2" />
                  File Export
                </TabsTrigger>
                <TabsTrigger value="jira" data-testid="jira-export-tab">
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Jira
                </TabsTrigger>
                <TabsTrigger value="azure" data-testid="azure-export-tab">
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Azure DevOps
                </TabsTrigger>
              </TabsList>

              {/* File Export Tab */}
              <TabsContent value="file">
                <Card>
                  <CardHeader>
                    <CardTitle>Download Export File</CardTitle>
                    <CardDescription>Export to a file format you can import manually</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <Button
                        variant="outline"
                        className="h-24 flex-col gap-2"
                        onClick={() => handleFileExport('jira_csv')}
                        disabled={!selectedEpic || loading}
                        data-testid="export-jira-csv-btn"
                      >
                        <FileSpreadsheet className="w-8 h-8 text-green-500" />
                        <span>Jira CSV</span>
                      </Button>
                      
                      <Button
                        variant="outline"
                        className="h-24 flex-col gap-2"
                        onClick={() => handleFileExport('azure_devops_csv')}
                        disabled={!selectedEpic || loading}
                        data-testid="export-azure-csv-btn"
                      >
                        <FileSpreadsheet className="w-8 h-8 text-blue-500" />
                        <span>Azure DevOps CSV</span>
                      </Button>
                      
                      <Button
                        variant="outline"
                        className="h-24 flex-col gap-2"
                        onClick={() => handleFileExport('json')}
                        disabled={!selectedEpic || loading}
                        data-testid="export-json-btn"
                      >
                        <FileJson className="w-8 h-8 text-amber-500" />
                        <span>JSON</span>
                      </Button>
                      
                      <Button
                        variant="outline"
                        className="h-24 flex-col gap-2"
                        onClick={() => handleFileExport('markdown')}
                        disabled={!selectedEpic || loading}
                        data-testid="export-markdown-btn"
                      >
                        <FileText className="w-8 h-8 text-purple-500" />
                        <span>Markdown</span>
                      </Button>
                    </div>

                    <Alert className="mt-4">
                      <Info className="w-4 h-4" />
                      <AlertTitle>Import Instructions</AlertTitle>
                      <AlertDescription className="text-sm">
                        <strong>Jira:</strong> Go to Project Settings → External System Import → CSV<br />
                        <strong>Azure DevOps:</strong> Go to Boards → Work Items → Import Work Items
                      </AlertDescription>
                    </Alert>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Jira Direct Export Tab */}
              <TabsContent value="jira">
                <Card>
                  <CardHeader>
                    <CardTitle>Export to Jira Cloud</CardTitle>
                    <CardDescription>Push directly to your Jira instance via API</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="jira-url">Jira Cloud URL</Label>
                        <Input
                          id="jira-url"
                          placeholder="https://yourcompany.atlassian.net"
                          value={jiraConfig.base_url}
                          onChange={(e) => setJiraConfig({ ...jiraConfig, base_url: e.target.value })}
                          data-testid="jira-url-input"
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="jira-project">Project Key</Label>
                        <Input
                          id="jira-project"
                          placeholder="PROJ"
                          value={jiraConfig.project_key}
                          onChange={(e) => setJiraConfig({ ...jiraConfig, project_key: e.target.value })}
                          data-testid="jira-project-input"
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="jira-email">Email</Label>
                        <Input
                          id="jira-email"
                          type="email"
                          placeholder="you@company.com"
                          value={jiraConfig.email}
                          onChange={(e) => setJiraConfig({ ...jiraConfig, email: e.target.value })}
                          data-testid="jira-email-input"
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="jira-token">API Token</Label>
                        <Input
                          id="jira-token"
                          type="password"
                          placeholder="••••••••"
                          value={jiraConfig.api_token}
                          onChange={(e) => setJiraConfig({ ...jiraConfig, api_token: e.target.value })}
                          data-testid="jira-token-input"
                        />
                      </div>
                    </div>

                    <Alert>
                      <Info className="w-4 h-4" />
                      <AlertDescription className="text-sm">
                        Generate an API token at{' '}
                        <a href="https://id.atlassian.com/manage-profile/security/api-tokens" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                          Atlassian Account Settings
                        </a>
                      </AlertDescription>
                    </Alert>

                    <Button
                      className="w-full"
                      onClick={handleJiraExport}
                      disabled={!selectedEpic || loading}
                      data-testid="export-to-jira-btn"
                    >
                      {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                      Export to Jira
                    </Button>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Azure DevOps Direct Export Tab */}
              <TabsContent value="azure">
                <Card>
                  <CardHeader>
                    <CardTitle>Export to Azure DevOps</CardTitle>
                    <CardDescription>Push directly to your Azure DevOps organization via API</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="azure-org">Organization</Label>
                        <Input
                          id="azure-org"
                          placeholder="your-organization"
                          value={azureConfig.organization}
                          onChange={(e) => setAzureConfig({ ...azureConfig, organization: e.target.value })}
                          data-testid="azure-org-input"
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="azure-project">Project</Label>
                        <Input
                          id="azure-project"
                          placeholder="Your Project"
                          value={azureConfig.project}
                          onChange={(e) => setAzureConfig({ ...azureConfig, project: e.target.value })}
                          data-testid="azure-project-input"
                        />
                      </div>
                      
                      <div className="col-span-2 space-y-2">
                        <Label htmlFor="azure-pat">Personal Access Token (PAT)</Label>
                        <Input
                          id="azure-pat"
                          type="password"
                          placeholder="••••••••"
                          value={azureConfig.pat}
                          onChange={(e) => setAzureConfig({ ...azureConfig, pat: e.target.value })}
                          data-testid="azure-pat-input"
                        />
                      </div>
                    </div>

                    <Alert>
                      <Info className="w-4 h-4" />
                      <AlertDescription className="text-sm">
                        Generate a PAT at{' '}
                        <a href="https://dev.azure.com" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                          Azure DevOps → User Settings → Personal Access Tokens
                        </a>
                        . Required scopes: Work Items (Read, write, & manage)
                      </AlertDescription>
                    </Alert>

                    <Button
                      className="w-full"
                      onClick={handleAzureExport}
                      disabled={!selectedEpic || loading}
                      data-testid="export-to-azure-btn"
                    >
                      {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                      Export to Azure DevOps
                    </Button>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {/* Field Mapping Info */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  Field Mapping
                </CardTitle>
                <CardDescription>How JarlPM items map to external systems</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-6 text-sm">
                  <div>
                    <h4 className="font-medium mb-2 text-blue-400">Jira</h4>
                    <ul className="space-y-1 text-muted-foreground">
                      <li>Epic → Epic</li>
                      <li>Feature → Story (linked to Epic)</li>
                      <li>User Story → Sub-task (linked to Story)</li>
                      <li>Bug → Bug</li>
                      <li>MoSCoW → Priority</li>
                      <li>RICE Score → Story Points</li>
                    </ul>
                  </div>
                  <div>
                    <h4 className="font-medium mb-2 text-cyan-400">Azure DevOps</h4>
                    <ul className="space-y-1 text-muted-foreground">
                      <li>Epic → Epic</li>
                      <li>Feature → Feature (linked to Epic)</li>
                      <li>User Story → User Story (linked to Feature)</li>
                      <li>Bug → Bug</li>
                      <li>MoSCoW → Priority (1-4)</li>
                      <li>RICE Score → Story Points</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      {/* Export Results Dialog */}
      <Dialog open={showResultsDialog} onOpenChange={setShowResultsDialog}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {exportResults?.success ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-500" />
              )}
              Export Results
            </DialogTitle>
            <DialogDescription>
              {exportResults?.created_count || 0} items created, {exportResults?.error_count || 0} errors
            </DialogDescription>
          </DialogHeader>

          {exportResults && (
            <div className="space-y-4">
              {/* Created Items */}
              {exportResults.created.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm mb-2 text-green-400">Created Successfully</h4>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {exportResults.created.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-sm py-1 px-2 rounded bg-green-500/10">
                        <CheckCircle2 className="w-3 h-3 text-green-500" />
                        <Badge variant="outline" className="text-xs">{item.type}</Badge>
                        <span className="truncate">{item.key || item.id}: {item.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Errors */}
              {exportResults.errors.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm mb-2 text-red-400">Errors</h4>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {exportResults.errors.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-sm py-1 px-2 rounded bg-red-500/10">
                        <XCircle className="w-3 h-3 text-red-500" />
                        <Badge variant="outline" className="text-xs">{item.type}</Badge>
                        <span className="truncate">{item.title}: {item.error}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setShowResultsDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Export;
