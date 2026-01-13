/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
        extend: {
                borderRadius: {
                        lg: 'var(--radius)',
                        md: 'calc(var(--radius) - 2px)',
                        sm: 'calc(var(--radius) - 4px)'
                },
                colors: {
                        /* Semantic Theme Tokens */
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
                        
                        /* Primary - Muted Nordic Blue */
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))'
                        },
                        
                        /* Secondary - Neutral Grays */
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))'
                        },
                        
                        /* Muted - Subtle backgrounds */
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        
                        /* Accent - Subtle highlight */
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        
                        /* Destructive - Muted Nordic Red */
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        
                        /* Success - Muted Nordic Green */
                        success: {
                                DEFAULT: 'hsl(var(--success))',
                                foreground: 'hsl(var(--success-foreground))'
                        },
                        
                        /* Warning - Muted Amber */
                        warning: {
                                DEFAULT: 'hsl(var(--warning))',
                                foreground: 'hsl(var(--warning-foreground))'
                        },
                        
                        /* UI Elements */
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))',
                        
                        /* Nordic Color Palette - Direct access */
                        nordic: {
                                blue: {
                                        50: 'hsl(var(--nordic-blue-50))',
                                        100: 'hsl(var(--nordic-blue-100))',
                                        200: 'hsl(var(--nordic-blue-200))',
                                        300: 'hsl(var(--nordic-blue-300))',
                                        400: 'hsl(var(--nordic-blue-400))',
                                        500: 'hsl(var(--nordic-blue-500))',
                                        600: 'hsl(var(--nordic-blue-600))',
                                        700: 'hsl(var(--nordic-blue-700))',
                                        800: 'hsl(var(--nordic-blue-800))',
                                        900: 'hsl(var(--nordic-blue-900))',
                                },
                                red: {
                                        50: 'hsl(var(--nordic-red-50))',
                                        100: 'hsl(var(--nordic-red-100))',
                                        200: 'hsl(var(--nordic-red-200))',
                                        300: 'hsl(var(--nordic-red-300))',
                                        400: 'hsl(var(--nordic-red-400))',
                                        500: 'hsl(var(--nordic-red-500))',
                                        600: 'hsl(var(--nordic-red-600))',
                                        700: 'hsl(var(--nordic-red-700))',
                                        800: 'hsl(var(--nordic-red-800))',
                                        900: 'hsl(var(--nordic-red-900))',
                                },
                                gray: {
                                        50: 'hsl(var(--nordic-gray-50))',
                                        100: 'hsl(var(--nordic-gray-100))',
                                        200: 'hsl(var(--nordic-gray-200))',
                                        300: 'hsl(var(--nordic-gray-300))',
                                        400: 'hsl(var(--nordic-gray-400))',
                                        500: 'hsl(var(--nordic-gray-500))',
                                        600: 'hsl(var(--nordic-gray-600))',
                                        700: 'hsl(var(--nordic-gray-700))',
                                        800: 'hsl(var(--nordic-gray-800))',
                                        900: 'hsl(var(--nordic-gray-900))',
                                        950: 'hsl(var(--nordic-gray-950))',
                                },
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
