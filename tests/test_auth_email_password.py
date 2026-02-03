"""
Test Email/Password Authentication for JarlPM
Tests: signup, login, me, logout endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL_PREFIX = f"TEST_auth_{uuid.uuid4().hex[:8]}"
TEST_USER_EMAIL = f"{TEST_EMAIL_PREFIX}@example.com"
TEST_USER_PASSWORD = "TestPassword123"
TEST_USER_NAME = "Auth Test User"


class TestAuthSignup:
    """Test POST /api/auth/signup endpoint"""
    
    def test_signup_success(self):
        """Test successful user registration"""
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Response should contain user_id"
        assert "email" in data, "Response should contain email"
        assert "name" in data, "Response should contain name"
        assert data["email"] == TEST_USER_EMAIL
        assert data["name"] == TEST_USER_NAME
        assert "message" in data
        print(f"SUCCESS: User created with ID: {data['user_id']}")
    
    def test_signup_duplicate_email(self):
        """Test signup with already registered email"""
        # First signup
        requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": f"duplicate_{TEST_EMAIL_PREFIX}@example.com",
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME
            }
        )
        
        # Second signup with same email
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": f"duplicate_{TEST_EMAIL_PREFIX}@example.com",
                "password": TEST_USER_PASSWORD,
                "name": "Another User"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "already registered" in data["detail"].lower() or "email" in data["detail"].lower()
        print(f"SUCCESS: Duplicate email rejected with message: {data['detail']}")
    
    def test_signup_short_password(self):
        """Test signup with password less than 8 characters"""
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": f"shortpw_{TEST_EMAIL_PREFIX}@example.com",
                "password": "short",  # Less than 8 chars
                "name": TEST_USER_NAME
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "8" in data["detail"] or "character" in data["detail"].lower()
        print(f"SUCCESS: Short password rejected with message: {data['detail']}")
    
    def test_signup_invalid_email(self):
        """Test signup with invalid email format"""
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": "not-an-email",
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME
            }
        )
        
        assert response.status_code == 422, f"Expected 422 for validation error, got {response.status_code}"
        print("SUCCESS: Invalid email format rejected")
    
    def test_signup_missing_fields(self):
        """Test signup with missing required fields"""
        # Missing password
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": f"missing_{TEST_EMAIL_PREFIX}@example.com",
                "name": TEST_USER_NAME
            }
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        
        # Missing name
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": f"missing2_{TEST_EMAIL_PREFIX}@example.com",
                "password": TEST_USER_PASSWORD
            }
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("SUCCESS: Missing fields rejected with 422")


class TestAuthLogin:
    """Test POST /api/auth/login endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_user(self):
        """Create a test user for login tests"""
        self.login_email = f"login_{TEST_EMAIL_PREFIX}@example.com"
        self.login_password = "LoginPassword123"
        
        # Create user
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": self.login_email,
                "password": self.login_password,
                "name": "Login Test User"
            }
        )
        # User might already exist from previous test run
        if response.status_code not in [200, 400]:
            pytest.fail(f"Failed to setup test user: {response.text}")
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": self.login_email,
                "password": self.login_password
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "name" in data
        assert data["email"] == self.login_email
        assert "message" in data
        
        # Check for session cookie
        cookies = response.cookies
        assert "session_token" in cookies or len(cookies) > 0, "Session cookie should be set"
        print(f"SUCCESS: Login successful for user: {data['user_id']}")
    
    def test_login_wrong_password(self):
        """Test login with incorrect password"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": self.login_email,
                "password": "WrongPassword123"
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"SUCCESS: Wrong password rejected with message: {data['detail']}")
    
    def test_login_nonexistent_user(self):
        """Test login with email that doesn't exist"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": TEST_USER_PASSWORD
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        # Should not reveal whether email exists or not
        assert "invalid" in data["detail"].lower()
        print(f"SUCCESS: Nonexistent user rejected with message: {data['detail']}")
    
    def test_login_invalid_email_format(self):
        """Test login with invalid email format"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "not-an-email",
                "password": TEST_USER_PASSWORD
            }
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("SUCCESS: Invalid email format rejected")


class TestAuthMe:
    """Test GET /api/auth/me endpoint"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Create user and get authenticated session"""
        session = requests.Session()
        email = f"me_{TEST_EMAIL_PREFIX}@example.com"
        password = "MeTestPassword123"
        
        # Create user
        session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": email,
                "password": password,
                "name": "Me Test User"
            }
        )
        
        # Login to get session
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": email,
                "password": password
            }
        )
        
        if response.status_code != 200:
            pytest.skip(f"Could not authenticate: {response.text}")
        
        return session, email
    
    def test_get_current_user_authenticated(self, authenticated_session):
        """Test getting current user with valid session"""
        session, email = authenticated_session
        
        response = session.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "name" in data
        assert data["email"] == email
        print(f"SUCCESS: Got current user: {data['user_id']}")
    
    def test_get_current_user_unauthenticated(self):
        """Test getting current user without session"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Unauthenticated request rejected")


class TestAuthLogout:
    """Test POST /api/auth/logout endpoint"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Create user and get authenticated session"""
        session = requests.Session()
        email = f"logout_{TEST_EMAIL_PREFIX}@example.com"
        password = "LogoutTestPassword123"
        
        # Create user
        session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": email,
                "password": password,
                "name": "Logout Test User"
            }
        )
        
        # Login to get session
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": email,
                "password": password
            }
        )
        
        if response.status_code != 200:
            pytest.skip(f"Could not authenticate: {response.text}")
        
        return session
    
    def test_logout_success(self, authenticated_session):
        """Test successful logout"""
        session = authenticated_session
        
        # Verify we're logged in first
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200, "Should be authenticated before logout"
        
        # Logout
        response = session.post(f"{BASE_URL}/api/auth/logout")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data
        print(f"SUCCESS: Logout successful: {data['message']}")
    
    def test_logout_invalidates_session(self, authenticated_session):
        """Test that logout invalidates the session"""
        session = authenticated_session
        
        # Logout
        session.post(f"{BASE_URL}/api/auth/logout")
        
        # Try to access protected endpoint
        response = session.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 401, f"Expected 401 after logout, got {response.status_code}"
        print("SUCCESS: Session invalidated after logout")


class TestTestLogin:
    """Test POST /api/auth/test-login endpoint (development feature)"""
    
    def test_test_login_success(self):
        """Test the test-login endpoint for development"""
        session = requests.Session()
        
        response = session.post(f"{BASE_URL}/api/auth/test-login")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "name" in data
        assert "subscription_status" in data
        assert data["subscription_status"] == "active"
        print(f"SUCCESS: Test login successful: {data['user_id']}")
        
        # Verify session works
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200, "Should be authenticated after test-login"
        print("SUCCESS: Test login session is valid")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
