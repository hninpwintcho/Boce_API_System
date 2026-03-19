import aiosqlite
import os

DATABASE_PATH = "./boce_api.db"

def get_db_connection():
    return aiosqlite.connect(DATABASE_PATH)

async def init_db():
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                key_secret TEXT UNIQUE NOT NULL,
                owner_name TEXT NOT NULL,
                daily_quota REAL DEFAULT 100.0,
                used_today REAL DEFAULT 0.0,
                is_active BOOLEAN DEFAULT 1,
                webhook_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS detection_tasks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                api_key_id TEXT, -- Traceability: which key requested this?
                provider TEXT DEFAULT 'boce',
                provider_task_id TEXT,
                status TEXT NOT NULL,
                priority INTEGER DEFAULT 10,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                regions_checked INTEGER DEFAULT 0,
                regions_available INTEGER DEFAULT 0,
                global_availability_percent REAL DEFAULT 0.0,
                anomaly_count INTEGER DEFAULT 0,
                error_code TEXT,
                error_message TEXT,
                webhook_url TEXT,
                FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority_created ON detection_tasks (status, priority DESC, created_at ASC)")
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS region_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                region TEXT NOT NULL,
                status_code INTEGER,
                response_ip TEXT,
                latency_ms REAL,
                available BOOLEAN,
                whitelist_match BOOLEAN,
                anomalies TEXT,
                FOREIGN KEY (task_id) REFERENCES detection_tasks (id)
            )
        """)
        await db.execute("""
            INSERT OR IGNORE INTO api_keys (id, key_secret, owner_name, daily_quota)
            VALUES ('admin', 'sk-test-points-safe-12345', 'Test Admin User', 1000.0)
        """)
        await db.commit()
