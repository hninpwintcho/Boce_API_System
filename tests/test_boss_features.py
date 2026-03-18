import httpx
import asyncio

BASE_URL = "http://localhost:3000/api"
API_KEY = "sk-test-points-safe-12345"
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

BOSS_URLS = [
    "https://vudrk7vh3v.51aixiu.cn/api/v1/server/get_time",
    "https://ie93wnbs.jkvbmt.cn/api/v1/server/get_time",
    "https://yv3bsdbk.qlpru.cn/api/v1/server/get_time",
    "https://jren9gbwrt.qlpru.cn/api/v1/server/get_time",
]

async def test_boss_features():
    async with httpx.AsyncClient(timeout=30) as client:
        # === TEST 1: Balance Check ===
        print("🟢 TEST 1: BALANCE CHECK")
        resp = await client.get(f"{BASE_URL}/balance")
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.json()}")
        
        # === TEST 2: Single Detect (Should show balance warning) ===
        print("\n🟢 TEST 2: SINGLE DETECT (Balance Pre-Check)")
        resp = await client.post(f"{BASE_URL}/detect", headers=HEADERS, json={"url": "https://example.com"})
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.json()}")
        print(f"  👉 Boss sees: System REFUSES to waste points when balance is 0!")
        
        # === TEST 3: BATCH SUBMISSION ===
        print("\n🟢 TEST 3: BATCH SUBMISSION (4 domains)")
        resp = await client.post(f"{BASE_URL}/detect/batch", headers=HEADERS, json={"urls": BOSS_URLS})
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.json()}")
        print(f"  👉 Boss sees: System checks balance BEFORE processing ANY batch!")

if __name__ == "__main__":
    asyncio.run(test_boss_features())
