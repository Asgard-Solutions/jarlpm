import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import ThemeToggle from '@/components/ThemeToggle';
import { useAuthStore, useThemeStore } from '@/store';
import { authAPI } from '@/api';
import { Loader2, Mail, Lock, User, AlertCircle, ArrowLeft, CheckCircle2 } from 'lucide-react';

const Signup = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const nextPath = useMemo(() => {
    const params = new URLSearchParams(location.search || '');
    const next = params.get('next');
    // Only allow internal paths
    if (next && next.startsWith('/')) return next;
    return '/dashboard';
  }, [location.search]);
  const { setUser } = useAuthStore();
  const { theme } = useThemeStore();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });

  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  // Password requirements
  const passwordRequirements = [
    { label: 'At least 8 characters', test: (pw) => pw.length >= 8 },
    { label: 'Contains a number', test: (pw) => /\d/.test(pw) },
    { label: 'Contains uppercase letter', test: (pw) => /[A-Z]/.test(pw) },
    { label: 'Contains lowercase letter', test: (pw) => /[a-z]/.test(pw) },
  ];

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const validatePassword = () => {
    const { password, confirmPassword } = formData;
    
    // Check minimum requirements
    if (password.length < 8) {
      return 'Password must be at least 8 characters';
    }
    
    // Check confirm password match
    if (password !== confirmPassword) {
      return 'Passwords do not match';
    }
    
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    // Validate password
    const passwordError = validatePassword();
    if (passwordError) {
      setError(passwordError);
      setIsLoading(false);
      return;
    }

    try {
      const response = await authAPI.signup({
        name: formData.name,
        email: formData.email,
        password: formData.password
      });
      const data = response.data;
      
      setUser({
        user_id: data.user_id,
        email: data.email,
        name: data.name,
        picture: null
      });
      
      navigate(nextPath, { replace: true });
    } catch (err) {
      console.error('Signup error:', err);
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('An error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

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

      {/* Signup Form */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md bg-card border-border">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl text-center text-foreground">Create an account</CardTitle>
            <CardDescription className="text-center text-muted-foreground">
              Start building better epics with JarlPM
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <Alert variant="destructive" className="bg-destructive/10 border-destructive/30">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="name" className="text-foreground">Full Name</Label>
                <div className="relative">
                  <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="John Doe"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    className="pl-10 bg-background border-border text-foreground"
                    data-testid="signup-name-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-foreground">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="name@example.com"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    className="pl-10 bg-background border-border text-foreground"
                    data-testid="signup-email-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-foreground">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    placeholder="Create a password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    className="pl-10 bg-background border-border text-foreground"
                    data-testid="signup-password-input"
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
                    placeholder="Confirm your password"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    required
                    className="pl-10 bg-background border-border text-foreground"
                    data-testid="signup-confirm-password-input"
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
                data-testid="signup-submit-btn"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  'Create account'
                )}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <p className="text-xs text-center text-muted-foreground">
              By creating an account, you agree to our Terms of Service and Privacy Policy.
            </p>
            <div className="text-sm text-center text-muted-foreground">
              Already have an account?{' '}
              <Link to="/login" className="text-primary hover:underline" data-testid="signup-login-link">
                Sign in
              </Link>
            </div>
            <Link 
              to="/" 
              className="flex items-center justify-center text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to home
            </Link>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default Signup;
