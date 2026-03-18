import httpx
import asyncio
import sqlite3

BASE_URL = "http://localhost:3000/api"
API_KEY = "sk-test-points-safe-12345"

async def verify_step_4_and_6():
    async with httpx.AsyncClient() as client:
        # --- STEP 4: BOCE INTEGRATION (BAIDU) ---
        print("🟢 STEP 4: BOCE INTEGRATION CHECK (baidu.com)")
        resp = await client.post(
            f"{BASE_URL}/detect", 
            headers={"X-API-KEY": API_KEY},
            json={"url": "https://www.baidu.com"}
        )
        print(f"  Submission: {resp.status_code} {resp.json().get('task_id')}")
        
        # --- STEP 6: QUOTA TEST ---
        print("\n🟢 STEP 6: QUOTA ENFORCEMENT TEST")
        # 1. Create a key with quota = 1
        QUOTA_KEY = "sk-low-quota-999"
        conn = sqlite3.connect("boce_api.db")
        conn.execute("INSERT OR IGNORE INTO api_keys (id, key_secret, owner_name, daily_quota, used_today) VALUES (?, ?, 'QuotaGuy', 1.0, 0.0)", 
                    ("quota-user", QUOTA_KEY, ))
        conn.commit()
        conn.close()

        # 2. Use it once (Request 1)
        resp1 = await client.post(f"{BASE_URL}/detect", headers={"X-API-KEY": QUOTA_KEY}, json={"url": "https://example1.com"})
        print(f"  Request 1: {resp1.status_code} (Expected 202)")
        
        # 3. Use it again (Request 2)
        resp2 = await client.post(f"{BASE_URL}/detect", headers={"X-API-KEY": QUOTA_KEY}, json={"url": "https://example2.com"})
        print(f"  Request 2: {resp2.status_code} {resp2.json().get('error', '')} (Expected 403 / QUOTA_EXCEEDED)")

if __name__ == "__main__":
    asyncio.run(verify_step_4_and_6())
