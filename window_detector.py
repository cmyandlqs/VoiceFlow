import logging
import subprocess

logger = logging.getLogger("voice_input.window_detector")


class PasteModeDetector:
    def __init__(
        self,
        default_shortcut: str = "ctrl+v",
        terminal_shortcut: str = "ctrl+shift+v",
        terminal_classes: list[str] | None = None,
        terminal_title_keywords: list[str] | None = None,
    ):
        self.default_shortcut = default_shortcut
        self.terminal_shortcut = terminal_shortcut
        self.terminal_classes = set((terminal_classes or []).copy())
        self.title_keywords = set((terminal_title_keywords or []).copy())

        logger.debug("PasteModeDetector initialized with terminal_classes=%s, title_keywords=%s",
                     self.terminal_classes, self.title_keywords)

    def detect_shortcut(self) -> str:
        """检测当前窗口应该使用的粘贴快捷键"""
        try:
            cls = self._get_active_window_class()
            title = self._get_active_window_title()

            logger.debug("Active window: class=%s, title=%s", cls, title)

            if self._is_terminal(cls, title):
                logger.debug("Detected terminal window, using terminal shortcut")
                return self.terminal_shortcut

            logger.debug("Detected normal window, using default shortcut")
            return self.default_shortcut
        except Exception as e:
            logger.warning("Failed to detect window type, using default: %s", e)
            return self.default_shortcut

    def _get_active_window_class(self) -> str:
        """获取当前窗口类名"""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowclassname"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            return result.stdout.strip().lower()
        except Exception as e:
            logger.debug("Could not get window class: %s", e)
            return ""

    def _get_active_window_title(self) -> str:
        """获取当前窗口标题"""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            return result.stdout.strip().lower()
        except Exception as e:
            logger.debug("Could not get window title: %s", e)
            return ""

    def _is_terminal(self, cls: str, title: str) -> bool:
        """判断是否是终端窗口"""
        # 检查窗口类名
        if self.terminal_classes:
            for terminal_cls in self.terminal_classes:
                if terminal_cls.lower() in cls:
                    logger.debug("Matched terminal class: %s in %s", terminal_cls, cls)
                    return True

        # 检查窗口标题关键词
        if self.title_keywords:
            for keyword in self.title_keywords:
                if keyword.lower() in title:
                    logger.debug("Matched title keyword: %s in %s", keyword, title)
                    return True

        return False
