import os
import json
import ast
import threading
import subprocess
import sys
import time
from bowl_monitor import BowlMonitor
from urllib.parse import urlparse
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory


app = Flask(__name__)
latest_frame = None
frame_condition = threading.Condition()
HISTORY_DIR = Path(__file__).resolve().parent / "camera_history"
HISTORY_DIR.mkdir(exist_ok=True)
CONFIG_FILE = HISTORY_DIR.parent / "camera_config.json"
HISTORY_RETENTION = timedelta(hours=1)
SNAPSHOT_INTERVAL_SECONDS = max(5, int(os.getenv("DOBU_SNAPSHOT_INTERVAL_SECONDS", "30")))
last_snapshot_at = None
history_lock = threading.Lock()
source_lock = threading.Lock()
capture_process = None
selected_source = None
bowl_monitor = BowlMonitor()
demo_analysis_lock = threading.Lock()
demo_analysis_job = {'status': 'idle'}


@app.route('/camera-source', methods=['GET', 'POST'])
def camera_source():
    global capture_process, selected_source, latest_frame
    if request.method == 'GET':
        return jsonify({'source': selected_source, 'running': capture_process is not None and capture_process.poll() is None})
    payload = request.get_json(silent=True) or {}
    source = payload.get('source')
    if source not in ('webcam', 'celular', 'exemplo', 'stop'):
        return jsonify({'error': 'Fonte inválida'}), 400
    root = Path(__file__).resolve().parent
    camera = '0'
    if source == 'exemplo':
        camera = str(root / 'demo-cat.mp4')
        if not Path(camera).is_file():
            return jsonify({'error': 'Vídeo de exemplo não encontrado'}), 404
    if source == 'celular':
        camera = str(payload.get('url', '')).strip()
        parsed = urlparse(camera)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return jsonify({'error': 'Endereço de câmera inválido'}), 400
    with source_lock:
        if capture_process is not None and capture_process.poll() is None:
            capture_process.terminate()
            try:
                capture_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                capture_process.kill()
                capture_process.wait()
        latest_frame = None
        state.update(pet_detected=False, pet_moving=False, species='', confidence=0,
                     quiet_seconds=0, last_frame_at=None, playback_started_at=None, activity_state='ausente')
        selected_source = source
        bowl_monitor.reset()
        if source == 'exemplo':
            state['bowl_config'] = normalizar_configuracao(json.loads((root / 'demo_config.json').read_text(encoding='utf-8')))
        elif source != 'stop':
            state['bowl_config'] = carregar_configuracao()
        if source != 'stop':
            with (root / 'camera-iot-out.log').open('a') as out, (root / 'camera-iot-err.log').open('a') as err:
                capture_process = subprocess.Popen(
                    [sys.executable, '-u', str(root / 'camera_iot.py'), '--camera', camera,
                     '--animal-only', '--animal-conf', '0.5', '--draw-detection', '--frame-intervalo', '0.12']
                    + (['--video-duration', '40'] if source == 'exemplo' else []),
                    cwd=str(root), stdout=out, stderr=err,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        else:
            capture_process = None
    return jsonify({'source': source, 'running': source != 'stop'})


@app.route('/demo-video')
def demo_video():
    return send_from_directory(str(Path(__file__).resolve().parent), 'demo-cat.mp4', mimetype='video/mp4', conditional=True)


@app.route('/demo-video-info')
def demo_video_info():
    return jsonify({'path': str(Path(__file__).resolve().parent / 'demo-cat.mp4')})


@app.route('/demo-analysis', methods=['GET', 'POST'])
def demo_analysis():
    global demo_analysis_job
    with demo_analysis_lock:
        if request.method == 'GET':
            return jsonify(demo_analysis_job)
        root = Path(__file__).resolve().parent
        config = normalizar_configuracao(json.loads((root / 'demo_config.json').read_text(encoding='utf-8')))
        if selected_source == 'exemplo':
            config = dict(state['bowl_config'])
        key = json.dumps(config, sort_keys=True)
        if demo_analysis_job.get('key') == key and demo_analysis_job['status'] in ('running', 'done'):
            return jsonify(demo_analysis_job)
        if demo_analysis_job['status'] == 'running':
            return jsonify({'error': 'Há uma análise em andamento. Aguarde sua conclusão.'}), 409
        demo_analysis_job = {'status': 'running', 'progress': 0, 'key': key}

        def run():
            try:
                from video_analysis import analyze_video
                def progress(value):
                    with demo_analysis_lock:
                        demo_analysis_job['progress'] = value
                result = analyze_video(root / 'demo-cat.mp4', config, progress, playback_duration=40)
                with demo_analysis_lock:
                    demo_analysis_job.update(status='done', progress=100, result=result)
            except Exception:
                app.logger.exception('Falha na análise da gravação')
                with demo_analysis_lock:
                    demo_analysis_job.update(status='error', error='Não foi possível analisar a gravação.')
        threading.Thread(target=run, daemon=True).start()
        return jsonify(demo_analysis_job), 202

state = {
    "pet_detected": False,
    "pet_moving": False,
    "abrupt_movement": False,
    "activity_state": "ausente",
    "last_seen": None,
    "confidence": 0.0,
    "species": "",
    "quiet_seconds": 0,
    "source": "dobu-cam-real",
    "protocol": "HTTP",
    "telemetry": {
        "device_id": "dobu-cam-real",
        "sensor": "webcam-real",
    },
    "events": [],
    "last_frame_at": None,
    "playback_started_at": None,
    "frame_count": 0,
    "bowl_config": {
        "food": "",
        "water": "",
    },
}


def carregar_configuracao():
    try:
        configuracao = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return normalizar_configuracao(configuracao)
    except (FileNotFoundError, OSError, ValueError, AttributeError):
        return {"food": "", "water": ""}


def normalizar_configuracao(configuracao):
    def normalizar_area(valor):
        if isinstance(valor, str) and valor.startswith("{"):
            try:
                valor = ast.literal_eval(valor)
            except (SyntaxError, ValueError):
                return None
        if isinstance(valor, dict):
            try:
                return {
                    "x": round(max(0, min(1, float(valor.get("x", 0)))), 4),
                    "y": round(max(0, min(1, float(valor.get("y", 0)))), 4),
                    "width": round(max(0, min(1, float(valor.get("width", 0)))), 4),
                    "height": round(max(0, min(1, float(valor.get("height", 0)))), 4),
                }
            except (TypeError, ValueError):
                return None
        return str(valor or "").strip() or None

    return {
        "food": normalizar_area(configuracao.get("food")),
        "water": normalizar_area(configuracao.get("water")),
    }


state["bowl_config"] = carregar_configuracao()


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def limpar_historico(expiration=None):
    expiration = expiration or datetime.now().astimezone() - HISTORY_RETENTION
    for arquivo in HISTORY_DIR.glob("*.jpg"):
        try:
            if datetime.fromtimestamp(arquivo.stat().st_mtime).astimezone() < expiration:
                arquivo.unlink(missing_ok=True)
        except (FileNotFoundError, OSError, ValueError):
            continue


def salvar_snapshot(frame_bytes):
    global last_snapshot_at
    agora = datetime.now().astimezone()
    if last_snapshot_at and (agora - last_snapshot_at).total_seconds() < SNAPSHOT_INTERVAL_SECONDS:
        return None

    nome = agora.strftime("%Y%m%d_%H%M%S_%f")[:-3] + ".jpg"
    caminho = HISTORY_DIR / nome
    try:
        caminho.write_bytes(frame_bytes)
        last_snapshot_at = agora
        limpar_historico(agora - HISTORY_RETENTION)
        return nome
    except OSError:
        return None


def listar_snapshots():
    expiration = datetime.now().astimezone() - HISTORY_RETENTION
    itens = []
    for arquivo in sorted(HISTORY_DIR.glob("*.jpg"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            criado = datetime.fromtimestamp(arquivo.stat().st_mtime).astimezone()
            if criado < expiration:
                arquivo.unlink(missing_ok=True)
                continue
            itens.append({
                "arquivo": arquivo.name,
                "criado_em": criado.isoformat(timespec="seconds"),
                "url": f"/camera-history/{arquivo.name}",
            })
        except (FileNotFoundError, OSError):
            continue
    return itens


def public_state():
    last_seen = state["last_seen"]
    return {
        "pet_detected": state["pet_detected"],
        "pet_moving": state["pet_moving"],
        "abrupt_movement": state["abrupt_movement"],
        "activity_state": state["activity_state"],
        "last_seen": last_seen or "--",
        "confidence": state["confidence"],
        "species": state["species"],
        "quiet_seconds": state["quiet_seconds"],
        "possible_rest": state["pet_detected"] and state["quiet_seconds"] >= 3600 and bool(state["last_frame_at"] and (datetime.now().astimezone() - datetime.fromisoformat(state["last_frame_at"])).total_seconds() <= 10),
        "source": state["source"],
        "protocol": state["protocol"],
        "telemetry": state["telemetry"],
        "events": state["events"][-8:],
        "camera_online": bool(state["last_frame_at"] and (datetime.now().astimezone() - datetime.fromisoformat(state["last_frame_at"])).total_seconds() <= 10),
        "last_frame_at": state["last_frame_at"] or "--",
        "playback_started_at": state["playback_started_at"],
        "frame_count": state["frame_count"],
        "bowl_config": state["bowl_config"],
        "bowl_observations": bowl_monitor.snapshot(state['bowl_config'], time.monotonic(), bool(state['last_frame_at'] and (datetime.now().astimezone() - datetime.fromisoformat(state['last_frame_at'])).total_seconds() <= 10)),
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
        state["last_frame_at"] = now_iso()
        if state['playback_started_at'] is None:
            state['playback_started_at'] = state['last_frame_at']
        state["frame_count"] += 1
        with frame_condition:
            frame_condition.notify_all()
        with history_lock:
            salvar_snapshot(latest_frame)
        return jsonify({"ok": True})

    if latest_frame:
        return Response(latest_frame, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    return "", 404


@app.route("/camera-stream")
def camera_stream():
    def frames():
        last_count = -1
        while True:
            with frame_condition:
                frame_condition.wait_for(lambda: latest_frame is not None and state["frame_count"] != last_count, timeout=5)
                frame = latest_frame
                count = state["frame_count"]
            if frame and count != last_count:
                last_count = count
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.route("/camera-history", methods=["GET"])
def camera_history():
    with history_lock:
        imagens = listar_snapshots()
    return jsonify({
        "retencao_horas": 1,
        "intervalo_segundos": SNAPSHOT_INTERVAL_SECONDS,
        "quantidade": len(imagens),
        "imagens": imagens,
    })


@app.route("/camera-history/<path:filename>", methods=["GET"])
def camera_history_file(filename):
    # send_from_directory impede que o nome do arquivo saia da pasta de histórico.
    return send_from_directory(HISTORY_DIR, filename, mimetype="image/jpeg", max_age=60)


@app.route("/status")
def status():
    return jsonify(public_state())


@app.route("/configuracao", methods=["GET", "POST", "OPTIONS"])
def configuracao():
    if request.method == "OPTIONS":
        return "", 204
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        state["bowl_config"] = normalizar_configuracao(payload)
        bowl_monitor.reset()
        try:
            config_file = CONFIG_FILE.parent / 'demo_config.json' if selected_source == 'exemplo' else CONFIG_FILE
            config_file.write_text(json.dumps(state["bowl_config"], ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return jsonify({"ok": False, "error": "não foi possível salvar a configuração"}), 500
    return jsonify({"ok": True, "bowl_config": state["bowl_config"]})


@app.route("/update/<detected>", methods=["GET", "POST", "OPTIONS"])
def update(detected):
    if request.method == "OPTIONS":
        return "", 204

    is_detected = detected in {"1", "true", "presente", "detected"}
    is_moving = request.values.get("moving", "0") in {"1", "true", "sim", "moving", "em_movimento"}
    abrupt_movement = request.values.get("abrupt_movement", "0") in {"1", "true", "sim", "moving", "movimento_brusco"}
    activity_state = request.values.get("activity_state")
    confidence = request.values.get("confidence", type=float)
    source = request.values.get("source") or request.values.get("device_id") or "dobu-cam-real"
    species = request.values.get("species") or ""
    timestamp = now_iso()
    telemetry = {
        "device_id": request.values.get("device_id", state["telemetry"]["device_id"]),
        "sensor": request.values.get("sensor", state["telemetry"]["sensor"]),
    }
    previous_detected = state["pet_detected"]
    previous_last_seen = state["last_seen"]

    state["pet_detected"] = is_detected
    state["pet_moving"] = is_detected and is_moving
    state["abrupt_movement"] = is_detected and abrupt_movement
    state["activity_state"] = activity_state or ("em_movimento" if state["pet_moving"] else "parado" if is_detected else "ausente")
    state["source"] = source
    state["confidence"] = round(confidence if confidence is not None else (0.92 if is_detected else 0.12), 2)
    state["species"] = species
    try:
        animal_box = json.loads(request.values.get('animal_box', 'null'))
    except (ValueError, TypeError):
        animal_box = None
    if selected_source == 'celular':
        bowl_monitor.update(state['bowl_config'], animal_box if is_detected else None, species,
                            confidence or 0, time.monotonic(), timestamp)
    state["quiet_seconds"] = max(0, request.values.get("quiet_seconds", default=0, type=float) or 0) if is_detected and not is_moving else 0
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
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
