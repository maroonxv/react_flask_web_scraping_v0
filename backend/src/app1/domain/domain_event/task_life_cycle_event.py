from dataclasses import dataclass
import datetime
from dataclasses import field

class BaseLifeCycleEvent:
    task_id: str

@dataclass
class TaskCreatedEvent(BaseLifeCycleEvent):
    start_url: str
    strategy: str
    max_depth: int
    max_pages: int
    request_interval: float
    allow_domains: list

@dataclass
class TaskStartedEvent(BaseLifeCycleEvent):
    start_time: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class TaskPausedEvent(BaseLifeCycleEvent):  
    pause_time: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class TaskResumedEvent(BaseLifeCycleEvent):
    resume_time: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class TaskCompletedEvent(BaseLifeCycleEvent):
    complete_time: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class TaskFailedEvent(BaseLifeCycleEvent):
    fail_time: datetime.datetime = field(default_factory=datetime.datetime.now)
