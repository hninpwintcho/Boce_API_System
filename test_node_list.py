import asyncio
import httpx
import json

API_KEY = "2188d7561581d5b24cdcbc8b3961b6e3"

async def test_node_list():
    url = "https://api.boce.com/v3/node/list"
    params = {"key": API_KEY}
    
    print(f"Testing Node List with Key: {API_KEY}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, params=params)
            print("Status Code:", r.status_code)
            data = r.json()
            print("Response:", json.dumps(data, ensure_ascii=False, indent=2)[:500] + "...")
            if data.get("error_code") == 0:
                nodes = data.get("data", {}).get("list", [])
                print(f"Successfully fetched {len(nodes)} nodes.")
            else:
                print(f"Failed to fetch nodes. Error: {data.get('error')}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_node_list())
