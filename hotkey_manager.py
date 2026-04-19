import threading
import logging

from Xlib import X, XK
from Xlib.display import Display

logger = logging.getLogger("voice_input.hotkey")


def _keycode_for_keysym(display: Display, keysym) -> int | None:
    for keycode in range(display.display.info.min_keycode,
                         display.display.info.max_keycode + 1):
        for idx in range(8):
            ks = display.keycode_to_keysym(keycode, idx)
            if ks == keysym:
                return keycode
    return None


class HotkeyManager:
    def __init__(self, combo: str = "f12"):
        self.combo = combo.lower()
        self._on_press_cb = None
        self._on_release_cb = None
        self._thread = None
        self._stop_event = threading.Event()
        self._pressed = False

    def on_press(self, callback) -> None:
        self._on_press_cb = callback

    def on_release(self, callback) -> None:
        self._on_release_cb = callback

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Hotkey registered: %s", self.combo)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("Hotkey listener stopped")

    def _run(self) -> None:
        display = Display()
        root = display.screen().root

        keysym = self._combo_to_keysym(self.combo)
        if keysym is None:
            logger.error("Unknown combo: %s", self.combo)
            return

        keycode = _keycode_for_keysym(display, keysym)
        if keycode is None:
            logger.error("Cannot find keycode for: %s", self.combo)
            return

        root.grab_key(keycode, 0, True, X.GrabModeAsync, X.GrabModeAsync)
        root.grab_key(keycode, X.Mod2Mask, True, X.GrabModeAsync, X.GrabModeAsync)
        root.grab_key(keycode, X.LockMask, True, X.GrabModeAsync, X.GrabModeAsync)
        root.grab_key(keycode, X.Mod2Mask | X.LockMask, True,
                      X.GrabModeAsync, X.GrabModeAsync)

        root.change_attributes(event_mask=X.KeyPressMask | X.KeyReleaseMask)

        while not self._stop_event.is_set():
            while display.pending_events():
                event = display.next_event()
                if event.type == X.KeyPress and not self._pressed:
                    self._pressed = True
                    if self._on_press_cb:
                        self._on_press_cb()
                elif event.type == X.KeyRelease and self._pressed:
                    if self._is_auto_repeat(display, event):
                        continue
                    self._pressed = False
                    if self._on_release_cb:
                        self._on_release_cb()
            self._stop_event.wait(0.01)

        root.ungrab_key(keycode, 0)
        root.ungrab_key(keycode, X.Mod2Mask)
        root.ungrab_key(keycode, X.LockMask)
        root.ungrab_key(keycode, X.Mod2Mask | X.LockMask)
        display.close()

    def _is_auto_repeat(self, display: Display, release_event) -> bool:
        try:
            next_event = display.pending_events()
            if next_event > 0:
                peek = display.next_event()
                if (peek.type == X.KeyPress and
                        peek.detail == release_event.detail and
                        peek.time == release_event.time):
                    return True
                else:
                    display.put_back_event(peek)
        except Exception:
            pass
        return False

    def _combo_to_keysym(self, combo: str) -> int | None:
        combo = combo.upper()
        fn_num = combo.lstrip("F")
        if combo.startswith("F") and fn_num.isdigit():
            val = getattr(XK, f"XK_F{fn_num}", None)
            if val is not None:
                return val() if callable(val) else val
        attr = getattr(XK, f"XK_{combo}", None)
        if attr is not None:
            return attr() if callable(attr) else attr
        return None
