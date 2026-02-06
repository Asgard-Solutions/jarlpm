/**
 * SubscriptionTab - Subscription status and management
 */
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CreditCard, CheckCircle, Loader2 } from 'lucide-react';

const SubscriptionTab = ({
  subscription,
  isActive,
  billingCycle,
  setBillingCycle,
  subscribing,
  checkingPayment,
  canceling,
  reactivating,
  onSubscribe,
  onCancel,
  onReactivate,
}) => {
  return (
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
                onClick={onReactivate}
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
                onClick={onCancel}
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
                onClick={onSubscribe}
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
  );
};

export default SubscriptionTab;
