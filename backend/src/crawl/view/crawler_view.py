from flask import Blueprint, jsonify

bp = Blueprint("crawl", __name__, url_prefix="/api/crawl")

@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
