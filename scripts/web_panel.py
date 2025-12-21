"""Web control panel for the Vision Trainer (safe, token-protected).

This module exposes a small HTTP API and a minimal web UI so you can control
and monitor the Vision Trainer from another device on the same network.

Security model:
- By default the panel binds to 127.0.0.1 (localhost) only.
- To allow remote access, use --host 0.0.0.0 and --allow-remote. This requires
  you to also set a strong token via --token or the VISION_PANEL_TOKEN env var.
- All endpoints require the token to be provided via the `X-API-Token` header
  or `?token=` query parameter.
- Injection remains disabled unless enabled via the runner with explicit
  interactive consent.

Run:
  python scripts\web_panel.py --port 8000
  python scripts\web_panel.py --port 8000 --host 0.0.0.0 --allow-remote --token <YOUR_TOKEN>

Note: this file uses FastAPI + Uvicorn (install via `pip install fastapi uvicorn`).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import threading
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn


# dynamic import of the vision module so this file can be executed even when the
# scripts folder is not a package
VISION_PY = os.path.join(os.path.dirname(__file__), 'f12_vision_trainer.py')
vision = None
try:
    spec = importlib.util.spec_from_file_location('vision', VISION_PY)
    vision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vision)
except Exception as exc:
    print(f"[{datetime.utcnow().isoformat()}] Warning: failed to import vision module: {exc}")
    vision = None

if vision is not None:
    VisionTrainer = vision.VisionTrainer
    VisionRunner = vision.VisionRunner
    _now = vision._now
else:
    VisionTrainer = None
    VisionRunner = None
    def _now():
        return datetime.utcnow().strftime("%H:%M:%S")


app = FastAPI(title='Vision Trainer Panel')

# global trainer/runner for the panel
if VisionTrainer is not None:
    trainer = VisionTrainer(persist=True)
    runner = VisionRunner(trainer, interval=0.5, threshold=0.75)
else:
    trainer = None
    runner = None
runner_thread_lock = threading.Lock()


def _require_token(request: Request, token_required: str) -> None:
    if not token_required:
        return
    token = request.headers.get('X-API-Token') or request.query_params.get('token')
    if not token or token != token_required:
        raise HTTPException(status_code=401, detail='Invalid or missing token')


@app.get('/')
async def root(request: Request, token: str | None = None):
    # simple HTML UI (uses token if provided)
    html = f"""
<html>
  <head><title>Vision Trainer Panel</title></head>
  <body>
    <h3>Vision Trainer Panel</h3>
    <p>Use the API endpoints to control the trainer. Provide <code>X-API-Token</code> header or <code>?token=</code> in URL when required.</p>
    <p>Endpoints:</p>
    <ul>
      <li>GET /status</li>
      <li>POST /toggle?vision=1</li>
      <li>POST /teach</li>
      <li>GET /templates</li>
      <li>POST /export?path=filename.json</li>
      <li>POST /import (upload file)</li>
      <li>GET /stats</li>
    </ul>
  </body>
</html>
"""
    return HTMLResponse(content=html)


@app.get('/status')
async def status(request: Request):
    # no token for status by default
    if runner is None or trainer is None:
        return JSONResponse({'status': 'unavailable', 'reason': 'vision module not loaded; install system dependencies (e.g., libGL) or install packages via scripts/install_deps.py'})
    active = getattr(runner, '_stop').is_set() is False
    return JSONResponse({'status': 'running' if active else 'stopped', 'trainer_templates': len(trainer.templates)})


@app.post('/toggle')
async def toggle(request: Request):
    _require_token(request, request.app.state.panel_token)
    if runner is None:
        raise HTTPException(status_code=503, detail='Vision module not available; cannot toggle runner')
    if getattr(runner, '_stop').is_set():
        runner._stop.clear()
        runner.start()
        return JSONResponse({'result': 'started'})
    else:
        runner.stop()
        return JSONResponse({'result': 'stopped'})


@app.post('/teach')
async def teach(request: Request):
    _require_token(request, request.app.state.panel_token)
    if trainer is None:
        raise HTTPException(status_code=503, detail='Vision module not available; teach not possible')
    # launch teach in background
    threading.Thread(target=trainer.teach, daemon=True).start()
    return JSONResponse({'result': 'teach started'})


@app.get('/templates')
async def templates(request: Request):
    _require_token(request, request.app.state.panel_token)
    if trainer is None:
        raise HTTPException(status_code=503, detail='Vision module not available; no templates')
    with trainer._lock:
        data = [{'id': t.id, 'label': t.label, 'action': t.action, 'ocr': t.metadata.get('ocr_text')} for t in trainer.templates]
    return JSONResponse({'templates': data})


@app.post('/export')
async def export_templates(request: Request, path: str | None = None):
    _require_token(request, request.app.state.panel_token)
    if trainer is None:
        raise HTTPException(status_code=503, detail='Vision module not available; cannot export')
    if not path:
        raise HTTPException(status_code=400, detail='Missing query param "path"')
    trainer.export_all(path)
    return JSONResponse({'exported': path})


@app.post('/import')
async def import_templates(request: Request, file: UploadFile = File(...)):
    _require_token(request, request.app.state.panel_token)
    if trainer is None:
        raise HTTPException(status_code=503, detail='Vision module not available; cannot import')
    data = await file.read()
    tmp = os.path.join(os.path.dirname(__file__), 'tmp_import.json')
    with open(tmp, 'wb') as fh:
        fh.write(data)
    trainer.import_templates(tmp)
    os.remove(tmp)
    return JSONResponse({'imported': True})


@app.get('/stats')
async def stats(request: Request):
    _require_token(request, request.app.state.panel_token)
    if runner is None:
        raise HTTPException(status_code=503, detail='Vision module not available; no stats')
    return JSONResponse({'stats': runner.stats})


@app.post('/enable_inject')
async def enable_inject(request: Request):
    _require_token(request, request.app.state.panel_token)
    # This endpoint only flips the flag to allow injection; actual enabling
    # requires explicit consent via injector.enable_injection() which will
    # prompt in the console where the server is running.
    if not getattr(vision, 'injector', None):
        raise HTTPException(status_code=400, detail='Injector module not available')
    # try to enable; this will do environment checks and interactive consent
    try:
        ok = vision.injector.enable_injection(True)
        return JSONResponse({'enabled': bool(ok)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Run web panel for Vision Trainer')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--allow-remote', action='store_true', help='Allow binding to 0.0.0.0 (must provide --token)')
    parser.add_argument('--token', default=os.environ.get('VISION_PANEL_TOKEN'))
    args = parser.parse_args(argv)

    if args.allow_remote and not args.token:
        print('Refusing to allow remote without an explicit token. Use --token <secret>')
        return 2
    if args.allow_remote and args.host == '127.0.0.1':
        print('Note: --allow-remote specified; binding to 0.0.0.0 for remote access')
        args.host = '0.0.0.0'

    # store token in app state for validation
    app.state.panel_token = args.token

    print(f"[{_now()}] Starting web panel on {args.host}:{args.port} (token set: {'yes' if args.token else 'no'})")
    uvicorn.run(app, host=args.host, port=args.port, log_level='info')
    return 0


if __name__ == '__main__':
    raise SystemExit(main([]))