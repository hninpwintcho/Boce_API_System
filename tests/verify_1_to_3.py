import httpx
import asyncio
import sqlite3

BASE_URL = "http://localhost:3000"
API_KEY = "sk-test-points-safe-12345"

async def verify_step_1_to_3():
    async with httpx.AsyncClient() as client:
        print("🟢 STEP 1: Basic Health Check")
        # Note: /docs is our main check since we don't have a / endpoint that returns {"status":"ok"}
        # But let's check /api/detect (which should return 405 or 401/403)
        resp = await client.get(f"{BASE_URL}/docs")
        if resp.status_code == 200:
            print("  ✅ Swagger Docs Alive")
        
        print("\n🟢 STEP 2: AUTH TEST")
        # ❌ No Key
        resp = await client.post(f"{BASE_URL}/api/detect", json={"url": "https://example.com"})
        print(f"  ❌ Without Key: {resp.status_code} (Expected 403)")
        
        # ✅ With Key
        resp = await client.post(
            f"{BASE_URL}/api/detect", 
            headers={"X-API-KEY": API_KEY},
            json={"url": "https://example.com"}
        )
        print(f"  ✅ With Key: {resp.status_code} (Expected 202)")
        task_id = resp.json().get("task_id")
        
        print("\n🟢 STEP 3: TASK FLOW TEST")
        if task_id:
            print(f"  Task Created: {task_id}")
            # Poll status
            for _ in range(5):
                await asyncio.sleep(2)
                resp = await client.get(
                    f"{BASE_URL}/api/detect/{task_id}",
                    headers={"X-API-KEY": API_KEY}
                )
                status = resp.json().get("status")
                print(f"  Polling Status: {status}")
                if status in ["completed", "failed"]:
                    break
            
            # DB Check
            conn = sqlite3.connect("boce_api.db")
            cursor = conn.cursor()
            cursor.execute("SELECT status, url FROM detection_tasks WHERE id=?", (task_id,))
            row = cursor.fetchone()
            if row:
                print(f"  ✅ DB Saved: {row[1]} is {row[0]}")
            conn.close()

if __name__ == "__main__":
    asyncio.run(verify_step_1_to_3())
