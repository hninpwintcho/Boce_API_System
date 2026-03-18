import httpx
import asyncio
import sqlite3

BASE_URL = "http://localhost:3000/api"
API_KEY = "sk-test-points-safe-12345"

async def verify_8_9_10():
    async with httpx.AsyncClient() as client:
        print("🟢 STEP 8: ANOMALY TEST (Invalid Domain)")
        # This will fail Boce task creation but should be handled gracefully by the proxy
        resp = await client.post(f"{BASE_URL}/detect", headers={"X-API-KEY": API_KEY}, json={"url": "https://this-domain-does-not-exist-999.com"})
        print(f"  Anomaly Submission: {resp.status_code} {resp.json()}")

        print("\n🟢 STEP 9: HIGH LOAD TEST (10 Requests)")
        tasks = []
        for i in range(10):
            tasks.append(client.post(f"{BASE_URL}/detect", headers={"X-API-KEY": API_KEY}, json={"url": f"https://load-test-{i}.com"}))
        
        results = await asyncio.gather(*tasks)
        success_count = len([r for r in results if r.status_code == 202])
        print(f"  Load Test: {success_count}/10 tasks queued successfully.")

        print("\n🟢 STEP 10: TRACEABILITY TEST (DB Audit)")
        conn = sqlite3.connect("boce_api.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, url, api_key_id, provider FROM detection_tasks ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"  ✅ Audit Record Found:")
            print(f"     Task ID: {row[0]}")
            print(f"     URL: {row[1]}")
            print(f"     Key ID: {row[2]}")
            print(f"     Provider: {row[3]}")
        conn.close()

if __name__ == "__main__":
    asyncio.run(verify_8_9_10())
