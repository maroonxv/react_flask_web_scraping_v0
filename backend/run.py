from src import create_app
from src.shared.logging_config import setup_logging

app = create_app()



from flask import Flask
from flask_socketio import SocketIO
from src.shared.logging_config import setup_logging
from src.shared.event_bus import EventBus
from src.shared.event_handlers.logging_handler import LoggingEventHandler
from src.shared.event_handlers.websocket_handler import WebSocketEventHandler
from src.crawl.view.crawler_view import inject_event_bus # 导入注入函数


# 创建 SocketIO 实例
socketio = SocketIO(app, cors_allowed_origins="*")

# ✅ 初始化日志系统（传入socketio实例）
setup_logging(socketio=socketio)

# 创建事件总线
event_bus = EventBus()

# 注册业务日志EventHandler
event_bus.subscribe(LoggingEventHandler())

# 注册WebSocket EventHandler（处理业务日志推送）
event_bus.subscribe(WebSocketEventHandler(socketio))

# 注入 EventBus 到 CrawlerService
inject_event_bus(event_bus)



if __name__ == '__main__':
    app.run(debug=True, port=5000)
