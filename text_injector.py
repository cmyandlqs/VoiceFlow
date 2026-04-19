import logging
import subprocess
import time

logger = logging.getLogger("voice_input.injector")


class TextInjector:
    def __init__(self, paste_shortcut: str = "ctrl+v",
                 restore_clipboard: bool = True):
        self.paste_shortcut = paste_shortcut
        self.restore_clipboard = restore_clipboard

    def inject(self, text: str) -> bool:
        if not text:
            logger.debug("Empty text, skipping paste")
            return False

        saved_clipboard = self._save_clipboard() if self.restore_clipboard else None

        try:
            self._set_clipboard(text)
            time.sleep(0.1)
            self._send_paste()
            time.sleep(0.1)
            logger.info("[paste] success text_len=%d", len(text))
            return True
        except Exception as e:
            logger.error("[paste] failed: %s", e)
            return False
        finally:
            if saved_clipboard is not None:
                time.sleep(0.5)
                self._restore_clipboard(saved_clipboard)

    def _save_clipboard(self) -> bytes | None:
        try:
            result = subprocess.run(
                ["xclip", "-sel", "clip", "-o"],
                capture_output=True, timeout=2,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            logger.debug("Could not save clipboard: %s", e)
        return None

    def _set_clipboard(self, text: str) -> None:
        subprocess.run(
            ["xclip", "-sel", "clip"],
            input=text.encode("utf-8"), check=True, timeout=2,
        )

    def _restore_clipboard(self, data: bytes) -> None:
        try:
            subprocess.run(
                ["xclip", "-sel", "clip"],
                input=data, check=False, timeout=2,
            )
            logger.debug("Clipboard restored (%d bytes)", len(data))
        except Exception as e:
            logger.warning("Failed to restore clipboard: %s", e)

    def _send_paste(self) -> None:
        for shortcut in [self.paste_shortcut, "ctrl+shift+v"]:
            if shortcut:
                subprocess.run(
                    ["xdotool", "key", "--clearmodifiers", shortcut],
                    check=False, timeout=2,
                )
                time.sleep(0.05)
