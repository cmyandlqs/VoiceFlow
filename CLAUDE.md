# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VoiceFlow is a local voice input assistant for Ubuntu (X11). Use **F10** (smart paste mode) or **F11** (terminal paste mode) to record speech, release to transcribe via local vLLM ASR service, and automatically paste the result at the cursor position.

**Core flow**: `HOTKEY_PRESS` → `RECORDING` → `HOTKEY_RELEASE` → `TRANSCRIBING` → `PASTING` → `IDLE`

**Dual hotkey modes**:
- **F10 (smart)**: Auto-detects active window type and picks the right paste shortcut (`ctrl+v` for normal apps, `ctrl+shift+v` for terminals).
- **F11 (terminal)**: Forces `ctrl+shift+v` — use when the smart detection misses a terminal window.

## Development Commands

### Installation
```bash
# Create venv and install dependencies
uv venv
uv pip install -e ".[dev]"
```

### Running
```bash
# Direct run
.venv/bin/python main.py

# Via script
./scripts/run.sh

# With custom config
VOICE_INPUT_CONFIG=/path/to/config.yaml .venv/bin/python main.py
```

### Testing
```bash
# All tests
uv run pytest tests/ -v

# Single test file
uv run pytest tests/test_state_machine.py -v

# With coverage
uv run pytest tests/ --cov=. --cov-report=term-missing
```

### System Dependencies
```bash
sudo apt install xclip xdotool libportaudio2
```

## Architecture

### State Machine Core
The entire application is driven by `StateMachine` ([state_machine.py](state_machine.py)). All module interactions flow through state transitions:
- `IDLE → RECORDING`: Hotkey press
- `RECORDING → TRANSCRIBING`: Hotkey release (audio ready)
- `TRANSCRIBING → PASTING`: ASR success
- `PASTING → IDLE`: Paste complete
- Any state → `ERROR`: Failure recovery
- `ERROR → IDLE`: Recovery complete

**Thread safety**: StateMachine uses `threading.Lock`. All state transitions must go through `transition()` or `force_reset()`.

### Threading Model
- **Main thread**: Runs signal.pause() loop, handles shutdown
- **Hotkey thread** ([hotkey_manager.py](hotkey_manager.py)): X11 event loop via XGrabKey, calls back on main
- **Audio callback** ([audio_recorder.py](audio_recorder.py)): sounddevice callback (real-time priority)
- **Indicator thread** ([voice_indicator.py](voice_indicator.py)): Tkinter mainloop with command queue

**No async/await**: This project uses threads exclusively. Tkinter must run in its own thread with a command queue (`queue.SimpleQueue`).

### Module Contracts

**ASRClient** ([asr_client.py](asr_client.py)):
- Input: Path to WAV file (16kHz, mono, int16)
- Output: `ASRResult(text, duration_ms, request_id)`
- Errors: `ASRTimeoutError`, `ASRUnavailableError`, `ASREmptyError`
- Retry: Built-in retry with exponential backoff (0.3s)
- API: OpenAI-compatible `/v1/audio/transcriptions`

**TextInjector** ([text_injector.py](text_injector.py)):
- Saves clipboard → sets new text → sends paste shortcut → restores clipboard
- Accepts optional `shortcut` parameter to override the default paste shortcut
- Timing: 0.1s delays between clipboard operations, 0.5s before clipboard restore

**HotkeyManager** ([hotkey_manager.py](hotkey_manager.py)):
- X11-only (XGrabKey on root window)
- Supports dual hotkey: accepts `combos` dict mapping key names to mode strings (e.g. `{"f10": "smart", "f11": "terminal"}`)
- `on_release` callback receives `combo_mode` string to identify which key was pressed
- Handles auto-repeat detection (peek next event)
- Registers each key with multiple modifiers (0, Mod2Mask, LockMask, combined)

## Configuration

All runtime behavior is configured via `config.yaml`:
- `hotkey.smart_combo`: F10 (smart paste mode)
- `hotkey.terminal_combo`: F11 (terminal paste mode)
- `audio`: sample_rate, channels, max_record_seconds
- `asr`: endpoint, model path, timeout, language, task, prompt
- `paste`: smart_mode (bool), default_shortcut, terminal_shortcut, terminal_classes, terminal_title_keywords, restore_clipboard
- `ux`: indicator (bool), indicator_follow_pointer, start_beep, end_beep, error_beep, notify

Config validation happens at startup in `utils.validate_config()` — missing required keys raise `ConfigValidationError`.

## Error Handling Patterns

1. **Expected failures** (ASR timeout, unavailable): Catch specific exceptions, transition to ERROR, show notification, return to IDLE
2. **Unexpected failures**: Log with `logger.exception()`, force_reset state, notify generic error
3. **Audio capture failures**: Raise `MicNotFoundError`, caller handles state cleanup
4. **Empty ASR results**: `ASREmptyError` is separate from failures — shows "未识别到语音" not error

**Never block the hotkey thread**: All callbacks from HotkeyManager should complete quickly. Long-running work (ASR, paste) happens after state transition.

## X11/Wayland Considerations

- **X11 required**: HotkeyManager uses XGrabKey which only works on X11
- **Pointer tracking**: VoiceIndicator uses Xlib.query_pointer() — fails gracefully on Wayland
- **Paste**: xclip/xdotool may have issues on Wayland; consider wl-clipboard/wtype for Wayland support

## Testing Strategy

- **State machine**: Thread-safety tests with 20 concurrent transitions
- **ASR client**: Full mock coverage with requests-mock (timeout, connection error, retry logic, empty results)
- **Utils**: Config validation tests

Tests use `autouse` fixtures for WAV file cleanup.

## Adding New Features

**New state**: Add to `AppState` enum, update `VALID_TRANSITIONS` dict, handle in main.py callbacks.

**New UX element**: Add to `config.yaml` schema, read in `VoiceInputApp.__init__()`, pass to relevant module.

**New ASR backend**: Only `asr_client.py` needs changes — keep the same `ASRResult` output format.

**PasteModeDetector** ([window_detector.py](window_detector.py)):
- Detects active window class (via `xprop`) and title (via `xdotool`)
- Matches against configurable `terminal_classes` and `terminal_title_keywords`
- Returns the appropriate paste shortcut for the current window
- Used only in smart mode (F10); F11 bypasses detection entirely
