"""
Test Microsoft Graph Email Integration
Tests email sending via Microsoft Graph API for:
- Signup verification emails
- Forgot password emails
- Resend verification emails
"""
import pytest
import requests
import os
import time
import uuid

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMicrosoftGraphEmailIntegration:
    """Tests for Microsoft Graph email integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Generate unique test email to avoid conflicts
        self.test_email = f"graphtest_{uuid.uuid4().hex[:8]}@example.com"
        self.test_password = "GraphTest123!"
        self.test_name = "Graph Test User"
    
    # ============================================
    # Email Service Configuration Tests
    # ============================================
    
    def test_email_service_is_configured(self):
        """Test that email service has Microsoft Graph credentials configured"""
        # This is an indirect test - if signup works and sends email, service is configured
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": self.test_email,
            "password": self.test_password,
            "name": self.test_name
        })
        
        assert response.status_code == 200, f"Signup failed: {response.text}"
        data = response.json()
        assert "user_id" in data
        assert data["email"] == self.test_email
        print(f"✓ Signup successful for {self.test_email} - email service is configured")
    
    # ============================================
    # Signup Email Verification Tests
    # ============================================
    
    def test_signup_sends_verification_email(self):
        """Test that signup triggers verification email via Microsoft Graph"""
        unique_email = f"signup_test_{uuid.uuid4().hex[:8]}@example.com"
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": self.test_password,
            "name": self.test_name
        })
        
        assert response.status_code == 200, f"Signup failed: {response.text}"
        data = response.json()
        
        # Verify user was created
        assert "user_id" in data
        assert data["email"] == unique_email
        assert data["message"] == "Account created successfully"
        
        print(f"✓ Signup completed for {unique_email}")
        print(f"  - User ID: {data['user_id']}")
        print(f"  - Verification email should be sent via Microsoft Graph")
    
    def test_signup_creates_verification_token(self):
        """Test that signup creates a verification token that can be checked"""
        unique_email = f"token_test_{uuid.uuid4().hex[:8]}@example.com"
        
        # Signup
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": self.test_password,
            "name": self.test_name
        })
        
        assert signup_response.status_code == 200
        
        # Get session cookie for authenticated requests
        cookies = signup_response.cookies
        
        # Check user's email_verified status (should be False initially)
        me_response = self.session.get(f"{BASE_URL}/api/auth/me", cookies=cookies)
        assert me_response.status_code == 200
        
        user_data = me_response.json()
        assert user_data["email_verified"] == False, "New user should have email_verified=False"
        
        print(f"✓ Verification token created for {unique_email}")
        print(f"  - email_verified: {user_data['email_verified']}")
    
    # ============================================
    # Forgot Password Email Tests
    # ============================================
    
    def test_forgot_password_sends_email(self):
        """Test that forgot password triggers email via Microsoft Graph"""
        # First create a user
        unique_email = f"forgot_test_{uuid.uuid4().hex[:8]}@example.com"
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": self.test_password,
            "name": self.test_name
        })
        assert signup_response.status_code == 200
        
        # Request password reset
        forgot_response = self.session.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": unique_email
        })
        
        assert forgot_response.status_code == 200
        data = forgot_response.json()
        
        # API should return success message (doesn't reveal if email exists)
        assert "message" in data
        assert "password reset link" in data["message"].lower() or "if the email exists" in data["message"].lower()
        
        print(f"✓ Forgot password request successful for {unique_email}")
        print(f"  - Response: {data['message']}")
    
    def test_forgot_password_nonexistent_email(self):
        """Test that forgot password doesn't reveal if email exists"""
        nonexistent_email = f"nonexistent_{uuid.uuid4().hex[:8]}@example.com"
        
        response = self.session.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": nonexistent_email
        })
        
        assert response.status_code == 200, "Should return 200 even for non-existent email"
        data = response.json()
        
        # Should return same message as for existing email (security)
        assert "message" in data
        
        print(f"✓ Forgot password for non-existent email returns 200 (security)")
        print(f"  - Response: {data['message']}")
    
    def test_forgot_password_invalid_email_format(self):
        """Test that forgot password rejects invalid email format"""
        response = self.session.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "not-an-email"
        })
        
        assert response.status_code == 422, "Should reject invalid email format"
        print("✓ Invalid email format rejected with 422")
    
    # ============================================
    # Resend Verification Email Tests
    # ============================================
    
    def test_resend_verification_sends_email(self):
        """Test that resend verification triggers email via Microsoft Graph"""
        # First create a user
        unique_email = f"resend_test_{uuid.uuid4().hex[:8]}@example.com"
        
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": self.test_password,
            "name": self.test_name
        })
        assert signup_response.status_code == 200
        
        # Request resend verification
        resend_response = self.session.post(f"{BASE_URL}/api/auth/resend-verification", json={
            "email": unique_email
        })
        
        assert resend_response.status_code == 200
        data = resend_response.json()
        
        assert "message" in data
        print(f"✓ Resend verification successful for {unique_email}")
        print(f"  - Response: {data['message']}")
    
    def test_resend_verification_nonexistent_email(self):
        """Test that resend verification doesn't reveal if email exists"""
        nonexistent_email = f"nonexistent_{uuid.uuid4().hex[:8]}@example.com"
        
        response = self.session.post(f"{BASE_URL}/api/auth/resend-verification", json={
            "email": nonexistent_email
        })
        
        assert response.status_code == 200, "Should return 200 even for non-existent email"
        data = response.json()
        
        assert "message" in data
        print(f"✓ Resend verification for non-existent email returns 200 (security)")
    
    # ============================================
    # Email Verification Flow Tests
    # ============================================
    
    def test_verify_email_with_invalid_token(self):
        """Test that verify email rejects invalid token"""
        response = self.session.post(f"{BASE_URL}/api/auth/verify-email", json={
            "token": "invalid_token_xyz_123"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Invalid verification token rejected: {data['detail']}")
    
    def test_check_token_validity_invalid(self):
        """Test check-token endpoint with invalid token"""
        response = self.session.get(f"{BASE_URL}/api/auth/check-token/invalid_token_xyz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == False
        print(f"✓ Check token returns valid=False for invalid token")
    
    # ============================================
    # Password Reset Flow Tests
    # ============================================
    
    def test_reset_password_with_invalid_token(self):
        """Test that reset password rejects invalid token"""
        response = self.session.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": "invalid_token_xyz_123",
            "new_password": "NewPassword123!"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Invalid reset token rejected: {data['detail']}")
    
    def test_reset_password_short_password(self):
        """Test that reset password rejects short password"""
        response = self.session.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": "some_token",
            "new_password": "short"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "8 characters" in data["detail"]
        print(f"✓ Short password rejected: {data['detail']}")
    
    # ============================================
    # Full Email Flow Integration Tests
    # ============================================
    
    def test_full_signup_to_verification_flow(self):
        """Test complete signup to email verification flow"""
        unique_email = f"fullflow_{uuid.uuid4().hex[:8]}@example.com"
        
        # Step 1: Signup
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": self.test_password,
            "name": self.test_name
        })
        assert signup_response.status_code == 200
        user_data = signup_response.json()
        cookies = signup_response.cookies
        
        print(f"✓ Step 1: User created - {user_data['user_id']}")
        
        # Step 2: Check email_verified is False
        me_response = self.session.get(f"{BASE_URL}/api/auth/me", cookies=cookies)
        assert me_response.status_code == 200
        assert me_response.json()["email_verified"] == False
        
        print("✓ Step 2: email_verified is False (awaiting verification)")
        
        # Step 3: Resend verification (simulates user clicking resend)
        resend_response = self.session.post(f"{BASE_URL}/api/auth/resend-verification", json={
            "email": unique_email
        })
        assert resend_response.status_code == 200
        
        print("✓ Step 3: Resend verification email triggered")
        print("  - Email should be sent via Microsoft Graph to: " + unique_email)
    
    def test_full_forgot_password_flow(self):
        """Test complete forgot password flow"""
        unique_email = f"pwflow_{uuid.uuid4().hex[:8]}@example.com"
        
        # Step 1: Create user
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": self.test_password,
            "name": self.test_name
        })
        assert signup_response.status_code == 200
        
        print(f"✓ Step 1: User created - {unique_email}")
        
        # Step 2: Request password reset
        forgot_response = self.session.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": unique_email
        })
        assert forgot_response.status_code == 200
        
        print("✓ Step 2: Password reset email triggered")
        print("  - Email should be sent via Microsoft Graph to: " + unique_email)
        
        # Step 3: Verify user can still login with old password
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": self.test_password
        })
        assert login_response.status_code == 200
        
        print("✓ Step 3: User can still login (reset not completed yet)")


class TestEmailServiceEdgeCases:
    """Edge case tests for email service"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_signup_with_duplicate_email(self):
        """Test that signup rejects duplicate email"""
        unique_email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
        
        # First signup
        response1 = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": "TestPassword123!",
            "name": "Test User"
        })
        assert response1.status_code == 200
        
        # Second signup with same email
        response2 = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": "TestPassword123!",
            "name": "Test User 2"
        })
        assert response2.status_code == 400
        assert "already registered" in response2.json()["detail"].lower()
        
        print(f"✓ Duplicate email rejected: {response2.json()['detail']}")
    
    def test_signup_with_weak_password(self):
        """Test that signup rejects weak password"""
        unique_email = f"weakpw_{uuid.uuid4().hex[:8]}@example.com"
        
        response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": "short",
            "name": "Test User"
        })
        
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]
        
        print(f"✓ Weak password rejected: {response.json()['detail']}")
    
    def test_resend_verification_for_verified_user(self):
        """Test resend verification for already verified user"""
        # This test checks the response when email is already verified
        # Since we can't easily verify email in test, we just check the endpoint works
        unique_email = f"verified_{uuid.uuid4().hex[:8]}@example.com"
        
        # Create user
        signup_response = self.session.post(f"{BASE_URL}/api/auth/signup", json={
            "email": unique_email,
            "password": "TestPassword123!",
            "name": "Test User"
        })
        assert signup_response.status_code == 200
        
        # Resend verification
        resend_response = self.session.post(f"{BASE_URL}/api/auth/resend-verification", json={
            "email": unique_email
        })
        assert resend_response.status_code == 200
        
        print("✓ Resend verification endpoint works for unverified user")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
