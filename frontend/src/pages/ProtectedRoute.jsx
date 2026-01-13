import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { authAPI } from '@/api';
import { useAuthStore } from '@/store';
import { Loader2 } from 'lucide-react';

const ProtectedRoute = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, setUser } = useAuthStore();
  const [isChecking, setIsChecking] = useState(true);
  const [authDone, setAuthDone] = useState(false);

  const checkAuth = useCallback(async () => {
    // If user data was passed from AuthCallback, use it
    if (location.state?.user) {
      setUser(location.state.user);
      setAuthDone(true);
      return;
    }

    // If we already have user from store, skip API call
    if (user) {
      setAuthDone(true);
      return;
    }

    // Server verification
    try {
      const response = await authAPI.getCurrentUser();
      setUser(response.data);
      setAuthDone(true);
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
      navigate('/', { replace: true });
    }
  }, [location.state, user, setUser, navigate]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (authDone) {
      setIsChecking(false);
    }
  }, [authDone]);

  if (isChecking) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  return children;
};

export default ProtectedRoute;
