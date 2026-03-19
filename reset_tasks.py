import asyncio
import aiosqlite

DATABASE_PATH = "./boce_api.db"

async def check():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT id, domain, status, started_at FROM scan_batch_items WHERE status != 'success'")
        rows = await cursor.fetchall()
        print("--- Stuck/Pending Tasks ---")
        for r in rows:
            print(f"ID: {r[0]}, Domain: {r[1]}, Status: {r[2]}, Started: {r[3]}")
        
        # Reset stuck tasks
        await db.execute("UPDATE scan_batch_items SET status = 'pending' WHERE status = 'processing'")
        await db.commit()
        print("\n✅ Reset all 'processing' tasks to 'pending' for retry.")

if __name__ == "__main__":
    asyncio.run(check())
