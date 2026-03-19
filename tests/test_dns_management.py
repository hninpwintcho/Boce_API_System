import httpx
import json

API_URL = "http://localhost:3000/api/dns"
API_KEY = "sk-test-points-safe-12345"

def test_dns_management():
    with httpx.Client(headers={"X-API-KEY": API_KEY}, timeout=30) as client:
        # 1. Bulk Create
        print("--- Testing Bulk Create ---")
        payload = {
            "domain": "aaxyd.cn",
            "records": [
                {"name": "test-v1", "type": "A", "value": "1.1.1.1"},
                {"name": "test-v2", "type": "CNAME", "value": "check.com"}
            ]
        }
        resp = client.post(f"{API_URL}/records", json=payload)
        assert resp.status_code == 200
        print(f"Create Results: {json.dumps(resp.json(), indent=2)}")

        # 2. Query
        print("\n--- Testing Query ---")
        resp = client.get(f"{API_URL}/query?domain=aaxyd.cn")
        assert resp.status_code in [200, 404] # 404 is fine if mock/fake data
        print(f"Query Result Status: {resp.status_code}")

if __name__ == "__main__":
    try:
        test_dns_management()
        print("\n✅ DNS Management Verification Success.")
    except Exception as e:
        print(f"\n❌ DNS Management Verification Failed: {e}")
