import httpx
import pytest
import json

API_URL = "http://localhost:3000/api/detect"
API_KEY = "sk-test-points-safe-12345"

def test_dns_enrichment():
    """
    Test that a single detection result contains the dns_context field.
    """
    with httpx.Client(headers={"X-API-KEY": API_KEY}, timeout=30) as client:
        payload = {
            "url": "https://555yy2.com",
            # We don't need ip_whitelist for this test
        }
        resp = client.post(API_URL, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        
        print(f"Response: {json.dumps(data, indent=2)}")
        
        assert "dns_context" in data
        # Even if the API call fails or is mocked to return None (if key is empty), 
        # the field should be present (possibly null).
        # In our case, we set a test key in .env, so it should try and likely fail 
        # (since the URL is fake) but return None gracefully.

if __name__ == "__main__":
    test_dns_enrichment()
    print("\n✅ DNS Enrichment Verification Complete.")
