# VoiceFlow

[中文文档](README.md)

**Local Voice Input Assistant** — Hold F12 to speak, release to transcribe and paste at the cursor.

No cloud, no app switching. Just speak and the text appears.

---

## Features

- **Global hotkey** — Hold F12 to record, release to transcribe, no workflow interruption
- **Auto-paste** — Recognized text is inserted directly at the cursor position
- **Fully local** — Audio never leaves the machine, privacy-first
- **Low latency** — End-to-end in 1-3 seconds
- **Swappable backend** — ASR model is configurable
- **Lightweight daemon** — Near-zero CPU when idle, < 50MB memory

## Quick Start

### 1. Install system dependencies

```bash
sudo apt install xclip xdotool libportaudio2
```

### 2. Start ASR service

A local vLLM service is required (e.g. qwen3-asr):

```bash
pip install "vllm[audio]"
python -m vllm.entrypoints.openai.api_server \
  --model /path/to/qwen3-asr-1.7B \
  --host 0.0.0.0 --port 8000
```

### 3. Install and run

```bash
uv venv
uv pip install -e ".[dev]"
.venv/bin/python main.py
```

Hold **F12** to start recording, release to transcribe and paste. Press `Ctrl+C` to quit.

## Usage

```
Focus any input field → Hold F12 → Speak → Release F12 → Text appears at cursor
```

## Configuration

Edit `config.yaml` to customize:

```yaml
hotkey:
  combo: f12

asr:
  endpoint: http://127.0.0.1:8000
  model: /path/to/qwen3-asr-1.7B
  language: zh

paste:
  linux_paste_shortcut: ctrl+v
  restore_clipboard: true

ux:
  start_beep: true
  notify: true
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13 |
| Package manager | uv |
| Hotkey | python-xlib (X11 XGrabKey) |
| Recording | sounddevice |
| ASR backend | vLLM (OpenAI-compatible API) |
| Clipboard | xclip + xdotool |
| Testing | pytest + requests-mock |

## Requirements

- **OS**: Ubuntu Desktop (X11)
- **Python**: >= 3.10
- **GPU**: Required for ASR model inference (e.g. RTX 4070+)
- **ASR Model**: A speech recognition model served by vLLM

## License

MIT
