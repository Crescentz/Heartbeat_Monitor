from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, jsonify, request


@dataclass
class State:
    ok: bool = True


state = State(ok=True)
app = Flask(__name__)


@app.get("/")
def index():
    if state.ok:
        return "<html><body><h3>LOCAL TEST SERVICE OK</h3></body></html>"
    return "<html><body><h3>LOCAL TEST SERVICE DOWN</h3></body></html>", 503


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=18080, debug=False, use_reloader=False)

