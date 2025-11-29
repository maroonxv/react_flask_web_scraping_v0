from flask import Flask
from crawl.view.crawler_view import bp as crawl_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(crawl_bp)
    return app
