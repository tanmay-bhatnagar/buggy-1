#!/usr/bin/env python3
"""
camera_stream.py - raw MJPEG camera stream for the Phase-3 Android app.

Run on Jetson:
    python3 camera_stream.py --source 0 --width 640 --height 480 --fps 20

Then open the printed URL from the Tab, or enter it in the BuggyUI stream box.
"""

import argparse
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

try:
    import cv2
except ImportError:
    cv2 = None


class Camera:
    def __init__(self, source, width: int, height: int, fps: int, quality: int):
        if cv2 is None:
            raise RuntimeError("OpenCV is not installed. Install python3-opencv or opencv-python.")

        self.source = source
        self.width = width
        self.height = height
        self.fps = max(1, fps)
        self.quality = max(30, min(95, quality))
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.latest_jpeg: Optional[bytes] = None
        self.latest_error: Optional[str] = None
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=2)

    def wait_for_frame(self, last_frame: Optional[bytes], timeout: float = 2.0) -> Optional[bytes]:
        deadline = time.monotonic() + timeout
        with self.condition:
            if self.latest_jpeg is not None and last_frame is None:
                return self.latest_jpeg
            while self.running and self.latest_jpeg is last_frame:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(timeout=remaining)
            return self.latest_jpeg

    def _capture_loop(self):
        cap = cv2.VideoCapture(self.source)
        if self.width > 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height > 0:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not cap.isOpened():
            self._set_error(f"Could not open camera source {self.source!r}")
            return

        frame_interval = 1.0 / self.fps
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]

        try:
            while self.running:
                t0 = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    self._set_error("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue

                ok, encoded = cv2.imencode(".jpg", frame, encode_params)
                if not ok:
                    self._set_error("Failed to encode frame")
                    time.sleep(0.1)
                    continue

                with self.condition:
                    self.latest_jpeg = encoded.tobytes()
                    self.latest_error = None
                    self.condition.notify_all()

                elapsed = time.monotonic() - t0
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
        finally:
            cap.release()

    def _set_error(self, message: str):
        with self.condition:
            self.latest_error = message
            self.condition.notify_all()
        print(f"camera_stream: {message}", file=sys.stderr)


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def parse_source(value: str):
    try:
        return int(value)
    except ValueError:
        return value


def make_handler(camera: Camera):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BuggyCameraStream/1.0"

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._serve_index()
            elif self.path.startswith("/stream"):
                self._serve_stream()
            elif self.path.startswith("/snapshot.jpg"):
                self._serve_snapshot()
            elif self.path.startswith("/health"):
                self._send_text("ok\n")
            else:
                self.send_error(404, "Not found")

        def log_message(self, fmt, *args):
            print(f"{self.client_address[0]} - {fmt % args}")

        def _serve_index(self):
            html = """<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <title>Buggy Camera</title>
  <style>
    html, body { margin: 0; height: 100%; background: #000; }
    img { width: 100vw; height: 100vh; object-fit: contain; display: block; }
  </style>
</head>
<body>
  <img src="/stream" alt="Buggy camera stream">
</body>
</html>
"""
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_snapshot(self):
            frame = camera.wait_for_frame(None, timeout=2.0)
            if frame is None:
                self.send_error(503, camera.latest_error or "No camera frame available")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(frame)

        def _serve_stream(self):
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()

            last_frame = None
            while camera.running:
                frame = camera.wait_for_frame(last_frame, timeout=2.0)
                if frame is None:
                    continue
                last_frame = frame
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break

        def _send_text(self, text: str):
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Serve a raw camera feed as MJPEG over HTTP.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--source", default="0", help="Camera index or video path. Default: 0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--quality", type=int, default=75, help="JPEG quality 30-95")
    args = parser.parse_args()

    camera = Camera(parse_source(args.source), args.width, args.height, args.fps, args.quality)
    camera.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(camera))
    url = f"http://{local_ip()}:{args.port}/"
    print(f"Buggy camera stream running: {url}")
    print(f"MJPEG endpoint: {url}stream")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping camera stream...")
    finally:
        server.shutdown()
        camera.stop()


if __name__ == "__main__":
    main()
