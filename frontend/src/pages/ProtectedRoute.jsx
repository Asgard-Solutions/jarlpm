import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { authAPI } from '@/api';
import { useAuthStore } from '@/store';
import { Loader2 } from 'lucide-react';

const ProtectedRoute = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, setUser, setLoading } = useAuthStore();
  const [isChecking, setIsChecking] = useState(!location.state?.user);

  useEffect(() => {
    // If user data was passed from AuthCallback, skip auth check
    if (location.state?.user) {
      setUser(location.state.user);
      setIsChecking(false);
      return;
    }

    // If we already have user, skip auth check
    if (user) {
      setIsChecking(false);
      return;
    }

    // Server verification
    const checkAuth = async () => {
      try {
        const response = await authAPI.getCurrentUser();
        setUser(response.data);
        setIsChecking(false);
      } catch (error) {
        console.error('Auth check failed:', error);
        setUser(null);
        navigate('/', { replace: true });
      }
    };

    checkAuth();
  }, [location.state, user, setUser, setLoading, navigate]);

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
