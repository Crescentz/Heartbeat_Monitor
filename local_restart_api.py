from __future__ import annotations

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
    return jsonify({"service": "local_restart_api", "ok": state.ok})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=18081, debug=False, use_reloader=False)

