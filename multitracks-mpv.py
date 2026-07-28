#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import sys
import time

from PyQt6.QtCore import QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MASTER_SOCKET = "/tmp/qt-mpv-master.sock"
SLAVE_SOCKET = "/tmp/qt-mpv-slave.sock"


def cleanup_sockets():
    for sock in [MASTER_SOCKET, SLAVE_SOCKET]:
        if os.path.exists(sock):
            try:
                os.remove(sock)
            except OSError:
                pass


def get_audio_devices():
    """Queries PipeWire/PulseAudio via pactl to get a list of sink names and descriptions."""
    devices = [("System Default", "")]
    try:
        output = subprocess.check_output(
            ["pactl", "list", "sinks"], text=True, stderr=subprocess.DEVNULL
        )
        current_name = ""
        current_desc = ""

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                current_name = line.split("Name:")[1].strip()
            elif line.startswith("Description:"):
                current_desc = line.split("Description:")[1].strip()
                if current_name and current_desc:
                    devices.append((current_desc, f"pulse/{current_name}"))
                    current_name, current_desc = "", ""
    except Exception:
        pass
    return devices


def get_audio_tracks(file_path):
    """Uses ffprobe to list audio tracks, languages, and titles inside the file."""
    tracks = []
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index,codec_name:stream_tags=language,title",
        "-of",
        "json",
        file_path,
    ]
    try:
        res = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        data = json.loads(res)
        for i, stream in enumerate(data.get("streams", [])):
            mpv_aid = i + 1  # mpv audio tracks start at 1
            codec = stream.get("codec_name", "unknown")
            tags = stream.get("tags", {})
            lang = tags.get("language", "")
            title = tags.get("title", "")

            label = f"Track {mpv_aid}: {codec.upper()}"
            if lang:
                label += f" [{lang}]"
            if title:
                label += f" - {title}"

            tracks.append((label, mpv_aid))
    except Exception:
        pass

    if not tracks:
        tracks = [("Track 1", 1), ("Track 2", 2)]
    return tracks


def send_ipc(sock_path, command):
    if not os.path.exists(sock_path):
        return None
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_path)
        payload = json.dumps({"command": command}) + "\n"
        client.sendall(payload.encode("utf-8"))
        data = client.recv(4096).decode("utf-8")
        client.close()
        return data
    except Exception:
        return None


class SyncThread(QThread):
    """Background thread that listens to master player state and mirrors it to slave."""

    master_closed = pyqtSignal()

    def run(self):
        time.sleep(1.0)
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(MASTER_SOCKET)
        except Exception:
            return

        stream = sock.makefile("rw")
        try:
            stream.write(
                json.dumps({"command": ["observe_property", 1, "pause"]}) + "\n"
            )
            stream.write(
                json.dumps({"command": ["observe_property", 2, "time-pos"]})
                + "\n"
            )
            stream.flush()

            while not self.isInterruptionRequested():
                line = stream.readline()
                if not line:
                    # Master IPC pipe closed (Master mpv was quit)
                    break
                try:
                    data = json.loads(line)
                    if data.get("event") == "property-change":
                        prop = data.get("name")
                        val = data.get("data")

                        if prop == "pause" and val is not None:
                            send_ipc(
                                SLAVE_SOCKET, ["set_property", "pause", val]
                            )
                        elif prop == "time-pos" and val is not None:
                            res = send_ipc(
                                SLAVE_SOCKET, ["get_property", "time-pos"]
                            )
                            if res:
                                slave_data = json.loads(res)
                                s_val = slave_data.get("data")
                                if (
                                    s_val is not None
                                    and abs(val - s_val) > 0.25
                                ):
                                    send_ipc(
                                        SLAVE_SOCKET,
                                        ["set_property", "time-pos", val],
                                    )
                except Exception:
                    pass
        finally:
            sock.close()
            # Signal the main window to kill slave and update buttons if master quit unexpectedly
            if not self.isInterruptionRequested():
                self.master_closed.emit()


class MultitrackApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multitrack MPV Player")
        self.resize(600, 380)

        # Set window icon if icon.png or icon.svg exists in script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for ext in ["png", "svg"]:
            icon_path = os.path.join(script_dir, f"icon.{ext}")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break

        # Enable drag and drop on the main window
        self.setAcceptDrops(True)

        # Initialize QSettings for persistence
        self.settings = QSettings("MultitrackMPV", "Settings")

        self.master_proc = None
        self.slave_proc = None
        self.sync_thread = None

        self.init_ui()
        self.load_settings()

        # Check if a file path was passed via CLI ("Open With...")
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            if os.path.exists(file_path):
                self.file_input.setText(file_path)
                self.load_tracks(file_path)
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # File Selection
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText(
            "Select or drag & drop video file here..."
        )
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Audio Devices List
        self.devices = get_audio_devices()

        # Track 1 Config Box (Master)
        box1 = QGroupBox("Master Output (Video + Primary Audio)")
        f1 = QFormLayout(box1)
        self.t1_combo = QComboBox()
        self.d1_combo = QComboBox()
        for desc, _ in self.devices:
            self.d1_combo.addItem(desc)
        self.d1_combo.currentIndexChanged.connect(self.save_settings)
        f1.addRow("Audio Track:", self.t1_combo)
        f1.addRow("Audio Output:", self.d1_combo)
        layout.addWidget(box1)

        # Track 2 Config Box (Slave)
        box2 = QGroupBox("Slave Output (Secondary Audio Device)")
        f2 = QFormLayout(box2)
        self.t2_combo = QComboBox()
        self.d2_combo = QComboBox()
        for desc, _ in self.devices:
            self.d2_combo.addItem(desc)
        self.d2_combo.currentIndexChanged.connect(self.save_settings)
        f2.addRow("Audio Track:", self.t2_combo)
        f2.addRow("Audio Output:", self.d2_combo)
        layout.addWidget(box2)

        # Play / Stop Controls
        btn_layout = QHBoxLayout()
        self.play_btn = QPushButton("Launch Playback")
        self.play_btn.clicked.connect(self.start_playback)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_playback)

        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

    # --- Persistence Helpers ---
    def save_settings(self):
        """Saves current selected output device targets across sessions."""
        d1_target = self.devices[self.d1_combo.currentIndex()][1]
        d2_target = self.devices[self.d2_combo.currentIndex()][1]
        self.settings.setValue("master_device", d1_target)
        self.settings.setValue("slave_device", d2_target)

    def load_settings(self):
        """Restores output device selections from previous session."""
        saved_d1 = self.settings.value("master_device", "")
        saved_d2 = self.settings.value("slave_device", "")

        for idx, (_, target) in enumerate(self.devices):
            if target == saved_d1 and saved_d1:
                self.d1_combo.setCurrentIndex(idx)
            if target == saved_d2 and saved_d2:
                self.d2_combo.setCurrentIndex(idx)

    # --- Drag and Drop Event Handlers ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.file_input.setText(file_path)
                self.load_tracks(file_path)
                break

    # ------------------------------------

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            "",
            "Video Files (*.mkv *.mp4 *.avi *.mov *.webm);;All Files (*)",
        )
        if file_path:
            self.file_input.setText(file_path)
            self.load_tracks(file_path)

    def load_tracks(self, file_path):
        tracks = get_audio_tracks(file_path)
        self.t1_combo.clear()
        self.t2_combo.clear()

        target_index = -1
        found_english = False

        for i, (label, aid) in enumerate(tracks):
            self.t1_combo.addItem(label, aid)
            self.t2_combo.addItem(label, aid)

            label_lower = label.lower()

            # Check for English tags ([eng] or [en])
            if "[eng]" in label_lower or "[en]" in label_lower:
                if not found_english:
                    target_index = i
                    found_english = True  # English takes priority

            # Check for Spanish tags ([spa] or [es]) if no English track locked yet
            elif not found_english and (
                "[spa]" in label_lower or "[es]" in label_lower
            ):
                target_index = i

        # Default Master to Track 1 (Index 0)
        self.t1_combo.setCurrentIndex(0)

        # Default Slave to detected English/Spanish track; otherwise default to Track 2
        if target_index != -1:
            self.t2_combo.setCurrentIndex(target_index)
        elif len(tracks) > 1:
            self.t2_combo.setCurrentIndex(1)

    def start_playback(self):
        file_path = self.file_input.text()
        if not file_path or not os.path.exists(file_path):
            return

        cleanup_sockets()

        t1_aid = self.t1_combo.currentData() or 1
        t2_aid = self.t2_combo.currentData() or 2

        d1_target = self.devices[self.d1_combo.currentIndex()][1]
        d2_target = self.devices[self.d2_combo.currentIndex()][1]

        base_args = ["mpv", "--hwdec=auto", "--vo=gpu"]

        # Master saves position on exit and restores it on start
        m_cmd = base_args + [
            file_path,
            f"--aid={t1_aid}",
            f"--input-ipc-server={MASTER_SOCKET}",
            "--title=Multitrack - Master",
            "--save-position-on-quit",
        ]
        if d1_target:
            m_cmd.append(f"--audio-device={d1_target}")

        s_cmd = base_args + [
            file_path,
            f"--aid={t2_aid}",
            "--no-video",
            f"--input-ipc-server={SLAVE_SOCKET}",
            "--title=Multitrack - Slave",
        ]
        if d2_target:
            s_cmd.append(f"--audio-device={d2_target}")

        self.slave_proc = subprocess.Popen(
            s_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self.master_proc = subprocess.Popen(m_cmd)

        self.sync_thread = SyncThread()
        self.sync_thread.master_closed.connect(self.stop_playback)
        self.sync_thread.start()

        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_playback(self):
        if self.sync_thread:
            # Safely attempt to disconnect to avoid TypeError if already disconnected
            try:
                self.sync_thread.master_closed.disconnect(self.stop_playback)
            except (TypeError, RuntimeError):
                pass

            self.sync_thread.requestInterruption()
            self.sync_thread.wait()
            self.sync_thread = None

        send_ipc(SLAVE_SOCKET, ["quit"])
        send_ipc(MASTER_SOCKET, ["quit"])

        if self.slave_proc:
            self.slave_proc.terminate()
            self.slave_proc = None
        if self.master_proc:
            self.master_proc.terminate()
            self.master_proc = None

        cleanup_sockets()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        self.save_settings()
        self.stop_playback()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Essential for Wayland / KDE Plasma icon mapping
    app.setDesktopFileName("multitrack-mpv")

    window = MultitrackApp()
    window.show()
    sys.exit(app.exec())
