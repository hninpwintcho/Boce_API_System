import asyncio
import aiosqlite
import httpx
import json
import uuid

# Configuration
DB_PATH = "./boce_api.db"
BASE_URL = "http://localhost:3000/api"

async def test_recovery_logic():
    print("--- Testing Point-Safe Recovery Logic (Multi-Provider) ---")
    
    # 1. Inject an "unfinished" task directly into the DB
    # Uses the NEW schema: provider_task_id and provider
    task_id = "recov-" + str(uuid.uuid4())[:8]
    provider_mock_id = "prov-id-" + str(uuid.uuid4())[:8]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO detection_tasks (id, url, provider_task_id, status, provider) VALUES (?, ?, ?, ?, ?)",
            (task_id, "https://robust.test", provider_mock_id, "created", "boce")
        )
        await db.commit()
    
    print(f"Injected task {task_id} (Boce) with provider ID {provider_mock_id}")
    
    # 2. Check if the server's Recovery Manager picked it up
    async with httpx.AsyncClient() as client:
        # Give a moment for the background task to start
        await asyncio.sleep(2)
        
        r = await client.get(f"{BASE_URL}/detect/{task_id}")
        data = r.json()
        print(f"Current Status: {data.get('status')}")
        
        if data.get("status") in ["processing", "completed"]:
            print("✅ SUCCESS: Recovery Manager resumed the task!")
        else:
            print(f"❌ FAILED: Status is {data.get('status')}")

async def test_batch_and_balance():
    async with httpx.AsyncClient(timeout=20) as client:
        # 1. Test Balance (Auditability)
        print("\n--- Testing GET /api/balance ---")
        r = await client.get(f"{BASE_URL}/balance")
        print("Balance Response:", r.json())

        # 2. Test Batch (Scale: 2000 Domains support)
        print("\n--- Testing POST /api/detect/batch ---")
        urls = [f"https://batch-test-{i}.com" for i in range(10)]
        r = await client.post(f"{BASE_URL}/detect/batch", json=urls)
        data = r.json()
        print(f"Queued {data.get('total_queued')} domains across providers.")
        
        # 3. Test History (Traceability)
        print("\n--- Testing GET /api/history ---")
        r = await client.get(f"{BASE_URL}/history")
        history = r.json()
        print(f"History contains {len(history.get('items', []))} items.")

if __name__ == "__main__":
    asyncio.run(test_recovery_logic())
    asyncio.run(test_batch_and_balance())
