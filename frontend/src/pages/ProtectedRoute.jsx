import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { authAPI } from '@/api';
import { useAuthStore } from '@/store';
import { Loader2 } from 'lucide-react';

const ProtectedRoute = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, setUser } = useAuthStore();
  const [isAuthenticated, setIsAuthenticated] = useState(
    location.state?.user ? true : (user ? true : null)
  );
  const hasChecked = useRef(false);

  const performAuthCheck = useCallback(async () => {
    // Server verification
    try {
      const response = await authAPI.getCurrentUser();
      setUser(response.data);
      return true;
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
      return false;
    }
  }, [setUser]);

  useEffect(() => {
    // If user data was passed from AuthCallback, use it
    if (location.state?.user && !hasChecked.current) {
      hasChecked.current = true;
      setUser(location.state.user);
      setIsAuthenticated(true);
      return;
    }

    // If we already have user from store, skip API call
    if (user && !hasChecked.current) {
      hasChecked.current = true;
      setIsAuthenticated(true);
      return;
    }

    // Need to check server
    if (!hasChecked.current) {
      hasChecked.current = true;
      performAuthCheck().then((isValid) => {
        if (isValid) {
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
          navigate('/', { replace: true });
        }
      });
    }
  }, [location.state, user, setUser, performAuthCheck, navigate]);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return children;
};

export default ProtectedRoute;
