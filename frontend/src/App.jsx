import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import '@/App.css';
import { useThemeStore } from '@/store';

// Layout
import AppLayout from '@/components/AppLayout';

// Pages
import Landing from '@/pages/Landing';
import Login from '@/pages/Login';
import Signup from '@/pages/Signup';
import ForgotPassword from '@/pages/ForgotPassword';
import ResetPassword from '@/pages/ResetPassword';
import VerifyEmail from '@/pages/VerifyEmail';
import AuthCallback from '@/pages/AuthCallback';
import ProtectedRoute from '@/pages/ProtectedRoute';
import Dashboard from '@/pages/Dashboard';
import Settings from '@/pages/Settings';
import Epic from '@/pages/Epic';
import StoryPlanning from '@/pages/StoryPlanning';
import CompletedEpic from '@/pages/CompletedEpic';
import Bugs from '@/pages/Bugs';
import Stories from '@/pages/Stories';
import Personas from '@/pages/Personas';
import Export from '@/pages/Export';
import Scoring from '@/pages/Scoring';
import Sprints from '@/pages/Sprints';
import PRDGenerator from '@/pages/PRDGenerator';
import LeanCanvas from '@/pages/LeanCanvas';
import PokerPlanning from '@/pages/PokerPlanning';

// Theme initializer component
const ThemeInitializer = ({ children }) => {
  const initTheme = useThemeStore((state) => state.initTheme);

  useEffect(() => {
    const cleanup = initTheme();
    return cleanup;
  }, [initTheme]);

  return children;
};

// Protected route with AppLayout wrapper
const ProtectedPage = ({ children }) => (
  <ProtectedRoute>
    <AppLayout>
      {children}
    </AppLayout>
  </ProtectedRoute>
);

// Route handler that checks for session_id in URL hash
const AppRouter = () => {
  const location = useLocation();

  // Check URL fragment for session_id (handles legacy auth callback)
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      
      {/* Protected routes with sidebar layout */}
      <Route path="/dashboard" element={<ProtectedPage><Dashboard /></ProtectedPage>} />
      <Route path="/settings" element={<ProtectedPage><Settings /></ProtectedPage>} />
      <Route path="/epic/:epicId" element={<ProtectedPage><Epic /></ProtectedPage>} />
      <Route path="/feature/:featureId/stories" element={<ProtectedPage><StoryPlanning /></ProtectedPage>} />
      <Route path="/epic/:epicId/review" element={<ProtectedPage><CompletedEpic /></ProtectedPage>} />
      <Route path="/bugs" element={<ProtectedPage><Bugs /></ProtectedPage>} />
      <Route path="/stories" element={<ProtectedPage><Stories /></ProtectedPage>} />
      <Route path="/personas" element={<ProtectedPage><Personas /></ProtectedPage>} />
      <Route path="/export" element={<ProtectedPage><Export /></ProtectedPage>} />
      <Route path="/scoring" element={<ProtectedPage><Scoring /></ProtectedPage>} />
      <Route path="/sprints" element={<ProtectedPage><Sprints /></ProtectedPage>} />
      
      {/* Catch-all redirect to landing */}
      <Route path="*" element={<Landing />} />
    </Routes>
  );
};

function App() {
  return (
    <ThemeInitializer>
      <div className="App min-h-screen bg-background text-foreground">
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
      </div>
    </ThemeInitializer>
  );
}

export default App;
