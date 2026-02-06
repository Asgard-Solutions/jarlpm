/**
 * IntegrationsTab - External integrations management (Linear, Jira, Azure DevOps)
 */
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Link2, Unlink, CheckCircle, AlertCircle, Loader2, ExternalLink 
} from 'lucide-react';

// Linear SVG Icon component
const LinearIcon = () => (
  <svg viewBox="0 0 100 100" className="w-6 h-6 text-white" fill="currentColor">
    <path d="M1.22541 61.5228c-.2225-.9485.90748-1.5459 1.59638-.857L39.3342 97.1782c.6889.6889.0915 1.8189-.857 1.5765C20.8 94.1102 5.95513 79.2002 1.22541 61.5228ZM.0222626 45.9876C-.077182 46.6422.387617 47.2239 1.04521 47.3005c16.9076 1.9666 31.9987 11.4328 41.0064 25.1052 1.0186 1.5445 3.302.8691 3.3451-.9911.0423-1.8237.0638-3.6541.0638-5.4903 0-36.8177-29.8487-66.6665-66.66657-66.6665-1.83593 0-3.66607.02185-5.49023.0645-1.86018.04289-2.53569 2.32647-.99128 3.34495C86.3328 12.9984 95.799 28.0895 97.7657 45.0064c.0766.6576.6583 1.1224 1.3129 1.0228 36.3254-5.5188 64.2133-35.9725 64.6528-73.2026.0024-.2045-.1662-.3716-.3707-.3692C28.9325 76.4257 0 47.4911.0222626 45.9876Z"/>
  </svg>
);

// Jira SVG Icon component
const JiraIcon = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6 text-white" fill="currentColor">
    <path d="M11.571 11.429L0 0h11.429a.571.571 0 0 1 .571.571v10.858l-.429-.001ZM12.428 12.428L24 24H12.571a.571.571 0 0 1-.571-.571V12.571l.428-.143ZM12.428 0L24 11.571V.571a.571.571 0 0 0-.571-.571H12.428ZM0 12.428L11.571 24H.571A.571.571 0 0 1 0 23.429V12.428Z"/>
  </svg>
);

// Azure DevOps SVG Icon component  
const AzureDevOpsIcon = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6 text-white" fill="currentColor">
    <path d="M0 8.877L2.247 5.91l8.405-3.416V.022l7.37 5.393L2.966 8.338v8.225L0 15.707v-6.83zm24 5.123l-2.248 2.968-8.405 3.416v2.472l-7.37-5.393 15.056-2.923V5.915L24 7.293v6.707z"/>
  </svg>
);

const IntegrationsTab = ({
  isActive,
  integrations,
  // Linear
  connectingLinear,
  disconnectingLinear,
  linearTeams,
  selectedTeam,
  setSelectedTeam,
  configuringLinear,
  onConnectLinear,
  onDisconnectLinear,
  onConfigureLinear,
  // Jira
  connectingJira,
  disconnectingJira,
  jiraProjects,
  selectedJiraProject,
  setSelectedJiraProject,
  configuringJira,
  onConnectJira,
  onDisconnectJira,
  onConfigureJira,
  // Azure DevOps
  connectingADO,
  disconnectingADO,
  adoOrgUrl,
  setAdoOrgUrl,
  adoPat,
  setAdoPat,
  adoProjects,
  selectedAdoProject,
  setSelectedAdoProject,
  configuringADO,
  onConnectADO,
  onDisconnectADO,
  onConfigureADO,
  // Tab navigation
  setActiveTab,
}) => {
  return (
    <Card className="bg-nordic-bg-secondary border-nordic-border">
      <CardHeader>
        <CardTitle className="text-nordic-text-primary flex items-center gap-2">
          <Link2 className="w-5 h-5 text-nordic-accent" />
          External Integrations
        </CardTitle>
        <CardDescription className="text-nordic-text-muted">
          Connect JarlPM to external project management tools to push your epics, features, and stories
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Subscription Required Notice */}
        {!isActive && (
          <div className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0" />
            <div>
              <p className="text-nordic-text-primary font-medium">Subscription Required</p>
              <p className="text-sm text-nordic-text-muted">
                External integrations are available for Pro subscribers.{' '}
                <button
                  onClick={() => setActiveTab('subscription')}
                  className="text-nordic-accent hover:underline"
                >
                  Subscribe now
                </button>
              </p>
            </div>
          </div>
        )}

        {/* Linear Integration */}
        <IntegrationCard
          name="Linear"
          description="Push issues to Linear workspaces"
          icon={<LinearIcon />}
          iconBgColor="#5E6AD2"
          status={integrations?.linear?.status}
          configured={integrations?.linear?.configured}
          accountName={integrations?.linear?.account_name}
          defaultTeam={integrations?.linear?.default_team}
          connecting={connectingLinear}
          disconnecting={disconnectingLinear}
          configuring={configuringLinear}
          onConnect={onConnectLinear}
          onDisconnect={onDisconnectLinear}
          onConfigure={onConfigureLinear}
          isActive={isActive}
          // Team/Project selection
          items={linearTeams}
          selectedItem={selectedTeam}
          setSelectedItem={setSelectedTeam}
          itemLabel="Team"
          getItemKey={(t) => t.id}
          getItemLabel={(t) => `${t.name} (${t.key})`}
          getItemValue={(t) => t.id}
        />

        {/* Jira Integration */}
        <IntegrationCard
          name="Jira"
          description="Push issues to Jira Cloud projects"
          icon={<JiraIcon />}
          iconBgColor="#0052CC"
          status={integrations?.jira?.status}
          configured={integrations?.jira?.configured}
          accountName={integrations?.jira?.account_name}
          defaultProject={integrations?.jira?.default_project}
          connecting={connectingJira}
          disconnecting={disconnectingJira}
          configuring={configuringJira}
          onConnect={onConnectJira}
          onDisconnect={onDisconnectJira}
          onConfigure={onConfigureJira}
          isActive={isActive}
          // Team/Project selection
          items={jiraProjects}
          selectedItem={selectedJiraProject}
          setSelectedItem={setSelectedJiraProject}
          itemLabel="Project"
          getItemKey={(p) => p.key}
          getItemLabel={(p) => `${p.name} (${p.key})`}
          getItemValue={(p) => p.key}
        />

        {/* Azure DevOps Integration */}
        <AzureDevOpsCard
          integrations={integrations}
          isActive={isActive}
          connectingADO={connectingADO}
          disconnectingADO={disconnectingADO}
          adoOrgUrl={adoOrgUrl}
          setAdoOrgUrl={setAdoOrgUrl}
          adoPat={adoPat}
          setAdoPat={setAdoPat}
          adoProjects={adoProjects}
          selectedAdoProject={selectedAdoProject}
          setSelectedAdoProject={setSelectedAdoProject}
          configuringADO={configuringADO}
          onConnectADO={onConnectADO}
          onDisconnectADO={onDisconnectADO}
          onConfigureADO={onConfigureADO}
        />
      </CardContent>
    </Card>
  );
};

// Generic Integration Card Component (for Linear and Jira)
const IntegrationCard = ({
  name,
  description,
  icon,
  iconBgColor,
  status,
  configured,
  accountName,
  defaultTeam,
  defaultProject,
  connecting,
  disconnecting,
  configuring,
  onConnect,
  onDisconnect,
  onConfigure,
  isActive,
  // Selection props
  items,
  selectedItem,
  setSelectedItem,
  itemLabel,
  getItemKey,
  getItemLabel,
  getItemValue,
}) => {
  const isConnected = status === 'connected';
  const hasDefault = defaultTeam || defaultProject;

  return (
    <div className="border border-nordic-border rounded-lg overflow-hidden">
      <div className="p-4 bg-nordic-bg-primary border-b border-nordic-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div 
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: iconBgColor }}
            >
              {icon}
            </div>
            <div>
              <h3 className="font-semibold text-nordic-text-primary">{name}</h3>
              <p className="text-sm text-nordic-text-muted">{description}</p>
            </div>
          </div>
          <Badge
            className={
              isConnected
                ? 'bg-nordic-green text-white'
                : configured
                ? 'bg-nordic-bg-primary text-nordic-text-muted border border-nordic-border'
                : 'bg-amber-500/20 text-amber-500 border border-amber-500/30'
            }
          >
            {isConnected ? 'Connected' : configured ? 'Not Connected' : 'Not Configured'}
          </Badge>
        </div>
      </div>
      
      <div className="p-4 space-y-4">
        {isConnected ? (
          <>
            {/* Connected State */}
            <div className="flex items-center gap-2 text-sm text-nordic-text-secondary">
              <CheckCircle className="w-4 h-4 text-nordic-green" />
              Connected to: <span className="font-medium text-nordic-text-primary">{accountName || `${name} Workspace`}</span>
            </div>
            
            {hasDefault && (
              <div className="text-sm text-nordic-text-secondary">
                Default {defaultTeam ? 'team' : 'project'}: <span className="font-medium text-nordic-text-primary">
                  {(defaultTeam || defaultProject)?.name}
                </span>
              </div>
            )}
            
            {/* Selection UI */}
            {!hasDefault && items.length > 0 && (
              <div className="space-y-3 p-3 bg-nordic-bg-primary rounded-lg border border-nordic-border">
                <Label className="text-nordic-text-secondary">Select Default {itemLabel}</Label>
                <Select value={selectedItem} onValueChange={setSelectedItem}>
                  <SelectTrigger className="bg-background border-border text-foreground">
                    <SelectValue placeholder={`Choose a ${itemLabel.toLowerCase()}`} />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border shadow-lg">
                    {items.map((item) => (
                      <SelectItem key={getItemKey(item)} value={getItemValue(item)}>
                        {getItemLabel(item)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={onConfigure}
                  disabled={!selectedItem || configuring}
                  size="sm"
                  className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                >
                  {configuring ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Configuration'
                  )}
                </Button>
              </div>
            )}
            
            <Button
              onClick={onDisconnect}
              disabled={disconnecting}
              variant="outline"
              className="border-red-500 text-red-500 hover:bg-red-500/10"
              data-testid={`disconnect-${name.toLowerCase()}-btn`}
            >
              {disconnecting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Disconnecting...
                </>
              ) : (
                <>
                  <Unlink className="w-4 h-4 mr-2" />
                  Disconnect
                </>
              )}
            </Button>
          </>
        ) : (
          <>
            {/* Disconnected State */}
            {configured ? (
              <Button
                onClick={onConnect}
                disabled={connecting || !isActive}
                className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                data-testid={`connect-${name.toLowerCase()}-btn`}
              >
                {connecting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <Link2 className="w-4 h-4 mr-2" />
                    Connect {name}
                  </>
                )}
              </Button>
            ) : (
              <div className="text-sm text-nordic-text-muted">
                <p>{name} integration requires server-side OAuth configuration.</p>
                <p className="mt-1">Contact your administrator to enable this integration.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// Azure DevOps Card Component (PAT-based, different UI)
const AzureDevOpsCard = ({
  integrations,
  isActive,
  connectingADO,
  disconnectingADO,
  adoOrgUrl,
  setAdoOrgUrl,
  adoPat,
  setAdoPat,
  adoProjects,
  selectedAdoProject,
  setSelectedAdoProject,
  configuringADO,
  onConnectADO,
  onDisconnectADO,
  onConfigureADO,
}) => {
  const isConnected = integrations?.azure_devops?.status === 'connected';
  const hasDefaultProject = integrations?.azure_devops?.default_project;

  return (
    <div className="border border-nordic-border rounded-lg overflow-hidden">
      <div className="p-4 bg-nordic-bg-primary border-b border-nordic-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#0078D4] flex items-center justify-center">
              <AzureDevOpsIcon />
            </div>
            <div>
              <h3 className="font-semibold text-nordic-text-primary">Azure DevOps</h3>
              <p className="text-sm text-nordic-text-muted">Push work items to Azure DevOps</p>
            </div>
          </div>
          <Badge
            className={
              isConnected
                ? 'bg-nordic-green text-white'
                : 'bg-nordic-bg-primary text-nordic-text-muted border border-nordic-border'
            }
          >
            {isConnected ? 'Connected' : 'Not Connected'}
          </Badge>
        </div>
      </div>
      
      <div className="p-4 space-y-4">
        {isConnected ? (
          <>
            {/* Connected State */}
            <div className="flex items-center gap-2 text-sm text-nordic-text-secondary">
              <CheckCircle className="w-4 h-4 text-nordic-green" />
              Connected to: <span className="font-medium text-nordic-text-primary">
                {integrations.azure_devops.account_name || 'Azure DevOps Organization'}
              </span>
            </div>
            
            {hasDefaultProject && (
              <div className="text-sm text-nordic-text-secondary">
                Default project: <span className="font-medium text-nordic-text-primary">
                  {integrations.azure_devops.default_project.name}
                </span>
              </div>
            )}
            
            {/* Project Selection */}
            {!hasDefaultProject && adoProjects.length > 0 && (
              <div className="space-y-3 p-3 bg-nordic-bg-primary rounded-lg border border-nordic-border">
                <Label className="text-nordic-text-secondary">Select Default Project</Label>
                <Select value={selectedAdoProject} onValueChange={setSelectedAdoProject}>
                  <SelectTrigger className="bg-background border-border text-foreground">
                    <SelectValue placeholder="Choose a project" />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border shadow-lg">
                    {adoProjects.map((project) => (
                      <SelectItem key={project.id} value={project.name}>
                        {project.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={onConfigureADO}
                  disabled={!selectedAdoProject || configuringADO}
                  size="sm"
                  className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                >
                  {configuringADO ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Configuration'
                  )}
                </Button>
              </div>
            )}
            
            <Button
              onClick={onDisconnectADO}
              disabled={disconnectingADO}
              variant="outline"
              className="border-red-500 text-red-500 hover:bg-red-500/10"
              data-testid="disconnect-ado-btn"
            >
              {disconnectingADO ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Disconnecting...
                </>
              ) : (
                <>
                  <Unlink className="w-4 h-4 mr-2" />
                  Disconnect
                </>
              )}
            </Button>
          </>
        ) : (
          <>
            {/* Disconnected State - PAT Connection Form */}
            <div className="space-y-4">
              <p className="text-sm text-nordic-text-muted">
                Connect using a Personal Access Token (PAT) from your Azure DevOps organization.
              </p>
              
              <div className="space-y-3 p-3 bg-nordic-bg-primary rounded-lg border border-nordic-border">
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Organization URL</Label>
                  <Input
                    type="url"
                    placeholder="https://dev.azure.com/your-org"
                    value={adoOrgUrl}
                    onChange={(e) => setAdoOrgUrl(e.target.value)}
                    className="bg-background border-border text-foreground"
                    data-testid="ado-org-url-input"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Personal Access Token</Label>
                  <Input
                    type="password"
                    placeholder="Enter your PAT"
                    value={adoPat}
                    onChange={(e) => setAdoPat(e.target.value)}
                    className="bg-background border-border text-foreground"
                    data-testid="ado-pat-input"
                  />
                  <p className="text-xs text-nordic-text-muted">
                    Required scopes: Work Items (Read & Write), Project and Team (Read)
                  </p>
                </div>
                
                <Button
                  onClick={onConnectADO}
                  disabled={connectingADO || !isActive || !adoOrgUrl || !adoPat}
                  className="bg-nordic-accent hover:bg-nordic-accent/90 text-white w-full"
                  data-testid="connect-ado-btn"
                >
                  {connectingADO ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <Link2 className="w-4 h-4 mr-2" />
                      Connect to Azure DevOps
                    </>
                  )}
                </Button>
              </div>
              
              <a 
                href="https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-nordic-accent hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                How to create a PAT
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default IntegrationsTab;
