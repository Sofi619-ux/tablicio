# -*- coding: utf-8 -*-
"""Таблицио — локальная программа-обёртка.

Запускает маленький веб-сервер на этом компьютере и открывает таблицу
в браузере по умолчанию (подходит любой, включая Firefox).
Данные хранятся в папке «данные» рядом с программой:
  данные/таблица.json  — сама таблица
  данные/вложения/     — крупные файлы и картинки
"""
import json
import logging
import os
import re
import socket
import sys
import threading
import uuid
import webbrowser

from flask import Flask, jsonify, request, send_file, send_from_directory


def base_dir() -> str:
    """Папка, где лежит exe (или app.py при разработке)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundle_dir() -> str:
    """Папка с ресурсами, зашитыми внутрь exe (index.html)."""
    return getattr(sys, "_MEIPASS", base_dir())


BASE = base_dir()
DATA_DIR = os.path.join(BASE, "данные")
ATTACH_DIR = os.path.join(DATA_DIR, "вложения")
STATE_PATH = os.path.join(DATA_DIR, "таблица.json")
os.makedirs(ATTACH_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(DATA_DIR, "журнал.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = Flask(__name__)

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@app.get("/")
def index():
    return send_file(os.path.join(bundle_dir(), "index.html"))


@app.get("/api/state")
def get_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return app.response_class(f.read(), mimetype="application/json")
    return jsonify(None)


@app.post("/api/state")
def set_state():
    raw = request.get_data(as_text=True)
    json.loads(raw)  # валидация: битый JSON не сохраняем
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(tmp, STATE_PATH)  # атомарная замена — файл не побьётся
    return jsonify({"ok": True})


@app.post("/api/upload")
def upload():
    f = request.files["file"]
    name = _UNSAFE.sub("_", f.filename or "файл").strip() or "файл"
    fname = uuid.uuid4().hex[:8] + "_" + name[:120]
    f.save(os.path.join(ATTACH_DIR, fname))
    logging.info("upload %s (%s)", fname, f.mimetype)
    return jsonify({"fname": fname})


@app.get("/files/<path:fname>")
def files(fname):
    return send_from_directory(ATTACH_DIR, fname)


@app.delete("/api/file/<path:fname>")
def delete_file(fname):
    path = os.path.join(ATTACH_DIR, os.path.basename(fname))
    if os.path.exists(path):
        os.remove(path)
        logging.info("delete %s", fname)
    return jsonify({"ok": True})


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


if __name__ == "__main__":
    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    logging.info("start %s", url)
    app.run(host="127.0.0.1", port=port, threaded=True)
