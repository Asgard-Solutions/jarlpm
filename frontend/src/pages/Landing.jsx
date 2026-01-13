import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Layers, Zap, Shield, Users, ArrowRight, 
  CheckCircle2, Brain, Lock, RefreshCw 
} from 'lucide-react';

const Landing = () => {
  const navigate = useNavigate();

  const handleGetStarted = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
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
    <div className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900">
      {/* Navigation */}
      <nav className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Layers className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">JarlPM</span>
            </div>
            <Button 
              onClick={handleGetStarted}
              className="bg-indigo-600 hover:bg-indigo-700"
              data-testid="nav-get-started-btn"
            >
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <Badge variant="outline" className="mb-4 border-indigo-500/50 text-indigo-400">
            AI-Agnostic Product Management
          </Badge>
          <h1 className="text-5xl md:text-6xl font-bold text-white mb-6 leading-tight">
            Build Epics That
            <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent"> Developers Love</span>
          </h1>
          <p className="text-xl text-slate-400 mb-8 max-w-2xl mx-auto">
            JarlPM is a conversation-driven product management system. 
            Create clear, implementation-ready Epics with AI assistance — using any LLM you choose.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              size="lg" 
              onClick={handleGetStarted}
              className="bg-indigo-600 hover:bg-indigo-700 text-lg px-8"
              data-testid="hero-get-started-btn"
            >
              Start Building <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button 
              size="lg" 
              variant="outline" 
              className="border-slate-700 text-slate-300 hover:bg-slate-800 text-lg px-8"
            >
              $20/month
            </Button>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-white text-center mb-12">Why JarlPM?</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, i) => (
              <Card key={i} className="bg-slate-900/50 border-slate-800 hover:border-indigo-500/50 transition-colors">
                <CardHeader>
                  <feature.icon className="w-10 h-10 text-indigo-400 mb-2" />
                  <CardTitle className="text-white">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-slate-400">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Epic Lifecycle */}
      <section className="py-16 px-4 bg-slate-900/50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-white text-center mb-4">The Epic Lifecycle</h2>
          <p className="text-slate-400 text-center mb-12">
            A monotonic state machine. No going back. No scope creep.
          </p>
          <div className="space-y-4">
            {stages.map((stage, i) => (
              <div key={i} className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-lg
                  ${stage.locked 
                    ? 'bg-emerald-500/20 text-emerald-400 border-2 border-emerald-500' 
                    : 'bg-indigo-500/20 text-indigo-400 border-2 border-indigo-500'}`}>
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">{stage.name}</span>
                    {stage.locked && (
                      <Badge variant="outline" className="border-emerald-500/50 text-emerald-400 text-xs">
                        <Lock className="w-3 h-3 mr-1" /> Locked
                      </Badge>
                    )}
                  </div>
                  <p className="text-slate-400 text-sm">{stage.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-16 px-4">
        <div className="max-w-xl mx-auto">
          <Card className="bg-gradient-to-br from-slate-900 to-slate-800 border-indigo-500/50">
            <CardHeader className="text-center">
              <CardTitle className="text-3xl text-white">$20<span className="text-lg font-normal text-slate-400">/month</span></CardTitle>
              <CardDescription className="text-slate-400">Everything you need to build great products</CardDescription>
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
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span className="text-slate-300">{item}</span>
                </div>
              ))}
              <div className="pt-4 border-t border-slate-700">
                <p className="text-sm text-slate-500 text-center">
                  Note: LLM API costs are separate. You use your own keys.
                </p>
              </div>
              <Button 
                className="w-full bg-indigo-600 hover:bg-indigo-700 mt-4" 
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
      <footer className="border-t border-slate-800 py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-purple-600 rounded flex items-center justify-center">
              <Layers className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm text-slate-400">JarlPM</span>
          </div>
          <p className="text-sm text-slate-500">
            © 2025 JarlPM. Build better products.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
