import React from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import '@/App.css';

// Pages
import Landing from '@/pages/Landing';
import AuthCallback from '@/pages/AuthCallback';
import ProtectedRoute from '@/pages/ProtectedRoute';
import Dashboard from '@/pages/Dashboard';
import Settings from '@/pages/Settings';
import Epic from '@/pages/Epic';

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
      
      {/* Catch-all redirect to landing */}
      <Route path="*" element={<Landing />} />
    </Routes>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </div>
  );
}

export default App;
