import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { subscriptionAPI, llmProviderAPI, authAPI, deliveryContextAPI, integrationsAPI } from '@/api';
import { useAuthStore, useSubscriptionStore, useLLMProviderStore, useThemeStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { 
  ArrowLeft, CreditCard, Key, Loader2, Palette, Briefcase, Link2
} from 'lucide-react';

// Import tab components
import {
  DeliveryContextTab,
  SubscriptionTab,
  LLMProviderTab,
  AppearanceTab,
  IntegrationsTab
} from '@/components/settings';

const Settings = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, logout } = useAuthStore();
  const { subscription, isActive, setSubscription } = useSubscriptionStore();
  const { providers, setProviders } = useLLMProviderStore();
  const { theme, setTheme } = useThemeStore();

  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [checkingPayment, setCheckingPayment] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [reactivating, setReactivating] = useState(false);
  const [billingCycle, setBillingCycle] = useState('annual');
  
  // LLM Provider state
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [keyError, setKeyError] = useState('');

  // Product Delivery Context state
  const [deliveryContext, setDeliveryContext] = useState({
    industry: '',
    delivery_methodology: '',
    sprint_cycle_length: '',
    sprint_start_date: '',
    num_developers: '',
    num_qa: '',
    points_per_dev_per_sprint: '8',
    delivery_platform: '',
    quality_mode: 'standard',
  });
  const [savingContext, setSavingContext] = useState(false);
  const [contextError, setContextError] = useState('');
  const [contextSuccess, setContextSuccess] = useState(false);

  // Tab state
  const [activeTab, setActiveTab] = useState('delivery');

  // External Integrations state
  const [integrations, setIntegrations] = useState({});
  const [connectingLinear, setConnectingLinear] = useState(false);
  const [disconnectingLinear, setDisconnectingLinear] = useState(false);
  const [linearTeams, setLinearTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState('');
  const [configuringLinear, setConfiguringLinear] = useState(false);

  // Jira integration state
  const [connectingJira, setConnectingJira] = useState(false);
  const [disconnectingJira, setDisconnectingJira] = useState(false);
  const [jiraProjects, setJiraProjects] = useState([]);
  const [selectedJiraProject, setSelectedJiraProject] = useState('');
  const [configuringJira, setConfiguringJira] = useState(false);

  // Azure DevOps integration state
  const [connectingADO, setConnectingADO] = useState(false);
  const [disconnectingADO, setDisconnectingADO] = useState(false);
  const [adoOrgUrl, setAdoOrgUrl] = useState('');
  const [adoPat, setAdoPat] = useState('');
  const [adoProjects, setAdoProjects] = useState([]);
  const [selectedAdoProject, setSelectedAdoProject] = useState('');
  const [configuringADO, setConfiguringADO] = useState(false);

  // Load data
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [subRes, provRes, contextRes, integrationsRes] = await Promise.all([
        subscriptionAPI.getStatus().catch(() => ({ data: null })),
        llmProviderAPI.list().catch(() => ({ data: { configs: [] } })),
        deliveryContextAPI.get().catch(() => ({ data: {} })),
        integrationsAPI.getStatus().catch(() => ({ data: {} })),
      ]);

      if (subRes.data) setSubscription(subRes.data);
      if (provRes.data?.configs) setProviders(provRes.data.configs);
      if (contextRes.data) {
        setDeliveryContext({
          industry: contextRes.data.industry || '',
          delivery_methodology: contextRes.data.delivery_methodology || '',
          sprint_cycle_length: contextRes.data.sprint_cycle_length?.toString() || '',
          sprint_start_date: contextRes.data.sprint_start_date || '',
          num_developers: contextRes.data.num_developers?.toString() || '',
          num_qa: contextRes.data.num_qa?.toString() || '',
          points_per_dev_per_sprint: contextRes.data.points_per_dev_per_sprint?.toString() || '8',
          delivery_platform: contextRes.data.delivery_platform || '',
          quality_mode: contextRes.data.quality_mode || 'standard',
        });
      }
      if (integrationsRes.data) setIntegrations(integrationsRes.data);
    } catch (error) {
      console.error('Failed to load settings data:', error);
    } finally {
      setLoading(false);
    }
  }, [setSubscription, setProviders]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle OAuth callback from URL params
  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab) setActiveTab(tab);

    const success = searchParams.get('success');
    const error = searchParams.get('error');
    const provider = searchParams.get('provider');

    if (success === 'true' && provider) {
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} connected successfully!`);
      loadData();
    } else if (error && provider) {
      toast.error(`Failed to connect ${provider}: ${error}`);
    }
  }, [searchParams, loadData]);

  // Subscription handlers
  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      const priceId = billingCycle === 'annual' 
        ? 'price_annual_placeholder' 
        : 'price_monthly_placeholder';
      
      const response = await subscriptionAPI.createCheckoutSession(priceId);
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (error) {
      console.error('Failed to create checkout session:', error);
      toast.error('Failed to start checkout. Please try again.');
    } finally {
      setSubscribing(false);
    }
  };

  const handleCancelSubscription = async () => {
    if (!window.confirm('Are you sure you want to cancel your subscription? You will keep access until the end of your billing period.')) {
      return;
    }
    setCanceling(true);
    try {
      await subscriptionAPI.cancel();
      await loadData();
      toast.success('Subscription cancelled. You will keep access until the end of your billing period.');
    } catch (error) {
      console.error('Failed to cancel subscription:', error);
      toast.error('Failed to cancel subscription. Please try again.');
    } finally {
      setCanceling(false);
    }
  };

  const handleReactivateSubscription = async () => {
    setReactivating(true);
    try {
      await subscriptionAPI.reactivate();
      await loadData();
      toast.success('Subscription reactivated!');
    } catch (error) {
      console.error('Failed to reactivate subscription:', error);
      toast.error('Failed to reactivate subscription. Please try again.');
    } finally {
      setReactivating(false);
    }
  };

  // LLM Provider handlers
  const handleSaveProvider = async () => {
    setKeyError('');
    setSavingKey(true);
    try {
      await llmProviderAPI.create({
        provider,
        api_key: apiKey,
        model_name: modelName || undefined,
        base_url: provider === 'local' ? baseUrl : undefined,
      });
      
      setApiKey('');
      setModelName('');
      setBaseUrl('');
      toast.success('Provider saved and validated!');
      await loadData();
    } catch (error) {
      console.error('Failed to save provider:', error);
      setKeyError(error.response?.data?.detail || 'Failed to save provider');
    } finally {
      setSavingKey(false);
    }
  };

  const handleDeleteProvider = async (configId) => {
    try {
      await llmProviderAPI.delete(configId);
      toast.success('Provider removed');
      await loadData();
    } catch (error) {
      console.error('Failed to delete provider:', error);
      toast.error('Failed to remove provider');
    }
  };

  // Delivery Context handlers
  const handleSaveDeliveryContext = async () => {
    setSavingContext(true);
    setContextError('');
    setContextSuccess(false);
    
    try {
      const payload = {
        industry: deliveryContext.industry || null,
        delivery_methodology: deliveryContext.delivery_methodology || null,
        sprint_cycle_length: deliveryContext.sprint_cycle_length ? parseInt(deliveryContext.sprint_cycle_length) : null,
        sprint_start_date: deliveryContext.sprint_start_date || null,
        num_developers: deliveryContext.num_developers ? parseInt(deliveryContext.num_developers) : null,
        num_qa: deliveryContext.num_qa ? parseInt(deliveryContext.num_qa) : null,
        points_per_dev_per_sprint: deliveryContext.points_per_dev_per_sprint ? parseInt(deliveryContext.points_per_dev_per_sprint) : 8,
        delivery_platform: deliveryContext.delivery_platform || null,
        quality_mode: deliveryContext.quality_mode || 'standard',
      };
      
      await deliveryContextAPI.save(payload);
      setContextSuccess(true);
      toast.success('Delivery context saved!');
      setTimeout(() => setContextSuccess(false), 3000);
    } catch (error) {
      console.error('Failed to save delivery context:', error);
      setContextError(error.response?.data?.detail || 'Failed to save context');
    } finally {
      setSavingContext(false);
    }
  };

  // Integration handlers - Linear
  const handleConnectLinear = async () => {
    setConnectingLinear(true);
    try {
      const res = await integrationsAPI.connectLinear({
        frontend_callback_url: `${window.location.origin}/settings?tab=integrations`
      });
      if (res.data.authorization_url) {
        window.location.href = res.data.authorization_url;
      }
    } catch (error) {
      console.error('Failed to initiate Linear OAuth:', error);
      toast.error(error.response?.data?.detail || 'Failed to connect Linear');
    } finally {
      setConnectingLinear(false);
    }
  };

  const handleDisconnectLinear = async () => {
    setDisconnectingLinear(true);
    try {
      await integrationsAPI.disconnectLinear();
      await loadData();
      toast.success('Linear disconnected');
    } catch (error) {
      console.error('Failed to disconnect Linear:', error);
      toast.error('Failed to disconnect Linear');
    } finally {
      setDisconnectingLinear(false);
    }
  };

  const handleConfigureLinear = async () => {
    if (!selectedTeam) {
      toast.error('Please select a team');
      return;
    }
    
    const team = linearTeams.find(t => t.id === selectedTeam);
    if (!team) return;
    
    setConfiguringLinear(true);
    try {
      await integrationsAPI.configureLinear({
        team_id: team.id,
        team_name: team.name,
      });
      await loadData();
      toast.success('Linear configured successfully');
    } catch (error) {
      console.error('Failed to configure Linear:', error);
      toast.error('Failed to configure Linear');
    } finally {
      setConfiguringLinear(false);
    }
  };

  // Integration handlers - Jira
  const handleConnectJira = async () => {
    setConnectingJira(true);
    try {
      const res = await integrationsAPI.connectJira({
        frontend_callback_url: `${window.location.origin}/settings?tab=integrations`
      });
      if (res.data.authorization_url) {
        window.location.href = res.data.authorization_url;
      }
    } catch (error) {
      console.error('Failed to initiate Jira OAuth:', error);
      toast.error(error.response?.data?.detail || 'Failed to connect Jira');
    } finally {
      setConnectingJira(false);
    }
  };

  const handleDisconnectJira = async () => {
    setDisconnectingJira(true);
    try {
      await integrationsAPI.disconnectJira();
      await loadData();
      toast.success('Jira disconnected');
    } catch (error) {
      console.error('Failed to disconnect Jira:', error);
      toast.error('Failed to disconnect Jira');
    } finally {
      setDisconnectingJira(false);
    }
  };

  const handleConfigureJira = async () => {
    if (!selectedJiraProject) {
      toast.error('Please select a project');
      return;
    }
    
    const project = jiraProjects.find(p => p.key === selectedJiraProject);
    if (!project) return;
    
    setConfiguringJira(true);
    try {
      await integrationsAPI.configureJira({
        cloud_id: integrations.jira?.account_id,
        site_name: integrations.jira?.account_name,
        project_key: project.key,
        project_name: project.name,
      });
      await loadData();
      toast.success('Jira configured successfully');
    } catch (error) {
      console.error('Failed to configure Jira:', error);
      toast.error('Failed to configure Jira');
    } finally {
      setConfiguringJira(false);
    }
  };

  // Integration handlers - Azure DevOps
  const handleConnectADO = async () => {
    if (!adoOrgUrl || !adoPat) {
      toast.error('Please enter organization URL and PAT');
      return;
    }
    
    setConnectingADO(true);
    try {
      await integrationsAPI.connectAzureDevOps({
        organization_url: adoOrgUrl,
        pat: adoPat,
      });
      setAdoPat('');
      await loadData();
      toast.success('Azure DevOps connected successfully');
    } catch (error) {
      console.error('Failed to connect Azure DevOps:', error);
      toast.error(error.response?.data?.detail || 'Failed to connect Azure DevOps');
    } finally {
      setConnectingADO(false);
    }
  };

  const handleDisconnectADO = async () => {
    setDisconnectingADO(true);
    try {
      await integrationsAPI.disconnectAzureDevOps();
      await loadData();
      toast.success('Azure DevOps disconnected');
    } catch (error) {
      console.error('Failed to disconnect Azure DevOps:', error);
      toast.error('Failed to disconnect Azure DevOps');
    } finally {
      setDisconnectingADO(false);
    }
  };

  const handleConfigureADO = async () => {
    if (!selectedAdoProject) {
      toast.error('Please select a project');
      return;
    }
    
    const project = adoProjects.find(p => p.name === selectedAdoProject);
    if (!project) return;
    
    setConfiguringADO(true);
    try {
      await integrationsAPI.configureAzureDevOps({
        organization_url: integrations.azure_devops?.account_name ? 
          `https://dev.azure.com/${integrations.azure_devops.account_name}` : adoOrgUrl,
        project_name: project.name,
        project_id: project.id,
      });
      await loadData();
      toast.success('Azure DevOps configured successfully');
    } catch (error) {
      console.error('Failed to configure Azure DevOps:', error);
      toast.error('Failed to configure Azure DevOps');
    } finally {
      setConfiguringADO(false);
    }
  };

  // Load teams when Linear is connected
  useEffect(() => {
    if (integrations?.linear?.status === 'connected' && !integrations?.linear?.default_team) {
      integrationsAPI.getLinearTeams()
        .then(res => setLinearTeams(res.data.teams || []))
        .catch(err => console.error('Failed to load Linear teams:', err));
    }
  }, [integrations?.linear?.status, integrations?.linear?.default_team]);

  // Load Jira projects when connected
  useEffect(() => {
    if (integrations?.jira?.status === 'connected' && !integrations?.jira?.default_project) {
      integrationsAPI.getJiraProjects()
        .then(res => setJiraProjects(res.data.projects || []))
        .catch(err => console.error('Failed to load Jira projects:', err));
    }
  }, [integrations?.jira?.status, integrations?.jira?.default_project]);

  // Load ADO projects when connected
  useEffect(() => {
    if (integrations?.azure_devops?.status === 'connected') {
      integrationsAPI.getAzureDevOpsProjects()
        .then(res => setAdoProjects(res.data.projects || []))
        .catch(err => console.error('Failed to load Azure DevOps projects:', err));
    }
  }, [integrations?.azure_devops?.status]);

  if (loading) {
    return (
      <div className="min-h-screen bg-nordic-bg-primary flex items-center justify-center" data-testid="settings-loading">
        <Loader2 className="w-8 h-8 text-nordic-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="-m-6">
      {/* Page Title Bar */}
      <div className="border-b border-nordic-border bg-nordic-bg-secondary/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/dashboard')}
              className="text-nordic-text-muted hover:text-nordic-text-primary"
              data-testid="back-to-dashboard"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <span className="text-lg font-semibold text-foreground">Settings</span>
          </div>
        </div>
      </div>

      <main className="container mx-auto px-4 py-8 max-w-4xl" data-testid="settings-page">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold text-nordic-text-primary">Settings</h1>
          <p className="text-nordic-text-muted mt-2">
            Configure your account, subscription, and integrations
          </p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-nordic-bg-secondary border border-nordic-border">
            <TabsTrigger value="delivery" className="data-[state=active]:bg-nordic-bg-primary" data-testid="tab-delivery">
              <Briefcase className="w-4 h-4 mr-2" />
              Delivery Context
            </TabsTrigger>
            <TabsTrigger value="subscription" className="data-[state=active]:bg-nordic-bg-primary" data-testid="tab-subscription">
              <CreditCard className="w-4 h-4 mr-2" />
              Subscription
            </TabsTrigger>
            <TabsTrigger value="llm" className="data-[state=active]:bg-nordic-bg-primary" data-testid="tab-llm">
              <Key className="w-4 h-4 mr-2" />
              LLM Provider
            </TabsTrigger>
            <TabsTrigger value="appearance" className="data-[state=active]:bg-nordic-bg-primary" data-testid="tab-appearance">
              <Palette className="w-4 h-4 mr-2" />
              Appearance
            </TabsTrigger>
            <TabsTrigger value="integrations" className="data-[state=active]:bg-nordic-bg-primary" data-testid="tab-integrations">
              <Link2 className="w-4 h-4 mr-2" />
              Integrations
            </TabsTrigger>
          </TabsList>

          {/* Delivery Context Tab */}
          <TabsContent value="delivery" data-testid="delivery-context-tab">
            <DeliveryContextTab
              deliveryContext={deliveryContext}
              setDeliveryContext={setDeliveryContext}
              savingContext={savingContext}
              contextError={contextError}
              contextSuccess={contextSuccess}
              onSave={handleSaveDeliveryContext}
            />
          </TabsContent>

          {/* Subscription Tab */}
          <TabsContent value="subscription" data-testid="subscription-tab">
            <SubscriptionTab
              subscription={subscription}
              isActive={isActive}
              billingCycle={billingCycle}
              setBillingCycle={setBillingCycle}
              subscribing={subscribing}
              checkingPayment={checkingPayment}
              canceling={canceling}
              reactivating={reactivating}
              onSubscribe={handleSubscribe}
              onCancel={handleCancelSubscription}
              onReactivate={handleReactivateSubscription}
            />
          </TabsContent>

          {/* LLM Provider Tab */}
          <TabsContent value="llm" data-testid="llm-tab">
            <LLMProviderTab
              providers={providers}
              provider={provider}
              setProvider={setProvider}
              apiKey={apiKey}
              setApiKey={setApiKey}
              modelName={modelName}
              setModelName={setModelName}
              baseUrl={baseUrl}
              setBaseUrl={setBaseUrl}
              savingKey={savingKey}
              keyError={keyError}
              onSave={handleSaveProvider}
              onDelete={handleDeleteProvider}
            />
          </TabsContent>

          {/* Appearance Tab */}
          <TabsContent value="appearance" data-testid="appearance-tab">
            <AppearanceTab theme={theme} setTheme={setTheme} />
          </TabsContent>

          {/* Integrations Tab */}
          <TabsContent value="integrations" data-testid="integrations-tab">
            <IntegrationsTab
              isActive={isActive}
              integrations={integrations}
              // Linear
              connectingLinear={connectingLinear}
              disconnectingLinear={disconnectingLinear}
              linearTeams={linearTeams}
              selectedTeam={selectedTeam}
              setSelectedTeam={setSelectedTeam}
              configuringLinear={configuringLinear}
              onConnectLinear={handleConnectLinear}
              onDisconnectLinear={handleDisconnectLinear}
              onConfigureLinear={handleConfigureLinear}
              // Jira
              connectingJira={connectingJira}
              disconnectingJira={disconnectingJira}
              jiraProjects={jiraProjects}
              selectedJiraProject={selectedJiraProject}
              setSelectedJiraProject={setSelectedJiraProject}
              configuringJira={configuringJira}
              onConnectJira={handleConnectJira}
              onDisconnectJira={handleDisconnectJira}
              onConfigureJira={handleConfigureJira}
              // Azure DevOps
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
              onConnectADO={handleConnectADO}
              onDisconnectADO={handleDisconnectADO}
              onConfigureADO={handleConfigureADO}
              // Tab navigation
              setActiveTab={setActiveTab}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Settings;
