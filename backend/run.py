from src import create_app
from src.shared.logging_config import setup_logging

app = create_app()



from flask import Flask
from flask_socketio import SocketIO
from src.shared.logging_config import setup_logging
from src.shared.event_bus import EventBus
from src.shared.event_handlers.logging_handler import LoggingEventHandler
from src.shared.event_handlers.websocket_handler import WebSocketEventHandler
from src.crawl.view.crawler_view import inject_event_bus, init_realtime_logging # 导入注入函数
from flask_socketio import join_room

# 创建 SocketIO 实例
socketio = SocketIO(app, cors_allowed_origins="*")

# 添加 join 事件处理
@socketio.on('join', namespace='/crawl')
def on_join(data):
    room = data.get('room')
    if room:
        join_room(room)
        print(f"Client joined room: {room}")

# ✅ 初始化日志系统（传入socketio实例）
# setup_logging(socketio=socketio) # 这一步已经在 init_realtime_logging 中做了部分，或者我们需要保留它？
# setup_logging 主要配置 logging 模块。init_realtime_logging 配置 View 层需要的 handler。
# 建议保留 setup_logging，但 init_realtime_logging 也会做类似的事。
# 让我们保留 setup_logging，然后调用 init_realtime_logging。
setup_logging(socketio=socketio)

# 创建事件总线
event_bus = EventBus()

# 注册业务日志EventHandler
logging_handler = LoggingEventHandler()
event_bus.subscribe_to_all(logging_handler.handle)

# 注册WebSocket EventHandler（处理业务日志推送）
# 这部分逻辑已经移到了 init_realtime_logging，但保留也无妨，只要不重复订阅
# 为了避免重复，我们可以移除这里的 WebSocketEventHandler 订阅，改用 init_realtime_logging
# event_bus.subscribe(WebSocketEventHandler(socketio))

# 注入 EventBus 到 CrawlerService 并初始化实时日志
inject_event_bus(event_bus)
init_realtime_logging(socketio, event_bus)



if __name__ == '__main__':
    app.run(debug=True, port=5000)
