from flask import render_template
from app.modules.fakenodo import fakenodo_bp


@fakenodo_bp.route("/fakenodo", methods=["GET"])
def home():
    return render_template("fakenodo/index.html")
