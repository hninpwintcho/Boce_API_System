import asyncio
import aiosqlite

DATABASE_PATH = "./boce_api.db"

async def migrate():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            print("Trying to add 'batch_type' to 'scan_batches'...")
            await db.execute("ALTER TABLE scan_batches ADD COLUMN batch_type TEXT DEFAULT 'detection'")
            await db.commit()
            print("✅ Successfully added 'batch_type' column.")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Column already exists, skipping.")
            else:
                print(f"❌ Migration Error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
