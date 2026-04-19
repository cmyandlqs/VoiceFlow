import logging
import subprocess
import os

logger = logging.getLogger("voice_input.notify")


class Notifier:
    def __init__(self, notify_enabled: bool = True, sound_enabled: bool = True):
        self.notify_enabled = notify_enabled
        self.sound_enabled = sound_enabled
        self._beep_dir = os.path.join(os.path.dirname(__file__), "beeps")

    def notify(self, message: str) -> None:
        if not self.notify_enabled:
            return
        try:
            subprocess.run(
                ["notify-send", "-t", "1500", "-u", "low", "语音输入", message],
                check=False, timeout=2,
            )
        except Exception as e:
            logger.debug("notify-send failed: %s", e)

    def play_start_beep(self) -> None:
        self._play_wav("start.wav")

    def play_end_beep(self) -> None:
        self._play_wav("end.wav")

    def play_error_beep(self) -> None:
        self._play_wav("error.wav")

    def _play_wav(self, filename: str) -> None:
        if not self.sound_enabled:
            return
        path = os.path.join(self._beep_dir, filename)
        if not os.path.exists(path):
            logger.debug("Beep file not found: %s", path)
            return
        try:
            subprocess.run(
                ["aplay", "-q", path],
                check=False, timeout=3,
            )
        except FileNotFoundError:
            logger.debug("aplay not available, skipping beep")
        except Exception as e:
            logger.debug("Beep playback failed: %s", e)
