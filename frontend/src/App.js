import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import '@/App.css';
import { useThemeStore } from '@/store';

// Pages
import Landing from '@/pages/Landing';
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

// Theme initializer component
const ThemeInitializer = ({ children }) => {
  const initTheme = useThemeStore((state) => state.initTheme);

  useEffect(() => {
    const cleanup = initTheme();
    return cleanup;
  }, [initTheme]);

  return children;
};

// Route handler that checks for session_id in URL hash
const AppRouter = () => {
  const location = useLocation();

  // Check URL fragment for session_id (handles auth callback)
  // This must be done synchronously during render, NOT in useEffect
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />
      
      {/* Protected routes */}
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      } />
      
      <Route path="/settings" element={
        <ProtectedRoute>
          <Settings />
        </ProtectedRoute>
      } />
      
      <Route path="/epic/:epicId" element={
        <ProtectedRoute>
          <Epic />
        </ProtectedRoute>
      } />
      
      <Route path="/feature/:featureId/stories" element={
        <ProtectedRoute>
          <StoryPlanning />
        </ProtectedRoute>
      } />
      
      <Route path="/epic/:epicId/review" element={
        <ProtectedRoute>
          <CompletedEpic />
        </ProtectedRoute>
      } />
      
      <Route path="/bugs" element={
        <ProtectedRoute>
          <Bugs />
        </ProtectedRoute>
      } />
      
      <Route path="/stories" element={
        <ProtectedRoute>
          <Stories />
        </ProtectedRoute>
      } />
      
      <Route path="/personas" element={
        <ProtectedRoute>
          <Personas />
        </ProtectedRoute>
      } />
      
      <Route path="/export" element={
        <ProtectedRoute>
          <Export />
        </ProtectedRoute>
      } />
      
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
