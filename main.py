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
from voice_indicator import VoiceIndicator
from window_detector import PasteModeDetector
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

        # 初始化窗口检测器
        paste_config = cfg.get("paste", {})
        if paste_config.get("smart_mode", True):
            self.detector = PasteModeDetector(
                default_shortcut=paste_config.get("default_shortcut", "ctrl+v"),
                terminal_shortcut=paste_config.get("terminal_shortcut", "ctrl+shift+v"),
                terminal_classes=paste_config.get("terminal_classes", []),
                terminal_title_keywords=paste_config.get("terminal_title_keywords", []),
            )
        else:
            self.detector = None
            logger.info("Smart paste mode disabled")

        self.injector = TextInjector(
            default_shortcut=paste_config.get("default_shortcut", "ctrl+v"),
            restore_clipboard=paste_config.get("restore_clipboard", True),
        )
        self.notifier = Notifier(
            notify_enabled=cfg.get("ux", {}).get("notify", True),
            sound_enabled=cfg.get("ux", {}).get("start_beep", True),
        )
        self.indicator = VoiceIndicator(
            enabled=cfg.get("ux", {}).get("indicator", True),
            follow_pointer=cfg.get("ux", {}).get("indicator_follow_pointer", True),
        )

        # 配置双热键
        hotkey_config = cfg.get("hotkey", {})
        combos = {
            hotkey_config.get("smart_combo", "f10"): "smart",
            hotkey_config.get("terminal_combo", "f11"): "terminal",
        }
        self.hotkey = HotkeyManager(combos=combos)
        self.hotkey.on_press(self._on_hotkey_press)
        self.hotkey.on_release(self._on_hotkey_release)

        self._running = False
        self._current_mode = None  # "smart" or "terminal"

    def _on_hotkey_press(self) -> None:
        if not self.state.is_idle:
            logger.debug("Not idle, ignoring hotkey press")
            return
        try:
            self.state.transition(AppState.RECORDING, "HOTKEY_PRESSED")
            self.recorder.start()
            self.indicator.show_listening()
            self.notifier.notify("正在聆听...")
            self.notifier.play_start_beep()
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            self.indicator.hide()
            self.state.force_reset("START_FAILED")

    def _on_hotkey_release(self, combo_mode: str | None = None) -> None:
        """热键释放时的处理

        Args:
            combo_mode: "smart" 或 "terminal"，表示是哪个热键触发
        """
        # 记录当前模式
        self._current_mode = combo_mode
        if not self.state.is_recording:
            return
        try:
            data, wav_path = self.recorder.stop()
            self.state.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
            self.indicator.show_transcribing()
            self.notifier.notify("识别中...")

            if not wav_path:
                logger.warning("No audio recorded")
                self.indicator.hide()
                self.state.force_reset("NO_AUDIO")
                return

            result = self.asr.transcribe(wav_path)
            logger.info("ASR result: %s", result.text)

            try:
                os.unlink(wav_path)
            except OSError:
                pass

            self.state.transition(AppState.PASTING, "ASR_SUCCESS")

            # 根据热键模式选择粘贴快捷键
            shortcut = None
            if self._current_mode == "terminal":
                # F11: 强制终端模式
                shortcut = "ctrl+shift+v"
                logger.info("Using terminal paste mode (F11)")
            elif self.detector:
                # F10: 智能检测模式
                shortcut = self.detector.detect_shortcut()
                logger.info("Smart paste detected shortcut: %s", shortcut)
            else:
                # 智能模式关闭，使用默认
                logger.info("Smart mode disabled, using default shortcut")

            if self.injector.inject(result.text, shortcut=shortcut):
                self.notifier.notify(f"已输入: {result.text}")
                self.notifier.play_end_beep()
            else:
                logger.warning("Paste returned False")

            self.state.transition(AppState.IDLE, "PASTE_DONE")
            self.indicator.hide()

        except (ASRTimeoutError, ASRUnavailableError) as e:
            logger.error("ASR failed: %s", e)
            self.state.transition(AppState.ERROR, "ASR_FAILED")
            self.indicator.hide()
            self.notifier.notify(f"识别失败: {type(e).__name__}")
            self.notifier.play_error_beep()
            self.state.transition(AppState.IDLE, "RECOVERED")
        except ASREmptyError:
            logger.warning("ASR returned empty result")
            self.indicator.hide()
            self.state.force_reset("ASR_EMPTY")
            self.notifier.notify("未识别到语音")
            self.notifier.play_error_beep()
        except Exception as e:
            logger.exception("Unexpected error in hotkey release: %s", e)
            self.indicator.hide()
            self.state.force_reset("UNEXPECTED_ERROR")
            self.notifier.notify("发生错误")
            self.notifier.play_error_beep()

    def run(self) -> None:
        self._running = True
        self.indicator.start()
        self.hotkey.start()
        logger.info("Voice Input started. Press F10 for smart paste, F11 for terminal paste. Ctrl+C to quit.")

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
            self.indicator.stop()
            self.hotkey.stop()
            logger.info("Voice Input stopped.")


def main():
    config_path = os.environ.get("VOICE_INPUT_CONFIG", "config.yaml")
    app = VoiceInputApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
