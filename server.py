#!/usr/bin/env python3
"""
Distributed Temperature Monitoring -- laptop server.

- POST /api/temperature   : receives readings from the Pi (JSON)
- GET  /                  : serves the medical dashboard
- WebSocket               : pushes new readings to every connected browser

Run:
    pip install -r requirements.txt
    python server.py
"""

import logging
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

# -------------------------------------------------------------------
# App + SocketIO
# -------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "demo-secret-not-for-production"
# threading async_mode keeps install simple (no eventlet/gevent needed)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Quiet Werkzeug's per-request logs so the console stays readable
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# Keep the last ~5 minutes of readings (at 1 Hz) so newly connected
# browsers can render the existing chart immediately.
HISTORY_MAX = 300
history = deque(maxlen=HISTORY_MAX)
latest = {"temperature_c": None, "timestamp": None, "patient_id": None}


def to_dashboard_payload(reading):
    t_c = reading["temperature_c"]
    ts = reading["timestamp"]
    return {
        "temperature_c": t_c,
        "temperature_f": round(t_c * 9 / 5 + 32, 2),
        "timestamp": ts,
        "time_str": datetime.fromtimestamp(ts).strftime("%H:%M:%S"),
        "patient_id": reading.get("patient_id", "—"),
        "sensor_id": reading.get("sensor_id", "—"),
    }


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/temperature", methods=["POST"])
def receive_temperature():
    data = request.get_json(silent=True) or {}
    if "temperature_c" not in data:
        return jsonify({"error": "missing temperature_c"}), 400

    reading = {
        "temperature_c": float(data["temperature_c"]),
        "timestamp": float(data.get("timestamp", datetime.now().timestamp())),
        "patient_id": data.get("patient_id", "PT-0427"),
        "sensor_id": data.get("sensor_id", "DS18B20"),
    }
    history.append(reading)
    latest.update(reading)

    payload = to_dashboard_payload(reading)
    socketio.emit("temperature_update", payload)
    print(f"[{payload['time_str']}] {payload['temperature_c']:.2f}°C  ({payload['patient_id']})")
    return jsonify({"status": "ok"}), 200


@app.route("/api/history")
def get_history():
    """New dashboard clients hit this once on load to backfill the chart."""
    return jsonify([to_dashboard_payload(r) for r in history])


@app.route("/api/latest")
def get_latest():
    return jsonify(latest)


@socketio.on("connect")
def on_connect():
    print(f"  + dashboard client connected ({request.sid})")


@socketio.on("disconnect")
def on_disconnect():
    print(f"  - dashboard client disconnected ({request.sid})")


# -------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  Distributed Temperature Monitoring -- laptop server")
    print("  Dashboard:   http://localhost:5000/")
    print("  Pi posts to: http://<your-laptop-LAN-IP>:5000/api/temperature")
    print("=" * 60)
    socketio.run(
        app,
        host="0.0.0.0",       # listen on every interface so the Pi can reach us
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True,
    )
