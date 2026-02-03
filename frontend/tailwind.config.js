/** @type {import('tailwindcss').Config} */
export default {
    darkMode: ["class"],
    content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}"
  ],
  theme: {
        extend: {
                borderRadius: {
                        lg: 'var(--radius)',
                        md: 'calc(var(--radius) - 2px)',
                        sm: 'calc(var(--radius) - 4px)'
                },
                colors: {
                        /* ========================================
                           JarlPM Nordic Palette v1 — Semantic Tokens
                           All components must reference these tokens.
                           ======================================== */
                        
                        /* Core Backgrounds */
                        background: 'hsl(var(--background))',
                        foreground: 'hsl(var(--foreground))',
                        
                        /* Card & Surface */
                        card: {
                                DEFAULT: 'hsl(var(--card))',
                                foreground: 'hsl(var(--card-foreground))'
                        },
                        popover: {
                                DEFAULT: 'hsl(var(--popover))',
                                foreground: 'hsl(var(--popover-foreground))'
                        },
                        
                        /* Primary — Nordic Blue (Muted) */
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))'
                        },
                        
                        /* Secondary — Neutral Backgrounds */
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))'
                        },
                        
                        /* Muted — Subtle backgrounds and text */
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        
                        /* Accent — Soft highlight */
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        
                        /* Destructive — Nordic Red (Muted) */
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        
                        /* Success — Status Confirmed (Nordic Green) */
                        success: {
                                DEFAULT: 'hsl(var(--success))',
                                foreground: 'hsl(var(--success-foreground))'
                        },
                        
                        /* Warning — Amber (Very Limited Use) */
                        warning: {
                                DEFAULT: 'hsl(var(--warning))',
                                foreground: 'hsl(var(--warning-foreground))'
                        },
                        
                        /* UI Elements */
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))',
                        
                        /* Direct Nordic Palette Access (Use sparingly) */
                        nordic: {
                                blue: {
                                        DEFAULT: 'hsl(var(--accent-blue))',
                                        hover: 'hsl(var(--accent-blue-hover))',
                                        soft: 'hsl(var(--accent-blue-soft))',
                                },
                                red: {
                                        DEFAULT: 'hsl(var(--accent-red))',
                                        hover: 'hsl(var(--accent-red-hover))',
                                        soft: 'hsl(var(--accent-red-soft))',
                                },
                                amber: 'hsl(var(--accent-amber))',
                        },
                        
                        /* Status Colors (Always pair with icons) */
                        status: {
                                confirmed: 'hsl(var(--status-confirmed))',
                                pending: 'hsl(var(--status-pending))',
                                locked: 'hsl(var(--status-locked))',
                        },
                        
                        /* Chart colors */
                        chart: {
                                '1': 'hsl(var(--chart-1))',
                                '2': 'hsl(var(--chart-2))',
                                '3': 'hsl(var(--chart-3))',
                                '4': 'hsl(var(--chart-4))',
                                '5': 'hsl(var(--chart-5))'
                        }
                },
                keyframes: {
                        'accordion-down': {
                                from: {
                                        height: '0'
                                },
                                to: {
                                        height: 'var(--radix-accordion-content-height)'
                                }
                        },
                        'accordion-up': {
                                from: {
                                        height: 'var(--radix-accordion-content-height)'
                                },
                                to: {
                                        height: '0'
                                }
                        }
                },
                animation: {
                        'accordion-down': 'accordion-down 0.2s ease-out',
                        'accordion-up': 'accordion-up 0.2s ease-out'
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};
