import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { subscriptionAPI, llmProviderAPI, authAPI } from '@/api';
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
  CheckCircle, AlertCircle, Trash2, ExternalLink, Palette, Sun, Moon, Monitor
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
  
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [keyError, setKeyError] = useState('');

  const loadData = useCallback(async () => {
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
  }, [setSubscription, setProviders]);

  const pollPaymentStatus = useCallback(async (sessionId, attempts = 0) => {
    const maxAttempts = 10;
    const pollInterval = 2000;
    if (attempts >= maxAttempts) { setCheckingPayment(false); return; }
    setCheckingPayment(true);
    try {
      const response = await subscriptionAPI.getCheckoutStatus(sessionId);
      if (response.data.payment_status === 'paid') {
        const subRes = await subscriptionAPI.getStatus();
        setSubscription(subRes.data);
        setCheckingPayment(false);
        navigate('/settings', { replace: true });
        return;
      }
      setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
    } catch (error) { setCheckingPayment(false); }
  }, [navigate, setSubscription]);

  useEffect(() => {
    loadData();
    const sessionId = searchParams.get('session_id');
    const paymentStatus = searchParams.get('payment');
    if (sessionId && paymentStatus === 'success') { pollPaymentStatus(sessionId); }
  }, [searchParams, loadData, pollPaymentStatus]);

  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      const response = await subscriptionAPI.createCheckout(window.location.origin);
      window.location.href = response.data.checkout_url;
    } catch (error) { setSubscribing(false); }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) { setKeyError('API key is required'); return; }
    setSavingKey(true); setKeyError('');
    try {
      await llmProviderAPI.create({ provider, api_key: apiKey, model_name: modelName || undefined, base_url: provider === 'local' ? baseUrl : undefined });
      const provRes = await llmProviderAPI.list();
      setProviders(provRes.data);
      setApiKey(''); setModelName(''); setBaseUrl('');
    } catch (error) { setKeyError(error.response?.data?.detail || 'Failed to save API key'); }
    finally { setSavingKey(false); }
  };

  const handleDeleteProvider = async (configId) => {
    try { await llmProviderAPI.delete(configId); const provRes = await llmProviderAPI.list(); setProviders(provRes.data); } catch (error) { console.error('Delete provider failed:', error); }
  };

  const handleActivateProvider = async (configId) => {
    try { await llmProviderAPI.activate(configId); const provRes = await llmProviderAPI.list(); setProviders(provRes.data); } catch (error) { console.error('Activate provider failed:', error); }
  };

  const handleLogout = async () => { try { await authAPI.logout(); } catch (error) { console.error('Logout failed:', error); } logout(); navigate('/'); };

  const defaultModels = { openai: 'gpt-4o', anthropic: 'claude-sonnet-4-20250514', local: 'default' };

  if (loading) {
    return (<div className="min-h-screen bg-background flex items-center justify-center"><Loader2 className="w-8 h-8 text-primary animate-spin" /></div>);
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16 gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="text-muted-foreground hover:text-foreground" data-testid="back-btn"><ArrowLeft className="w-5 h-5" /></Button>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center"><Layers className="w-5 h-5 text-primary-foreground" /></div>
              <span className="text-xl font-bold text-foreground">Settings</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {checkingPayment && (<Card className="bg-primary/10 border-primary/30 mb-6"><CardContent className="flex items-center gap-4 py-4"><Loader2 className="w-6 h-6 text-primary animate-spin" /><div><p className="text-foreground font-medium">Processing Payment</p><p className="text-muted-foreground text-sm">Please wait...</p></div></CardContent></Card>)}

        <Tabs defaultValue="subscription" className="space-y-6">
          <TabsList className="bg-muted border border-border">
            <TabsTrigger value="subscription" className="data-[state=active]:bg-background"><CreditCard className="w-4 h-4 mr-2" /> Subscription</TabsTrigger>
            <TabsTrigger value="llm" className="data-[state=active]:bg-background"><Key className="w-4 h-4 mr-2" /> LLM Providers</TabsTrigger>
            <TabsTrigger value="appearance" className="data-[state=active]:bg-background"><Palette className="w-4 h-4 mr-2" /> Appearance</TabsTrigger>
          </TabsList>

          <TabsContent value="subscription">
            <Card className="bg-card border-border">
              <CardHeader><CardTitle className="text-foreground flex items-center gap-2"><CreditCard className="w-5 h-5" /> Subscription</CardTitle><CardDescription className="text-muted-foreground">Manage your JarlPM subscription</CardDescription></CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                  <div><p className="text-foreground font-medium">Current Status</p><p className="text-muted-foreground text-sm">$20/month for full access</p></div>
                  <Badge variant="outline" className={isActive ? 'border-success text-success' : 'border-destructive text-destructive'}>{isActive ? (<><CheckCircle className="w-4 h-4 mr-1" /> Active</>) : (<><AlertCircle className="w-4 h-4 mr-1" /> Inactive</>)}</Badge>
                </div>
                {!isActive && (<div className="space-y-4"><div className="text-sm text-muted-foreground"><p className="mb-2">Your subscription includes:</p><ul className="list-disc list-inside space-y-1"><li>Unlimited Epics</li><li>Full conversation history</li><li>Immutable decision log</li><li>Features, Stories & Bugs tracking</li></ul></div><Button onClick={handleSubscribe} disabled={subscribing} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground" data-testid="subscribe-btn">{subscribing ? (<><Loader2 className="w-4 h-4 animate-spin mr-2" /> Redirecting...</>) : (<><CreditCard className="w-4 h-4 mr-2" /> Subscribe for $20/month</>)}</Button></div>)}
                {isActive && subscription?.current_period_end && (<p className="text-sm text-muted-foreground">Next billing date: {new Date(subscription.current_period_end).toLocaleDateString()}</p>)}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="llm">
            <div className="space-y-6">
              {providers.length > 0 && (<Card className="bg-card border-border"><CardHeader><CardTitle className="text-foreground">Your LLM Providers</CardTitle></CardHeader><CardContent className="space-y-3">{providers.map((prov) => (<div key={prov.config_id} className={`flex items-center justify-between p-4 rounded-lg border ${prov.is_active ? 'bg-primary/10 border-primary/30' : 'bg-muted/50 border-border'}`}><div><div className="flex items-center gap-2"><span className="text-foreground font-medium capitalize">{prov.provider}</span>{prov.is_active && (<Badge className="bg-primary/20 text-primary border-primary">Active</Badge>)}</div><p className="text-sm text-muted-foreground">Model: {prov.model_name || defaultModels[prov.provider]}</p></div><div className="flex items-center gap-2">{!prov.is_active && (<Button variant="outline" size="sm" onClick={() => handleActivateProvider(prov.config_id)} className="border-border text-foreground">Activate</Button>)}<Button variant="ghost" size="icon" onClick={() => handleDeleteProvider(prov.config_id)} data-testid={`delete-provider-${prov.config_id}`}><Trash2 className="w-4 h-4 text-destructive" /></Button></div></div>))}</CardContent></Card>)}
              <Card className="bg-card border-border">
                <CardHeader><CardTitle className="text-foreground flex items-center gap-2"><Key className="w-5 h-5" /> Add LLM Provider</CardTitle><CardDescription className="text-muted-foreground">Add your own API key to use AI features. Keys are encrypted.</CardDescription></CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2"><Label className="text-foreground">Provider</Label><Select value={provider} onValueChange={setProvider}><SelectTrigger className="bg-background border-border text-foreground" data-testid="provider-select"><SelectValue /></SelectTrigger><SelectContent className="bg-card border-border"><SelectItem value="openai">OpenAI</SelectItem><SelectItem value="anthropic">Anthropic</SelectItem><SelectItem value="local">Local (HTTP)</SelectItem></SelectContent></Select></div>
                  <div className="space-y-2"><Label className="text-foreground">API Key</Label><Input type="password" placeholder={provider === 'openai' ? 'sk-...' : provider === 'anthropic' ? 'sk-ant-...' : 'Your API key'} value={apiKey} onChange={(e) => setApiKey(e.target.value)} className="bg-background border-border text-foreground" data-testid="api-key-input" /></div>
                  {provider === 'local' && (<div className="space-y-2"><Label className="text-foreground">Base URL</Label><Input placeholder="http://localhost:1234" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className="bg-background border-border text-foreground" /></div>)}
                  <div className="space-y-2"><Label className="text-foreground">Model (optional)</Label><Input placeholder={defaultModels[provider]} value={modelName} onChange={(e) => setModelName(e.target.value)} className="bg-background border-border text-foreground" /><p className="text-xs text-muted-foreground">Leave blank to use default: {defaultModels[provider]}</p></div>
                  {keyError && (<p className="text-sm text-destructive flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {keyError}</p>)}
                  <Button onClick={handleSaveApiKey} disabled={savingKey || !apiKey.trim()} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground" data-testid="save-api-key-btn">{savingKey ? (<><Loader2 className="w-4 h-4 animate-spin mr-2" /> Validating...</>) : (<><Key className="w-4 h-4 mr-2" /> Save API Key</>)}</Button>
                  <div className="pt-4 border-t border-border"><p className="text-xs text-muted-foreground mb-2">Get your API keys:</p><div className="flex flex-wrap gap-2"><a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:text-primary/80 flex items-center gap-1">OpenAI <ExternalLink className="w-3 h-3" /></a><a href="https://console.anthropic.com/" target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:text-primary/80 flex items-center gap-1">Anthropic <ExternalLink className="w-3 h-3" /></a></div></div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="appearance">
            <Card className="bg-card border-border">
              <CardHeader><CardTitle className="text-foreground flex items-center gap-2"><Palette className="w-5 h-5" /> Appearance</CardTitle><CardDescription className="text-muted-foreground">Customize the look and feel of JarlPM</CardDescription></CardHeader>
              <CardContent className="space-y-6">
                <div><Label className="text-foreground mb-3 block">Theme</Label>
                  <div className="grid grid-cols-3 gap-3">
                    <Button variant={theme === 'light' ? 'default' : 'outline'} className={theme === 'light' ? 'bg-primary text-primary-foreground' : 'border-border text-foreground hover:bg-accent'} onClick={() => setTheme('light')}><Sun className="w-4 h-4 mr-2" /> Light</Button>
                    <Button variant={theme === 'dark' ? 'default' : 'outline'} className={theme === 'dark' ? 'bg-primary text-primary-foreground' : 'border-border text-foreground hover:bg-accent'} onClick={() => setTheme('dark')}><Moon className="w-4 h-4 mr-2" /> Dark</Button>
                    <Button variant={theme === 'system' ? 'default' : 'outline'} className={theme === 'system' ? 'bg-primary text-primary-foreground' : 'border-border text-foreground hover:bg-accent'} onClick={() => setTheme('system')}><Monitor className="w-4 h-4 mr-2" /> System</Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">Choose your preferred color scheme or follow system settings.</p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <Card className="bg-card border-border mt-6">
          <CardHeader><CardTitle className="text-foreground">Account</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div><p className="text-foreground font-medium">{user?.name}</p><p className="text-muted-foreground text-sm">{user?.email}</p></div>
              <Button variant="outline" onClick={handleLogout} className="border-destructive/50 text-destructive hover:bg-destructive/10" data-testid="logout-settings-btn">Log Out</Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default Settings;
