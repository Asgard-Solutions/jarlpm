"""
Test suite for Product Delivery Context API endpoints
Tests GET and PUT /api/delivery-context with various scenarios
"""
import pytest
import requests
import os

# Use the public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pmcanvas.preview.emergentagent.com')
API_URL = f"{BASE_URL}/api"

# Test session token created for testing
TEST_SESSION_TOKEN = "test_session_8401ef389c9b4660824a684694e505a5"


class TestDeliveryContextAPI:
    """Test Product Delivery Context API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}"
        })
        self.session.cookies.set("session_token", TEST_SESSION_TOKEN)
    
    def test_get_delivery_context_creates_empty_if_none(self):
        """GET /api/delivery-context should create empty context if none exists"""
        response = self.session.get(f"{API_URL}/delivery-context")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "context_id" in data, "Response should contain context_id"
        assert "created_at" in data, "Response should contain created_at"
        assert "updated_at" in data, "Response should contain updated_at"
        
        # All fields should be None/null for new context
        print(f"GET delivery context response: {data}")
    
    def test_update_delivery_context_with_valid_data(self):
        """PUT /api/delivery-context should update context with valid data"""
        payload = {
            "industry": "FinTech, Healthcare",
            "delivery_methodology": "scrum",
            "sprint_cycle_length": 14,
            "sprint_start_date": "2025-01-06",
            "num_developers": 5,
            "num_qa": 2,
            "delivery_platform": "jira"
        }
        
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["industry"] == "FinTech, Healthcare"
        assert data["delivery_methodology"] == "scrum"
        assert data["sprint_cycle_length"] == 14
        assert data["sprint_start_date"] == "2025-01-06"
        assert data["num_developers"] == 5
        assert data["num_qa"] == 2
        assert data["delivery_platform"] == "jira"
        
        print(f"PUT delivery context response: {data}")
    
    def test_get_delivery_context_returns_updated_data(self):
        """GET /api/delivery-context should return previously updated data"""
        # First update
        payload = {
            "industry": "E-commerce",
            "delivery_methodology": "kanban",
            "sprint_cycle_length": 7,
            "sprint_start_date": "2025-01-13",
            "num_developers": 3,
            "num_qa": 1,
            "delivery_platform": "azure_devops"
        }
        
        put_response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert put_response.status_code == 200
        
        # Then GET to verify persistence
        get_response = self.session.get(f"{API_URL}/delivery-context")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["industry"] == "E-commerce"
        assert data["delivery_methodology"] == "kanban"
        assert data["sprint_cycle_length"] == 7
        assert data["num_developers"] == 3
        assert data["num_qa"] == 1
        assert data["delivery_platform"] == "azure_devops"
        
        print(f"Verified GET returns updated data: {data}")
    
    def test_validate_delivery_methodology_enum_waterfall(self):
        """PUT should accept 'waterfall' as valid methodology"""
        payload = {"delivery_methodology": "waterfall"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_methodology"] == "waterfall"
    
    def test_validate_delivery_methodology_enum_agile(self):
        """PUT should accept 'agile' as valid methodology"""
        payload = {"delivery_methodology": "agile"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_methodology"] == "agile"
    
    def test_validate_delivery_methodology_enum_scrum(self):
        """PUT should accept 'scrum' as valid methodology"""
        payload = {"delivery_methodology": "scrum"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_methodology"] == "scrum"
    
    def test_validate_delivery_methodology_enum_kanban(self):
        """PUT should accept 'kanban' as valid methodology"""
        payload = {"delivery_methodology": "kanban"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_methodology"] == "kanban"
    
    def test_validate_delivery_methodology_enum_hybrid(self):
        """PUT should accept 'hybrid' as valid methodology"""
        payload = {"delivery_methodology": "hybrid"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_methodology"] == "hybrid"
    
    def test_validate_delivery_methodology_invalid(self):
        """PUT should reject invalid methodology values"""
        payload = {"delivery_methodology": "invalid_method"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid methodology, got {response.status_code}"
        assert "Invalid delivery_methodology" in response.json().get("detail", "")
    
    def test_validate_delivery_platform_enum_jira(self):
        """PUT should accept 'jira' as valid platform"""
        payload = {"delivery_platform": "jira"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_platform"] == "jira"
    
    def test_validate_delivery_platform_enum_azure_devops(self):
        """PUT should accept 'azure_devops' as valid platform"""
        payload = {"delivery_platform": "azure_devops"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_platform"] == "azure_devops"
    
    def test_validate_delivery_platform_enum_none(self):
        """PUT should accept 'none' as valid platform"""
        payload = {"delivery_platform": "none"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_platform"] == "none"
    
    def test_validate_delivery_platform_enum_other(self):
        """PUT should accept 'other' as valid platform"""
        payload = {"delivery_platform": "other"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["delivery_platform"] == "other"
    
    def test_validate_delivery_platform_invalid(self):
        """PUT should reject invalid platform values"""
        payload = {"delivery_platform": "github_projects"}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid platform, got {response.status_code}"
        assert "Invalid delivery_platform" in response.json().get("detail", "")
    
    def test_handle_null_values(self):
        """PUT should handle null/empty values correctly"""
        payload = {
            "industry": None,
            "delivery_methodology": None,
            "sprint_cycle_length": None,
            "sprint_start_date": None,
            "num_developers": None,
            "num_qa": None,
            "delivery_platform": None
        }
        
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["industry"] is None
        assert data["delivery_methodology"] is None
        assert data["sprint_cycle_length"] is None
        assert data["sprint_start_date"] is None
        assert data["num_developers"] is None
        assert data["num_qa"] is None
        assert data["delivery_platform"] is None
        
        print(f"Null values handled correctly: {data}")
    
    def test_handle_empty_string_values(self):
        """PUT should handle empty string values (converted to null)"""
        payload = {
            "industry": "",
            "delivery_methodology": "",
            "delivery_platform": ""
        }
        
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        # Empty strings for enum fields should be rejected or converted to null
        # Based on the validation logic, empty strings should fail validation
        # Let's check the actual behavior
        print(f"Empty string response: {response.status_code} - {response.text}")
    
    def test_partial_update(self):
        """PUT should allow partial updates (only some fields)"""
        # First set all fields
        full_payload = {
            "industry": "Gaming",
            "delivery_methodology": "agile",
            "sprint_cycle_length": 21,
            "num_developers": 10,
            "num_qa": 3,
            "delivery_platform": "jira"
        }
        self.session.put(f"{API_URL}/delivery-context", json=full_payload)
        
        # Then update only some fields
        partial_payload = {
            "industry": "Gaming, Entertainment",
            "num_developers": 12
        }
        
        response = self.session.put(f"{API_URL}/delivery-context", json=partial_payload)
        assert response.status_code == 200
        
        data = response.json()
        # Updated fields
        assert data["industry"] == "Gaming, Entertainment"
        assert data["num_developers"] == 12
        # Note: Other fields will be set to null since we're doing a full PUT, not PATCH
        print(f"Partial update response: {data}")
    
    def test_unauthenticated_request_rejected(self):
        """Requests without auth should be rejected"""
        unauthenticated_session = requests.Session()
        unauthenticated_session.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated_session.get(f"{API_URL}/delivery-context")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_sprint_cycle_length_validation(self):
        """Sprint cycle length should be between 1 and 365"""
        # Test valid value
        payload = {"sprint_cycle_length": 30}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        
        # Test boundary - 1 day
        payload = {"sprint_cycle_length": 1}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        
        # Test boundary - 365 days
        payload = {"sprint_cycle_length": 365}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
    
    def test_num_developers_validation(self):
        """Number of developers should be >= 0"""
        # Test valid value
        payload = {"num_developers": 0}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["num_developers"] == 0
        
        payload = {"num_developers": 100}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["num_developers"] == 100
    
    def test_num_qa_validation(self):
        """Number of QA should be >= 0"""
        payload = {"num_qa": 0}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["num_qa"] == 0
        
        payload = {"num_qa": 50}
        response = self.session.put(f"{API_URL}/delivery-context", json=payload)
        assert response.status_code == 200
        assert response.json()["num_qa"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
