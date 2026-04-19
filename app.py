"""轻量标注工具后端。

职责：
1) 提供视频上传/抓帧接口给前端标注页面使用。
2) 管理摄像头地址列表。
3) 保存标注 JSON。
"""

import base64
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import cv2
from flask import Flask, jsonify, request, send_from_directory

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = BASE_DIR

UPLOAD_DIR = BASE_DIR / "uploads"
ANNOTATION_DIR = BASE_DIR / "annotation_json"
CAMERA_IP_FILE = BASE_DIR / "camera_ips.json"
CURRENT_VIDEO = UPLOAD_DIR / "current_video"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


def resize_frame_to_480p(frame):
    """Resize frame to max 480p while keeping aspect ratio."""
    src_h, src_w = frame.shape[:2]
    target_h = min(480, src_h)
    target_w = int(round(src_w * (target_h / src_h)))
    target_w = max(2, target_w - (target_w % 2))
    target_h = max(2, target_h - (target_h % 2))

    if target_w == src_w and target_h == src_h:
        return frame

    return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)


def load_camera_ips():
    """读取已保存的摄像头地址列表。"""
    if not CAMERA_IP_FILE.exists():
        return []
    try:
        data = json.loads(CAMERA_IP_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    out = []
    for item in data:
        if isinstance(item, dict):
            url = str(item.get("url", "")).strip()
            name = str(item.get("name", "")).strip()
            if url:
                out.append({"name": name or url, "url": url})
    return out


def save_camera_ips(items):
    """覆盖写入摄像头地址列表。"""
    CAMERA_IP_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_non_black_frame(cap, max_reads=30):
    """从视频流读取第一帧可用画面，尽量跳过全黑帧。"""
    best_frame = None
    best_score = -1.0
    for _ in range(max_reads):
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        score = float(frame.mean())
        if score > best_score:
            best_score = score
            best_frame = frame
        if score >= 10.0:
            break
    return best_frame


def frame_to_base64(frame):
    """将 OpenCV BGR 图像编码为 base64 JPEG。"""
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("utf-8")


@app.get("/")
def index():
    """返回前端标注页面。"""
    return send_from_directory(RESOURCE_DIR, "annotation_tool.html")


@app.post("/api/upload_video")
def upload_video():
    """接收用户上传视频并保存为当前工作视频。"""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "missing file"}), 400

    file.save(CURRENT_VIDEO)
    return jsonify({"status": "success"})


@app.get("/api/get_first_frame")
def get_first_frame():
    """提取已上传视频首帧，并统一缩放到 480p 后返回。"""
    if not CURRENT_VIDEO.exists():
        return jsonify({"error": "no uploaded video"}), 400

    cap = cv2.VideoCapture(str(CURRENT_VIDEO))
    frame = read_non_black_frame(cap)
    cap.release()

    if frame is None:
        return jsonify({"error": "failed to decode first frame"}), 400

    frame = resize_frame_to_480p(frame)

    image_b64 = frame_to_base64(frame)
    if image_b64 is None:
        return jsonify({"error": "failed to encode frame"}), 500
    return jsonify({"status": "success", "image": image_b64})


@app.get("/api/camera_ips")
def get_camera_ips():
    """获取摄像头地址列表。"""
    return jsonify({"status": "success", "items": load_camera_ips()})


@app.post("/api/camera_ips")
def add_camera_ip():
    """新增或更新单条摄像头地址。"""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    name = str(payload.get("name", "")).strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    items = load_camera_ips()
    replaced = False
    for item in items:
        if item["url"] == url:
            item["name"] = name or item["name"] or url
            replaced = True
            break

    if not replaced:
        items.append({"name": name or url, "url": url})

    save_camera_ips(items)
    return jsonify({"status": "success", "items": items})


@app.delete("/api/camera_ips")
def delete_camera_ip():
    """删除一条摄像头地址。"""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    items = load_camera_ips()
    new_items = [item for item in items if item.get("url") != url]
    if len(new_items) == len(items):
        return jsonify({"error": "camera ip not found"}), 404

    save_camera_ips(new_items)
    return jsonify({"status": "success", "items": new_items})


@app.post("/api/get_camera_frame")
def get_camera_frame():
    """从摄像头抓取一帧用于标注，并统一缩放到 480p 后返回。"""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        cap.release()
        return jsonify({"error": "failed to open camera stream"}), 400

    frame = read_non_black_frame(cap)
    cap.release()
    if frame is None:
        return jsonify({"error": "failed to read frame from camera"}), 400

    frame = resize_frame_to_480p(frame)

    image_b64 = frame_to_base64(frame)
    if image_b64 is None:
        return jsonify({"error": "failed to encode frame"}), 500

    return jsonify({"status": "success", "image": image_b64})


@app.post("/api/save_annotation")
def save_annotation():
    """保存标注 JSON。"""
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid json body"}), 400

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ANNOTATION_DIR / f"annotation_{stamp}.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return jsonify({
        "status": "success",
        "json_path": out_path.relative_to(BASE_DIR).as_posix(),
    })


@app.post("/api/shutdown")
def shutdown_service():
    """关闭当前 Flask 服务进程。"""
    shutdown_func = request.environ.get("werkzeug.server.shutdown")

    if shutdown_func is not None:
        threading.Timer(0.2, shutdown_func).start()
        return jsonify({"status": "success", "message": "service shutting down"})

    # Fallback for packaged/non-werkzeug contexts.
    threading.Timer(0.2, lambda: os._exit(0)).start()
    return jsonify({"status": "success", "message": "process exiting"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
