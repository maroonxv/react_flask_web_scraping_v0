
class EventBus:
    """
    事件总线 - 用于发布和订阅事件
    """

    def subscribe(self, event_type: str, handler):
        """
        订阅事件
        
        参数:
            event_type: 事件类型
            handler: 事件处理函数
        """
        ...

    def publish(self, event_type: str, event_data: dict):
        """
        发布事件
        
        参数:
            event_type: 事件类型
            event_data: 事件数据
        """
        ...
