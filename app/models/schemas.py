from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, AnyHttpUrl


# ─── Boce raw response schemas ────────────────────────────────────────────────

class BoceCreateTaskResponse(BaseModel):
    """Response from POST /v3/task/create/curl"""
    error_code: int
    error: str = ""
    data: Optional[dict] = None   # contains {"id": "<task-id>"}


class BoceRegionData(BaseModel):
    """One entry in the result list returned by GET /v3/task/curl/{id}"""
    node_id: int
    node_name: str                  # e.g. "河北电信"
    host: str                       # checked host
    http_code: int                  # HTTP status code
    remote_ip: str = ""             # resolved IP of the host (response IP)
    origin_ip: str = ""             # IP of the detection node itself
    ip_isp: str = ""                # ISP description, e.g. "电信"
    ip_region: str = ""             # full region string, e.g. "中国北京北京电信"
    time_total: float = 0.0         # total time in seconds
    download_time: float = 0.0
    time_connect: float = 0.0
    time_namelookup: float = 0.0
    error_code: int = 0
    error: str = ""


class BoceResultResponse(BaseModel):
    """Response from GET /v3/task/curl/{id}"""
    done: bool
    id: str = ""
    list: List[BoceRegionData] = []
    max_node: int = 0


# ─── Normalised / internal schemas ────────────────────────────────────────────

class AnomalyItem(BaseModel):
    region: str
    ip: str
    reason: str


class RegionResult(BaseModel):
    region: str           # node_name from Boce
    status_code: int      # http_code from Boce
    response_ip: str      # remote_ip from Boce (the server's IP seen by that node)
    latency_ms: float     # time_total * 1000
    available: bool
    whitelist_match: Optional[bool]
    anomalies: List[str] = []


class DetectionSummary(BaseModel):
    regions_checked: int
    regions_available: int
    global_availability_percent: float
    anomaly_count: int


class DetectionResult(BaseModel):
    success: bool = True
    url: str
    summary: DetectionSummary
    regions: List[RegionResult]
    anomaly_list: List[AnomalyItem]


# ─── API request / error schemas ──────────────────────────────────────────────

class DetectRequest(BaseModel):
    url: AnyHttpUrl
    ip_whitelist: Optional[List[str]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
