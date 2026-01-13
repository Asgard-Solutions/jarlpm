import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { subscriptionAPI, llmProviderAPI, authAPI, deliveryContextAPI } from '@/api';
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
import { 
  Layers, ArrowLeft, CreditCard, Key, Loader2, 
  CheckCircle, AlertCircle, Trash2, ExternalLink, Palette, Sun, Moon, Monitor,
  Briefcase, Users, Calendar
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
  });
  const [savingContext, setSavingContext] = useState(false);
  const [contextError, setContextError] = useState('');
  const [contextSuccess, setContextSuccess] = useState(false);

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
        });
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
      const res = await subscriptionAPI.createCheckout(window.location.origin);
      window.location.href = res.data.checkout_url;
    } catch (error) {
      console.error('Failed to create checkout:', error);
      setSubscribing(false);
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
      };
      
      await deliveryContextAPI.update(data);
      setContextSuccess(true);
      setTimeout(() => setContextSuccess(false), 3000);
    } catch (error) {
      setContextError(error.response?.data?.detail || 'Failed to save delivery context');
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

  if (loading) {
    return (
      <div className="min-h-screen bg-nordic-bg-primary flex items-center justify-center" data-testid="settings-loading">
        <Loader2 className="w-8 h-8 text-nordic-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-nordic-bg-primary">
      <header className="border-b border-nordic-border bg-nordic-bg-secondary/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => navigate('/dashboard')}
              className="text-nordic-text-muted hover:text-nordic-text-primary"
              data-testid="back-to-dashboard"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-nordic-text-secondary text-sm">{user?.email}</span>
            <Button variant="outline" onClick={handleLogout} data-testid="logout-button">
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-4xl" data-testid="settings-page">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold text-nordic-text-primary">Settings</h1>
          <p className="text-nordic-text-muted mt-2">
            Configure your account, subscription, and integrations
          </p>
        </div>

        <Tabs defaultValue="delivery" className="space-y-6">
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
                  Configure your team's delivery context. This information is automatically included in all AI prompts as read-only context.
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
                    <li>• Missing values are shown as "Not specified"</li>
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
                        {isActive ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                    <p className="text-nordic-text-muted text-sm">
                      {isActive 
                        ? `Your subscription is active until ${new Date(subscription.current_period_end).toLocaleDateString()}`
                        : 'Subscribe to unlock AI-powered features'
                      }
                    </p>
                  </div>
                  {!isActive && (
                    <Button
                      onClick={handleSubscribe}
                      disabled={subscribing || checkingPayment}
                      className="bg-nordic-accent hover:bg-nordic-accent/90 text-white"
                      data-testid="subscribe-button"
                    >
                      {subscribing || checkingPayment ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          {checkingPayment ? 'Verifying...' : 'Processing...'}
                        </>
                      ) : (
                        <>Subscribe - $20/month</>
                      )}
                    </Button>
                  )}
                </div>

                <div className="border-t border-nordic-border pt-6">
                  <h4 className="font-medium text-nordic-text-primary mb-4">Included Features</h4>
                  <ul className="space-y-3">
                    {[
                      'AI-powered Epic refinement',
                      'Problem statement analysis',
                      'Outcome definition assistance',
                      'User story generation',
                      'Acceptance criteria suggestions',
                    ].map((feature, i) => (
                      <li key={i} className="flex items-center gap-3 text-nordic-text-secondary">
                        <CheckCircle className="w-4 h-4 text-nordic-green flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
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
        </Tabs>
      </main>
    </div>
  );
};

export default Settings;
