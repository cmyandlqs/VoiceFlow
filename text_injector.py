import logging
import subprocess
import time

logger = logging.getLogger("voice_input.injector")


class TextInjector:
    def __init__(self, default_shortcut: str = "ctrl+v",
                 restore_clipboard: bool = True):
        self.default_shortcut = default_shortcut
        self.restore_clipboard = restore_clipboard

    def inject(self, text: str, shortcut: str | None = None) -> bool:
        """注入文本到光标位置

        Args:
            text: 要注入的文本
            shortcut: 粘贴快捷键，None 表示使用 default_shortcut
        """
        if not text:
            logger.debug("Empty text, skipping paste")
            return False

        saved_clipboard = self._save_clipboard() if self.restore_clipboard else None

        try:
            self._set_clipboard(text)
            time.sleep(0.1)

            # 使用指定的快捷键，或默认快捷键
            final_shortcut = shortcut or self.default_shortcut
            self._send_paste(final_shortcut)

            time.sleep(0.1)
            logger.info("[paste] success text_len=%d shortcut=%s", len(text), final_shortcut)
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

    def _send_paste(self, shortcut: str) -> None:
        """发送粘贴快捷键（只发送一次）"""
        if not shortcut:
            logger.debug("No shortcut provided, skipping paste")
            return

        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", shortcut],
            check=False, timeout=2,
        )
        logger.debug("Sent paste shortcut: %s", shortcut)
