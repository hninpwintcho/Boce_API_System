import aiosqlite
import os

DATABASE_PATH = "./boce_api.db"

def get_db_connection():
    return aiosqlite.connect(DATABASE_PATH)

async def init_db():
    async with get_db_connection() as db:
        # 1. Tenants Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Enhanced API Keys Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                key_secret TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                daily_quota REAL DEFAULT 100.0,
                used_today REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active',
                rate_limit INTEGER DEFAULT 60,
                webhook_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)

        # 3. Scan Batches Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_batches (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                batch_code TEXT,
                source_type TEXT DEFAULT 'api',
                batch_type TEXT DEFAULT 'detection', -- 'detection' or 'cert'
                total_items INTEGER DEFAULT 0,
                pending_items INTEGER DEFAULT 0,
                processing_items INTEGER DEFAULT 0,
                success_items INTEGER DEFAULT 0,
                failed_items INTEGER DEFAULT 0,
                priority_default INTEGER DEFAULT 10,
                webhook_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)

        # 4. Scan Batch Items (Detailed Tasks)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_batch_items (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                priority INTEGER DEFAULT 10,
                status TEXT DEFAULT 'pending',
                provider_task_id TEXT,
                retry_count INTEGER DEFAULT 0,
                result_summary TEXT, -- JSONB equivalent in SQLite
                error_code TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (batch_id) REFERENCES scan_batches(id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_batch_items_priority ON scan_batch_items (status, priority DESC, created_at ASC)")

        # 5. Webhook Deliveries Table (Step 9)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                item_id TEXT,
                url TEXT NOT NULL,
                event TEXT NOT NULL, -- batch.completed, item.completed
                payload TEXT,
                status_code INTEGER,
                response_body TEXT,
                retry_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- pending, sent, failed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Legacy Support / Migration for detection_tasks (optional, but keeping it for now)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS detection_tasks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                api_key_id TEXT,
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

        # Default data for testing
        await db.execute("INSERT OR IGNORE INTO tenants (id, name) VALUES ('default_tenant', 'Default Business')")
        await db.execute("""
            INSERT OR IGNORE INTO api_keys (id, tenant_id, key_secret, name, daily_quota)
            VALUES ('admin', 'default_tenant', 'sk-test-points-safe-12345', 'Test Admin Key', 1000.0)
        """)
        await db.commit()
