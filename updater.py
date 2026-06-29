import os
import sys
import json
import shutil
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk
from urllib.request import urlopen, Request
from urllib.error import URLError
from packaging.version import Version

GITHUB_OWNER   = "sadaadiel-gif"
GITHUB_REPO    = "PDF417Studio"
EXE_NAME       = "PDF417Studio.exe"
VERSION_FILE   = "version.txt"
API_URL        = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
DOWNLOAD_URL   = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest/download/{EXE_NAME}"

HEADERS = {
    "Accept":     "application/vnd.github+json",
    "User-Agent": f"{GITHUB_REPO}-updater/1.0",
}

def _exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_local_version() -> str:
    path = os.path.join(_exe_dir(), VERSION_FILE)
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "1.0.0"

def get_remote_version() -> tuple[str, str]:
    req  = Request(API_URL, headers=HEADERS)
    with urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read())
    tag  = data["tag_name"].lstrip("v")
    for asset in data.get("assets", []):
        if asset["name"] == EXE_NAME:
            return tag, asset["browser_download_url"]
    return tag, DOWNLOAD_URL

def is_newer(remote: str, local: str) -> bool:
    try:
        return Version(remote) > Version(local)
    except Exception:
        return False

def download_update(url: str, progress_cb=None) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        tmp   = tempfile.NamedTemporaryFile(
            delete=False, suffix=".exe",
            prefix="PDF417Studio_update_"
        )
        downloaded = 0
        chunk_size = 65536
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            tmp.write(chunk)
            downloaded += len(chunk)
            if progress_cb:
                progress_cb(downloaded, total)
        tmp.close()
    return tmp.name

def apply_update(tmp_exe: str):
    current_exe = sys.executable if getattr(sys, "frozen", False) else None
    if current_exe is None:
        os.startfile(os.path.dirname(tmp_exe))
        return
    bat = tempfile.NamedTemporaryFile(
        delete=False, suffix=".bat", mode="w",
        prefix="pdf417_update_"
    )
    bat.write(
        f'@echo off\n'
        f'ping 127.0.0.1 -n 3 > nul\n'
        f'move /Y "{tmp_exe}" "{current_exe}"\n'
        f'start "" "{current_exe}"\n'
        f'del "%~f0"\n'
    )
    bat.close()
    subprocess.Popen(["cmd.exe", "/c", bat.name],
                     creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit(0)

class UpdateToast(tk.Toplevel):
    def __init__(self, parent: tk.Tk, remote_version: str, download_url: str):
        super().__init__(parent)
        self._parent        = parent
        self._remote_ver    = remote_version
        self._download_url  = download_url
        self._dismissed     = False
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)
        self.configure(bg="#11131f")
        self._build()
        self._position()
        self._fade_in()

    def _build(self):
        outer = tk.Frame(self, bg="#11131f", bd=1, relief="solid",
                         highlightbackground="#4f8ef7", highlightthickness=1)
        outer.pack(fill="both", expand=True, padx=1, pady=1)
        hdr = tk.Frame(outer, bg="#1a1a2e")
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔄  Update Available",
                 bg="#1a1a2e", fg="white",
                 font=("Helvetica", 11, "bold"),
                 pady=10, padx=14).pack(side="left")
        tk.Button(hdr, text="✕", bg="#1a1a2e", fg="#7a83a6",
                  relief="flat", cursor="hand2",
                  font=("Helvetica", 10),
                  command=self._dismiss).pack(side="right", padx=8)
        body = tk.Frame(outer, bg="#11131f", padx=14, pady=10)
        body.pack(fill="x")
        local = get_local_version()
        tk.Label(body,
                 text=f"PDF417 Studio {self._remote_ver} is available\n"
                      f"(you have {local})",
                 bg="#11131f", fg="#e8ecf4",
                 font=("Helvetica", 9),
                 justify="left").pack(anchor="w")
        self._progress_var = tk.DoubleVar(value=0)
        self._progress     = ttk.Progressbar(
            body, variable=self._progress_var,
            maximum=100, length=260, mode="determinate"
        )
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(body, textvariable=self._status_var,
                                    bg="#11131f", fg="#7a83a6",
                                    font=("Helvetica", 8))
        btns = tk.Frame(body, bg="#11131f")
        btns.pack(fill="x", pady=(10, 0))
        self._install_btn = tk.Button(
            btns, text="Install Update",
            bg="#4f8ef7", fg="white",
            relief="flat", cursor="hand2",
            font=("Helvetica", 9, "bold"),
            padx=12, pady=5,
            command=self._install
        )
        self._install_btn.pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Later",
                  bg="#242840", fg="#e8ecf4",
                  relief="flat", cursor="hand2",
                  font=("Helvetica", 9),
                  padx=12, pady=5,
                  command=self._dismiss).pack(side="left")

    def _position(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = 300
        h  = self.winfo_reqheight() or 160
        x  = sw - w - 24
        y  = sh - h - 60
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _fade_in(self, alpha=0.0):
        if self._dismissed:
            return
        alpha = min(alpha + 0.07, 0.97)
        self.attributes("-alpha", alpha)
        if alpha < 0.97:
            self.after(20, self._fade_in, alpha)

    def _dismiss(self):
        self._dismissed = True
        self.destroy()

    def _install(self):
        self._install_btn.config(state="disabled", text="Downloading…")
        self._progress.pack(fill="x", pady=(8, 2))
        self._status_lbl.pack(anchor="w")
        self._position()
        def _do_download():
            def _progress(dl, total):
                if total:
                    pct = dl / total * 100
                    self._progress_var.set(pct)
                    self._status_var.set(
                        f"{dl//1024} KB / {total//1024} KB")
                else:
                    self._status_var.set(f"{dl//1024} KB downloaded…")
            try:
                tmp = download_update(self._download_url, _progress)
                self._status_var.set("Installing…")
                self.after(500, lambda: apply_update(tmp))
            except Exception as exc:
                self._status_var.set(f"Failed: {exc}")
                self._install_btn.config(state="normal", text="Retry")
        threading.Thread(target=_do_download, daemon=True).start()

def check_for_update(root: tk.Tk, silent: bool = True):
    def _run():
        try:
            remote_ver, dl_url = get_remote_version()
            local_ver          = get_local_version()
            if is_newer(remote_ver, local_ver):
                root.after(2000, lambda: UpdateToast(root, remote_ver, dl_url))
        except (URLError, Exception):
            pass
    threading.Thread(target=_run, daemon=True).start()