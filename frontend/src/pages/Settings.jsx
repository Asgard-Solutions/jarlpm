import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { subscriptionAPI, llmProviderAPI, authAPI, deliveryContextAPI, integrationsAPI } from '@/api';
import { useAuthStore, useSubscriptionStore, useLLMProviderStore, useThemeStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { 
  ArrowLeft, CreditCard, Key, Loader2, 
  CheckCircle, AlertCircle, Trash2, ExternalLink, Palette, Sun, Moon, Monitor,
  Briefcase, Users, Calendar, Sparkles, Link2, Unlink
} from 'lucide-react';

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
  const [billingCycle, setBillingCycle] = useState('annual'); // Default to annual (better value)
  
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
    delivery_platform: '',
    points_per_dev_per_sprint: '8',
    quality_mode: 'standard',
  });
  const [savingContext, setSavingContext] = useState(false);
  const [contextError, setContextError] = useState('');
  const [contextSuccess, setContextSuccess] = useState(false);

  // Integrations state
  const [integrations, setIntegrations] = useState({});
  const [loadingIntegrations, setLoadingIntegrations] = useState(false);
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

  // Tab state - controlled by query param
  const [activeTab, setActiveTab] = useState('delivery');

  // Handle tab from URL query params
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && ['delivery', 'subscription', 'llm', 'appearance', 'integrations'].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  // Select logo based on theme
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [subRes, provRes, ctxRes] = await Promise.all([
        subscriptionAPI.getStatus(),
        llmProviderAPI.list(),
        deliveryContextAPI.get().catch(() => ({ data: null })),
      ]);
      setSubscription(subRes.data);
      setProviders(provRes.data);
      
      if (ctxRes.data) {
        setDeliveryContext({
          industry: ctxRes.data.industry || '',
          delivery_methodology: ctxRes.data.delivery_methodology || '',
          sprint_cycle_length: ctxRes.data.sprint_cycle_length?.toString() || '',
          sprint_start_date: ctxRes.data.sprint_start_date || '',
          num_developers: ctxRes.data.num_developers?.toString() || '',
          num_qa: ctxRes.data.num_qa?.toString() || '',
          delivery_platform: ctxRes.data.delivery_platform || '',
          points_per_dev_per_sprint: ctxRes.data.points_per_dev_per_sprint?.toString() || '8',
          quality_mode: ctxRes.data.quality_mode || 'standard',
        });
      }
      
      // Load integrations status (only if subscribed)
      if (subRes.data?.status === 'active') {
        try {
          const intRes = await integrationsAPI.getStatus();
          setIntegrations(intRes.data);
        } catch (intError) {
          console.log('Integrations status not available:', intError);
        }
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  }, [setSubscription, setProviders]);

  const pollPaymentStatus = useCallback(async (sessionId, attempts = 0) => {
    const maxAttempts = 10;
    const pollInterval = 2000;

    if (attempts >= maxAttempts) {
      setCheckingPayment(false);
      return;
    }

    try {
      const res = await subscriptionAPI.getCheckoutStatus(sessionId);
      if (res.data.payment_status === 'paid') {
        await loadData();
        setCheckingPayment(false);
      } else if (res.data.status === 'expired' || res.data.payment_status === 'failed') {
        setCheckingPayment(false);
      } else {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
      }
    } catch {
      setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
    }
  }, [loadData]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const paymentStatus = searchParams.get('payment');
    const sessionId = searchParams.get('session_id');
    
    if (paymentStatus === 'success' && sessionId) {
      setCheckingPayment(true);
      pollPaymentStatus(sessionId);
    }
  }, [searchParams, pollPaymentStatus]);

  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      const res = await subscriptionAPI.createCheckout(window.location.origin, billingCycle);
      window.location.href = res.data.checkout_url;
    } catch (error) {
      console.error('Failed to create checkout:', error);
      setSubscribing(false);
    }
  };

  const handleCancelSubscription = async () => {
    if (!confirm('Are you sure you want to cancel your subscription? You will retain access until the end of your billing period.')) {
      return;
    }
    
    setCanceling(true);
    try {
      await subscriptionAPI.cancel(true); // Cancel at period end
      await loadData();
    } catch (error) {
      console.error('Failed to cancel subscription:', error);
    } finally {
      setCanceling(false);
    }
  };

  const handleReactivateSubscription = async () => {
    setReactivating(true);
    try {
      await subscriptionAPI.reactivate();
      await loadData();
    } catch (error) {
      console.error('Failed to reactivate subscription:', error);
    } finally {
      setReactivating(false);
    }
  };

  const handleSaveProvider = async () => {
    if (!apiKey.trim()) {
      setKeyError('API key is required');
      return;
    }

    setSavingKey(true);
    setKeyError('');
    
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
      await loadData();
    } catch (error) {
      setKeyError(error.response?.data?.detail || 'Failed to save API key');
    } finally {
      setSavingKey(false);
    }
  };

  const handleDeleteProvider = async (configId) => {
    try {
      await llmProviderAPI.delete(configId);
      await loadData();
    } catch (error) {
      console.error('Failed to delete provider:', error);
    }
  };

  const handleSaveDeliveryContext = async () => {
    setSavingContext(true);
    setContextError('');
    setContextSuccess(false);
    
    try {
      const data = {
        industry: deliveryContext.industry || null,
        delivery_methodology: deliveryContext.delivery_methodology || null,
        sprint_cycle_length: deliveryContext.sprint_cycle_length ? parseInt(deliveryContext.sprint_cycle_length) : null,
        sprint_start_date: deliveryContext.sprint_start_date || null,
        num_developers: deliveryContext.num_developers ? parseInt(deliveryContext.num_developers) : null,
        num_qa: deliveryContext.num_qa ? parseInt(deliveryContext.num_qa) : null,
        delivery_platform: deliveryContext.delivery_platform || null,
        points_per_dev_per_sprint: deliveryContext.points_per_dev_per_sprint ? parseInt(deliveryContext.points_per_dev_per_sprint) : 8,
        quality_mode: deliveryContext.quality_mode || 'standard',
      };
      
      const response = await deliveryContextAPI.update(data);
      
      // Update local state with saved data from server
      if (response.data) {
        setDeliveryContext({
          industry: response.data.industry || '',
          delivery_methodology: response.data.delivery_methodology || '',
          sprint_cycle_length: response.data.sprint_cycle_length?.toString() || '',
          sprint_start_date: response.data.sprint_start_date || '',
          num_developers: response.data.num_developers?.toString() || '',
          num_qa: response.data.num_qa?.toString() || '',
          delivery_platform: response.data.delivery_platform || '',
          points_per_dev_per_sprint: response.data.points_per_dev_per_sprint?.toString() || '8',
          quality_mode: response.data.quality_mode || 'standard',
        });
      }
      
      setContextSuccess(true);
      toast.success('Delivery context saved successfully');
      setTimeout(() => setContextSuccess(false), 3000);
    } catch (error) {
      setContextError(error.response?.data?.detail || 'Failed to save delivery context');
      toast.error('Failed to save delivery context');
    } finally {
      setSavingContext(false);
    }
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } catch {
      // Continue anyway
    }
    logout();
    navigate('/');
  };

  // Integration handlers
  const handleConnectLinear = async () => {
    setConnectingLinear(true);
    try {
      const callbackUrl = `${window.location.origin}/settings?tab=integrations`;
      const res = await integrationsAPI.connectLinear(callbackUrl);
      window.location.href = res.data.authorization_url;
    } catch (error) {
      console.error('Failed to initiate Linear connection:', error);
      toast.error(error.response?.data?.detail || 'Failed to connect to Linear');
      setConnectingLinear(false);
    }
  };

  const handleDisconnectLinear = async () => {
    if (!confirm('Are you sure you want to disconnect Linear? This will remove all your Linear integration settings.')) {
      return;
    }
    
    setDisconnectingLinear(true);
    try {
      await integrationsAPI.disconnectLinear();
      await loadData();
      setLinearTeams([]);
      setSelectedTeam('');
      toast.success('Linear disconnected successfully');
    } catch (error) {
      console.error('Failed to disconnect Linear:', error);
      toast.error('Failed to disconnect Linear');
    } finally {
      setDisconnectingLinear(false);
    }
  };

  const loadLinearTeams = async () => {
    try {
      const res = await integrationsAPI.getLinearTeams();
      setLinearTeams(res.data.teams || []);
    } catch (error) {
      console.error('Failed to load Linear teams:', error);
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

  // Check for OAuth callback
  useEffect(() => {
    const success = searchParams.get('success');
    const error = searchParams.get('error');
    const provider = searchParams.get('provider');
    
    if (provider === 'linear') {
      if (success === 'true') {
        toast.success('Linear connected successfully!');
        loadData();
        loadLinearTeams();
      } else if (error) {
        toast.error(`Linear connection failed: ${error}`);
      }
      
      // Clean up URL
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('success');
      newUrl.searchParams.delete('error');
      newUrl.searchParams.delete('provider');
      window.history.replaceState({}, '', newUrl.toString());
    }
  }, [searchParams]);

  // Load Linear teams when integration is connected
  useEffect(() => {
    if (integrations?.linear?.status === 'connected') {
      loadLinearTeams();
    }
  }, [integrations?.linear?.status]);

  // Jira integration handlers
  const handleConnectJira = async () => {
    setConnectingJira(true);
    try {
      const callbackUrl = `${window.location.origin}/settings?tab=integrations`;
      const res = await integrationsAPI.connectJira(callbackUrl);
      window.location.href = res.data.authorization_url;
    } catch (error) {
      console.error('Failed to initiate Jira connection:', error);
      toast.error(error.response?.data?.detail || 'Failed to connect to Jira');
      setConnectingJira(false);
    }
  };

  const handleDisconnectJira = async () => {
    if (!confirm('Are you sure you want to disconnect Jira? This will remove all your Jira integration settings.')) {
      return;
    }
    
    setDisconnectingJira(true);
    try {
      await integrationsAPI.disconnectJira();
      await loadData();
      setJiraProjects([]);
      setSelectedJiraProject('');
      toast.success('Jira disconnected successfully');
    } catch (error) {
      console.error('Failed to disconnect Jira:', error);
      toast.error('Failed to disconnect Jira');
    } finally {
      setDisconnectingJira(false);
    }
  };

  const loadJiraProjects = async () => {
    try {
      const res = await integrationsAPI.getJiraProjects();
      setJiraProjects(res.data.projects || []);
    } catch (error) {
      console.error('Failed to load Jira projects:', error);
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
        cloud_id: integrations.jira?.account_name ? integrations.jira.account_name : '',
        site_name: integrations.jira?.account_name || '',
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

  // Load Jira projects when integration is connected
  useEffect(() => {
    if (integrations?.jira?.status === 'connected') {
      loadJiraProjects();
    }
  }, [integrations?.jira?.status]);

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

          {/* Product Delivery Context Tab */}
          <TabsContent value="delivery" data-testid="delivery-context-tab">
            <Card className="bg-nordic-bg-secondary border-nordic-border">
              <CardHeader>
                <CardTitle className="text-nordic-text-primary flex items-center gap-2">
                  <Briefcase className="w-5 h-5 text-nordic-accent" />
                  Product Delivery Context
                </CardTitle>
                <CardDescription className="text-nordic-text-muted">
                  Configure your team&apos;s delivery context. This information is automatically included in all AI prompts as read-only context.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Industry */}
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Industry</Label>
                  <Input
                    value={deliveryContext.industry}
                    onChange={(e) => setDeliveryContext({ ...deliveryContext, industry: e.target.value })}
                    placeholder="e.g., FinTech, Healthcare, E-commerce (comma-separated)"
                    className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                    data-testid="input-industry"
                  />
                  <p className="text-xs text-nordic-text-muted">Comma-separated list of industries</p>
                </div>

                {/* Delivery Methodology */}
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Delivery Methodology</Label>
                  <Select
                    value={deliveryContext.delivery_methodology}
                    onValueChange={(value) => setDeliveryContext({ ...deliveryContext, delivery_methodology: value })}
                  >
                    <SelectTrigger className="bg-background border-border text-foreground" data-testid="select-methodology">
                      <SelectValue placeholder="Select methodology" />
                    </SelectTrigger>
                    <SelectContent className="bg-popover border-border shadow-lg">
                      <SelectItem value="waterfall">Waterfall</SelectItem>
                      <SelectItem value="agile">Agile</SelectItem>
                      <SelectItem value="scrum">Scrum</SelectItem>
                      <SelectItem value="kanban">Kanban</SelectItem>
                      <SelectItem value="hybrid">Hybrid</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Sprint Details Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary">Sprint Cycle Length (days)</Label>
                    <Input
                      type="number"
                      min="1"
                      max="365"
                      value={deliveryContext.sprint_cycle_length}
                      onChange={(e) => setDeliveryContext({ ...deliveryContext, sprint_cycle_length: e.target.value })}
                      placeholder="e.g., 14"
                      className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                      data-testid="input-sprint-length"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary">Sprint Start Date</Label>
                    <Input
                      type="date"
                      value={deliveryContext.sprint_start_date}
                      onChange={(e) => setDeliveryContext({ ...deliveryContext, sprint_start_date: e.target.value })}
                      className="bg-background border-border text-foreground"
                      data-testid="input-sprint-date"
                    />
                  </div>
                </div>

                {/* Team Size Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary flex items-center gap-2">
                      <Users className="w-4 h-4" />
                      Number of Developers
                    </Label>
                    <Input
                      type="number"
                      min="0"
                      value={deliveryContext.num_developers}
                      onChange={(e) => setDeliveryContext({ ...deliveryContext, num_developers: e.target.value })}
                      placeholder="e.g., 5"
                      className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                      data-testid="input-num-developers"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary flex items-center gap-2">
                      <Users className="w-4 h-4" />
                      Number of QA
                    </Label>
                    <Input
                      type="number"
                      min="0"
                      value={deliveryContext.num_qa}
                      onChange={(e) => setDeliveryContext({ ...deliveryContext, num_qa: e.target.value })}
                      placeholder="e.g., 2"
                      className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                      data-testid="input-num-qa"
                    />
                  </div>
                </div>

                {/* Velocity */}
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Velocity (Points per Dev per Sprint)</Label>
                  <Input
                    type="number"
                    min="1"
                    max="50"
                    value={deliveryContext.points_per_dev_per_sprint}
                    onChange={(e) => setDeliveryContext({ ...deliveryContext, points_per_dev_per_sprint: e.target.value })}
                    placeholder="e.g., 8"
                    className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                    data-testid="input-velocity"
                  />
                  <p className="text-xs text-muted-foreground">
                    Used in Delivery Reality to calculate 2-sprint capacity. Default is 8 points.
                  </p>
                </div>

                {/* Delivery Platform */}
                <div className="space-y-2">
                  <Label className="text-nordic-text-secondary">Delivery Platform</Label>
                  <Select
                    value={deliveryContext.delivery_platform}
                    onValueChange={(value) => setDeliveryContext({ ...deliveryContext, delivery_platform: value })}
                  >
                    <SelectTrigger className="bg-background border-border text-foreground" data-testid="select-platform">
                      <SelectValue placeholder="Select platform" />
                    </SelectTrigger>
                    <SelectContent className="bg-popover border-border shadow-lg">
                      <SelectItem value="jira">Jira</SelectItem>
                      <SelectItem value="azure_devops">Azure DevOps</SelectItem>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Quality Mode Toggle */}
                <div className="space-y-3 pt-4 border-t border-border">
                  <Label className="text-nordic-text-secondary flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    AI Quality Mode
                  </Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setDeliveryContext({ ...deliveryContext, quality_mode: 'standard' })}
                      className={`p-3 rounded-lg border transition-all ${
                        deliveryContext.quality_mode === 'standard'
                          ? 'border-nordic-accent bg-nordic-accent/10 text-nordic-accent'
                          : 'border-border bg-background text-muted-foreground hover:border-nordic-accent/50'
                      }`}
                      data-testid="quality-mode-standard"
                    >
                      <div className="font-medium text-sm">Standard</div>
                      <div className="text-xs mt-1 opacity-70">Single pass, faster</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeliveryContext({ ...deliveryContext, quality_mode: 'quality' })}
                      className={`p-3 rounded-lg border transition-all ${
                        deliveryContext.quality_mode === 'quality'
                          ? 'border-nordic-accent bg-nordic-accent/10 text-nordic-accent'
                          : 'border-border bg-background text-muted-foreground hover:border-nordic-accent/50'
                      }`}
                      data-testid="quality-mode-quality"
                    >
                      <div className="font-medium text-sm">Quality</div>
                      <div className="text-xs mt-1 opacity-70">2-pass with critique</div>
                    </button>
                  </div>
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 border border-border">
                    <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                    <div className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">Cost tradeoff:</span> Quality mode uses ~2x tokens but produces more reliable output. 
                      Recommended for smaller models (GPT-3.5, Claude Haiku) or complex initiatives.
                    </div>
                  </div>
                </div>

                {/* Error/Success Messages */}
                {contextError && (
                  <div className="flex items-center gap-2 text-nordic-red text-sm">
                    <AlertCircle className="w-4 h-4" />
                    {contextError}
                  </div>
                )}
                
                {contextSuccess && (
                  <div className="flex items-center gap-2 text-nordic-green text-sm">
                    <CheckCircle className="w-4 h-4" />
                    Delivery context saved successfully
                  </div>
                )}

                {/* Save Button */}
                <Button
                  onClick={handleSaveDeliveryContext}
                  disabled={savingContext}
                  className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                  data-testid="save-context-button"
                >
                  {savingContext ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Context'
                  )}
                </Button>

                {/* Info Box */}
                <div className="bg-nordic-bg-primary border border-nordic-border rounded-lg p-4 mt-4">
                  <h4 className="text-sm font-medium text-nordic-text-primary mb-2">How this is used</h4>
                  <ul className="text-xs text-nordic-text-muted space-y-1">
                    <li>• This context is automatically injected into every AI prompt</li>
                    <li>• The AI treats this as read-only background information</li>
                    <li>• Missing values are shown as &quot;Not specified&quot;</li>
                    <li>• Context persists across all Epics and sessions</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Subscription Tab */}
          <TabsContent value="subscription" data-testid="subscription-tab">
            <Card className="bg-nordic-bg-secondary border-nordic-border">
              <CardHeader>
                <CardTitle className="text-nordic-text-primary flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-nordic-accent" />
                  Subscription Status
                </CardTitle>
                <CardDescription className="text-nordic-text-muted">
                  Manage your JarlPM subscription for AI features
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-nordic-bg-primary rounded-lg border border-nordic-border">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-semibold text-nordic-text-primary">Current Plan</h3>
                      <Badge 
                        variant={isActive ? "default" : "secondary"}
                        className={isActive ? "bg-nordic-green text-white" : "bg-nordic-text-muted/20 text-nordic-text-muted"}
                      >
                        {isActive ? 'Active' : subscription?.status === 'past_due' ? 'Past Due' : 'Inactive'}
                      </Badge>
                      {subscription?.cancel_at_period_end && (
                        <Badge variant="outline" className="border-amber-500 text-amber-500">
                          Cancels at period end
                        </Badge>
                      )}
                    </div>
                    <p className="text-nordic-text-muted text-sm">
                      {isActive 
                        ? subscription?.cancel_at_period_end
                          ? `Your subscription will end on ${new Date(subscription.current_period_end).toLocaleDateString()}`
                          : `Your subscription renews on ${new Date(subscription.current_period_end).toLocaleDateString()}`
                        : subscription?.status === 'past_due'
                          ? 'Payment failed. Please update your payment method.'
                          : 'Subscribe to unlock AI-powered features'
                      }
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {isActive && subscription?.cancel_at_period_end && (
                      <Button
                        onClick={handleReactivateSubscription}
                        disabled={reactivating}
                        className="bg-nordic-green hover:bg-nordic-green/90 text-white"
                        data-testid="reactivate-button"
                      >
                        {reactivating ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : null}
                        Reactivate
                      </Button>
                    )}
                    {isActive && !subscription?.cancel_at_period_end && (
                      <Button
                        onClick={handleCancelSubscription}
                        disabled={canceling}
                        variant="outline"
                        className="border-red-500 text-red-500 hover:bg-red-500/10"
                        data-testid="cancel-subscription-button"
                      >
                        {canceling ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : null}
                        Cancel Subscription
                      </Button>
                    )}
                  </div>
                </div>

                {/* Pricing Options - Show when not subscribed */}
                {!isActive && (
                  <div className="border-t border-nordic-border pt-6">
                    <h4 className="font-medium text-nordic-text-primary mb-4">Choose Your Plan</h4>
                    
                    {/* Billing Toggle */}
                    <div className="flex items-center justify-center gap-4 mb-6">
                      <button
                        onClick={() => setBillingCycle('monthly')}
                        className={`px-4 py-2 rounded-lg transition-all ${
                          billingCycle === 'monthly' 
                            ? 'bg-nordic-accent text-white' 
                            : 'bg-nordic-bg-primary text-nordic-text-muted hover:text-nordic-text-primary'
                        }`}
                      >
                        Monthly
                      </button>
                      <button
                        onClick={() => setBillingCycle('annual')}
                        className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
                          billingCycle === 'annual' 
                            ? 'bg-nordic-accent text-white' 
                            : 'bg-nordic-bg-primary text-nordic-text-muted hover:text-nordic-text-primary'
                        }`}
                      >
                        Annual
                        <Badge className="bg-nordic-green text-white text-xs">Save $108</Badge>
                      </button>
                    </div>

                    {/* Pricing Card */}
                    <div className={`p-6 rounded-xl border-2 transition-all ${
                      billingCycle === 'annual' 
                        ? 'border-nordic-green bg-nordic-green/5' 
                        : 'border-nordic-border bg-nordic-bg-primary'
                    }`}>
                      <div className="text-center mb-4">
                        {billingCycle === 'annual' ? (
                          <>
                            <div className="text-4xl font-bold text-nordic-text-primary">
                              $432<span className="text-lg font-normal text-nordic-text-muted">/year</span>
                            </div>
                            <div className="text-nordic-green text-sm mt-1">
                              $36/month · 2 months free
                            </div>
                          </>
                        ) : (
                          <div className="text-4xl font-bold text-nordic-text-primary">
                            $45<span className="text-lg font-normal text-nordic-text-muted">/month</span>
                          </div>
                        )}
                      </div>
                      
                      <Button
                        onClick={handleSubscribe}
                        disabled={subscribing || checkingPayment}
                        className="w-full bg-nordic-accent hover:bg-nordic-accent/90 text-white py-6 text-lg"
                        data-testid="subscribe-button"
                      >
                        {subscribing || checkingPayment ? (
                          <>
                            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                            {checkingPayment ? 'Verifying...' : 'Processing...'}
                          </>
                        ) : (
                          <>Get Started</>
                        )}
                      </Button>
                    </div>
                  </div>
                )}

                <div className="border-t border-nordic-border pt-6">
                  <h4 className="font-medium text-nordic-text-primary mb-4">What You Get</h4>
                  <ul className="space-y-3">
                    {[
                      { text: 'Turn messy ideas into PRD + stories in seconds', highlight: true },
                      { text: 'AI team estimates (5 personas, Fibonacci points)', highlight: true },
                      { text: 'Lean Canvas generation from your epic', highlight: false },
                      { text: 'Sprint planning with 2-sprint roadmap', highlight: false },
                      { text: 'Export to Jira / Azure DevOps', highlight: false },
                      { text: 'Unlimited epics, features & stories', highlight: false },
                    ].map((feature, i) => (
                      <li key={i} className="flex items-center gap-3 text-nordic-text-secondary">
                        <CheckCircle className={`w-4 h-4 flex-shrink-0 ${feature.highlight ? 'text-nordic-accent' : 'text-nordic-green'}`} />
                        <span className={feature.highlight ? 'font-medium text-nordic-text-primary' : ''}>
                          {feature.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-nordic-text-muted mt-4">
                    Save 2-4 hours per epic. One initiative pays for itself.
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* LLM Provider Tab */}
          <TabsContent value="llm" data-testid="llm-tab">
            <Card className="bg-nordic-bg-secondary border-nordic-border">
              <CardHeader>
                <CardTitle className="text-nordic-text-primary flex items-center gap-2">
                  <Key className="w-5 h-5 text-nordic-accent" />
                  LLM Provider Configuration
                </CardTitle>
                <CardDescription className="text-nordic-text-muted">
                  Configure your AI provider. Your API key is encrypted and stored securely.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Configured Providers */}
                {providers.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="font-medium text-nordic-text-primary">Configured Providers</h4>
                    {providers.map((p) => (
                      <div 
                        key={p.config_id}
                        className="flex items-center justify-between p-4 bg-nordic-bg-primary rounded-lg border border-nordic-border"
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${p.is_active ? 'bg-nordic-green' : 'bg-nordic-text-muted/30'}`} />
                          <div>
                            <span className="font-medium text-nordic-text-primary capitalize">{p.provider}</span>
                            {p.model_name && (
                              <span className="text-nordic-text-muted text-sm ml-2">({p.model_name})</span>
                            )}
                          </div>
                          {p.is_active && (
                            <Badge className="bg-nordic-accent/20 text-nordic-accent border-nordic-accent/30">
                              Active
                            </Badge>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteProvider(p.config_id)}
                          className="text-nordic-text-muted hover:text-nordic-red"
                          data-testid={`delete-provider-${p.config_id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add New Provider */}
                <div className="space-y-4 pt-4 border-t border-nordic-border">
                  <h4 className="font-medium text-nordic-text-primary">Add Provider</h4>
                  
                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary">Provider</Label>
                    <Select value={provider} onValueChange={setProvider}>
                      <SelectTrigger className="bg-background border-border text-foreground" data-testid="select-provider">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-popover border-border shadow-lg">
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                        <SelectItem value="local">Local / Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary">API Key</Label>
                    <Input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={provider === 'openai' ? 'sk-...' : provider === 'anthropic' ? 'sk-ant-...' : 'Enter API key'}
                      className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                      data-testid="input-api-key"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="text-nordic-text-secondary">Model Name (optional)</Label>
                    <Input
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      placeholder={provider === 'openai' ? 'gpt-4o' : provider === 'anthropic' ? 'claude-sonnet-4-20250514' : 'model-name'}
                      className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                      data-testid="input-model-name"
                    />
                  </div>

                  {provider === 'local' && (
                    <div className="space-y-2">
                      <Label className="text-nordic-text-secondary">Base URL</Label>
                      <Input
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder="http://localhost:11434/v1"
                        className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                        data-testid="input-base-url"
                      />
                    </div>
                  )}

                  {keyError && (
                    <div className="flex items-center gap-2 text-nordic-red text-sm">
                      <AlertCircle className="w-4 h-4" />
                      {keyError}
                    </div>
                  )}

                  <Button
                    onClick={handleSaveProvider}
                    disabled={savingKey || !apiKey.trim()}
                    className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                    data-testid="save-provider-button"
                  >
                    {savingKey ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Validating & Saving...
                      </>
                    ) : (
                      'Save Provider'
                    )}
                  </Button>
                </div>

                {/* Help Links */}
                <div className="bg-nordic-bg-primary border border-nordic-border rounded-lg p-4 mt-4">
                  <h4 className="text-sm font-medium text-nordic-text-primary mb-3">Get API Keys</h4>
                  <div className="space-y-2">
                    <a 
                      href="https://platform.openai.com/api-keys" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-nordic-accent hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                      OpenAI API Keys
                    </a>
                    <a 
                      href="https://console.anthropic.com/settings/keys" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-nordic-accent hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Anthropic API Keys
                    </a>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Appearance Tab */}
          <TabsContent value="appearance" data-testid="appearance-tab">
            <Card className="bg-nordic-bg-secondary border-nordic-border">
              <CardHeader>
                <CardTitle className="text-nordic-text-primary flex items-center gap-2">
                  <Palette className="w-5 h-5 text-nordic-accent" />
                  Appearance
                </CardTitle>
                <CardDescription className="text-nordic-text-muted">
                  Customize the visual appearance of JarlPM
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Label className="text-nordic-text-secondary">Theme</Label>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => setTheme('light')}
                      className={`p-4 rounded-lg border-2 transition-all flex flex-col items-center gap-2 ${
                        theme === 'light'
                          ? 'border-nordic-accent bg-nordic-accent/10'
                          : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
                      }`}
                      data-testid="theme-light"
                    >
                      <Sun className="w-6 h-6 text-nordic-text-primary" />
                      <span className="text-sm text-nordic-text-secondary">Light</span>
                    </button>
                    <button
                      onClick={() => setTheme('dark')}
                      className={`p-4 rounded-lg border-2 transition-all flex flex-col items-center gap-2 ${
                        theme === 'dark'
                          ? 'border-nordic-accent bg-nordic-accent/10'
                          : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
                      }`}
                      data-testid="theme-dark"
                    >
                      <Moon className="w-6 h-6 text-nordic-text-primary" />
                      <span className="text-sm text-nordic-text-secondary">Dark</span>
                    </button>
                    <button
                      onClick={() => setTheme('system')}
                      className={`p-4 rounded-lg border-2 transition-all flex flex-col items-center gap-2 ${
                        theme === 'system'
                          ? 'border-nordic-accent bg-nordic-accent/10'
                          : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
                      }`}
                      data-testid="theme-system"
                    >
                      <Monitor className="w-6 h-6 text-nordic-text-primary" />
                      <span className="text-sm text-nordic-text-secondary">System</span>
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Integrations Tab */}
          <TabsContent value="integrations" data-testid="integrations-tab">
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
                <div className="border border-nordic-border rounded-lg overflow-hidden">
                  <div className="p-4 bg-nordic-bg-primary border-b border-nordic-border">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-[#5E6AD2] flex items-center justify-center">
                          <svg viewBox="0 0 100 100" className="w-6 h-6 text-white" fill="currentColor">
                            <path d="M1.22541 61.5228c-.2225-.9485.90748-1.5459 1.59638-.857L39.3342 97.1782c.6889.6889.0915 1.8189-.857 1.5765C20.8 94.1102 5.95513 79.2002 1.22541 61.5228ZM.0222626 45.9876C-.077182 46.6422.387617 47.2239 1.04521 47.3005c16.9076 1.9666 31.9987 11.4328 41.0064 25.1052 1.0186 1.5445 3.302.8691 3.3451-.9911.0423-1.8237.0638-3.6541.0638-5.4903 0-36.8177-29.8487-66.6665-66.66657-66.6665-1.83593 0-3.66607.02185-5.49023.0645-1.86018.04289-2.53569 2.32647-.99128 3.34495C86.3328 12.9984 95.799 28.0895 97.7657 45.0064c.0766.6576.6583 1.1224 1.3129 1.0228 36.3254-5.5188 64.2133-35.9725 64.6528-73.2026.0024-.2045-.1662-.3716-.3707-.3692C28.9325 76.4257 0 47.4911.0222626 45.9876Z"/>
                          </svg>
                        </div>
                        <div>
                          <h3 className="font-semibold text-nordic-text-primary">Linear</h3>
                          <p className="text-sm text-nordic-text-muted">Push issues to Linear workspaces</p>
                        </div>
                      </div>
                      <Badge
                        className={
                          integrations?.linear?.status === 'connected'
                            ? 'bg-nordic-green text-white'
                            : integrations?.linear?.configured
                            ? 'bg-nordic-bg-primary text-nordic-text-muted border border-nordic-border'
                            : 'bg-amber-500/20 text-amber-500 border border-amber-500/30'
                        }
                      >
                        {integrations?.linear?.status === 'connected'
                          ? 'Connected'
                          : integrations?.linear?.configured
                          ? 'Not Connected'
                          : 'Not Configured'}
                      </Badge>
                    </div>
                  </div>
                  
                  <div className="p-4 space-y-4">
                    {integrations?.linear?.status === 'connected' ? (
                      <>
                        {/* Connected State */}
                        <div className="flex items-center gap-2 text-sm text-nordic-text-secondary">
                          <CheckCircle className="w-4 h-4 text-nordic-green" />
                          Connected to: <span className="font-medium text-nordic-text-primary">{integrations.linear.account_name || 'Linear Workspace'}</span>
                        </div>
                        
                        {integrations.linear.default_team && (
                          <div className="text-sm text-nordic-text-secondary">
                            Default team: <span className="font-medium text-nordic-text-primary">{integrations.linear.default_team.name}</span>
                          </div>
                        )}
                        
                        {/* Team Selection */}
                        {!integrations.linear.default_team && linearTeams.length > 0 && (
                          <div className="space-y-3 p-3 bg-nordic-bg-primary rounded-lg border border-nordic-border">
                            <Label className="text-nordic-text-secondary">Select Default Team</Label>
                            <Select value={selectedTeam} onValueChange={setSelectedTeam}>
                              <SelectTrigger className="bg-background border-border text-foreground">
                                <SelectValue placeholder="Choose a team" />
                              </SelectTrigger>
                              <SelectContent className="bg-popover border-border shadow-lg">
                                {linearTeams.map((team) => (
                                  <SelectItem key={team.id} value={team.id}>
                                    {team.name} ({team.key})
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <Button
                              onClick={handleConfigureLinear}
                              disabled={!selectedTeam || configuringLinear}
                              size="sm"
                              className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                            >
                              {configuringLinear ? (
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
                          onClick={handleDisconnectLinear}
                          disabled={disconnectingLinear}
                          variant="outline"
                          className="border-red-500 text-red-500 hover:bg-red-500/10"
                          data-testid="disconnect-linear-btn"
                        >
                          {disconnectingLinear ? (
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
                    ) : integrations?.linear?.configured ? (
                      <>
                        {/* Not Connected State */}
                        <p className="text-sm text-nordic-text-muted">
                          Click Connect to authorize JarlPM to access your Linear workspace.
                        </p>
                        <Button
                          onClick={handleConnectLinear}
                          disabled={connectingLinear || !isActive}
                          className="bg-[#5E6AD2] hover:bg-[#5E6AD2]/90 text-white"
                          data-testid="connect-linear-btn"
                        >
                          {connectingLinear ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Connecting...
                            </>
                          ) : (
                            <>
                              <Link2 className="w-4 h-4 mr-2" />
                              Connect to Linear
                            </>
                          )}
                        </Button>
                      </>
                    ) : (
                      <>
                        {/* Not Configured State */}
                        <div className="flex items-center gap-2 text-sm text-amber-500">
                          <AlertCircle className="w-4 h-4" />
                          OAuth credentials not configured on server
                        </div>
                        <p className="text-xs text-nordic-text-muted">
                          Contact your administrator to set up LINEAR_OAUTH_CLIENT_ID, LINEAR_OAUTH_CLIENT_SECRET, and LINEAR_OAUTH_REDIRECT_URI environment variables.
                        </p>
                      </>
                    )}
                  </div>
                </div>

                {/* Jira Integration (Coming Soon) */}
                <div className="border border-nordic-border rounded-lg overflow-hidden opacity-60">
                  <div className="p-4 bg-nordic-bg-primary border-b border-nordic-border">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-[#0052CC] flex items-center justify-center">
                          <svg viewBox="0 0 32 32" className="w-6 h-6 text-white" fill="currentColor">
                            <path d="M15.967 0c-.278.017-4.935 4.785-4.935 4.785l4.394 4.392 5.118-5.118L15.967 0z"/>
                            <path d="M11.567 4.785L6.449 9.903l4.395 4.394 5.118-5.12-4.395-4.392z"/>
                            <path d="M6.449 9.903L.608 15.744 6.449 21.586l4.395-4.395 5.12-5.118-4.395-4.394-5.12 5.118z" opacity=".6"/>
                            <path d="M6.449 21.586l4.395 4.392 5.118-5.118-4.395-4.395-5.118 5.12z"/>
                            <path d="M15.967 26.17l4.577 4.577 5.118-5.12-4.395-4.392-5.3 4.935z"/>
                          </svg>
                        </div>
                        <div>
                          <h3 className="font-semibold text-nordic-text-primary">Jira</h3>
                          <p className="text-sm text-nordic-text-muted">Push issues to Jira projects</p>
                        </div>
                      </div>
                      <Badge className="bg-nordic-bg-primary text-nordic-text-muted border border-nordic-border">
                        Coming Soon
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Azure DevOps Integration (Coming Soon) */}
                <div className="border border-nordic-border rounded-lg overflow-hidden opacity-60">
                  <div className="p-4 bg-nordic-bg-primary border-b border-nordic-border">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-[#0078D7] flex items-center justify-center">
                          <svg viewBox="0 0 24 24" className="w-6 h-6 text-white" fill="currentColor">
                            <path d="M0 8.877L2.247 5.91l8.405-3.416V.022l7.37 5.393L2.966 8.338v8.225L0 15.707zm24-4.45v15.15l-7.37 5.393-9.96-5.015V15.33l9.96 4.89 7.37-5.015v-10.78z"/>
                          </svg>
                        </div>
                        <div>
                          <h3 className="font-semibold text-nordic-text-primary">Azure DevOps</h3>
                          <p className="text-sm text-nordic-text-muted">Push work items to Azure DevOps</p>
                        </div>
                      </div>
                      <Badge className="bg-nordic-bg-primary text-nordic-text-muted border border-nordic-border">
                        Coming Soon
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Info Box */}
                <div className="bg-nordic-bg-primary border border-nordic-border rounded-lg p-4">
                  <h4 className="text-sm font-medium text-nordic-text-primary mb-2">How Integrations Work</h4>
                  <ul className="text-xs text-nordic-text-muted space-y-1">
                    <li>• Connect once, push anytime from any epic</li>
                    <li>• Idempotent: re-pushing updates existing items, doesn&apos;t create duplicates</li>
                    <li>• Choose scope: Epic only, Epic + Features, or Full hierarchy</li>
                    <li>• Preview changes before pushing</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Settings;
