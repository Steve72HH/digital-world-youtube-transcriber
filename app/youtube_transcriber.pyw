import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import BooleanVar, PhotoImage, StringVar, Tk, filedialog, messagebox
from tkinter import ttk


APP_NAME = "Digital World YouTube Transcriber"
APP_VERSION = "1.1.0"
APP_CREATED = "Mai 2026"
APP_WEBSITE = "digital-world.dev"
APP_CONTACT = "kontakt@digital-world.dev"
GITHUB_REPO = "Steve72HH/digital-world-youtube-transcriber"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DEFAULT_OUTPUT_DIR = Path("I:/transkriptions")
DOWNLOAD_TEMPLATE = "%(uploader)s-%(id)s.%(ext)s"
VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".flv",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_dir()
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
CONFIG_PATH = BASE_DIR / "yt_transcriber_config.json"
LOGO_PATH = RESOURCE_DIR / "assets" / "logo.png"


def load_config() -> dict:
    defaults = {
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "yt_dlp_path": "",
        "whisper_path": "",
        "model": "small",
        "language": "de",
        "open_folder": True,
        "platform": "Auto",
        "export_txt": True,
        "export_md": False,
        "export_pdf": False,
        "timestamps": False,
        "check_updates": True,
    }
    if not CONFIG_PATH.exists():
        return defaults
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    defaults.update({key: value for key, value in data.items() if value is not None})
    return defaults


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_version(version: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def seconds_to_stamp(seconds: float) -> str:
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def plain_transcript(segments: list[dict], timestamps: bool) -> str:
    lines = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        if timestamps:
            start = seconds_to_stamp(float(segment.get("start", 0)))
            end = seconds_to_stamp(float(segment.get("end", 0)))
            lines.append(f"[{start} - {end}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines).strip() + "\n"


def markdown_transcript(video_path: Path, segments: list[dict], timestamps: bool) -> str:
    body = plain_transcript(segments, timestamps)
    return f"# Transkript\n\n**Quelle:** `{video_path.name}`\n\n{body}"


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_line(line: str, width: int = 92) -> list[str]:
    words = line.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current += " " + word
    lines.append(current)
    return lines


def write_simple_pdf(path: Path, title: str, text: str) -> None:
    wrapped = [title, ""]
    for line in text.splitlines():
        wrapped.extend(wrap_line(line))

    pages = []
    for index in range(0, len(wrapped), 44):
        pages.append(wrapped[index : index + 44])

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_refs = " ".join(f"{3 + idx * 2} 0 R" for idx in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{page_refs}] /Count {len(pages)} >>".encode("ascii"))

    for idx, page_lines in enumerate(pages):
        page_obj = 3 + idx * 2
        content_obj = page_obj + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_obj} 0 R >>".encode(
                "ascii"
            )
        )
        stream_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for line in page_lines:
            safe = pdf_escape(line).encode("cp1252", errors="replace").decode("cp1252")
            stream_lines.append(f"({safe}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("cp1252", errors="replace")
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{idx} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_pos = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    path.write_bytes(bytes(content))


def executable_exists(path: str) -> bool:
    try:
        return bool(path and Path(path).exists() and Path(path).is_file())
    except OSError:
        return bool(path and path.lower().endswith(".exe"))


def find_executable(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found

    candidates = [
        Path.home() / f"{name}.exe",
        Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "Scripts" / f"{name}.exe",
        Path.home() / "AppData" / "Roaming" / "Python" / "Python312" / "Scripts" / f"{name}.exe",
        Path.home() / "AppData" / "Roaming" / "Python" / "Python311" / "Scripts" / f"{name}.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python313" / "Scripts" / f"{name}.exe",
        Path("C:/Python313/Scripts") / f"{name}.exe",
        Path("C:/Python312/Scripts") / f"{name}.exe",
        Path("C:/Python311/Scripts") / f"{name}.exe",
    ]
    for candidate in candidates:
        try:
            exists = candidate.exists()
        except OSError:
            exists = True
        if exists:
            return str(candidate)
    return ""


def find_js_runtime() -> str:
    for name in ("deno", "node", "bun"):
        found = shutil.which(name)
        if found:
            return name

    candidates = [
        Path("D:/Program Files/nodejs/node.exe"),
        Path("C:/Program Files/nodejs/node.exe"),
        Path("C:/Program Files (x86)/nodejs/node.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "nodejs" / "node.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return f"node:{candidate}"
    return ""


def stream_process(command: list[str], cwd: Path, log) -> tuple[int, list[str]]:
    log(f"> {' '.join(command)}")
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        clean = line.rstrip()
        lines.append(clean)
        log(clean)
    return process.wait(), lines


def newest_media_file(output_dir: Path, since: float) -> Path | None:
    files = [
        path
        for path in output_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
        and path.stat().st_mtime >= since - 2
    ]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


class TranscriberApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("900x720")
        self.root.minsize(760, 640)

        self.config = load_config()
        if not self.config["yt_dlp_path"]:
            self.config["yt_dlp_path"] = find_executable("yt-dlp")
        if not self.config["whisper_path"]:
            self.config["whisper_path"] = find_executable("whisper")

        self.url = StringVar(value="")
        self.output_dir = StringVar(value=self.config["output_dir"])
        self.yt_dlp_path = StringVar(value=self.config["yt_dlp_path"])
        self.whisper_path = StringVar(value=self.config["whisper_path"])
        self.model = StringVar(value=self.config["model"])
        self.language = StringVar(value=self.config["language"])
        self.platform = StringVar(value=self.config["platform"])
        self.open_folder = BooleanVar(value=bool(self.config["open_folder"]))
        self.export_txt = BooleanVar(value=bool(self.config["export_txt"]))
        self.export_md = BooleanVar(value=bool(self.config["export_md"]))
        self.export_pdf = BooleanVar(value=bool(self.config["export_pdf"]))
        self.timestamps = BooleanVar(value=bool(self.config["timestamps"]))
        self.check_updates = BooleanVar(value=bool(self.config["check_updates"]))
        self.status = StringVar(value="Bereit")
        self.update_status = StringVar(value="Nicht geprüft")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.logo_image = None
        self.build_ui()
        self.root.after(120, self.flush_log_queue)
        if self.check_updates.get():
            self.root.after(900, lambda: self.check_for_updates(silent=True))

    def build_ui(self) -> None:
        self.root.configure(bg="#f7f8fb")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f7f8fb")
        style.configure("Header.TFrame", background="#111827")
        style.configure("TLabel", background="#f7f8fb", foreground="#111827", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#f7f8fb", foreground="#667085")
        style.configure("Header.TLabel", background="#111827", foreground="#ffffff", font=("Segoe UI", 18, "bold"))
        style.configure("HeaderSmall.TLabel", background="#111827", foreground="#cbd5e1", font=("Segoe UI", 10))
        style.configure("InfoTitle.TLabel", background="#f7f8fb", foreground="#111827", font=("Segoe UI", 18, "bold"))
        style.configure("InfoValue.TLabel", background="#f7f8fb", foreground="#111827", font=("Segoe UI", 12))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(16, 10))
        style.configure("TEntry", padding=8)

        header = ttk.Frame(self.root, style="Header.TFrame", padding=(24, 18))
        header.pack(fill="x")

        if LOGO_PATH.exists():
            try:
                source_logo = PhotoImage(file=str(LOGO_PATH))
                scale = max(1, min(source_logo.width() // 150, source_logo.height() // 84))
                self.logo_image = source_logo.subsample(scale, scale)
                logo_label = ttk.Label(header, image=self.logo_image, background="#111827")
                logo_label.pack(side="left", padx=(0, 18))
            except Exception:
                self.logo_image = None

        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="YouTube Transcriber", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="YouTube, TikTok und weitere Videos laden, lokal speichern und direkt mit Whisper transkribieren.",
            style="HeaderSmall.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)

        body = ttk.Frame(notebook, padding=24)
        notebook.add(body, text="Transkription")
        body.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(body, text="Video URL").grid(row=row, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(body, textvariable=self.url).grid(row=row, column=1, sticky="ew", pady=(0, 8), padx=(12, 0))

        row += 1
        ttk.Label(body, text="Plattform").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Combobox(
            body,
            textvariable=self.platform,
            values=("Auto", "YouTube", "TikTok"),
            state="readonly",
            width=16,
        ).grid(row=row, column=1, sticky="w", pady=8, padx=(12, 0))

        row += 1
        ttk.Label(body, text="Zielordner").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(body, textvariable=self.output_dir).grid(row=row, column=1, sticky="ew", pady=8, padx=(12, 8))
        ttk.Button(body, text="Ordner", command=self.choose_output_dir).grid(row=row, column=2, sticky="ew", pady=8)

        row += 1
        ttk.Label(body, text="yt-dlp").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(body, textvariable=self.yt_dlp_path).grid(row=row, column=1, sticky="ew", pady=8, padx=(12, 8))
        ttk.Button(body, text="Auswählen", command=lambda: self.choose_exe(self.yt_dlp_path)).grid(
            row=row, column=2, sticky="ew", pady=8
        )

        row += 1
        ttk.Label(body, text="Whisper").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(body, textvariable=self.whisper_path).grid(row=row, column=1, sticky="ew", pady=8, padx=(12, 8))
        ttk.Button(body, text="Auswählen", command=lambda: self.choose_exe(self.whisper_path)).grid(
            row=row, column=2, sticky="ew", pady=8
        )

        row += 1
        ttk.Label(body, text="Whisper Modell").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Combobox(
            body,
            textvariable=self.model,
            values=("tiny", "base", "small", "medium", "large"),
            state="readonly",
            width=16,
        ).grid(row=row, column=1, sticky="w", pady=8, padx=(12, 0))

        options = ttk.Frame(body)
        options.grid(row=row, column=1, sticky="e", pady=8)
        ttk.Label(options, text="Sprache").pack(side="left", padx=(0, 8))
        ttk.Combobox(
            options,
            textvariable=self.language,
            values=("de", "en", "auto"),
            state="readonly",
            width=8,
        ).pack(side="left")
        ttk.Checkbutton(options, text="Ordner danach öffnen", variable=self.open_folder).pack(side="left", padx=(18, 0))

        row += 1
        ttk.Label(body, text="Export").grid(row=row, column=0, sticky="w", pady=8)
        export_options = ttk.Frame(body)
        export_options.grid(row=row, column=1, sticky="w", pady=8, padx=(12, 0))
        ttk.Checkbutton(export_options, text="TXT", variable=self.export_txt).pack(side="left")
        ttk.Checkbutton(export_options, text="Markdown", variable=self.export_md).pack(side="left", padx=(14, 0))
        ttk.Checkbutton(export_options, text="PDF", variable=self.export_pdf).pack(side="left", padx=(14, 0))
        ttk.Checkbutton(export_options, text="Zeitstempel", variable=self.timestamps).pack(side="left", padx=(18, 0))

        row += 1
        actions = ttk.Frame(body)
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(18, 14))
        self.start_button = ttk.Button(actions, text="Download & Transkription starten", style="Primary.TButton", command=self.start)
        self.start_button.pack(side="left")
        ttk.Button(actions, text="Pfade neu suchen", command=self.refresh_tools).pack(side="left", padx=(12, 0))
        ttk.Label(actions, textvariable=self.status, style="Muted.TLabel").pack(side="right")

        row += 1
        ttk.Label(body, text="Protokoll").grid(row=row, column=0, sticky="nw", pady=(0, 8))
        log_frame = ttk.Frame(body)
        log_frame.grid(row=row, column=1, columnspan=2, sticky="nsew", padx=(12, 0))
        body.rowconfigure(row, weight=1)
        self.log_text = self.make_log_widget(log_frame)

        info = ttk.Frame(notebook, padding=32)
        notebook.add(info, text="Info")
        self.build_info_tab(info)

        updates = ttk.Frame(notebook, padding=32)
        notebook.add(updates, text="Updates")
        self.build_updates_tab(updates)

    def build_info_tab(self, parent) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=APP_NAME, style="InfoTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 26)
        )

        rows = [
            ("App Name", APP_NAME),
            ("Versionsnummer", APP_VERSION),
            ("Erstellungsmonat/Jahr", APP_CREATED),
            ("Website", APP_WEBSITE),
            ("Kontakt-Mail", APP_CONTACT),
        ]
        for index, (label, value) in enumerate(rows, start=1):
            ttk.Label(parent, text=label, style="Muted.TLabel").grid(row=index, column=0, sticky="w", pady=8, padx=(0, 28))
            ttk.Label(parent, text=value, style="InfoValue.TLabel").grid(row=index, column=1, sticky="w", pady=8)

    def build_updates_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Updates", style="InfoTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 18))
        ttk.Label(
            parent,
            text="Die App kann GitHub Releases prüfen und bei einer neuen Version den Installer herunterladen.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(0, 18))
        ttk.Checkbutton(parent, text="Beim Start nach Updates suchen", variable=self.check_updates, command=self.persist_config).grid(
            row=2, column=0, sticky="w", pady=8
        )
        ttk.Label(parent, textvariable=self.update_status, style="InfoValue.TLabel").grid(row=3, column=0, sticky="w", pady=(18, 8))
        ttk.Button(parent, text="Jetzt nach Updates suchen", command=lambda: self.check_for_updates(silent=False)).grid(
            row=4, column=0, sticky="w", pady=8
        )

    def make_log_widget(self, parent):
        import tkinter as tk

        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        text = tk.Text(
            parent,
            height=16,
            wrap="word",
            bg="#ffffff",
            fg="#111827",
            insertbackground="#111827",
            relief="solid",
            borderwidth=1,
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        return text

    def choose_output_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir.get() or str(DEFAULT_OUTPUT_DIR))
        if chosen:
            self.output_dir.set(chosen)
            self.persist_config()

    def choose_exe(self, variable: StringVar) -> None:
        chosen = filedialog.askopenfilename(filetypes=(("Programme", "*.exe"), ("Alle Dateien", "*.*")))
        if chosen:
            variable.set(chosen)
            self.persist_config()

    def refresh_tools(self) -> None:
        self.yt_dlp_path.set(find_executable("yt-dlp"))
        self.whisper_path.set(find_executable("whisper"))
        self.persist_config()
        self.log("Tool-Suche abgeschlossen.")

    def persist_config(self) -> None:
        save_config(
            {
                "output_dir": self.output_dir.get().strip(),
                "yt_dlp_path": self.yt_dlp_path.get().strip(),
                "whisper_path": self.whisper_path.get().strip(),
                "model": self.model.get(),
                "language": self.language.get(),
                "platform": self.platform.get(),
                "open_folder": self.open_folder.get(),
                "export_txt": self.export_txt.get(),
                "export_md": self.export_md.get(),
                "export_pdf": self.export_pdf.get(),
                "timestamps": self.timestamps.get(),
                "check_updates": self.check_updates.get(),
            }
        )

    def log(self, text: str) -> None:
        self.log_queue.put(text)

    def flush_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert("end", f"{line}\n")
            self.log_text.see("end")
        self.root.after(120, self.flush_log_queue)

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        url = self.url.get().strip()
        if not url:
            messagebox.showwarning(APP_NAME, "Bitte zuerst eine YouTube URL eintragen.")
            return
        output_dir = Path(self.output_dir.get().strip())
        yt_dlp = self.yt_dlp_path.get().strip()
        whisper = self.whisper_path.get().strip()
        if not (self.export_txt.get() or self.export_md.get() or self.export_pdf.get()):
            messagebox.showwarning(APP_NAME, "Bitte mindestens ein Exportformat auswählen.")
            return
        if not executable_exists(yt_dlp):
            messagebox.showerror(APP_NAME, "yt-dlp wurde nicht gefunden. Bitte die yt-dlp.exe auswählen.")
            return
        if not executable_exists(whisper):
            messagebox.showerror(APP_NAME, "Whisper wurde nicht gefunden. Bitte die whisper.exe auswählen.")
            return

        self.persist_config()
        self.start_button.configure(state="disabled")
        self.status.set("Läuft...")
        self.worker = threading.Thread(target=self.run_job, args=(url, output_dir, yt_dlp, whisper), daemon=True)
        self.worker.start()

    def run_job(self, url: str, output_dir: Path, yt_dlp: str, whisper: str) -> None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            started = time.time()
            self.log("")
            self.log("Download startet...")
            yt_command = [
                yt_dlp,
                "-P",
                str(output_dir),
                "-o",
                DOWNLOAD_TEMPLATE,
                "--print",
                "after_move:filepath",
                url,
            ]
            js_runtime = find_js_runtime()
            if js_runtime:
                yt_command[1:1] = ["--js-runtimes", js_runtime]
            code, lines = stream_process(yt_command, output_dir, self.log)
            if code != 0:
                raise RuntimeError(f"yt-dlp wurde mit Code {code} beendet.")

            video_path = self.detect_downloaded_file(output_dir, lines, started)
            if not video_path:
                raise RuntimeError("Download erfolgreich, aber die Videodatei konnte nicht eindeutig gefunden werden.")

            self.log(f"Videodatei: {video_path}")
            self.log("Whisper startet...")
            self.log("Hinweis: Die Transkription kann je nach Videolänge und Modell einige Minuten dauern.")
            whisper_command = [
                whisper,
                str(video_path),
                "--model",
                self.model.get(),
                "--output_dir",
                str(output_dir),
                "--output_format",
                "json",
            ]
            if self.language.get() != "auto":
                whisper_command.extend(["--language", self.language.get()])

            code, _ = stream_process(whisper_command, output_dir, self.log)
            if code != 0:
                raise RuntimeError(f"Whisper wurde mit Code {code} beendet.")

            self.create_exports(video_path, output_dir)
            self.log("Fertig. Transkript-Export liegt im gleichen Ordner.")
            self.root.after(0, lambda: self.status.set("Fertig"))
            if self.open_folder.get() and os.name == "nt":
                os.startfile(str(output_dir))
        except Exception as exc:
            self.log(f"FEHLER: {exc}")
            message = str(exc)
            self.root.after(0, lambda: self.status.set("Fehler"))
            self.root.after(0, lambda: messagebox.showerror(APP_NAME, message))
        finally:
            self.root.after(0, lambda: self.start_button.configure(state="normal"))

    def detect_downloaded_file(self, output_dir: Path, lines: list[str], started: float) -> Path | None:
        for line in reversed(lines):
            candidate = Path(line.strip().strip('"'))
            if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS:
                return candidate
        return newest_media_file(output_dir, started)

    def create_exports(self, video_path: Path, output_dir: Path) -> None:
        json_path = output_dir / f"{video_path.stem}.json"
        if not json_path.exists():
            raise RuntimeError(f"Whisper JSON wurde nicht gefunden: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        segments = data.get("segments") or []
        if not segments:
            text = str(data.get("text", "")).strip()
            segments = [{"start": 0, "end": 0, "text": text}]

        if self.export_txt.get():
            target = output_dir / f"{video_path.stem}.txt"
            target.write_text(plain_transcript(segments, self.timestamps.get()), encoding="utf-8")
            self.log(f"TXT exportiert: {target.name}")
        if self.export_md.get():
            target = output_dir / f"{video_path.stem}.md"
            target.write_text(markdown_transcript(video_path, segments, self.timestamps.get()), encoding="utf-8")
            self.log(f"Markdown exportiert: {target.name}")
        if self.export_pdf.get():
            target = output_dir / f"{video_path.stem}.pdf"
            write_simple_pdf(target, f"Transkript - {video_path.name}", plain_transcript(segments, self.timestamps.get()))
            self.log(f"PDF exportiert: {target.name}")

    def check_for_updates(self, silent: bool) -> None:
        self.update_status.set("Prüfe Updates...")
        threading.Thread(target=self.run_update_check, args=(silent,), daemon=True).start()

    def run_update_check(self, silent: bool) -> None:
        try:
            request = urllib.request.Request(LATEST_RELEASE_API, headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(request, timeout=10) as response:
                release = json.loads(response.read().decode("utf-8"))
            latest_tag = release.get("tag_name", "")
            latest_version = parse_version(latest_tag)
            current_version = parse_version(APP_VERSION)
            release_url = release.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")

            if latest_version <= current_version:
                self.root.after(0, lambda: self.update_status.set(f"Aktuell: Version {APP_VERSION}"))
                if not silent:
                    self.root.after(0, lambda: messagebox.showinfo(APP_NAME, "Du nutzt bereits die aktuelle Version."))
                return

            self.root.after(0, lambda: self.update_status.set(f"Update verfügbar: {latest_tag}"))
            assets = release.get("assets", [])
            installer = next((asset for asset in assets if asset.get("name", "").endswith(".exe") and "Installer" in asset.get("name", "")), None)
            if self.root.after:
                self.root.after(0, lambda: self.offer_update(latest_tag, release_url, installer))
        except Exception as exc:
            self.root.after(0, lambda: self.update_status.set("Update-Prüfung fehlgeschlagen"))
            if not silent:
                message = str(exc)
                self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"Update-Prüfung fehlgeschlagen:\n{message}"))

    def offer_update(self, latest_tag: str, release_url: str, installer: dict | None) -> None:
        if not messagebox.askyesno(APP_NAME, f"Version {latest_tag} ist verfügbar.\n\nInstaller herunterladen und starten?"):
            webbrowser.open(release_url)
            return
        if not installer:
            webbrowser.open(release_url)
            return
        threading.Thread(target=self.download_and_start_update, args=(installer,), daemon=True).start()

    def download_and_start_update(self, installer: dict) -> None:
        try:
            url = installer["browser_download_url"]
            name = installer["name"]
            target = Path(os.environ.get("TEMP", str(BASE_DIR))) / name
            self.root.after(0, lambda: self.update_status.set("Lade Update herunter..."))
            urllib.request.urlretrieve(url, target)
            self.root.after(0, lambda: self.update_status.set(f"Update geladen: {target.name}"))
            if os.name == "nt":
                os.startfile(str(target))
        except Exception as exc:
            message = str(exc)
            self.root.after(0, lambda: self.update_status.set("Update-Download fehlgeschlagen"))
            self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"Update-Download fehlgeschlagen:\n{message}"))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    TranscriberApp().run()
