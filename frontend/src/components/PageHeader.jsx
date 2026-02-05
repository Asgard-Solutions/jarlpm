import React from 'react';
import { cn } from '@/lib/utils';

/**
 * Standard page header.
 *
 * Props:
 * - title: string
 * - description?: string
 * - actions?: ReactNode (right side)
 * - compact?: boolean (reduced vertical space)
 */
const PageHeader = ({ title, description, actions, compact = false, className }) => {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between',
        compact ? 'mb-4' : 'mb-6',
        className
      )}
      data-testid="page-header"
    >
      <div className="min-w-0">
        <h1 className={cn('font-bold tracking-tight', compact ? 'text-xl' : 'text-2xl')}>
          {title}
        </h1>
        {description ? (
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            {description}
          </p>
        ) : null}
      </div>

      {actions ? (
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          {actions}
        </div>
      ) : null}
    </div>
  );
};

export default PageHeader;
