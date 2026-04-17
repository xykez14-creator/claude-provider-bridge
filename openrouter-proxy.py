#!/usr/bin/env python3
"""OpenRouter proxy — converts OpenAI format to Anthropic format."""

from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests as req
import json
import os

load_dotenv()

app = Flask(__name__)

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
OPENROUTER_URL = os.getenv(
    "OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"
)
OPENROUTER_PORT = int(os.getenv("OPENROUTER_PORT", "4001"))
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"
)


@app.route("/v1/chat/completions", methods=["POST"])
@app.route("/v1/messages", methods=["POST"])
@app.route("/v1/messages/", methods=["POST"])
def chat():
    try:
        data = request.json or {}
    except:
        data = {}

    model = data.get("model", OPENROUTER_MODEL)
    mapped_model = OPENROUTER_MODEL

    messages = data.get("messages", [])
    # Convert Anthropic content array to string if needed
    clean_msgs = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            text = ""
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text += c.get("text", "")
            content = text
        clean_msgs.append({"role": msg.get("role", "user"), "content": content})

    try:
        resp = req.post(
            OPENROUTER_URL,
            json={"model": mapped_model, "messages": clean_msgs, "max_tokens": 4096},
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://openrouter.ai",
                "X-Title": "ClaudeCode",
            },
            timeout=60,
        )

        if resp.status_code == 200:
            result = resp.json()
            # Extract from OpenAI format
            choice = result.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")

            return jsonify(
                {
                    "id": result.get("id", "msg_1"),
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": content}],
                    "model": model,
                    "created": result.get("created", 1234567890),
                    "stop_reason": choice.get("finish_reason", "end_turn"),
                    "usage": result.get(
                        "usage", {"input_tokens": 10, "output_tokens": 20}
                    ),
                }
            )
        else:
            return jsonify(
                {"error": {"type": "invalid_request_error", "message": resp.text}}
            ), resp.status_code
    except Exception as e:
        return jsonify(
            {"error": {"type": "invalid_request_error", "message": str(e)}}
        ), 500


@app.route("/")
@app.route("/health")
def health():
    return jsonify({"status": "ok", "provider": "openrouter"})


@app.route("/v1/models")
@app.route("/v1/models/")
def models():
    return jsonify(
        {
            "data": [
                {
                    "id": OPENROUTER_MODEL,
                    "object": "model",
                    "created": 1234567890,
                    "owned_by": "openrouter",
                },
            ]
        }
    )


if __name__ == "__main__":
    print(
        f"OpenRouter proxy starting on port {OPENROUTER_PORT} (model: {OPENROUTER_MODEL})"
    )
    app.run(host="0.0.0.0", port=OPENROUTER_PORT, threaded=True)
