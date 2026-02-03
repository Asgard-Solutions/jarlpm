import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import ThemeToggle from '@/components/ThemeToggle';
import { useThemeStore, useAuthStore } from '@/store';
import { authAPI } from '@/api';
import { Loader2, AlertCircle, CheckCircle2, Mail } from 'lucide-react';

const VerifyEmail = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { theme } = useThemeStore();
  const { user, setUser } = useAuthStore();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const token = searchParams.get('token');
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png';

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token) {
        setError('No verification token provided');
        setIsLoading(false);
        return;
      }

      try {
        await authAPI.verifyEmail(token);
        setSuccess(true);
        
        // Update user state if logged in
        if (user) {
          setUser({ ...user, email_verified: true });
        }
      } catch (err) {
        console.error('Email verification error:', err);
        if (err.response?.data?.detail) {
          setError(err.response.data.detail);
        } else {
          setError('Failed to verify email. The link may be invalid or expired.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    verifyEmail();
  }, [token, user, setUser]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">Verifying your email...</p>
        </div>
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

      {/* Verification Result */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md bg-card border-border">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl text-center text-foreground">
              {success ? 'Email Verified!' : 'Verification Failed'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {success ? (
              <div className="text-center space-y-4">
                <div className="flex justify-center">
                  <CheckCircle2 className="h-16 w-16 text-success" />
                </div>
                <p className="text-muted-foreground">
                  Your email has been verified successfully.
                </p>
                <Button
                  onClick={() => navigate('/dashboard')}
                  className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
                  data-testid="verify-email-continue-btn"
                >
                  Continue to Dashboard
                </Button>
              </div>
            ) : (
              <div className="text-center space-y-4">
                <div className="flex justify-center">
                  <AlertCircle className="h-16 w-16 text-destructive" />
                </div>
                <Alert variant="destructive" className="bg-destructive/10 border-destructive/30">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                <p className="text-muted-foreground text-sm">
                  The verification link may have expired or already been used.
                </p>
              </div>
            )}
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            {!success && (
              <Button
                variant="outline"
                onClick={() => navigate('/login')}
                className="w-full"
              >
                <Mail className="mr-2 h-4 w-4" />
                Login to resend verification
              </Button>
            )}
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default VerifyEmail;
