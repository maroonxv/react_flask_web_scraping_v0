from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class HttpResponse:
    url: str
    status_code: int
    headers: Dict[str, str]
    content: str
    content_type: str
    is_success: bool
    error_message: Optional[str] = None
