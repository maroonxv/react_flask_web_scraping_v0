from flask import Flask
from flask_cors import CORS
from .crawl.view.crawler_view import bp as crawl_bp
from .shared.db_manager import db_session

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()
        
    app.register_blueprint(crawl_bp)
    return app
