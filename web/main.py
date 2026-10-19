import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from setu.solver.backend import log_file  # noqa: E402
from flask import Flask  # noqa: E402

import routes  # noqa: E402


# the Flask app with its static files and routes
def create_app():
    app = Flask(__name__, static_folder="static")
    routes.register(app)
    return app


if __name__ == "__main__":
    log_file(os.devnull)
    create_app().run(port=int(os.environ.get("PORT", 5000)), threaded=True)
