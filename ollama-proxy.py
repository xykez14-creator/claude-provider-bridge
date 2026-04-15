#!/usr/bin/env python3
"""Ollama Cloud proxy — converts Ollama responses to Anthropic format."""
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests as req
import json
import os

load_dotenv()

app = Flask(__name__)

OLLAMA_KEY = os.getenv("OLLAMA_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "https://ollama.com/api/chat")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "4000"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "glm-5.1")


@app.route("/v1/chat/completions", methods=["POST"])
@app.route("/v1/messages", methods=["POST"])
@app.route("/v1/messages/", methods=["POST"])
def chat():
    try:
        data = request.json or {}
    except:
        data = {}

    model = data.get("model", OLLAMA_MODEL)

    messages = data.get("messages", [])
    ollama_msgs = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            text = ""
            for c in content:
                if isinstance(c, dict):
                    if c.get("type") == "text":
                        text += c.get("text", "")
            content = text
        ollama_msgs.append({"role": msg.get("role", "user"), "content": content})

    try:
        resp = req.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": ollama_msgs, "stream": False},
            headers={"Authorization": f"Bearer {OLLAMA_KEY}", "Content-Type": "application/json"},
            timeout=60,
        )

        if resp.status_code == 200:
            result = resp.json()
            content = result.get("message", {}).get("content", "")

            # Exact Anthropic API format
            return jsonify({
                "id": f"msg_{abs(hash(model))}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": content}],
                "model": model,
                "created": 1234567890,
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": sum(len(m.get("content", "")) for m in messages),
                    "output_tokens": len(content.split()),
                },
            })
        else:
            return jsonify({"error": {"type": "invalid_request_error", "message": resp.text}}), resp.status_code
    except Exception as e:
        return jsonify({"error": {"type": "invalid_request_error", "message": str(e)}}), 500


@app.route("/")
@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/v1/models")
@app.route("/v1/models/")
def models():
    return jsonify({
        "data": [{
            "id": f"ollama/{OLLAMA_MODEL}:cloud",
            "object": "model",
            "created": 1234567890,
            "owned_by": "ollama",
            "permission": [],
        }]
    })


if __name__ == "__main__":
    print(f"Ollama proxy starting on port {OLLAMA_PORT} (model: {OLLAMA_MODEL})")
    app.run(host="0.0.0.0", port=OLLAMA_PORT, threaded=True)
