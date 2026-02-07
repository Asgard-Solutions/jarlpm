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
import { Key, Trash2, AlertCircle, Loader2, ExternalLink, Server, CheckCircle2 } from 'lucide-react';

// Provider metadata for better UX
const PROVIDER_INFO = {
  openai: {
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4 Turbo, and other OpenAI models',
    keyPlaceholder: 'sk-...',
    defaultModel: 'gpt-4o',
    modelSuggestions: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    docsUrl: 'https://platform.openai.com/api-keys',
    docsLabel: 'OpenAI API Keys'
  },
  anthropic: {
    name: 'Anthropic',
    description: 'Claude Sonnet, Opus, and Haiku models',
    keyPlaceholder: 'sk-ant-...',
    defaultModel: 'claude-sonnet-4-20250514',
    modelSuggestions: ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
    docsUrl: 'https://console.anthropic.com/settings/keys',
    docsLabel: 'Anthropic API Keys'
  },
  google: {
    name: 'Google Gemini',
    description: 'Gemini 2.0 Flash, Pro, and other Google AI models',
    keyPlaceholder: 'AIza...',
    defaultModel: 'gemini-2.0-flash',
    modelSuggestions: ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash'],
    docsUrl: 'https://aistudio.google.com/app/apikey',
    docsLabel: 'Google AI Studio API Keys'
  },
  local: {
    name: 'Self-Hosted / Custom',
    description: 'LM Studio, Ollama, vLLM, or any OpenAI-compatible endpoint',
    keyPlaceholder: 'Optional API key',
    defaultModel: '',
    modelSuggestions: [],
    docsUrl: null,
    docsLabel: null
  }
};

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
  const currentProviderInfo = PROVIDER_INFO[provider] || PROVIDER_INFO.openai;
  
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
            {providers.map((p) => {
              const providerMeta = PROVIDER_INFO[p.provider] || { name: p.provider };
              return (
                <div 
                  key={p.config_id}
                  className="flex items-center justify-between p-4 bg-nordic-bg-primary rounded-lg border border-nordic-border"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${p.is_active ? 'bg-nordic-green' : 'bg-nordic-text-muted/30'}`} />
                    <div>
                      <span className="font-medium text-nordic-text-primary">{providerMeta.name}</span>
                      {p.model_name && (
                        <span className="text-nordic-text-muted text-sm ml-2">({p.model_name})</span>
                      )}
                      {p.base_url && (
                        <span className="text-nordic-text-muted text-xs ml-2 flex items-center gap-1">
                          <Server className="w-3 h-3" />
                          {p.base_url}
                        </span>
                      )}
                    </div>
                    {p.is_active && (
                      <Badge className="bg-nordic-accent/20 text-nordic-accent border-nordic-accent/30">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
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
              );
            })}
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
                <SelectItem value="openai">
                  <div className="flex flex-col">
                    <span>OpenAI</span>
                  </div>
                </SelectItem>
                <SelectItem value="anthropic">
                  <div className="flex flex-col">
                    <span>Anthropic (Claude)</span>
                  </div>
                </SelectItem>
                <SelectItem value="google">
                  <div className="flex flex-col">
                    <span>Google Gemini</span>
                  </div>
                </SelectItem>
                <SelectItem value="local">
                  <div className="flex flex-col">
                    <span>Self-Hosted / Custom</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-nordic-text-muted">
              {currentProviderInfo.description}
            </p>
          </div>

          {provider === 'local' && (
            <div className="space-y-2">
              <Label className="text-nordic-text-secondary">
                Base URL <span className="text-nordic-red">*</span>
              </Label>
              <Input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:1234/v1"
                className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                data-testid="input-base-url"
              />
              <p className="text-xs text-nordic-text-muted">
                The base URL of your OpenAI-compatible API endpoint. Common setups:
              </p>
              <ul className="text-xs text-nordic-text-muted list-disc list-inside ml-2 space-y-1">
                <li><code className="bg-nordic-bg-primary px-1 rounded">http://localhost:1234/v1</code> - LM Studio</li>
                <li><code className="bg-nordic-bg-primary px-1 rounded">http://localhost:11434/v1</code> - Ollama</li>
                <li><code className="bg-nordic-bg-primary px-1 rounded">http://localhost:8000/v1</code> - vLLM</li>
              </ul>
            </div>
          )}

          <div className="space-y-2">
            <Label className="text-nordic-text-secondary">
              API Key {provider !== 'local' && <span className="text-nordic-red">*</span>}
              {provider === 'local' && <span className="text-nordic-text-muted text-xs ml-1">(optional)</span>}
            </Label>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={currentProviderInfo.keyPlaceholder}
              className="bg-background border-border text-foreground placeholder:text-muted-foreground"
              data-testid="input-api-key"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-nordic-text-secondary">
              Model Name 
              {provider !== 'local' && <span className="text-nordic-text-muted text-xs ml-1">(optional, defaults to {currentProviderInfo.defaultModel || 'provider default'})</span>}
            </Label>
            <Input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder={currentProviderInfo.defaultModel || 'model-name'}
              className="bg-background border-border text-foreground placeholder:text-muted-foreground"
              data-testid="input-model-name"
            />
            {currentProviderInfo.modelSuggestions.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {currentProviderInfo.modelSuggestions.map((model) => (
                  <button
                    key={model}
                    type="button"
                    onClick={() => setModelName(model)}
                    className="text-xs px-2 py-0.5 rounded bg-nordic-bg-primary border border-nordic-border text-nordic-text-muted hover:text-nordic-accent hover:border-nordic-accent transition-colors"
                  >
                    {model}
                  </button>
                ))}
              </div>
            )}
          </div>

          {keyError && (
            <div className="flex items-center gap-2 text-nordic-red text-sm">
              <AlertCircle className="w-4 h-4" />
              {keyError}
            </div>
          )}

          <Button
            onClick={onSave}
            disabled={savingKey || (provider !== 'local' && !apiKey.trim()) || (provider === 'local' && !baseUrl.trim())}
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
            {Object.entries(PROVIDER_INFO).map(([key, info]) => (
              info.docsUrl && (
                <a 
                  key={key}
                  href={info.docsUrl} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-nordic-accent hover:underline"
                >
                  <ExternalLink className="w-3 h-3" />
                  {info.docsLabel}
                </a>
              )
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default LLMProviderTab;
