from dataclasses import dataclass

@dataclass(frozen=True)
class QueuedUrl:
    url: str
    depth: int
    priority: int = 0