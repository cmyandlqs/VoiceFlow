import os
import signal
import sys
import logging

from state_machine import StateMachine, AppState
from audio_recorder import AudioRecorder
from asr_client import ASRClient, ASRTimeoutError, ASRUnavailableError, ASREmptyError
from text_injector import TextInjector
from hotkey_manager import HotkeyManager
from notifier import Notifier
from utils import load_config, setup_logging

logger = logging.getLogger("voice_input.main")


class VoiceInputApp:
    def __init__(self, config_path: str = "config.yaml"):
        cfg = load_config(config_path)
        setup_logging(
            level=cfg.get("log", {}).get("level", "INFO"),
            log_file=cfg.get("log", {}).get("file", ""),
        )

        self.state = StateMachine()
        self.recorder = AudioRecorder(
            sample_rate=cfg["audio"]["sample_rate"],
            channels=cfg["audio"]["channels"],
            max_seconds=cfg["audio"].get("max_record_seconds", 60),
        )
        self.asr = ASRClient(
            endpoint=cfg["asr"]["endpoint"],
            timeout=cfg["asr"].get("timeout_seconds", 20),
            language=cfg["asr"].get("language", "zh"),
            task=cfg["asr"].get("task", "transcribe"),
            prompt=cfg["asr"].get("prompt", ""),
            model=cfg["asr"].get("model", ""),
        )
        self.injector = TextInjector(
            paste_shortcut=cfg["paste"].get("linux_paste_shortcut", "ctrl+shift+v"),
            restore_clipboard=cfg["paste"].get("restore_clipboard", True),
        )
        self.notifier = Notifier(
            notify_enabled=cfg.get("ux", {}).get("notify", True),
            sound_enabled=cfg.get("ux", {}).get("start_beep", True),
        )

        self.hotkey = HotkeyManager(combo=cfg["hotkey"]["combo"])
        self.hotkey.on_press(self._on_hotkey_press)
        self.hotkey.on_release(self._on_hotkey_release)

        self._running = False

    def _on_hotkey_press(self) -> None:
        if not self.state.is_idle:
            logger.debug("Not idle, ignoring hotkey press")
            return
        try:
            self.state.transition(AppState.RECORDING, "HOTKEY_PRESSED")
            self.recorder.start()
            self.notifier.notify("正在聆听...")
            self.notifier.play_start_beep()
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            self.state.force_reset("START_FAILED")

    def _on_hotkey_release(self) -> None:
        if not self.state.is_recording:
            return
        try:
            data, wav_path = self.recorder.stop()
            self.state.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
            self.notifier.notify("识别中...")

            if not wav_path:
                logger.warning("No audio recorded")
                self.state.force_reset("NO_AUDIO")
                return

            result = self.asr.transcribe(wav_path)
            logger.info("ASR result: %s", result.text)

            try:
                os.unlink(wav_path)
            except OSError:
                pass

            self.state.transition(AppState.PASTING, "ASR_SUCCESS")

            if self.injector.inject(result.text):
                self.notifier.notify(f"已输入: {result.text}")
                self.notifier.play_end_beep()
            else:
                logger.warning("Paste returned False")

            self.state.transition(AppState.IDLE, "PASTE_DONE")

        except (ASRTimeoutError, ASRUnavailableError) as e:
            logger.error("ASR failed: %s", e)
            self.state.transition(AppState.ERROR, "ASR_FAILED")
            self.notifier.notify(f"识别失败: {type(e).__name__}")
            self.notifier.play_error_beep()
            self.state.transition(AppState.IDLE, "RECOVERED")
        except ASREmptyError:
            logger.warning("ASR returned empty result")
            self.state.force_reset("ASR_EMPTY")
            self.notifier.notify("未识别到语音")
            self.notifier.play_error_beep()
        except Exception as e:
            logger.exception("Unexpected error in hotkey release: %s", e)
            self.state.force_reset("UNEXPECTED_ERROR")
            self.notifier.notify("发生错误")
            self.notifier.play_error_beep()

    def run(self) -> None:
        self._running = True
        self.hotkey.start()
        logger.info("Voice Input started. Press F12 to talk. Ctrl+C to quit.")

        def signal_handler(sig, frame):
            logger.info("Received signal %s, shutting down...", sig)
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while self._running:
                signal.pause() if hasattr(signal, "pause") else __import__("time").sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.hotkey.stop()
            logger.info("Voice Input stopped.")


def main():
    config_path = os.environ.get("VOICE_INPUT_CONFIG", "config.yaml")
    app = VoiceInputApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
