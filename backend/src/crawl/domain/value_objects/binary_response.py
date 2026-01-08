from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class BinaryResponse:
    """二进制 HTTP 响应值对象（不可变）"""
    url: str
    status_code: int
    headers: Dict[str, str]
    content: bytes
    content_type: str
    is_success: bool
    error_message: Optional[str] = None
