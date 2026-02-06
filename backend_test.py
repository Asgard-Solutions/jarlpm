#!/usr/bin/env python3
"""
JarlPM Backend API Testing Suite
Tests all API endpoints with proper authentication
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class JarlPMAPITester:
    def __init__(self, base_url: str = "https://convo-pm-system.preview.emergentagent.com"):
        self.base_url = base_url
        self.session_token = "test_session_1768266514950"  # Provided test token
        self.epic_id = "epic_8c3454380b4c"  # Provided test epic
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.session_token}'
        }

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, auth_required: bool = True) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('/') else f"{self.base_url}{endpoint}"
        headers = self.get_headers() if auth_required else {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 200:
                        print(f"   Response: {response_data}")
                except:
                    pass
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Raw response: {response.text[:200]}")
                
                self.failed_tests.append({
                    'name': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'endpoint': endpoint
                })

            return success, response.json() if response.content else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'name': name,
                'error': str(e),
                'endpoint': endpoint
            })
            return False, {}

    def test_health_endpoints(self):
        """Test basic health check endpoints"""
        print("\n" + "="*50)
        print("TESTING HEALTH ENDPOINTS")
        print("="*50)
        
        # Test root endpoint
        self.run_test("API Root", "GET", "", 200, auth_required=False)
        
        # Test health endpoint
        self.run_test("Health Check", "GET", "health", 200, auth_required=False)

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n" + "="*50)
        print("TESTING AUTH ENDPOINTS")
        print("="*50)
        
        # Test get current user
        self.run_test("Get Current User", "GET", "auth/me", 200)
        
        # Test logout
        self.run_test("Logout", "POST", "auth/logout", 200)

    def test_subscription_endpoints(self):
        """Test subscription endpoints"""
        print("\n" + "="*50)
        print("TESTING SUBSCRIPTION ENDPOINTS")
        print("="*50)
        
        # Test subscription status
        self.run_test("Subscription Status", "GET", "subscription/status", 200)
        
        # Test create checkout (should work but we won't complete payment)
        checkout_data = {"origin_url": "https://convo-pm-system.preview.emergentagent.com"}
        self.run_test("Create Checkout Session", "POST", "subscription/create-checkout", 200, checkout_data)

    def test_epic_endpoints(self):
        """Test epic CRUD operations"""
        print("\n" + "="*50)
        print("TESTING EPIC ENDPOINTS")
        print("="*50)
        
        # Test list epics
        success, epics_data = self.run_test("List Epics", "GET", "epics", 200)
        
        # Test get specific epic
        self.run_test("Get Epic", "GET", f"epics/{self.epic_id}", 200)
        
        # Test create new epic
        new_epic_data = {"title": f"Test Epic {datetime.now().strftime('%H%M%S')}"}
        success, create_response = self.run_test("Create Epic", "POST", "epics", 201, new_epic_data)
        
        if success and 'epic_id' in create_response:
            new_epic_id = create_response['epic_id']
            print(f"   Created epic with ID: {new_epic_id}")
            
            # Test get the newly created epic
            self.run_test("Get New Epic", "GET", f"epics/{new_epic_id}", 200)
            
            # Test delete the newly created epic
            self.run_test("Delete Epic", "DELETE", f"epics/{new_epic_id}", 200)

    def test_epic_workflow(self):
        """Test epic workflow endpoints (chat, proposals, etc.)"""
        print("\n" + "="*50)
        print("TESTING EPIC WORKFLOW")
        print("="*50)
        
        # Test chat endpoint (will fail without LLM config, but should return proper error)
        chat_data = {"content": "What should we focus on for this epic?"}
        self.run_test("Epic Chat (No LLM)", "POST", f"epics/{self.epic_id}/chat", 400, chat_data)
        
        # Test transcript
        self.run_test("Get Transcript", "GET", f"epics/{self.epic_id}/transcript", 200)
        
        # Test decisions
        self.run_test("Get Decisions", "GET", f"epics/{self.epic_id}/decisions", 200)
        
        # Test artifacts
        self.run_test("List Artifacts", "GET", f"epics/{self.epic_id}/artifacts", 200)

    def test_llm_provider_endpoints(self):
        """Test LLM provider management"""
        print("\n" + "="*50)
        print("TESTING LLM PROVIDER ENDPOINTS")
        print("="*50)
        
        # Test list LLM providers
        self.run_test("List LLM Providers", "GET", "llm-providers", 200)
        
        # Test validate API key (with invalid key - should fail gracefully)
        validate_data = {
            "provider": "openai",
            "api_key": "invalid-key-test",
            "model_name": "gpt-4"
        }
        self.run_test("Validate Invalid API Key", "POST", "llm-providers/validate", 200, validate_data)

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting JarlPM API Test Suite")
        print(f"Base URL: {self.base_url}")
        print(f"Session Token: {self.session_token}")
        
        # Run test suites
        self.test_health_endpoints()
        self.test_auth_endpoints()
        self.test_subscription_endpoints()
        self.test_epic_endpoints()
        self.test_epic_workflow()
        self.test_llm_provider_endpoints()
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"📊 Tests passed: {self.tests_passed}/{self.tests_run}")
        print(f"✅ Success rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ Failed tests ({len(self.failed_tests)}):")
            for test in self.failed_tests:
                if 'error' in test:
                    print(f"   • {test['name']}: {test['error']}")
                else:
                    print(f"   • {test['name']}: Expected {test['expected']}, got {test['actual']}")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test runner"""
    tester = JarlPMAPITester()
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())