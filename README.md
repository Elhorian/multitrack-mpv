# Multitrack MPV Player

A lightweight PyQt6 GUI utility for Linux (KDE Plasma/Wayland ready) that launches and synchronizes two concurrent `mpv` instances. This allows you to output two audio streams from the same video file to two separate audio devices simultaneously (e.g., primary audio to speakers/TV, secondary language or audio commentary track to headphones).

![KDE Plasma / Wayland Ready](https://img.shields.io/badge/Platform-Linux%20%7C%20KDE%20%7C%20Wayland-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen)
![License](https://img.shields.io/badge/License-MIT-orange)

---

## Features

* **Multi-Device Audio Routing:** Play different audio tracks (e.g., English on Master, Spanish on Slave) out to separate physical sound outputs at the same time.
* **Bi-directional IPC Sync:** Automatically keeps playback, pausing, and seeking synchronized between the master video player and the secondary audio slave.
* **Auto Track Detection:** Parses video files via `ffprobe` to automatically list languages and codecs, defaulting smart secondary language selection.
* **Wayland & KDE Plasma Native:** Includes native desktop launcher integration (`app_id` mapping) and window icon handling.
* **Persistent Settings:** Remembers your preferred master and slave audio device assignments across sessions using `QSettings`.
* **Drag-and-Drop:** Drop any video file directly into the application window to load tracks instantly.

---

## Requirements

### System Dependencies

The application relies on `mpv` for playback, `ffprobe` (via `ffmpeg`) for track metadata extraction, and `pactl` (via PulseAudio or PipeWire) for audio sink enumeration:

* **Arch Linux / EndeavourOS:**
  ```bash
  sudo pacman -S mpv ffmpeg libpulse python-pyqt6
  ```

* **Ubuntu / Debian:**
  ```bash
  sudo apt update
  sudo apt install mpv ffmpeg pulseaudio-utils python3-pyqt6
  ```

* **Fedora:**
  ```bash
  sudo dnf install mpv ffmpeg pulseaudio-utils python3-qt6
  ```

### Python Dependencies

If installing Python modules via `pip` inside a virtual environment or user environment:

```bash
pip install -r requirements.txt
```

---

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Elhorian/multitrack-mpv.git](https://github.com/Elhorian/multitrack-mpv.git)
   cd multitrack-mpv
   ```

2. **Make the script executable:**
   ```bash
   chmod +x multitracks-mpv.py
   ```

3. **Run the application:**
   ```bash
   ./multitracks-mpv.py
   ```

---

## How It Works

1. **File Load:** Browse or drop a video file. `ffprobe` scans the streams to identify audio track numbers, languages (`[eng]`, `[spa]`), and codec descriptions.
2. **Audio Sinks:** `pactl` queries PipeWire/PulseAudio to populate available physical outputs (e.g., HDMI, Headset, USB DAC).
3. **Master Instance:** Launches `mpv` with full video controls, primary track, and IPC socket listener at `/tmp/qt-mpv-master.sock`.
4. **Slave Instance:** Launches `mpv --no-video` with secondary track and IPC socket listener at `/tmp/qt-mpv-slave.sock`.
5. **Sync Engine:** A dedicated `QThread` monitors properties on the master player (`pause`, `time-pos`) and mirrors state adjustments to the slave in real time.

---

## Desktop Integration (.desktop file)

To launch the app directly from Application Launchers (KRunner, Kickoff, Rofi, etc.), create `~/.local/share/applications/multitrack-mpv.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Multitrack MPV
Comment=Dual audio track synchronized player
Exec=/path/to/multitrack-mpv/multitracks-mpv.py
Icon=/path/to/multitrack-mpv/icon.png
Terminal=false
Categories=AudioVideo;Player;Qt;
StartupWMClass=multitrack-mpv
```

---

## License

Distributed under the MIT License. See `LICENSE` for more information.