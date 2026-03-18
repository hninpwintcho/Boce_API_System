import httpx
import asyncio
import json

BASE_URL = "http://localhost:3000/api"
API_KEY = "sk-test-points-safe-12345"

URLS = [
    "https://vudrk7vh3v.51aixiu.cn/api/v1/server/get_time",
    "https://ie93wnbs.jkvbmt.cn/api/v1/server/get_time",
    "https://yv3bsdbk.qlpru.cn/api/v1/server/get_time",
    "https://jren9gbwrt.qlpru.cn/api/v1/server/get_time",
    "https://mbr3bdscv.xycbu.cn/api/v1/server/get_time",
    "https://dvd33bvd.xycbu.cn/api/v1/server/get_time",
    "https://veiih3bv.xycbu.cn/api/v1/server/get_time",
    "https://sdgb04ehj.jkvbmt.cn/api/v1/server/get_time"
]

async def check_list():
    async with httpx.AsyncClient() as client:
        print(f"🚀 Submitting {len(URLS)} domains to the Proxy...")
        
        tasks = []
        for url in URLS:
            tasks.append(client.post(
                f"{BASE_URL}/detect",
                headers={"X-API-KEY": API_KEY},
                json={"url": url}
            ))
        
        responses = await asyncio.gather(*tasks)
        
        print("\n--- 📋 Submission Results ---")
        for i, resp in enumerate(responses):
            if resp.status_code == 202:
                data = resp.json()
                print(f"✅ [{i+1}] {URLS[i]} -> Task ID: {data['task_id']}")
            else:
                print(f"❌ [{i+1}] {URLS[i]} -> Error: {resp.status_code} {resp.text}")

        print("\n💡 Tip: You can now see these in real-time at http://localhost:3000/dashboard")

if __name__ == "__main__":
    asyncio.run(check_list())
