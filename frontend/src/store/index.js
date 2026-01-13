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
