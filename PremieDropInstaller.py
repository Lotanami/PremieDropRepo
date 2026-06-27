import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import urlopen


APP_NAME = "PremieDrop"
EXE_NAME = "premiedrop.exe"
DOWNLOAD_URL = os.environ.get(
    "PREMIEDROP_DOWNLOAD_URL",
    "https://github.com/Lotanami/PremieDropRepo/releases/latest/download/premiedrop.exe",
)


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_path) / relative_path


def local_app_dir():
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / APP_NAME


def desktop_dir():
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def run_hidden(command):
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(
        command,
        startupinfo=startupinfo,
        capture_output=True,
        text=True,
        check=False,
    )


def ps_single_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PremieDrop Installer")
        self.geometry("520x370")
        self.minsize(520, 370)
        self.resizable(False, False)

        self.install_cep = tk.BooleanVar(value=True)
        self.install_shortcut = tk.BooleanVar(value=True)
        self.install_dir = tk.StringVar(value=str(local_app_dir()))
        self.status_text = tk.StringVar(value="Ready to install PremieDrop.")

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="PremieDrop", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            frame,
            text="Install the desktop app and optional editor integrations.",
        )
        subtitle.pack(anchor="w", pady=(2, 16))

        path_frame = ttk.LabelFrame(frame, text="Install location", padding=10)
        path_frame.pack(fill="x")
        path_entry = ttk.Entry(path_frame, textvariable=self.install_dir)
        path_entry.pack(side="left", fill="x", expand=True)

        options = ttk.LabelFrame(frame, text="Editor packages", padding=10)
        options.pack(fill="x", pady=(14, 0))

        ttk.Checkbutton(
            options,
            text="Premiere Pro CEP extension",
            variable=self.install_cep,
        ).pack(anchor="w")

        uxp = ttk.Checkbutton(
            options,
            text="Premiere Pro UXP extension (coming soon)",
            state="disabled",
        )
        uxp.pack(anchor="w", pady=(6, 0))

        extras = ttk.LabelFrame(frame, text="Shortcuts", padding=10)
        extras.pack(fill="x", pady=(14, 0))
        ttk.Checkbutton(
            extras,
            text="Create desktop shortcut",
            variable=self.install_shortcut,
        ).pack(anchor="w")

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(16, 8))

        ttk.Label(frame, textvariable=self.status_text).pack(anchor="w")

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(18, 0))

        self.install_button = ttk.Button(
            button_row,
            text="Install",
            command=self.start_install,
        )
        self.install_button.pack(side="right")

        ttk.Button(button_row, text="Cancel", command=self.destroy).pack(
            side="right",
            padx=(0, 8),
        )

    def start_install(self):
        self.install_button.configure(state="disabled")
        self.progress.start(12)
        thread = threading.Thread(target=self.install, daemon=True)
        thread.start()

    def install(self):
        try:
            install_dir = Path(self.install_dir.get()).expanduser()
            install_dir.mkdir(parents=True, exist_ok=True)

            exe_path = install_dir / EXE_NAME
            self.set_status("Downloading premiedrop.exe...")
            self.download_file(DOWNLOAD_URL, exe_path)

            if self.install_cep.get():
                self.set_status("Installing Premiere Pro CEP extension...")
                self.install_cep_extension()

            if self.install_shortcut.get():
                self.set_status("Creating desktop shortcut...")
                self.create_shortcut(exe_path)

            self.set_status("PremieDrop installed.")
            self.after(0, self.install_complete, exe_path)
        except Exception as exc:
            self.after(0, self.install_failed, exc)

    def download_file(self, url, destination):
        temporary = destination.with_suffix(".download")
        try:
            with urlopen(url, timeout=60) as response:
                with open(temporary, "wb") as file_handle:
                    shutil.copyfileobj(response, file_handle)
            temporary.replace(destination)
        except URLError as exc:
            raise RuntimeError(f"Could not download PremieDrop from {url}: {exc}") from exc
        finally:
            if temporary.exists():
                temporary.unlink()

    def install_cep_extension(self):
        source = resource_path("cep-extension")
        script = source / "install.ps1"
        if not script.exists():
            raise RuntimeError("The CEP extension payload is missing from the installer.")

        result = run_hidden([
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ])
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"CEP extension install failed. {details}")

    def create_shortcut(self, exe_path):
        shortcut = desktop_dir() / "PremieDrop.lnk"
        script = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut({ps_single_quote(shortcut)}); "
            f"$shortcut.TargetPath = {ps_single_quote(exe_path)}; "
            f"$shortcut.WorkingDirectory = {ps_single_quote(exe_path.parent)}; "
            "$shortcut.Save()"
        )
        result = run_hidden([
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ])
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Shortcut creation failed. {details}")

    def set_status(self, text):
        self.after(0, self.status_text.set, text)

    def install_complete(self, exe_path):
        self.progress.stop()
        self.install_button.configure(state="normal")
        if messagebox.askyesno(
            "PremieDrop installed",
            "PremieDrop installed successfully. Launch it now?",
        ):
            subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
            self.destroy()

    def install_failed(self, exc):
        self.progress.stop()
        self.install_button.configure(state="normal")
        self.status_text.set("Install failed.")
        messagebox.showerror("Install failed", str(exc))


if __name__ == "__main__":
    InstallerApp().mainloop()
