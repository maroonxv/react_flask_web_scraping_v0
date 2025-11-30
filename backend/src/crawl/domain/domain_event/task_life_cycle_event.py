from dataclasses import dataclass, field
from datetime import datetime
from src.shared.domain.events import DomainEvent

@dataclass
class TaskCreatedEvent(DomainEvent):
    start_url: str
    strategy: str
    max_depth: int
    max_pages: int
    request_interval: float
    allow_domains: list

@dataclass
class TaskStartedEvent(DomainEvent):
    pass

@dataclass
class TaskPausedEvent(DomainEvent):  
    pass

@dataclass
class TaskResumedEvent(DomainEvent):
    pass

@dataclass
class TaskStoppedEvent(DomainEvent):
    reason: str = "用户手动停止"

@dataclass
class TaskCompletedEvent(DomainEvent):
    total_pages: int
    total_pdfs: int
    elapsed_time: float

@dataclass
class TaskFailedEvent(DomainEvent):
    error_message: str
    stack_trace: str = ""
