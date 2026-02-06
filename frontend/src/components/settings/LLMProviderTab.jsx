/**
 * LLMProviderTab - LLM provider configuration
 */
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
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
import { Key, Trash2, AlertCircle, Loader2, ExternalLink } from 'lucide-react';

const LLMProviderTab = ({
  providers,
  provider,
  setProvider,
  apiKey,
  setApiKey,
  modelName,
  setModelName,
  baseUrl,
  setBaseUrl,
  savingKey,
  keyError,
  onSave,
  onDelete,
}) => {
  return (
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
                  onClick={() => onDelete(p.config_id)}
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
            onClick={onSave}
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
  );
};

export default LLMProviderTab;
