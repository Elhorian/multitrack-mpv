# Multitrack MPV Player

A lightweight PyQt6 GUI utility for Linux (KDE Plasma/Wayland ready) that launches and synchronizes two concurrent `mpv` instances. This allows you to output two audio streams from the same video file to two separate audio devices simultaneously (e.g., primary audio to speakers/TV, secondary language or audio commentary track to headphones).

![KDE Plasma / Wayland Ready](https://img.shields.io/badge/Platform-Linux%20%7C%20KDE%20%7C%20Wayland-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen)
![License](https://img.shields.io/badge/License-MIT-orange)

---

## Features

* **Multi-Device Audio Routing:** Play different audio tracks (e.g., English on Master, Spanish on Slave) out to separate physical sound outputs at the same time.
* **Bi-directional IPC Sync:** Automatically keeps playback, pausing, and seeking synchronized between the master video player and the secondary audio slave.
* **Auto Track Detection:** Parses video files via `ffprobe` to automatically list languages and codecs, defaulting smart secondary language selection (e.g., English/Spanish tags).
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