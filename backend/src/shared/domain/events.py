"""
领域事件基类
写在这里是因为 event_handlers/中的base_event_handler需要识别领域事件共同的字段
而shared本身是独立于任何app的，因此写在这里才能让base_event_handler与所有app解耦
"""


from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional

@dataclass
class DomainEvent:
    """
    所有领域事件的基类
    自动提供时间戳和通用的数据转换接口
    
    注意：为了解决 Dataclass 继承中的默认参数顺序问题，
    我们这里不给 timestamp 设置默认值，而是设为 Optional 并在 post_init 中处理。
    但 Dataclass 规则是：如果有默认值的字段（包括 default=None），它必须在无默认值字段之后。
    
    如果基类 DomainEvent 有 `timestamp: datetime = None`，那么它就是一个带默认值的字段。
    子类如果定义 `start_url: str`（无默认值），就会报错 "non-default argument follows default argument"。
    
    唯一的解法是：
    1. 基类没有任何带默认值的字段。
    2. 或者利用 kw_only=True (Python 3.10+)。
    
    为了兼容性和简单性，我们强制要求 task_id 和 timestamp 都是必须的吗？
    或者，我们把 timestamp 设为无默认值，但在构造时如果不传会怎样？会报错。
    
    另一个方案：不使用继承的 dataclass 字段，而是手动定义基类，让子类去声明 dataclass。
    但这样失去了基类的类型提示优势。
    
    让我们尝试最干净的方案：基类不定义为 dataclass，或者基类字段不带默认值。
    如果 timestamp 不带默认值，每次创建事件都要传 datetime.now() 也很麻烦。
    
    折中方案：
    在基类中，timestamp 不带默认值。
    子类实例化时，必须传入 task_id 和 timestamp。
    为了方便，我们可以提供一个工厂方法或者辅助函数。
    
    或者，我们让 timestamp 是一个 InitVar？不，它需要被存储。
    
    让我们再试一次：利用 Python 3.10+ 的 kw_only=True。
    如果环境支持 3.10+ (我们看到是 Python 3.13)，这是最好的。
    """
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now, kw_only=True)

    @property
    def event_type(self) -> str:
        """默认使用类名作为事件类型"""
        return self.__class__.__name__

    @property
    def data(self) -> Dict[str, Any]:
        """将事件字段转换为字典，排除基类字段"""
        all_data = asdict(self)
        return {
            k: v for k, v in all_data.items() 
            if k not in ('task_id', 'timestamp')
        }
