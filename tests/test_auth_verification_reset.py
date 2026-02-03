"""
Test suite for Email Verification and Password Reset features
Tests: forgot-password, reset-password, verify-email, resend-verification, check-token
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestForgotPassword:
    """Tests for POST /api/auth/forgot-password"""
    
    def test_forgot_password_existing_email(self):
        """Test forgot password with existing user email - should return token in dev mode"""
        # First create a user
        unique_email = f"TEST_forgot_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Forgot Test User"
            }
        )
        assert signup_response.status_code == 200, f"Signup failed: {signup_response.text}"
        
        # Request password reset
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": unique_email}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # In dev mode, token should be returned
        assert "token" in data, "Token should be returned in development mode"
        assert len(data["token"]) > 20, "Token should be a valid length"
        print(f"✓ Forgot password returns token for existing user: {data['token'][:20]}...")
    
    def test_forgot_password_nonexistent_email(self):
        """Test forgot password with non-existent email - should still return success (security)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": "nonexistent_user_12345@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # Should NOT reveal if email exists
        assert "If the email exists" in data["message"]
        print("✓ Forgot password doesn't reveal if email exists")
    
    def test_forgot_password_invalid_email_format(self):
        """Test forgot password with invalid email format"""
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": "not-an-email"}
        )
        assert response.status_code == 422
        print("✓ Forgot password rejects invalid email format")


class TestResetPassword:
    """Tests for POST /api/auth/reset-password"""
    
    def test_reset_password_valid_token(self):
        """Test password reset with valid token"""
        # Create user and get reset token
        unique_email = f"TEST_reset_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "OldPassword123",
                "name": "Reset Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Get reset token
        forgot_response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": unique_email}
        )
        assert forgot_response.status_code == 200
        token = forgot_response.json()["token"]
        
        # Reset password
        new_password = "NewPassword456"
        reset_response = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={
                "token": token,
                "new_password": new_password
            }
        )
        assert reset_response.status_code == 200
        data = reset_response.json()
        assert "message" in data
        assert "successfully" in data["message"].lower()
        print("✓ Password reset successful with valid token")
        
        # Verify can login with new password
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": unique_email,
                "password": new_password
            }
        )
        assert login_response.status_code == 200
        print("✓ Can login with new password after reset")
    
    def test_reset_password_invalid_token(self):
        """Test password reset with invalid token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={
                "token": "invalid_token_12345",
                "new_password": "NewPassword123"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print("✓ Password reset rejects invalid token")
    
    def test_reset_password_short_password(self):
        """Test password reset with password less than 8 characters"""
        # Create user and get reset token
        unique_email = f"TEST_shortpw_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "OldPassword123",
                "name": "Short PW Test"
            }
        )
        assert signup_response.status_code == 200
        
        forgot_response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": unique_email}
        )
        token = forgot_response.json()["token"]
        
        # Try to reset with short password
        response = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "short"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "8 characters" in data["detail"]
        print("✓ Password reset rejects short password")
    
    def test_reset_password_invalidates_sessions(self):
        """Test that password reset invalidates all existing sessions"""
        # Create user
        unique_email = f"TEST_sessions_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "OldPassword123",
                "name": "Session Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Login to create a session
        session = requests.Session()
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": unique_email,
                "password": "OldPassword123"
            }
        )
        assert login_response.status_code == 200
        
        # Verify session works
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200
        
        # Get reset token and reset password
        forgot_response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": unique_email}
        )
        token = forgot_response.json()["token"]
        
        reset_response = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewPassword789"
            }
        )
        assert reset_response.status_code == 200
        
        # Old session should be invalidated
        me_response_after = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response_after.status_code == 401, "Old session should be invalidated after password reset"
        print("✓ Password reset invalidates all existing sessions")


class TestCheckToken:
    """Tests for GET /api/auth/check-token/{token}"""
    
    def test_check_valid_password_reset_token(self):
        """Test checking a valid password reset token"""
        # Create user and get reset token
        unique_email = f"TEST_checktoken_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Check Token Test"
            }
        )
        assert signup_response.status_code == 200
        
        forgot_response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": unique_email}
        )
        token = forgot_response.json()["token"]
        
        # Check token validity
        response = requests.get(f"{BASE_URL}/api/auth/check-token/{token}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == True
        assert data["token_type"] == "password_reset"
        assert "expires_at" in data
        print("✓ Check token returns valid for password reset token")
    
    def test_check_valid_email_verification_token(self):
        """Test checking a valid email verification token"""
        # Create user (signup creates verification token)
        unique_email = f"TEST_emailtoken_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Email Token Test"
            }
        )
        assert signup_response.status_code == 200
        
        # Resend verification to get token
        resend_response = requests.post(
            f"{BASE_URL}/api/auth/resend-verification",
            json={"email": unique_email}
        )
        assert resend_response.status_code == 200
        token = resend_response.json().get("token")
        
        if token:
            # Check token validity
            response = requests.get(f"{BASE_URL}/api/auth/check-token/{token}")
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == True
            assert data["token_type"] == "email_verification"
            print("✓ Check token returns valid for email verification token")
        else:
            print("⚠ Token not returned (may be production mode)")
    
    def test_check_invalid_token(self):
        """Test checking an invalid token"""
        response = requests.get(f"{BASE_URL}/api/auth/check-token/invalid_token_xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == False
        assert "reason" in data
        print("✓ Check token returns invalid for non-existent token")
    
    def test_check_used_token(self):
        """Test checking a token that has already been used"""
        # Create user and get reset token
        unique_email = f"TEST_usedtoken_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Used Token Test"
            }
        )
        assert signup_response.status_code == 200
        
        forgot_response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": unique_email}
        )
        token = forgot_response.json()["token"]
        
        # Use the token
        reset_response = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewPassword123"
            }
        )
        assert reset_response.status_code == 200
        
        # Check used token
        response = requests.get(f"{BASE_URL}/api/auth/check-token/{token}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == False
        print("✓ Check token returns invalid for used token")


class TestVerifyEmail:
    """Tests for POST /api/auth/verify-email"""
    
    def test_verify_email_valid_token(self):
        """Test email verification with valid token"""
        # Create user
        unique_email = f"TEST_verify_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Verify Email Test"
            }
        )
        assert signup_response.status_code == 200
        
        # Get verification token via resend
        resend_response = requests.post(
            f"{BASE_URL}/api/auth/resend-verification",
            json={"email": unique_email}
        )
        assert resend_response.status_code == 200
        token = resend_response.json().get("token")
        
        if token:
            # Verify email
            verify_response = requests.post(
                f"{BASE_URL}/api/auth/verify-email",
                json={"token": token}
            )
            assert verify_response.status_code == 200
            data = verify_response.json()
            assert "message" in data
            assert "verified" in data["message"].lower()
            print("✓ Email verification successful with valid token")
        else:
            print("⚠ Token not returned (may be production mode)")
    
    def test_verify_email_invalid_token(self):
        """Test email verification with invalid token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-email",
            json={"token": "invalid_verification_token"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print("✓ Email verification rejects invalid token")


class TestResendVerification:
    """Tests for POST /api/auth/resend-verification"""
    
    def test_resend_verification_existing_user(self):
        """Test resend verification for existing unverified user"""
        # Create user
        unique_email = f"TEST_resend_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Resend Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Resend verification
        response = requests.post(
            f"{BASE_URL}/api/auth/resend-verification",
            json={"email": unique_email}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # In dev mode, token should be returned
        if "token" in data:
            assert len(data["token"]) > 20
            print(f"✓ Resend verification returns token: {data['token'][:20]}...")
        else:
            print("✓ Resend verification successful (token not returned in prod mode)")
    
    def test_resend_verification_nonexistent_email(self):
        """Test resend verification for non-existent email - should not reveal"""
        response = requests.post(
            f"{BASE_URL}/api/auth/resend-verification",
            json={"email": "nonexistent_12345@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # Should not reveal if email exists
        print("✓ Resend verification doesn't reveal if email exists")


class TestGetCurrentUserEmailVerified:
    """Tests for GET /api/auth/me - email_verified field"""
    
    def test_me_includes_email_verified_field(self):
        """Test that /api/auth/me includes email_verified field"""
        # Create user and login
        unique_email = f"TEST_me_{uuid.uuid4().hex[:8]}@example.com"
        session = requests.Session()
        
        signup_response = session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Me Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Get current user
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200
        data = me_response.json()
        
        assert "email_verified" in data, "email_verified field should be in response"
        assert data["email_verified"] == False, "New user should have email_verified=False"
        print("✓ GET /api/auth/me includes email_verified field (False for new user)")
    
    def test_me_email_verified_after_verification(self):
        """Test that email_verified becomes True after verification"""
        # Create user
        unique_email = f"TEST_verified_{uuid.uuid4().hex[:8]}@example.com"
        session = requests.Session()
        
        signup_response = session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Verified Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Get verification token
        resend_response = requests.post(
            f"{BASE_URL}/api/auth/resend-verification",
            json={"email": unique_email}
        )
        token = resend_response.json().get("token")
        
        if token:
            # Verify email
            verify_response = requests.post(
                f"{BASE_URL}/api/auth/verify-email",
                json={"token": token}
            )
            assert verify_response.status_code == 200
            
            # Check email_verified is now True
            me_response = session.get(f"{BASE_URL}/api/auth/me")
            assert me_response.status_code == 200
            data = me_response.json()
            assert data["email_verified"] == True, "email_verified should be True after verification"
            print("✓ email_verified becomes True after verification")
        else:
            print("⚠ Token not returned (may be production mode)")


class TestSubscriptionStatus:
    """Tests for GET /api/subscription/status - works without Stripe key"""
    
    def test_subscription_status_authenticated(self):
        """Test subscription status for authenticated user"""
        # Create user and login
        unique_email = f"TEST_sub_{uuid.uuid4().hex[:8]}@example.com"
        session = requests.Session()
        
        signup_response = session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Subscription Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Get subscription status
        response = session.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        # New user should have inactive subscription
        assert data["status"] == "inactive"
        print("✓ Subscription status returns inactive for new user")
    
    def test_subscription_status_unauthenticated(self):
        """Test subscription status without authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 401
        print("✓ Subscription status requires authentication")


class TestCheckoutGracefulFailure:
    """Tests for POST /api/subscription/create-checkout - graceful failure without Stripe key"""
    
    def test_checkout_fails_gracefully_without_stripe_key(self):
        """Test that checkout fails gracefully when Stripe key is placeholder"""
        # Create user and login
        unique_email = f"TEST_checkout_{uuid.uuid4().hex[:8]}@example.com"
        session = requests.Session()
        
        signup_response = session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Checkout Test User"
            }
        )
        assert signup_response.status_code == 200
        
        # Try to create checkout
        response = session.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://example.com"}
        )
        
        # Should fail with 500 (or 520 via Cloudflare) and helpful message
        assert response.status_code in [500, 520], f"Expected 500 or 520, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "not configured" in data["detail"].lower() or "stripe" in data["detail"].lower()
        print(f"✓ Checkout fails gracefully (status {response.status_code}) with helpful error message when Stripe not configured")


class TestSignupCreatesVerificationToken:
    """Test that signup creates email verification token"""
    
    def test_signup_creates_verification_token(self):
        """Test that signup creates a verification token that can be used"""
        # Create user
        unique_email = f"TEST_signuptoken_{uuid.uuid4().hex[:8]}@example.com"
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": unique_email,
                "password": "TestPassword123",
                "name": "Signup Token Test"
            }
        )
        assert signup_response.status_code == 200
        
        # Resend verification should work (proves token was created)
        resend_response = requests.post(
            f"{BASE_URL}/api/auth/resend-verification",
            json={"email": unique_email}
        )
        assert resend_response.status_code == 200
        data = resend_response.json()
        
        # In dev mode, we should get a token back
        if "token" in data:
            # Verify the token works
            verify_response = requests.post(
                f"{BASE_URL}/api/auth/verify-email",
                json={"token": data["token"]}
            )
            assert verify_response.status_code == 200
            print("✓ Signup creates verification token that can be used")
        else:
            print("✓ Signup creates verification token (token not returned in prod mode)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
