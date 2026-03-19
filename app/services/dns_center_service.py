import httpx
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class DNSCenterService:
    """
    Integration with the Senior's DNS Center Skill.
    Provides authoritative DNS record lookups.
    """
    def __init__(self):
        self.base_url = settings.DNS_CENTER_API_URL.rstrip('/')
        self.api_key = settings.DNS_CENTER_API_KEY

    async def query_dns(self, domain: str) -> Optional[dict]:
        """
        Fetch DNS records for a domain from the DNS Center.
        """
        domain = domain.strip()
        if not self.api_key:
            logger.warning("DNS_CENTER_API_KEY not set. Skipping DNS enrichment.")
            return None

        url = f"{self.base_url}/dns/query"
        params = {"domain": domain}
        headers = {"X-API-KEY": self.api_key}

        logger.info(f"🔍 Querying DNS Center for {domain}")
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # Expecting data format based on Senior's log:
                    # { "status": "ACTIVE", "provider": "alibaba", "records": [...], ... }
                    return data
                else:
                    logger.warning(f"⚠️ DNS Center returned {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"❌ Failed to reach DNS Center: {e}")
        
        return None

    async def create_records(self, domain: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create DNS records. 
        Senior-Log Fix: We loop through records to send single-record requests 
        because the bulk 'records' array currently has metadata issues.
        """
        results = []
        for rec in records:
            url = f"{self.base_url}/dns/records"
            # Payload tailored to Senior's discovery: {"record": {...}}
            payload = {
                "action": "create",
                "domain": domain,
                "record": rec
            }
            headers = {"X-API-KEY": self.api_key}
            
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    res_data = resp.json() if resp.status_code < 300 else {"error": resp.text, "code": resp.status_code}
                    results.append({"name": rec.get("name"), "result": res_data})
            except Exception as e:
                results.append({"name": rec.get("name"), "error": str(e)})
        
        return results

    async def update_record(self, record_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific record by ID."""
        url = f"{self.base_url}/dns/records/{record_id}"
        payload = {"action": "update", "record": updates}
        headers = {"X-API-KEY": self.api_key}
        
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(url, json=payload, headers=headers)
            return resp.json()

    async def delete_record(self, record_id: str) -> Dict[str, Any]:
        """Delete a specific record by ID."""
        url = f"{self.base_url}/dns/records/{record_id}"
        headers = {"X-API-KEY": self.api_key}
        
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(url, headers=headers)
            return resp.json()

dns_center_service = DNSCenterService()
