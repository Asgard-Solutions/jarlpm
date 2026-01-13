import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { subscriptionAPI, llmProviderAPI, authAPI } from '@/api';
import { useAuthStore, useSubscriptionStore, useLLMProviderStore } from '@/store';
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
  CheckCircle, AlertCircle, Trash2, ExternalLink 
} from 'lucide-react';

const Settings = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, logout } = useAuthStore();
  const { subscription, isActive, setSubscription } = useSubscriptionStore();
  const { providers, activeProvider, setProviders } = useLLMProviderStore();

  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [checkingPayment, setCheckingPayment] = useState(false);
  
  // LLM Provider form
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [keyError, setKeyError] = useState('');

  useEffect(() => {
    loadData();
    
    // Check for payment return
    const sessionId = searchParams.get('session_id');
    const paymentStatus = searchParams.get('payment');
    
    if (sessionId && paymentStatus === 'success') {
      pollPaymentStatus(sessionId);
    }
  }, [searchParams]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [subRes, provRes] = await Promise.all([
        subscriptionAPI.getStatus(),
        llmProviderAPI.list(),
      ]);
      setSubscription(subRes.data);
      setProviders(provRes.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    const maxAttempts = 10;
    const pollInterval = 2000;

    if (attempts >= maxAttempts) {
      setCheckingPayment(false);
      return;
    }

    setCheckingPayment(true);
    try {
      const response = await subscriptionAPI.getCheckoutStatus(sessionId);
      if (response.data.payment_status === 'paid') {
        // Reload subscription status
        const subRes = await subscriptionAPI.getStatus();
        setSubscription(subRes.data);
        setCheckingPayment(false);
        // Clear URL params
        navigate('/settings', { replace: true });
        return;
      }

      setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
    } catch (error) {
      console.error('Payment status check failed:', error);
      setCheckingPayment(false);
    }
  };

  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      const originUrl = window.location.origin;
      const response = await subscriptionAPI.createCheckout(originUrl);
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Failed to create checkout:', error);
      setSubscribing(false);
    }
  };

  const handleSaveApiKey = async () => {
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

      // Reload providers
      const provRes = await llmProviderAPI.list();
      setProviders(provRes.data);

      // Clear form
      setApiKey('');
      setModelName('');
      setBaseUrl('');
    } catch (error) {
      setKeyError(error.response?.data?.detail || 'Failed to save API key');
    } finally {
      setSavingKey(false);
    }
  };

  const handleDeleteProvider = async (configId) => {
    try {
      await llmProviderAPI.delete(configId);
      const provRes = await llmProviderAPI.list();
      setProviders(provRes.data);
    } catch (error) {
      console.error('Failed to delete provider:', error);
    }
  };

  const handleActivateProvider = async (configId) => {
    try {
      await llmProviderAPI.activate(configId);
      const provRes = await llmProviderAPI.list();
      setProviders(provRes.data);
    } catch (error) {
      console.error('Failed to activate provider:', error);
    }
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout();
      logout();
      navigate('/');
    } catch (error) {
      logout();
      navigate('/');
    }
  };

  const defaultModels = {
    openai: 'gpt-4o',
    anthropic: 'claude-sonnet-4-20250514',
    local: 'default',
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16 gap-4">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => navigate('/dashboard')}
              data-testid="back-btn"
            >
              <ArrowLeft className="w-5 h-5 text-slate-400" />
            </Button>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Layers className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">Settings</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {checkingPayment && (
          <Card className="bg-indigo-500/10 border-indigo-500/50 mb-6">
            <CardContent className="flex items-center gap-4 py-4">
              <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
              <div>
                <p className="text-indigo-200 font-medium">Processing Payment</p>
                <p className="text-indigo-300/70 text-sm">Please wait while we confirm your subscription...</p>
              </div>
            </CardContent>
          </Card>
        )}

        <Tabs defaultValue="subscription" className="space-y-6">
          <TabsList className="bg-slate-900 border border-slate-800">
            <TabsTrigger value="subscription" className="data-[state=active]:bg-slate-800">
              <CreditCard className="w-4 h-4 mr-2" /> Subscription
            </TabsTrigger>
            <TabsTrigger value="llm" className="data-[state=active]:bg-slate-800">
              <Key className="w-4 h-4 mr-2" /> LLM Providers
            </TabsTrigger>
          </TabsList>

          {/* Subscription Tab */}
          <TabsContent value="subscription">
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <CreditCard className="w-5 h-5" /> Subscription
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Manage your JarlPM subscription
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg">
                  <div>
                    <p className="text-white font-medium">Current Status</p>
                    <p className="text-slate-400 text-sm">$20/month for full access</p>
                  </div>
                  <Badge 
                    variant="outline" 
                    className={isActive 
                      ? 'border-emerald-500 text-emerald-400' 
                      : 'border-red-500 text-red-400'
                    }
                  >
                    {isActive ? (
                      <><CheckCircle className="w-4 h-4 mr-1" /> Active</>
                    ) : (
                      <><AlertCircle className="w-4 h-4 mr-1" /> Inactive</>
                    )}
                  </Badge>
                </div>

                {!isActive && (
                  <div className="space-y-4">
                    <div className="text-sm text-slate-400">
                      <p className="mb-2">Your subscription includes:</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Unlimited Epics</li>
                        <li>Full conversation history</li>
                        <li>Immutable decision log</li>
                        <li>Features, Stories & Bugs tracking</li>
                      </ul>
                    </div>
                    <Button 
                      onClick={handleSubscribe}
                      disabled={subscribing}
                      className="w-full bg-indigo-600 hover:bg-indigo-700"
                      data-testid="subscribe-btn"
                    >
                      {subscribing ? (
                        <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Redirecting...</>
                      ) : (
                        <><CreditCard className="w-4 h-4 mr-2" /> Subscribe for $20/month</>
                      )}
                    </Button>
                  </div>
                )}

                {isActive && subscription?.current_period_end && (
                  <p className="text-sm text-slate-500">
                    Next billing date: {new Date(subscription.current_period_end).toLocaleDateString()}
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* LLM Providers Tab */}
          <TabsContent value="llm">
            <div className="space-y-6">
              {/* Existing Providers */}
              {providers.length > 0 && (
                <Card className="bg-slate-900/50 border-slate-800">
                  <CardHeader>
                    <CardTitle className="text-white">Your LLM Providers</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {providers.map((prov) => (
                      <div 
                        key={prov.config_id}
                        className={`flex items-center justify-between p-4 rounded-lg border transition-colors ${
                          prov.is_active 
                            ? 'bg-indigo-500/10 border-indigo-500/50' 
                            : 'bg-slate-800/50 border-slate-700'
                        }`}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-white font-medium capitalize">{prov.provider}</span>
                            {prov.is_active && (
                              <Badge className="bg-indigo-500/20 text-indigo-400 border-indigo-500">
                                Active
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-slate-400">
                            Model: {prov.model_name || defaultModels[prov.provider]}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {!prov.is_active && (
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handleActivateProvider(prov.config_id)}
                              className="border-slate-700 text-slate-300"
                            >
                              Activate
                            </Button>
                          )}
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => handleDeleteProvider(prov.config_id)}
                            data-testid={`delete-provider-${prov.config_id}`}
                          >
                            <Trash2 className="w-4 h-4 text-red-400" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Add New Provider */}
              <Card className="bg-slate-900/50 border-slate-800">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Key className="w-5 h-5" /> Add LLM Provider
                  </CardTitle>
                  <CardDescription className="text-slate-400">
                    Add your own API key to use AI features. Keys are encrypted.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-slate-300">Provider</Label>
                    <Select value={provider} onValueChange={setProvider}>
                      <SelectTrigger className="bg-slate-800 border-slate-700 text-white" data-testid="provider-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-800 border-slate-700">
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                        <SelectItem value="local">Local (HTTP)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-slate-300">API Key</Label>
                    <Input
                      type="password"
                      placeholder={provider === 'openai' ? 'sk-...' : provider === 'anthropic' ? 'sk-ant-...' : 'Your API key'}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="bg-slate-800 border-slate-700 text-white"
                      data-testid="api-key-input"
                    />
                  </div>

                  {provider === 'local' && (
                    <div className="space-y-2">
                      <Label className="text-slate-300">Base URL</Label>
                      <Input
                        placeholder="http://localhost:1234"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        className="bg-slate-800 border-slate-700 text-white"
                      />
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label className="text-slate-300">Model (optional)</Label>
                    <Input
                      placeholder={defaultModels[provider]}
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      className="bg-slate-800 border-slate-700 text-white"
                    />
                    <p className="text-xs text-slate-500">
                      Leave blank to use default: {defaultModels[provider]}
                    </p>
                  </div>

                  {keyError && (
                    <p className="text-sm text-red-400 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4" /> {keyError}
                    </p>
                  )}

                  <Button 
                    onClick={handleSaveApiKey}
                    disabled={savingKey || !apiKey.trim()}
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                    data-testid="save-api-key-btn"
                  >
                    {savingKey ? (
                      <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Validating...</>
                    ) : (
                      <><Key className="w-4 h-4 mr-2" /> Save API Key</>
                    )}
                  </Button>

                  <div className="pt-4 border-t border-slate-800">
                    <p className="text-xs text-slate-500 mb-2">Get your API keys:</p>
                    <div className="flex flex-wrap gap-2">
                      <a 
                        href="https://platform.openai.com/api-keys" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                      >
                        OpenAI <ExternalLink className="w-3 h-3" />
                      </a>
                      <a 
                        href="https://console.anthropic.com/" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                      >
                        Anthropic <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>

        {/* Account Section */}
        <Card className="bg-slate-900/50 border-slate-800 mt-6">
          <CardHeader>
            <CardTitle className="text-white">Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white font-medium">{user?.name}</p>
                <p className="text-slate-400 text-sm">{user?.email}</p>
              </div>
              <Button 
                variant="outline" 
                onClick={handleLogout}
                className="border-red-500/50 text-red-400 hover:bg-red-500/20"
                data-testid="logout-settings-btn"
              >
                Log Out
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default Settings;
