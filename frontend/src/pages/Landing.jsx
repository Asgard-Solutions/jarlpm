import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import ThemeToggle from '@/components/ThemeToggle';
import { useAuthStore } from '@/store';
import { 
  Layers, Zap, Shield, Users, ArrowRight, 
  CheckCircle2, Brain, Lock, RefreshCw, Loader2, FlaskConical
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const Landing = () => {
  const navigate = useNavigate();
  const { setUser } = useAuthStore();
  const [testLoading, setTestLoading] = useState(false);

  const handleGetStarted = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const handleTestLogin = async () => {
    setTestLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/auth/test-login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        const data = await response.json();
        setUser({
          user_id: data.user_id,
          email: data.email,
          name: data.name,
          picture: null
        });
        navigate('/dashboard');
      } else {
        console.error('Test login failed');
      }
    } catch (error) {
      console.error('Test login error:', error);
    } finally {
      setTestLoading(false);
    }
  };

  const features = [
    {
      icon: Brain,
      title: 'AI-Agnostic',
      description: 'Use OpenAI, Anthropic, or your own local LLM. Bring your own API keys.'
    },
    {
      icon: Layers,
      title: 'Epic-Centric',
      description: 'Everything revolves around Epics. Features, stories, and bugs flow naturally.'
    },
    {
      icon: Lock,
      title: 'Immutable Decisions',
      description: 'Confirmed decisions are locked. No accidental overwrites or scope creep.'
    },
    {
      icon: RefreshCw,
      title: 'Conversation-Driven',
      description: 'Natural dialogue to capture problems, outcomes, and acceptance criteria.'
    }
  ];

  const stages = [
    { name: 'Problem Capture', desc: 'Define the problem you\'re solving' },
    { name: 'Problem Confirmed', desc: 'Lock the problem statement', locked: true },
    { name: 'Outcome Capture', desc: 'Define success metrics' },
    { name: 'Outcome Confirmed', desc: 'Lock desired outcomes', locked: true },
    { name: 'Epic Draft', desc: 'Comprehensive epic with acceptance criteria' },
    { name: 'Epic Locked', desc: 'Implementation-ready, immutable', locked: true },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <Layers className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="text-xl font-bold text-foreground">JarlPM</span>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button 
                onClick={handleGetStarted}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
                data-testid="nav-get-started-btn"
              >
                Get Started
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <Badge variant="outline" className="mb-4 border-primary/30 text-primary">
            AI-Agnostic Product Management
          </Badge>
          <h1 className="text-5xl md:text-6xl font-bold text-foreground mb-6 leading-tight">
            Build Epics That
            <span className="text-primary"> Developers Love</span>
          </h1>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            JarlPM is a conversation-driven product management system. 
            Create clear, implementation-ready Epics with AI assistance — using any LLM you choose.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              onClick={handleGetStarted}
              className="bg-primary hover:bg-primary/90 text-primary-foreground text-lg px-8"
              data-testid="hero-get-started-btn"
            >
              Start Building <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button 
              size="lg" 
              variant="outline" 
              onClick={handleTestLogin}
              disabled={testLoading}
              className="border-primary/50 text-primary hover:bg-primary/10 text-lg px-8"
              data-testid="hero-test-login-btn"
            >
              {testLoading ? (
                <>
                  <Loader2 className="mr-2 w-5 h-5 animate-spin" />
                  Logging in...
                </>
              ) : (
                <>
                  <FlaskConical className="mr-2 w-5 h-5" />
                  Test Login
                </>
              )}
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-4">
            Use "Test Login" for instant access with full features enabled
          </p>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-foreground text-center mb-12">Why JarlPM?</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, i) => (
              <Card key={i} className="bg-card border-border hover:border-primary/30 transition-colors">
                <CardHeader>
                  <feature.icon className="w-10 h-10 text-primary mb-2" />
                  <CardTitle className="text-foreground">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Epic Lifecycle */}
      <section className="py-16 px-4 bg-muted/30">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-foreground text-center mb-4">The Epic Lifecycle</h2>
          <p className="text-muted-foreground text-center mb-12">
            A monotonic state machine. No going back. No scope creep.
          </p>
          <div className="space-y-4">
            {stages.map((stage, i) => (
              <div key={i} className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-lg
                  ${stage.locked 
                    ? 'bg-success/20 text-success border-2 border-success' 
                    : 'bg-primary/20 text-primary border-2 border-primary'}`}>
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">{stage.name}</span>
                    {stage.locked && (
                      <Badge variant="outline" className="border-success/50 text-success text-xs">
                        <Lock className="w-3 h-3 mr-1" /> Locked
                      </Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-sm">{stage.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-16 px-4">
        <div className="max-w-xl mx-auto">
          <Card className="bg-card border-primary/30">
            <CardHeader className="text-center">
              <CardTitle className="text-3xl text-foreground">$20<span className="text-lg font-normal text-muted-foreground">/month</span></CardTitle>
              <CardDescription className="text-muted-foreground">Everything you need to build great products</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                'Unlimited Epics',
                'Full conversation history',
                'Bring your own LLM keys',
                'Features, Stories & Bugs',
                'Immutable decision log',
                'Export capabilities',
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-success" />
                  <span className="text-foreground">{item}</span>
                </div>
              ))}
              <div className="pt-4 border-t border-border">
                <p className="text-sm text-muted-foreground text-center">
                  Note: LLM API costs are separate. You use your own keys.
                </p>
              </div>
              <Button 
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground mt-4" 
                size="lg"
                onClick={handleGetStarted}
                data-testid="pricing-get-started-btn"
              >
                Get Started
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 bg-primary rounded flex items-center justify-center">
              <Layers className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="text-sm text-muted-foreground">JarlPM</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2025 JarlPM. Build better products.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
