/**
 * AppearanceTab - Theme customization
 */
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Palette, Sun, Moon, Monitor } from 'lucide-react';

const AppearanceTab = ({ theme, setTheme }) => {
  return (
    <Card className="bg-nordic-bg-secondary border-nordic-border">
      <CardHeader>
        <CardTitle className="text-nordic-text-primary flex items-center gap-2">
          <Palette className="w-5 h-5 text-nordic-accent" />
          Appearance
        </CardTitle>
        <CardDescription className="text-nordic-text-muted">
          Customize the visual appearance of JarlPM
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <Label className="text-nordic-text-secondary">Theme</Label>
          <div className="grid grid-cols-3 gap-3">
            <button
              onClick={() => setTheme('light')}
              className={`p-4 rounded-lg border-2 transition-all flex flex-col items-center gap-2 ${
                theme === 'light'
                  ? 'border-nordic-accent bg-nordic-accent/10'
                  : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
              }`}
              data-testid="theme-light"
            >
              <Sun className="w-6 h-6 text-nordic-text-primary" />
              <span className="text-sm text-nordic-text-secondary">Light</span>
            </button>
            <button
              onClick={() => setTheme('dark')}
              className={`p-4 rounded-lg border-2 transition-all flex flex-col items-center gap-2 ${
                theme === 'dark'
                  ? 'border-nordic-accent bg-nordic-accent/10'
                  : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
              }`}
              data-testid="theme-dark"
            >
              <Moon className="w-6 h-6 text-nordic-text-primary" />
              <span className="text-sm text-nordic-text-secondary">Dark</span>
            </button>
            <button
              onClick={() => setTheme('system')}
              className={`p-4 rounded-lg border-2 transition-all flex flex-col items-center gap-2 ${
                theme === 'system'
                  ? 'border-nordic-accent bg-nordic-accent/10'
                  : 'border-nordic-border bg-nordic-bg-primary hover:border-nordic-accent/50'
              }`}
              data-testid="theme-system"
            >
              <Monitor className="w-6 h-6 text-nordic-text-primary" />
              <span className="text-sm text-nordic-text-secondary">System</span>
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AppearanceTab;
