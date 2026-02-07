/**
 * JarlPM UI Classes - Standardized form control styling
 * 
 * Use these classes for consistent form styling across the app.
 * All classes use semantic color tokens that work in both light and dark themes.
 */

/**
 * Standard form control class string
 * Use for: Input, Textarea, Select triggers, search boxes
 */
export const FORM_CONTROL_CLASS = [
  'bg-background',
  'text-foreground',
  'border',
  'border-input',
  'placeholder:text-muted-foreground',
  'focus-visible:outline-none',
  'focus-visible:ring-2',
  'focus-visible:ring-ring/30',
  'focus-visible:border-primary/40',
  'disabled:opacity-50',
  'disabled:cursor-not-allowed',
].join(' ');

/**
 * Form control with error state
 */
export const FORM_CONTROL_ERROR_CLASS = [
  'bg-background',
  'text-foreground',
  'border',
  'border-destructive',
  'placeholder:text-muted-foreground',
  'focus-visible:outline-none',
  'focus-visible:ring-2',
  'focus-visible:ring-destructive/30',
  'focus-visible:border-destructive',
  'disabled:opacity-50',
  'disabled:cursor-not-allowed',
].join(' ');

/**
 * Card/Panel background class
 * Use for: Cards, modals, dropdowns, panels
 */
export const CARD_CLASS = 'bg-card text-card-foreground border border-border';

/**
 * Muted section background
 * Use for: Secondary panels, info boxes
 */
export const MUTED_SECTION_CLASS = 'bg-muted text-muted-foreground';

/**
 * Primary button class
 */
export const PRIMARY_BUTTON_CLASS = 'bg-primary text-primary-foreground hover:bg-primary/90';

/**
 * Secondary/Ghost button class
 */
export const SECONDARY_BUTTON_CLASS = 'bg-secondary text-secondary-foreground hover:bg-secondary/80';

/**
 * Label class for form labels
 */
export const LABEL_CLASS = 'text-foreground font-medium';

/**
 * Muted label class for secondary labels
 */
export const LABEL_MUTED_CLASS = 'text-muted-foreground';
