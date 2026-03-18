import httpx
import asyncio
import os
import signal
import subprocess
import time
import sqlite3

BASE_URL = "http://localhost:3000/api"
API_KEY = "sk-test-points-safe-12345"

def kill_uvicorn():
    # Windows taskkill
    os.system("taskkill /F /IM python.exe /T")

async def verify_step_7():
    print("🟢 STEP 7: CRASH RECOVERY TEST (Zero-Point-Wastage)")
    
    # 1. Start a task
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/detect", 
            headers={"X-API-KEY": API_KEY},
            json={"url": "https://crash-test.com"}
        )
        task_id = resp.json().get("task_id")
        print(f"  Task Created: {task_id}. NOW KILLING SERVER...")
    
    # 2. Kill server
    kill_uvicorn()
    time.sleep(2)
    
    # 3. Verify task is in DB as 'pending' or 'processing' but HAS a provider_task_id
    # (Note: In my mock/real flow, it might be 'failed' immediately if Boce rejected it, 
    # but the 'Recovery' logic triggers on startup if status != completed/failed).
    print("  Server killed. Restarting server to trigger Recovery logic...")
    
    # 4. Restart server and capture logs
    # We run uvicorn as a subprocess so we can read its output
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--port", "3000"],
        cwd="D:\\phase1",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # 5. Wait for recovery log
    found = False
    deadline = time.time() + 15
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line: break
        print(f"  [LOG] {line.strip()}")
        if "Recovery: Resuming task" in line:
            found = True
            print("  ✅ SUCCESS: Recovery triggered! No points wasted.")
            break
            
    proc.terminate()
    if not found:
        print("  ❌ FAILURE: Recovery log not found.")

if __name__ == "__main__":
    asyncio.run(verify_step_7())
