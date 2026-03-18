import asyncio
import httpx
import json
import time

BASE_URL = "http://localhost:3000/api"

async def verify_phase2():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Test /api/detect (Enqueue)
        print("--- Testing POST /api/detect ---")
        payload = {"url": "https://www.baidu.com"}
        r = await client.post(f"{BASE_URL}/detect", json=payload)
        print("Status Code:", r.status_code)
        data = r.json()
        print("Response:", json.dumps(data, indent=2))
        
        task_id = data.get("task_id")
        if not task_id:
            print("FAILED: No task_id returned")
            return

        # 2. Test /api/detect/{task_id} (Poll)
        print(f"\n--- Testing GET /api/detect/{task_id} ---")
        for i in range(10):
            r = await client.get(f"{BASE_URL}/detect/{task_id}")
            data = r.json()
            status = data.get("status")
            print(f"Poll {i+1}: Status = {status}")
            
            if status == "completed":
                print("SUCCESS: Task completed!")
                print("Result Summary:", json.dumps(data.get("summary"), indent=2))
                break
            elif status == "failed":
                print("FAILED: Task failed!")
                print("Error:", data.get("message"))
                break
            
            await asyncio.sleep(3)

        # 3. Test /api/history
        print("\n--- Testing GET /api/history ---")
        r = await client.get(f"{BASE_URL}/history")
        data = r.json()
        print("History Items:", len(data.get("items", [])))
        if len(data.get("items", [])) > 0:
            print("First Item:", json.dumps(data.get("items")[0], indent=2))

if __name__ == "__main__":
    asyncio.run(verify_phase2())
