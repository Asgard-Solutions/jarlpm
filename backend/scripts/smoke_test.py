#!/usr/bin/env python3
"""
JarlPM Smoke Test Script

Runs essential health checks and endpoint verification:
1. Database connectivity
2. API health endpoint
3. Auth endpoints (login/signup)
4. Core feature endpoints
5. Integration status endpoints

Usage:
    python smoke_test.py [--base-url URL] [--verbose]
"""
import asyncio
import sys
import os
import argparse
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SmokeTestResult:
    """Result of a single smoke test."""
    
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.passed = False
        self.duration_ms: float = 0
        self.error: Optional[str] = None
        self.details: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "details": self.details
        }


class SmokeTestRunner:
    """Runs smoke tests against JarlPM API."""
    
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.results: List[SmokeTestResult] = []
        self.session_token: Optional[str] = None
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message if verbose mode is enabled."""
        if self.verbose or level == "ERROR":
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")
    
    async def run_test(
        self, 
        name: str, 
        category: str,
        test_func
    ) -> SmokeTestResult:
        """Run a single test and record the result."""
        result = SmokeTestResult(name, category)
        
        import time
        start = time.time()
        
        try:
            details = await test_func()
            result.passed = True
            result.details = details or {}
            self.log(f"✓ {name}", "PASS")
        except Exception as e:
            result.passed = False
            result.error = str(e)
            self.log(f"✗ {name}: {e}", "ERROR")
        
        result.duration_ms = (time.time() - start) * 1000
        self.results.append(result)
        return result
    
    async def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/health", timeout=10)
            response.raise_for_status()
            data = response.json()
            assert data.get("status") == "healthy", f"Unhealthy status: {data}"
            return data
    
    async def test_root_endpoint(self) -> Dict[str, Any]:
        """Test the root API endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/", timeout=10)
            response.raise_for_status()
            return response.json()
    
    async def test_login_invalid(self) -> Dict[str, Any]:
        """Test login endpoint with invalid credentials returns 401."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/login",
                json={"email": "nonexistent@test.com", "password": "wrongpassword"},
                timeout=10
            )
            assert response.status_code == 401, f"Expected 401, got {response.status_code}"
            return {"status_code": response.status_code}
    
    async def test_signup_validation(self) -> Dict[str, Any]:
        """Test signup endpoint validates input."""
        async with httpx.AsyncClient() as client:
            # Test with too short password
            response = await client.post(
                f"{self.base_url}/api/auth/signup",
                json={
                    "email": "test@test.com",
                    "password": "short",  # Too short
                    "name": "Test User"
                },
                timeout=10
            )
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            return {"status_code": response.status_code}
    
    async def test_test_login(self) -> Dict[str, Any]:
        """Test the test login endpoint for development."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/test-login",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract session token from cookies
            if "session_token" in response.cookies:
                self.session_token = response.cookies["session_token"]
            
            return {
                "user_id": data.get("user_id"),
                "subscription_status": data.get("subscription_status")
            }
    
    async def test_me_endpoint(self) -> Dict[str, Any]:
        """Test the /me endpoint returns user info."""
        if not self.session_token:
            raise Exception("No session token available")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/auth/me",
                cookies={"session_token": self.session_token},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            assert "user_id" in data, "Missing user_id in response"
            return {"user_id": data.get("user_id"), "email": data.get("email")}
    
    async def test_subscription_status(self) -> Dict[str, Any]:
        """Test the subscription status endpoint."""
        if not self.session_token:
            raise Exception("No session token available")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/subscription/status",
                cookies={"session_token": self.session_token},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
    
    async def test_integrations_status(self) -> Dict[str, Any]:
        """Test the integrations status endpoint."""
        if not self.session_token:
            raise Exception("No session token available")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/integrations/status",
                cookies={"session_token": self.session_token},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return {"providers_checked": list(data.keys()) if isinstance(data, dict) else []}
    
    async def test_delivery_context(self) -> Dict[str, Any]:
        """Test the delivery context endpoint."""
        if not self.session_token:
            raise Exception("No session token available")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/delivery-context",
                cookies={"session_token": self.session_token},
                timeout=10
            )
            response.raise_for_status()
            return {"has_context": response.json() is not None}
    
    async def test_initiatives_list(self) -> Dict[str, Any]:
        """Test the initiatives list endpoint."""
        if not self.session_token:
            raise Exception("No session token available")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/initiatives",
                cookies={"session_token": self.session_token},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return {"initiative_count": len(data) if isinstance(data, list) else 0}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all smoke tests."""
        self.log(f"Starting smoke tests against {self.base_url}")
        self.log("=" * 50)
        
        # Category: Health
        await self.run_test("API Health", "health", self.test_health_endpoint)
        await self.run_test("API Root", "health", self.test_root_endpoint)
        
        # Category: Auth (unauthenticated)
        await self.run_test("Login Invalid Credentials", "auth", self.test_login_invalid)
        await self.run_test("Signup Validation", "auth", self.test_signup_validation)
        
        # Category: Auth (authenticated via test login)
        await self.run_test("Test Login", "auth", self.test_test_login)
        
        if self.session_token:
            await self.run_test("Get Current User", "auth", self.test_me_endpoint)
            
            # Category: Features (require auth)
            await self.run_test("Subscription Status", "features", self.test_subscription_status)
            await self.run_test("Integrations Status", "features", self.test_integrations_status)
            await self.run_test("Delivery Context", "features", self.test_delivery_context)
            await self.run_test("Initiatives List", "features", self.test_initiatives_list)
        
        # Generate summary
        self.log("=" * 50)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "base_url": self.base_url,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "N/A",
            "results": [r.to_dict() for r in self.results],
            "failed_tests": [r.name for r in self.results if not r.passed]
        }
        
        if failed > 0:
            self.log(f"FAILED: {failed}/{total} tests failed", "ERROR")
        else:
            self.log(f"PASSED: All {total} tests passed", "INFO")
        
        return summary


async def run_smoke_tests(base_url: str, verbose: bool = False) -> Dict[str, Any]:
    """Run smoke tests and return results."""
    runner = SmokeTestRunner(base_url, verbose)
    return await runner.run_all_tests()


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(description="JarlPM Smoke Test Script")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_TEST_URL", "http://localhost:8001"),
        help="Base URL of the JarlPM API"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    # Run tests
    results = asyncio.run(run_smoke_tests(args.base_url, args.verbose))
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # Print summary
        print(f"\n{'='*50}")
        print(f"Smoke Test Summary")
        print(f"{'='*50}")
        print(f"Base URL: {results['base_url']}")
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Success Rate: {results['success_rate']}")
        
        if results['failed_tests']:
            print(f"\nFailed Tests:")
            for test in results['failed_tests']:
                print(f"  - {test}")
    
    # Exit with appropriate code
    sys.exit(0 if results['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
