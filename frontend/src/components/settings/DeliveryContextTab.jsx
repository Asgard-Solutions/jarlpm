/**
 * DeliveryContextTab - Product delivery context configuration
 */
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Briefcase, Users, Sparkles, AlertCircle, CheckCircle, Loader2 
} from 'lucide-react';

const DeliveryContextTab = ({
  deliveryContext,
  setDeliveryContext,
  savingContext,
  contextError,
  contextSuccess,
  onSave,
}) => {
  return (
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
          onClick={onSave}
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
  );
};

export default DeliveryContextTab;
