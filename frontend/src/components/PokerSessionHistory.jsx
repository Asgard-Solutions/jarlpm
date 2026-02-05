import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from '@/components/ui/dialog';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { 
  History, 
  ChevronDown, 
  ChevronUp, 
  Clock, 
  Check, 
  Users,
  MessageSquare,
  Trophy
} from 'lucide-react';
import { pokerAPI } from '@/api';

const PERSONA_AVATARS = {
  'Sarah': '👩‍💻',
  'Alex': '👨‍💻',
  'Maya': '🧪',
  'Jordan': '🔧',
  'Riley': '🎨',
};

const PokerSessionHistory = ({ storyId, storyTitle }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [expandedSessions, setExpandedSessions] = useState({});

  const loadSessions = async () => {
    if (!storyId) return;
    setLoading(true);
    try {
      const response = await pokerAPI.getSessions(storyId);
      setSessions(response.data?.sessions || []);
    } catch (error) {
      console.error('Failed to load poker sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && storyId) {
      loadSessions();
    }
  }, [open, storyId]);

  const toggleSession = (sessionId) => {
    setExpandedSessions(prev => ({
      ...prev,
      [sessionId]: !prev[sessionId]
    }));
  };

  const getConfidenceColor = (confidence) => {
    switch (confidence) {
      case 'high': return 'text-green-500';
      case 'medium': return 'text-yellow-500';
      case 'low': return 'text-red-500';
      default: return 'text-muted-foreground';
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className="gap-2"
          data-testid="view-estimation-history"
        >
          <History className="h-4 w-4" />
          View History
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Estimation History
          </DialogTitle>
          <DialogDescription>
            Past AI poker planning sessions for "{storyTitle?.substring(0, 50) || 'this story'}..."
          </DialogDescription>
        </DialogHeader>
        
        <ScrollArea className="h-[60vh] pr-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">No Estimation History</h3>
              <p className="text-muted-foreground">
                Run AI Poker Planning to see estimation sessions here.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {sessions.map((session, index) => (
                <Collapsible 
                  key={session.session_id}
                  open={expandedSessions[session.session_id]}
                  onOpenChange={() => toggleSession(session.session_id)}
                >
                  <Card className="border-border">
                    <CollapsibleTrigger asChild>
                      <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors py-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="flex items-center text-sm text-muted-foreground gap-1">
                              <Clock className="h-4 w-4" />
                              {formatDate(session.created_at)}
                            </div>
                            {session.accepted_estimate && (
                              <Badge className="bg-green-500/10 text-green-500 border-green-500/30 gap-1">
                                <Check className="h-3 w-3" />
                                Accepted: {session.accepted_estimate} pts
                              </Badge>
                            )}
                            {index === 0 && (
                              <Badge variant="secondary" className="text-xs">Latest</Badge>
                            )}
                          </div>
                          {expandedSessions[session.session_id] ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm mt-2">
                          <div className="flex items-center gap-1">
                            <Trophy className="h-4 w-4 text-yellow-500" />
                            <span className="font-medium">Suggested: {session.suggested_estimate}</span>
                          </div>
                          <Separator orientation="vertical" className="h-4" />
                          <span className="text-muted-foreground">
                            Range: {session.min_estimate} - {session.max_estimate}
                          </span>
                          <Separator orientation="vertical" className="h-4" />
                          <span className="text-muted-foreground">
                            Avg: {session.average_estimate?.toFixed(1)}
                          </span>
                        </div>
                      </CardHeader>
                    </CollapsibleTrigger>
                    
                    <CollapsibleContent>
                      <CardContent className="pt-0">
                        <Separator className="mb-4" />
                        <div className="space-y-4">
                          <h4 className="text-sm font-medium flex items-center gap-2">
                            <MessageSquare className="h-4 w-4" />
                            Persona Reasoning
                          </h4>
                          <div className="space-y-3">
                            {session.estimates?.map((estimate, estIndex) => (
                              <div 
                                key={estIndex}
                                className="p-3 rounded-lg border border-border bg-muted/20"
                              >
                                <div className="flex items-center gap-3 mb-2">
                                  <Avatar className="h-8 w-8">
                                    <AvatarFallback className="text-base bg-primary/10">
                                      {PERSONA_AVATARS[estimate.persona_name] || '🤖'}
                                    </AvatarFallback>
                                  </Avatar>
                                  <div className="flex-1 min-w-0">
                                    <p className="font-medium text-sm text-foreground">
                                      {estimate.persona_name}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      {estimate.persona_role}
                                    </p>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className={`text-xs ${getConfidenceColor(estimate.confidence)}`}>
                                      {estimate.confidence} confidence
                                    </span>
                                    <Badge variant="outline" className="text-lg font-bold">
                                      {estimate.estimate_points}
                                    </Badge>
                                  </div>
                                </div>
                                <p className="text-sm text-muted-foreground pl-11">
                                  {estimate.reasoning}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </CardContent>
                    </CollapsibleContent>
                  </Card>
                </Collapsible>
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

export default PokerSessionHistory;
