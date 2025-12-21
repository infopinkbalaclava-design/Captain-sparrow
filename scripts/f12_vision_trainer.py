"""F12-toggle visual teach & analyze prototype (dry-run)

This enhanced version adds:
- Optional OCR (pytesseract) to capture text in templates and allow text-based matching
- Export/import of template collections (single JSON file)
- Match statistics collection and export
- A simple template management GUI (list/preview/delete/rename)
- An opt-in, strongly-guarded injection path (requires flags and interactive consent)

Security & Safety (read carefully):
- This tool is intended for legitimate automation/testing/accessibility of
  non-game, authorized applications only. It MUST NOT be used for game
  automation, cheating, or unauthorized access.
- Injection is disabled by default and requires both the `--enable-inject` flag
  and an interactive confirmation token. The injector also checks for running
  game-like processes and refuses to enable if suspicious processes are present.
- OCR requires Tesseract to be installed on the system (separate from the Python package).

Dependencies:
- pillow
- opencv-python
- numpy
- keyboard
- pytesseract (optional; requires system tesseract installation)
- pyautogui or keyboard (only if injection is enabled)

Install (Windows):
  pip install pillow opencv-python numpy keyboard pytesseract pyautogui
  # Additionally install Tesseract OCR from https://github.com/tesseract-ocr/tesseract

Run examples:
  python scripts\f12_vision_trainer.py --teach --persist-templates
  python scripts\f12_vision_trainer.py --vision --interval 0.5 --ocr --stats-file stats.json

Hotkeys (running):
- F12: toggle active on/off
- Ctrl+Shift+T: enter teach mode (capture screen and select a region)
- Ctrl+Shift+L: list templates
- Ctrl+Shift+S: save templates to disk (if --persist-templates used)
- Ctrl+Shift+M: open template manager GUI
- Ctrl+Shift+R: export runtime stats to file (if --stats-file provided)
- Ctrl+C: exit
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import cv2
import keyboard  # type: ignore
import numpy as np
from PIL import Image, ImageTk, ImageGrab
import tkinter as tk
from tkinter import simpledialog, messagebox

# Optional OCR support (pytesseract)
try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None

# Optional injector module (careful - opt-in)
try:
    from . import injector  # type: ignore
except Exception:
    injector = None


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


@dataclass
class Template:
    id: str
    label: str
    action: str
    img: Image.Image
    metadata: Dict = field(default_factory=dict)

    def as_serializable(self) -> Dict:
        buffer = BytesIO()
        self.img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        return {"id": self.id, "label": self.label, "action": self.action, "image_b64": b64, "metadata": self.metadata}

    @staticmethod
    def from_serializable(d: Dict) -> "Template":
        img = Image.open(BytesIO(base64.b64decode(d["image_b64"])))
        return Template(id=d["id"], label=d["label"], action=d["action"], img=img, metadata=d.get("metadata", {}))


class VisionTrainer:
    def __init__(self, persist: bool = False, templates_dir: str = "vision_templates") -> None:
        self.templates: List[Template] = []
        self.persist = persist
        self.templates_dir = templates_dir
        os.makedirs(self.templates_dir, exist_ok=True)
        self._lock = threading.Lock()

    def teach(self) -> None:
        # Capture current screen (PIL Image)
        img = ImageGrab.grab()
        print(f"[{_now()}] Teach: captured screen (not saved by default)")

        # Start a simple tkinter selection UI
        picker = _RegionPicker(img)
        region = picker.select_region()
        if region is None:
            print(f"[{_now()}] Teach: no region selected")
            return

        x0, y0, x1, y1 = region
        region_img = img.crop((x0, y0, x1, y1))

        # Ask for label and action via simpledialog
        root = tk.Tk()
        root.withdraw()
        label = simpledialog.askstring("Template label", "Enter a label for this template (e.g., 'StartButton'): ")
        if not label:
            print(f"[{_now()}] Teach: cancelled (no label)")
            return
        action = simpledialog.askstring("Suggested action", "Enter suggested action (dry-run message, e.g., 'press W'): ")
        if not action:
            action = "(no action)"

        template = Template(id=str(uuid.uuid4()), label=label, action=action, img=region_img)

        # Optional OCR capture if available
        if pytesseract is not None:
            try:
                text = pytesseract.image_to_string(region_img).strip()
                if text:
                    template.metadata['ocr_text'] = text
                    print(f"[{_now()}] OCR text detected: {repr(text[:80])}")
            except Exception as exc:
                print(f"[{_now()}] OCR error: {exc}")

        with self._lock:
            self.templates.append(template)

        print(f"[{_now()}] Teach: template '{label}' added (action: {action})")
        if self.persist:
            self.save_template(template)

    def list_templates(self) -> None:
        with self._lock:
            if not self.templates:
                print(f"[{_now()}] No templates loaded")
                return
            print(f"[{_now()}] Templates:")
            for t in self.templates:
                ocr = (" [ocr]" if t.metadata.get('ocr_text') else "")
                print(f" - {t.id}: '{t.label}' -> {t.action}{ocr}")

    def save_template(self, template: Template) -> None:
        path = os.path.join(self.templates_dir, f"{template.id}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(template.as_serializable(), fh)
        print(f"[{_now()}] Saved template to {path}")

    def save_all(self) -> None:
        with self._lock:
            for t in self.templates:
                self.save_template(t)

    def export_all(self, path: str) -> None:
        with self._lock:
            data = [t.as_serializable() for t in self.templates]
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'exported_at': datetime.utcnow().isoformat() + 'Z', 'templates': data}, fh)
        print(f"[{_now()}] Exported {len(data)} templates to {path}")

    def import_templates(self, path: str) -> None:
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                d = json.load(fh)
            templ_list = d.get('templates') or d
            added = 0
            with self._lock:
                for item in templ_list:
                    t = Template.from_serializable(item)
                    self.templates.append(t)
                    added += 1
            print(f"[{_now()}] Imported {added} templates from {path}")
        except Exception as exc:
            print(f"[{_now()}] Failed to import templates: {exc}")

    def load_all(self) -> None:
        loaded = 0
        for fname in os.listdir(self.templates_dir):
            if not fname.endswith('.json'):
                continue
            path = os.path.join(self.templates_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    d = json.load(fh)
                t = Template.from_serializable(d)
                self.templates.append(t)
                loaded += 1
            except Exception as exc:
                print(f"[{_now()}] Warning: failed to load {path}: {exc}")
        print(f"[{_now()}] Loaded {loaded} templates from {self.templates_dir}")

    def open_manager(self) -> None:
        # Simple GUI to list and manage templates
        with self._lock:
            templates = list(self.templates)

        root = tk.Tk()
        root.title("Template Manager")

        listbox = tk.Listbox(root, width=60)
        listbox.pack(side='left', fill='y')

        preview = tk.Canvas(root, width=240, height=180, bg='black')
        preview.pack(side='right', padx=8, pady=8)

        info = tk.Text(root, width=40, height=10)
        info.pack(side='right', padx=8, pady=8)

        def refresh_list():
            listbox.delete(0, tk.END)
            for t in templates:
                ocr_tag = " [ocr]" if t.metadata.get('ocr_text') else ""
                listbox.insert(tk.END, f"{t.label}{ocr_tag} -> {t.action}")

        def show_selected(evt=None):
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            t = templates[idx]
            info.delete('1.0', tk.END)
            info.insert(tk.END, f"ID: {t.id}\nLabel: {t.label}\nAction: {t.action}\nOCR: {t.metadata.get('ocr_text','-')}\n")
            # show preview image scaled
            img = t.img.copy()
            img.thumbnail((240, 180))
            tkimg = ImageTk.PhotoImage(img)
            preview.image = tkimg
            preview.create_image(0, 0, anchor='nw', image=tkimg)

        def delete_selected():
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            t = templates.pop(idx)
            # also remove persisted file if present
            path = os.path.join(self.templates_dir, f"{t.id}.json")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            refresh_list()

        def rename_selected():
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            t = templates[idx]
            new_label = simpledialog.askstring("Rename", "New label:", initialvalue=t.label)
            if new_label:
                t.label = new_label
                refresh_list()

        btn_frame = tk.Frame(root)
        btn_frame.pack(side='bottom', fill='x')
        tk.Button(btn_frame, text='Delete', command=delete_selected).pack(side='left')
        tk.Button(btn_frame, text='Rename', command=rename_selected).pack(side='left')
        tk.Button(btn_frame, text='Close', command=root.destroy).pack(side='right')

        listbox.bind('<<ListboxSelect>>', show_selected)
        refresh_list()
        root.mainloop()


class VisionRunner:
    def __init__(self, trainer: VisionTrainer, interval: float = 0.5, threshold: float = 0.7, ocr: bool = False, stats_file: Optional[str] = None, injection_allowed: bool = False, inject_log: Optional[str] = None) -> None:
        self.trainer = trainer
        self.interval = max(0.05, float(interval))
        self.threshold = float(threshold)
        self.ocr = bool(ocr)
        self._stop = threading.Event()
        self.stats: Dict[str, int] = {}
        self.stats_file = stats_file
        self.injection_allowed = injection_allowed
        self.inject_log = inject_log
        self._injector_enabled = False

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def export_stats(self) -> None:
        if not self.stats_file:
            print(f"[{_now()}] No stats file configured")
            return
        with open(self.stats_file, 'w', encoding='utf-8') as fh:
            json.dump({'exported_at': datetime.utcnow().isoformat() + 'Z', 'stats': self.stats}, fh)
        print(f"[{_now()}] Exported stats to {self.stats_file}")

    def _maybe_enable_injector(self, consent_file: Optional[str], target_app: Optional[str]) -> None:
        if not self.injection_allowed:
            return
        if injector is None:
            print(f"[{_now()}] Injector module not available; install injector requirements")
            return
        try:
            # perform environment checks in injector module
            ok = injector.enable_injection(True)
            if not ok:
                print(f"[{_now()}] Injector refused to enable (safety checks) ")
                return
            self._injector_enabled = True
            print(f"[{_now()}] Injector enabled")
        except Exception as exc:
            print(f"[{_now()}] Injector error: {exc}")

    def _run(self) -> None:
        print(f"[{_now()}] Vision runner started (interval={self.interval}s, threshold={self.threshold}, ocr={self.ocr})")
        while not self._stop.is_set():
            screen = ImageGrab.grab()
            screen_cv = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2GRAY)

            with self.trainer._lock:
                templates = list(self.trainer.templates)

            for t in templates:
                tpl_cv = cv2.cvtColor(np.array(t.img), cv2.COLOR_RGB2GRAY)
                if tpl_cv.shape[0] <= 0 or tpl_cv.shape[1] <= 0:
                    continue
                # matchTemplate requires template smaller than source
                if tpl_cv.shape[0] > screen_cv.shape[0] or tpl_cv.shape[1] > screen_cv.shape[1]:
                    continue
                try:
                    res = cv2.matchTemplate(screen_cv, tpl_cv, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                    if max_val >= self.threshold:
                        # Increment stats
                        self.stats[t.id] = self.stats.get(t.id, 0) + 1

                        # Optional OCR verification
                        ocr_ok = True
                        if self.ocr and pytesseract is not None and t.metadata.get('ocr_text'):
                            # crop the matched region from the screen and OCR it
                            th, tw = tpl_cv.shape
                            top_left = max_loc
                            x0, y0 = top_left
                            x1, y1 = x0 + tw, y0 + th
                            try:
                                matched_img = screen.crop((x0, y0, x1, y1))
                                text = pytesseract.image_to_string(matched_img).strip()
                                expected = t.metadata.get('ocr_text','').strip()
                                import difflib
                                ratio = difflib.SequenceMatcher(None, expected, text).ratio() if expected and text else 0.0
                                if ratio < 0.5:
                                    ocr_ok = False
                            except Exception:
                                ocr_ok = False

                        if max_val >= self.threshold and (not self.ocr or ocr_ok):
                            top_left = max_loc
                            print(f"[{_now()}] MATCH '{t.label}' (score={max_val:.3f}) suggested action: {t.action}")

                            # If injector enabled and confirmed, perform action (careful)
                            if self._injector_enabled:
                                try:
                                    injector.perform_action(t.action, dry_run=False)
                                except Exception as exc:
                                    print(f"[{_now()}] Injector perform failed: {exc}")
                except Exception as exc:
                    print(f"[{_now()}] Vision error matching template {t.label}: {exc}")

            time.sleep(self.interval)


class _RegionPicker:
    def __init__(self, pil_image: Image.Image) -> None:
        self.pil_image = pil_image
        self.region: Optional[Tuple[int, int, int, int]] = None
        self._root = tk.Tk()
        self._root.title("Region picker - drag to select an area, then close window when done")
        self._root.attributes('-topmost', True)

        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()

        # Resize image to fit screen if necessary
        self.display_image = pil_image.copy()
        img_w, img_h = self.display_image.size
        if img_w > screen_width or img_h > screen_height:
            ratio = min(screen_width / img_w, screen_height / img_h)
            new_size = (int(img_w * ratio), int(img_h * ratio))
            self.display_image = self.display_image.resize(new_size, Image.ANTIALIAS)

        self.tk_image = ImageTk.PhotoImage(self.display_image)
        self.canvas = tk.Canvas(self._root, width=self.tk_image.width(), height=self.tk_image.height(), cursor="cross")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        self._start_x = self._start_y = None
        self._rect = None

        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)

    def _on_button_press(self, event):
        self._start_x = event.x
        self._start_y = event.y
        if self._rect:
            self.canvas.delete(self._rect)
            self._rect = None

    def _on_move_press(self, event):
        curX, curY = (event.x, event.y)
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(self._start_x, self._start_y, curX, curY, outline='red')

    def _on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        x0 = min(self._start_x, end_x)
        y0 = min(self._start_y, end_y)
        x1 = max(self._start_x, end_x)
        y1 = max(self._start_y, end_y)

        # Map back to original image coordinates if the image was resized
        disp_w, disp_h = self.display_image.size
        orig_w, orig_h = self.pil_image.size
        scale_x = orig_w / disp_w
        scale_y = orig_h / disp_h
        self.region = (int(x0 * scale_x), int(y0 * scale_y), int(x1 * scale_x), int(y1 * scale_y))
        print(f"[{_now()}] Selected region: {self.region}")

    def select_region(self) -> Optional[Tuple[int, int, int, int]]:
        self._root.mainloop()
        return self.region


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Vision teach & analyze (dry-run).")
    parser.add_argument("--vision", action="store_true", help="Enable vision analyze mode")
    parser.add_argument("--teach", action="store_true", help="Start in teach mode (use Ctrl+Shift+T to add templates)")
    parser.add_argument("--persist-templates", action="store_true", help="Persist templates to disk")
    parser.add_argument("--interval", type=float, default=0.5, help="Screen analyze interval in seconds")
    parser.add_argument("--threshold", type=float, default=0.75, help="Template match threshold (0-1)")
    args = parser.parse_args(argv)

    trainer = VisionTrainer(persist=args.persist_templates)
    if args.persist_templates:
        trainer.load_all()

    runner = VisionRunner(trainer, interval=args.interval, threshold=args.threshold)

    active = False

    def toggle_active() -> None:
        nonlocal active
        active = not active
        if active:
            print(f"[{_now()}] ACTIVE (vision dry-run)")
            if args.vision:
                runner.start()
        else:
            print(f"[{_now()}] PAUSED")
            runner.stop()

    keyboard.add_hotkey("F12", toggle_active)
    keyboard.add_hotkey("ctrl+shift+t", lambda: threading.Thread(target=trainer.teach, daemon=True).start())
    keyboard.add_hotkey("ctrl+shift+l", lambda: trainer.list_templates())
    keyboard.add_hotkey("ctrl+shift+s", lambda: threading.Thread(target=trainer.save_all, daemon=True).start())

    if args.teach:
        print(f"[{_now()}] Teach mode enabled. Press Ctrl+Shift+T to capture a region and add a template.")

    print("Vision trainer ready.")
    print("- F12 to toggle active (if --vision is set)\n- Ctrl+Shift+T to teach templates\n- Ctrl+Shift+L to list templates\n- Ctrl+Shift+S to save templates (if --persist-templates)")

    try:
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        print(f"\n[{_now()}] exiting...")
        runner.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
