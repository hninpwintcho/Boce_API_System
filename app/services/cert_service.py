import socket
import ssl
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CertService:
    @staticmethod
    async def get_cert_info(domain: str) -> Optional[Dict[str, Any]]:
        domain = domain.strip()
        try:
            # Clean domain (remove protocol)
            if "://" in domain:
                domain = domain.split("://")[1]
            if "/" in domain:
                domain = domain.split("/")[0]

            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    if not cert:
                        return None

                    # Parse 'notAfter' (Expiry Date)
                    # Example format: 'Mar 17 23:59:59 2026 GMT'
                    expiry_str = cert.get('notAfter')
                    expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                    
                    days_remaining = (expiry_date - datetime.utcnow()).days
                    
                    # Extract Issuer
                    issuer = dict(x[0] for x in cert.get('issuer', ()))
                    common_name = issuer.get('commonName', 'Unknown')

                    return {
                        "domain": domain,
                        "issuer": common_name,
                        "expiry_date": expiry_date.isoformat(),
                        "days_remaining": days_remaining,
                        "is_valid": days_remaining > 0,
                        "is_critical": days_remaining < 7
                    }
        except Exception as e:
            logger.error(f"Failed to fetch cert for {domain}: {e}")
            return {
                "domain": domain,
                "error": str(e),
                "is_valid": False,
                "days_remaining": -1
            }

cert_service = CertService()
