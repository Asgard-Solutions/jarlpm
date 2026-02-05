import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

const EmptyState = ({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  secondaryLabel,
  onSecondary,
  className,
}) => {
  return (
    <div
      className={cn(
        'rounded-lg border border-dashed border-border p-8 text-center bg-card/40',
        className
      )}
      data-testid="empty-state"
    >
      {Icon ? (
        <div className="mx-auto mb-3 h-11 w-11 rounded-full bg-muted flex items-center justify-center">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
      ) : null}

      <div className="font-semibold">{title}</div>
      {description ? (
        <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
          {description}
        </p>
      ) : null}

      {(actionLabel || secondaryLabel) && (
        <div className="mt-4 flex items-center justify-center gap-2">
          {actionLabel ? (
            <Button onClick={onAction} className="gap-2">
              {actionLabel}
            </Button>
          ) : null}
          {secondaryLabel ? (
            <Button variant="outline" onClick={onSecondary}>
              {secondaryLabel}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default EmptyState;
