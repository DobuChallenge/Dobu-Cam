from datetime import datetime

from flask import Flask, Response, jsonify, request, send_from_directory


app = Flask(__name__)
latest_frame = None

state = {
    "pet_detected": False,
    "pet_moving": False,
    "activity_state": "ausente",
    "last_seen": None,
    "confidence": 0.0,
    "source": "dobu-cam-real",
    "protocol": "HTTP",
    "telemetry": {
        "device_id": "dobu-cam-real",
        "sensor": "webcam-real",
    },
    "events": [],
}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def public_state():
    last_seen = state["last_seen"]
    return {
        "pet_detected": state["pet_detected"],
        "pet_moving": state["pet_moving"],
        "activity_state": state["activity_state"],
        "last_seen": last_seen or "--",
        "confidence": state["confidence"],
        "source": state["source"],
        "protocol": state["protocol"],
        "telemetry": state["telemetry"],
        "events": state["events"][-8:],
    }


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/")
def dashboard():
    return send_from_directory(".", "dashboard.html")


@app.route("/logo.png")
def logo():
    return send_from_directory(".", "logo.png")


@app.route("/camera-frame", methods=["GET", "POST"])
def camera_frame():
    global latest_frame

    if request.method == "POST":
        frame = request.files.get("frame")
        if not frame:
            return jsonify({"ok": False, "error": "frame ausente"}), 400

        latest_frame = frame.read()
        return jsonify({"ok": True})

    if latest_frame:
        return Response(latest_frame, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    return "", 404


@app.route("/status")
def status():
    return jsonify(public_state())


@app.route("/update/<detected>", methods=["GET", "POST", "OPTIONS"])
def update(detected):
    if request.method == "OPTIONS":
        return "", 204

    is_detected = detected in {"1", "true", "presente", "detected"}
    is_moving = request.values.get("moving", "0") in {"1", "true", "sim", "moving", "em_movimento"}
    activity_state = request.values.get("activity_state")
    confidence = request.values.get("confidence", type=float)
    source = request.values.get("source") or request.values.get("device_id") or "dobu-cam-real"
    timestamp = now_iso()
    telemetry = {
        "device_id": request.values.get("device_id", state["telemetry"]["device_id"]),
        "sensor": request.values.get("sensor", state["telemetry"]["sensor"]),
    }
    previous_detected = state["pet_detected"]
    previous_last_seen = state["last_seen"]

    state["pet_detected"] = is_detected
    state["pet_moving"] = is_detected and is_moving
    state["activity_state"] = activity_state or ("em_movimento" if state["pet_moving"] else "parado" if is_detected else "ausente")
    state["source"] = source
    state["confidence"] = round(confidence if confidence is not None else (0.92 if is_detected else 0.12), 2)
    state["telemetry"] = {
        key: value if value is not None else state["telemetry"].get(key)
        for key, value in telemetry.items()
    }

    if is_detected:
        state["last_seen"] = timestamp
        if not previous_detected:
            state["events"].append(
                {
                    "timestamp": timestamp,
                    "last_seen": timestamp,
                    "message": "Animal voltou para a câmera",
                }
            )
            state["events"] = state["events"][-8:]
    elif previous_detected and previous_last_seen:
        state["events"].append(
            {
                "timestamp": timestamp,
                "last_seen": previous_last_seen,
                "message": "Animal saiu da câmera",
            }
        )
        state["events"] = state["events"][-8:]

    return jsonify({"ok": True, **public_state()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
