import httpx
import time
import uuid

API_URL = "http://localhost:3000/api/detect"
API_KEY = "sk-test-points-safe-12345"

def test_platform_flow():
    with httpx.Client(headers={"X-API-KEY": API_KEY}, timeout=30) as client:
        # 1. Submit Batch
        print("--- Submitting Batch ---")
        batch_payload = {
            "urls": ["https://google.com", "https://github.com"],
            "priority": 50,
            "webhook_url": "https://httpbin.org/post"
        }
        resp = client.post(f"{API_URL}/batch", json=batch_payload)
        if resp.status_code != 202:
            print(f"FAILED to submit: {resp.status_code} - {resp.text}")
        assert resp.status_code == 202
        batch_id = resp.json()["batch_id"]
        print(f"Batch Created: {batch_id}")

        # 2. Check Progress (Immediate)
        print("--- Checking Progress (Immediate) ---")
        resp = client.get(f"{API_URL}/batch/{batch_id}")
        assert resp.status_code == 200
        print(f"Progress: {resp.json()['progress_percent']}%")

        # 3. Check Stats (Immediate)
        print("--- Checking Stats (Immediate) ---")
        resp = client.get(f"{API_URL}/batch/{batch_id}/stats")
        assert resp.status_code == 200
        print(f"Stats: {resp.json()['counts']}")

if __name__ == "__main__":
    try:
        test_platform_flow()
        print("\n✅ Verification SUCCESS: Platform flow works.")
    except Exception as e:
        print(f"\n❌ Verification FAILED: {e}")
