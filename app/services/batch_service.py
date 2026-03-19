import uuid
import logging
from typing import List, Optional
from app.database import get_db_connection

logger = logging.getLogger(__name__)

class BatchService:
    @staticmethod
    async def create_monitoring_batch(
        tenant_id: str,
        user_id: str,
        items_list: List[str],
        batch_type: str = "detection",
        priority: int = 10,
        webhook_url: Optional[str] = None
    ) -> str:
        batch_id = str(uuid.uuid4())
        
        async with get_db_connection() as db:
            # 1. Create the Batch Header
            await db.execute("""
                INSERT INTO scan_batches 
                (id, tenant_id, source_type, batch_type, total_items, pending_items, priority_default, webhook_url, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (batch_id, tenant_id, 'api', batch_type, len(items_list), len(items_list), priority, webhook_url, 'pending'))
            
            # 2. Prepare items for bulk insert
            task_data = []
            for item in items_list:
                task_id = str(uuid.uuid4())
                task_data.append((
                    task_id, batch_id, tenant_id, str(item), priority, 'pending'
                ))

            # 3. Chunked Insert 
            CHUNK_SIZE = 1000
            for i in range(0, len(task_data), CHUNK_SIZE):
                chunk = task_data[i:i + CHUNK_SIZE]
                await db.executemany(
                    "INSERT INTO scan_batch_items (id, batch_id, tenant_id, domain, priority, status) VALUES (?, ?, ?, ?, ?, ?)",
                    chunk
                )
            
            # 4. Update API Key usage/quota tracking
            await db.execute("UPDATE api_keys SET used_today = used_today + ? WHERE id = ?", (len(task_data), user_id))
            await db.commit()
            
        return batch_id

batch_service = BatchService()
