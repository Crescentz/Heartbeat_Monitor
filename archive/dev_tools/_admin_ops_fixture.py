from __future__ import annotations

import argparse
from dataclasses import dataclass

from flask import Flask, jsonify, request


@dataclass
class State:
    ok: bool = True


state = State(ok=True)
app = Flask(__name__)


@app.get("/health")
def health():
    if state.ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 503


@app.post("/toggle")
def toggle():
    body = request.get_json(silent=True) or {}
    if "ok" in body:
        state.ok = bool(body["ok"])
    else:
        state.ok = not state.ok
    return jsonify({"ok": state.ok})


@app.get("/")
def index():
    return jsonify({"service": "admin_ops_fixture", "ok": state.ok})


def main() -> int:
    parser = argparse.ArgumentParser(description="Local fixture for admin common ops regression.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18121)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
