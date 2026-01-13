import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      
      setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
      setLoading: (isLoading) => set({ isLoading }),
      logout: () => set({ user: null, isAuthenticated: false, isLoading: false }),
    }),
    {
      name: 'jarlpm-auth',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

export const useSubscriptionStore = create((set) => ({
  subscription: null,
  isActive: false,
  
  setSubscription: (subscription) => set({ 
    subscription, 
    isActive: subscription?.status === 'active' 
  }),
}));

export const useLLMProviderStore = create((set) => ({
  providers: [],
  activeProvider: null,
  
  setProviders: (providers) => {
    const active = providers.find(p => p.is_active);
    set({ providers, activeProvider: active });
  },
}));

// Theme store with persistence and system preference support
export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'system', // 'light', 'dark', or 'system'
      resolvedTheme: 'light', // Actual theme being displayed
      
      setTheme: (theme) => {
        set({ theme });
        get().applyTheme(theme);
      },
      
      applyTheme: (theme) => {
        const root = window.document.documentElement;
        let resolved = theme;
        
        if (theme === 'system') {
          resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        
        root.classList.remove('light', 'dark');
        root.classList.add(resolved);
        set({ resolvedTheme: resolved });
      },
      
      initTheme: () => {
        const { theme, applyTheme } = get();
        applyTheme(theme);
        
        // Listen for system preference changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handler = () => {
          if (get().theme === 'system') {
            applyTheme('system');
          }
        };
        mediaQuery.addEventListener('change', handler);
        
        return () => mediaQuery.removeEventListener('change', handler);
      },
    }),
    {
      name: 'jarlpm-theme',
      partialize: (state) => ({ theme: state.theme }),
    }
  )
);
