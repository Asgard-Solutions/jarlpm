import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import ThemeToggle from '@/components/ThemeToggle';
import { useThemeStore } from '@/store';
import { authAPI } from '@/api';
import { Loader2, Lock, AlertCircle, ArrowLeft, CheckCircle2 } from 'lucide-react';

const ResetPassword = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useThemeStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [tokenValid, setTokenValid] = useState(false);
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: ''
  });

  const token = searchParams.get('token');
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  // Password requirements
  const passwordRequirements = [
    { label: 'At least 8 characters', test: (pw) => pw.length >= 8 },
    { label: 'Contains a number', test: (pw) => /\d/.test(pw) },
    { label: 'Contains uppercase letter', test: (pw) => /[A-Z]/.test(pw) },
    { label: 'Contains lowercase letter', test: (pw) => /[a-z]/.test(pw) },
  ];

  useEffect(() => {
    const checkToken = async () => {
      if (!token) {
        setError('No reset token provided');
        setIsChecking(false);
        return;
      }

      try {
        const response = await authAPI.checkToken(token);
        if (response.data.valid && response.data.token_type === 'password_reset') {
          setTokenValid(true);
        } else {
          setError(response.data.reason || 'Invalid or expired reset link');
        }
      } catch (err) {
        setError('Failed to verify reset link');
      } finally {
        setIsChecking(false);
      }
    };

    checkToken();
  }, [token]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    // Validate password
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      setIsLoading(false);
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      setIsLoading(false);
      return;
    }

    try {
      await authAPI.resetPassword(token, formData.password);
      setSuccess(true);
      // Redirect to login after 3 seconds
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      console.error('Reset password error:', err);
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('An error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (isChecking) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Navigation */}
      <nav className="border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center space-x-2">
              <img src={logoSrc} alt="JarlPM" className="h-9 w-auto" />
              <span className="text-xl font-bold text-foreground">JarlPM</span>
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </nav>

      {/* Reset Password Form */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md bg-card border-border">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl text-center text-foreground">
              {success ? 'Password Reset!' : 'Create new password'}
            </CardTitle>
            <CardDescription className="text-center text-muted-foreground">
              {success ? 'You can now login with your new password' : 'Enter your new password below'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {success ? (
              <div className="text-center space-y-4">
                <div className="flex justify-center">
                  <CheckCircle2 className="h-16 w-16 text-success" />
                </div>
                <p className="text-muted-foreground">
                  Redirecting to login page...
                </p>
              </div>
            ) : !tokenValid ? (
              <div className="text-center space-y-4">
                <Alert variant="destructive" className="bg-destructive/10 border-destructive/30">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error || 'Invalid reset link'}</AlertDescription>
                </Alert>
                <p className="text-muted-foreground">
                  Please request a new password reset link.
                </p>
                <Button
                  variant="outline"
                  onClick={() => navigate('/forgot-password')}
                  className="mt-4"
                >
                  Request new link
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <Alert variant="destructive" className="bg-destructive/10 border-destructive/30">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}
                
                <div className="space-y-2">
                  <Label htmlFor="password" className="text-foreground">New Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="password"
                      name="password"
                      type="password"
                      placeholder="Enter new password"
                      value={formData.password}
                      onChange={handleChange}
                      required
                      className="pl-10 bg-background border-border text-foreground"
                      data-testid="reset-password-input"
                    />
                  </div>
                  
                  {/* Password requirements */}
                  {formData.password && (
                    <div className="mt-2 space-y-1">
                      {passwordRequirements.map((req, i) => (
                        <div 
                          key={i} 
                          className={`flex items-center text-xs ${
                            req.test(formData.password) ? 'text-success' : 'text-muted-foreground'
                          }`}
                        >
                          <CheckCircle2 className={`mr-1 h-3 w-3 ${
                            req.test(formData.password) ? 'text-success' : 'text-muted-foreground/50'
                          }`} />
                          {req.label}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword" className="text-foreground">Confirm Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="confirmPassword"
                      name="confirmPassword"
                      type="password"
                      placeholder="Confirm new password"
                      value={formData.confirmPassword}
                      onChange={handleChange}
                      required
                      className="pl-10 bg-background border-border text-foreground"
                      data-testid="reset-confirm-password-input"
                    />
                  </div>
                  {formData.confirmPassword && formData.password !== formData.confirmPassword && (
                    <p className="text-xs text-destructive">Passwords do not match</p>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
                  disabled={isLoading}
                  data-testid="reset-password-submit-btn"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Resetting...
                    </>
                  ) : (
                    'Reset password'
                  )}
                </Button>
              </form>
            )}
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Link 
              to="/login" 
              className="flex items-center justify-center text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to login
            </Link>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default ResetPassword;
