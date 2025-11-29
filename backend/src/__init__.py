from flask import Flask
from flask_cors import CORS
from .crawl.view.crawler_view import bp as crawl_bp

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes
    app.register_blueprint(crawl_bp)
    return app
