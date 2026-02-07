import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import ThemeToggle from '@/components/ThemeToggle';
import ExampleOutputModal from '@/components/ExampleOutputModal';
import { useAuthStore, useThemeStore } from '@/store';
import { 
  ArrowRight, 
  CheckCircle2, 
  Brain, 
  Lock, 
  MessageSquare, 
  Layers,
  FileText,
  ListChecks,
  Send,
  Eye,
  LayoutDashboard,
} from 'lucide-react';
import {
  trackLandingPageView,
  trackGenerateInitiativeClick,
  trackSeeExampleClick,
  trackSignInClick,
  trackGetStartedClick,
} from '@/utils/analytics';

const Landing = () => {
  const navigate = useNavigate();
  const { theme } = useThemeStore();
  const { user } = useAuthStore();
  const [showExampleModal, setShowExampleModal] = useState(false);

  // Track landing page view on mount
  useEffect(() => {
    trackLandingPageView();
  }, []);

  // Select logo based on theme
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  const handleGetStarted = (location = 'nav') => {
    trackGetStartedClick(location);
    navigate('/signup');
  };

  const handleGenerateInitiative = (location = 'hero') => {
    trackGenerateInitiativeClick(!!user, location);
    if (user) {
      navigate('/new');
      return;
    }
    navigate('/signup?next=/new');
  };

  const handleSignIn = (location = 'nav') => {
    trackSignInClick(location);
    navigate('/login?next=/new');
  };

  const handleSeeExample = () => {
    trackSeeExampleClick();
    setShowExampleModal(true);
  };

  const handleGoToDashboard = () => {
    navigate('/dashboard');
  };

  // 3-step workflow cards
  const workflowSteps = [
    {
      step: 1,
      icon: FileText,
      title: 'Define problem + metrics',
      description: 'Structured PRD with personas, success metrics, assumptions, and validation plan',
      tag: 'PRD',
    },
    {
      step: 2,
      icon: ListChecks,
      title: 'Generate buildable stories',
      description: 'Acceptance criteria, edge cases, instrumentation, and engineering notes',
      tag: 'Stories',
    },
    {
      step: 3,
      icon: Send,
      title: 'Plan + push to tools',
      description: 'Capacity-aware sprint plan → Jira, Linear, or Azure DevOps',
      tag: 'Execute',
    },
  ];

  // Integration logos (using simple text badges for now)
  const integrations = [
    { name: 'Jira', color: 'bg-blue-500' },
    { name: 'Linear', color: 'bg-purple-500' },
    { name: 'Azure DevOps', color: 'bg-sky-500' },
  ];

  const features = [
    {
      icon: Brain,
      title: 'AI-Agnostic',
      description: 'Use OpenAI, Anthropic, or your own local LLM. You control the intelligence. JarlPM controls the process.'
    },
    {
      icon: Layers,
      title: 'Epic-Centric',
      description: 'Every workflow revolves around the Epic — from problem definition to implementation-ready scope.'
    },
    {
      icon: Lock,
      title: 'Immutable Decisions',
      description: 'Once confirmed, decisions are locked. No accidental rewrites. No silent scope creep.'
    },
    {
      icon: MessageSquare,
      title: 'Conversation-Driven',
      description: 'Structured dialogue designed to surface clarity, not noise.'
    }
  ];

  const stages = [
    { name: 'Problem Capture', desc: "Define the problem you're solving" },
    { name: 'Problem Confirmed', desc: 'Lock the problem statement', locked: true },
    { name: 'Outcome Capture', desc: 'Define success metrics' },
    { name: 'Outcome Confirmed', desc: 'Lock desired outcomes', locked: true },
    { name: 'Epic Draft', desc: 'Comprehensive epic with acceptance criteria' },
    { name: 'Epic Locked', desc: 'Implementation-ready, immutable', locked: true },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Welcome Back Banner for Logged-in Users */}
      {user && (
        <div className="bg-primary/10 border-b border-primary/20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center justify-between">
            <p className="text-sm text-foreground">
              Welcome back, <span className="font-medium">{user.name || user.email}</span>
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={handleGoToDashboard}
              className="gap-2"
              data-testid="welcome-back-dashboard-btn"
            >
              <LayoutDashboard className="w-4 h-4" />
              Go to Dashboard
            </Button>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <img 
                src={logoSrc} 
                alt="JarlPM" 
                className="h-9 w-auto"
              />
              <span className="text-xl font-bold text-foreground">JarlPM</span>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              {!user && (
                <>
                  <Button 
                    variant="ghost"
                    onClick={() => handleSignIn('nav')}
                    className="text-muted-foreground hover:text-foreground"
                    data-testid="nav-signin-btn"
                  >
                    Sign in
                  </Button>
                  <Button 
                    onClick={() => handleGetStarted('nav')}
                    className="bg-primary hover:bg-primary/90 text-primary-foreground"
                    data-testid="nav-get-started-btn"
                  >
                    Get Started
                  </Button>
                </>
              )}
              {user && (
                <Button 
                  onClick={handleGoToDashboard}
                  className="bg-primary hover:bg-primary/90 text-primary-foreground"
                  data-testid="nav-dashboard-btn"
                >
                  Dashboard
                </Button>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-16 md:py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <Badge variant="outline" className="mb-4 border-primary/30 text-primary">
            AI-Agnostic Product Management
          </Badge>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-foreground mb-6 leading-tight">
            Ship like you have a
            <span className="text-primary"> Senior PM</span>
          </h1>
          <p className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Turn a messy idea into a PRD, buildable stories, and a 2‑sprint plan — then push to Jira, Linear, or Azure DevOps.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button 
              size="lg" 
              onClick={() => handleGenerateInitiative('hero')}
              className="bg-primary hover:bg-primary/90 text-primary-foreground text-lg px-8"
              data-testid="hero-generate-initiative-btn"
            >
              Generate an Initiative <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={handleSeeExample}
              className="text-lg px-8"
              data-testid="hero-see-example-btn"
            >
              <Eye className="mr-2 w-5 h-5" />
              See Example Output
            </Button>
          </div>

          <p className="text-sm text-muted-foreground mt-4">
            {user ? 'Welcome back — jump straight into your workspace.' : '$45/month · Bring your own LLM keys'}
          </p>
        </div>
      </section>

      {/* 3-Step Workflow */}
      <section className="py-12 px-4 bg-muted/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-foreground text-center mb-8">
            From idea to sprint-ready in 3 steps
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {workflowSteps.map((step) => (
              <Card key={step.step} className="bg-card border-border hover:border-primary/30 transition-colors relative">
                <div className="absolute -top-3 left-4">
                  <Badge className="bg-primary text-primary-foreground px-3 py-1">
                    Step {step.step}
                  </Badge>
                </div>
                <CardHeader className="pt-8 pb-2">
                  <step.icon className="w-10 h-10 text-primary mb-2" />
                  <CardTitle className="text-lg text-foreground">{step.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Integrations Row */}
      <section className="py-12 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-xl font-semibold text-foreground mb-4">
            Push directly to your tools
          </h2>
          <p className="text-muted-foreground mb-6">
            Create or update — no duplicates. Your existing workflow stays intact.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            {integrations.map((integration) => (
              <div
                key={integration.name}
                className="flex items-center gap-2 px-4 py-2 rounded-full border border-border bg-card"
              >
                <div className={`w-3 h-3 rounded-full ${integration.color}`} />
                <span className="font-medium text-foreground">{integration.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-12 px-4 bg-muted/30">
        <div className="max-w-6xl mx-auto">
          <p className="text-muted-foreground text-center mb-4 max-w-2xl mx-auto">
            Good products start with clear decisions. Great products don&apos;t revisit them.
          </p>
          <h2 className="text-2xl md:text-3xl font-bold text-foreground text-center mb-10">Why JarlPM?</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, i) => (
              <Card key={i} className="bg-card border-border hover:border-primary/30 transition-colors">
                <CardHeader>
                  <feature.icon className="w-10 h-10 text-primary mb-2" />
                  <CardTitle className="text-foreground">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground text-sm">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Epic Lifecycle - Lower Priority */}
      <section className="py-12 px-4">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-foreground text-center mb-4">The Epic Lifecycle</h2>
          <p className="text-muted-foreground text-center mb-10 text-sm">
            A monotonic decision lifecycle. No going back. No scope creep.
          </p>
          <div className="space-y-3">
            {stages.map((stage, i) => (
              <div key={i} className="flex items-center gap-4">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm
                  ${stage.locked 
                    ? 'bg-green-500/20 text-green-600 border-2 border-green-500' 
                    : 'bg-primary/20 text-primary border-2 border-primary'}`}>
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground text-sm">{stage.name}</span>
                    {stage.locked && (
                      <Badge variant="outline" className="border-green-500/50 text-green-600 text-xs py-0">
                        <Lock className="w-3 h-3 mr-1" /> Locked
                      </Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-xs">{stage.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground/70 italic text-center mt-6">
            A Jarl does not reopen settled decisions.
          </p>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-12 px-4 bg-muted/30">
        <div className="max-w-xl mx-auto">
          <p className="text-muted-foreground text-center mb-6 text-sm">
            Simple pricing for serious product teams
          </p>
          <Card className="bg-card border-primary/30">
            <CardHeader className="text-center">
              <CardTitle className="text-3xl text-foreground">$45<span className="text-lg font-normal text-muted-foreground">/month</span></CardTitle>
              <CardDescription className="text-muted-foreground">Everything you need to build great products</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                'Unlimited Epics',
                'Full conversation history',
                'Bring your own LLM keys',
                'Features, Stories & Bugs',
                'Immutable decision log',
                'Export + Push to tools',
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  <span className="text-foreground text-sm">{item}</span>
                </div>
              ))}
              <div className="pt-3 border-t border-border">
                <p className="text-xs text-muted-foreground text-center">
                  LLM API costs are separate. You use your own keys.
                </p>
              </div>
              <Button 
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground mt-4" 
                size="lg"
                onClick={() => handleGenerateInitiative('pricing')}
                data-testid="pricing-get-started-btn"
              >
                Generate an Initiative <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center space-x-2">
            <img 
              src={logoSrc} 
              alt="JarlPM" 
              className="h-7 w-auto"
            />
            <span className="text-sm text-muted-foreground">JarlPM</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2026 JarlPM · Built by Asgard Solutions LLC
          </p>
        </div>
      </footer>

      {/* Example Output Modal */}
      <ExampleOutputModal 
        open={showExampleModal} 
        onOpenChange={setShowExampleModal}
      />
    </div>
  );
};

export default Landing;
