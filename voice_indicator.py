import logging
import queue
import threading
from typing import Literal

logger = logging.getLogger("voice_input.indicator")


class VoiceIndicator:
    """A tiny floating indicator window for recording/transcribing states."""

    def __init__(self, enabled: bool = True, follow_pointer: bool = True):
        self.enabled = enabled
        self.follow_pointer = follow_pointer
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._cmd_q: queue.SimpleQueue[str] = queue.SimpleQueue()

    def start(self) -> None:
        if not self.enabled or self._thread:
            return
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_ui, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=1.5)

    def stop(self) -> None:
        if not self._thread:
            return
        self._enqueue("stop")
        self._thread.join(timeout=2)
        self._thread = None

    def show_listening(self) -> None:
        self._enqueue("show_listening")

    def show_transcribing(self) -> None:
        self._enqueue("show_transcribing")

    def hide(self) -> None:
        self._enqueue("hide")

    def _enqueue(self, cmd: str) -> None:
        if not self.enabled:
            return
        self._cmd_q.put(cmd)

    def _run_ui(self) -> None:
        try:
            import tkinter as tk
        except Exception as e:
            logger.warning("Tkinter unavailable, indicator disabled: %s", e)
            self.enabled = False
            self._ready.set()
            return

        try:
            root = tk.Tk()
        except Exception as e:
            logger.warning("Cannot create Tk window, indicator disabled: %s", e)
            self.enabled = False
            self._ready.set()
            return

        pointer_display = None
        if self.follow_pointer:
            try:
                from Xlib.display import Display
                pointer_display = Display()
            except Exception as e:
                logger.debug("Pointer tracking unavailable: %s", e)

        width = 108
        height = 44
        x = max(20, (root.winfo_screenwidth() - width) // 2)
        y = max(20, int(root.winfo_screenheight() * 0.12))

        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.97)
        except Exception:
            pass
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.configure(bg="#111318")

        canvas = tk.Canvas(
            root,
            width=width,
            height=height,
            bg="#111318",
            bd=0,
            highlightthickness=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)

        # Shadow
        canvas.create_oval(3, 5, 43, 41, fill="#0A0C10", outline="")
        canvas.create_rectangle(23, 5, 85, 41, fill="#0A0C10", outline="")
        canvas.create_oval(65, 5, 105, 41, fill="#0A0C10", outline="")

        # Capsule body
        canvas.create_oval(2, 2, 42, 42, fill="#1B1E25", outline="#2F3440", width=1)
        canvas.create_rectangle(22, 2, 86, 42, fill="#1B1E25", outline="#2F3440", width=1)
        canvas.create_oval(66, 2, 106, 42, fill="#1B1E25", outline="#2F3440", width=1)

        pulse_ring = canvas.create_oval(13, 13, 31, 31, outline="#FF5D55", width=2)
        core_dot = canvas.create_oval(16, 16, 28, 28, fill="#FF3B30", outline="")
        dots = [
            canvas.create_oval(60, 19, 68, 27, fill="#8F98A8", outline=""),
            canvas.create_oval(72, 19, 80, 27, fill="#8F98A8", outline=""),
            canvas.create_oval(84, 19, 92, 27, fill="#8F98A8", outline=""),
        ]
        label = canvas.create_text(45, 22, text="REC", fill="#AEB6C4", anchor="w")

        mode: Literal["hidden", "listening", "transcribing"] = "hidden"
        tick = 0

        def set_visible(visible: bool) -> None:
            if visible:
                root.deiconify()
                root.lift()
            else:
                root.withdraw()

        def apply_mode(next_mode: Literal["hidden", "listening", "transcribing"]) -> None:
            nonlocal mode
            mode = next_mode
            if mode == "hidden":
                set_visible(False)
                return

            set_visible(True)
            if mode == "listening":
                canvas.itemconfigure(label, text="REC", fill="#C3CBDA")
                canvas.itemconfigure(core_dot, state="normal")
                canvas.itemconfigure(pulse_ring, state="normal")
                for d in dots:
                    canvas.itemconfigure(d, state="hidden")
            else:
                canvas.itemconfigure(label, text="ASR", fill="#AEB6C4")
                canvas.itemconfigure(core_dot, state="hidden")
                canvas.itemconfigure(pulse_ring, state="hidden")
                for d in dots:
                    canvas.itemconfigure(d, state="normal")

        def update_position() -> None:
            if not pointer_display:
                return
            try:
                pointer = pointer_display.screen().root.query_pointer()
                mouse_x = pointer.root_x
                mouse_y = pointer.root_y
            except Exception:
                return

            offset_x = 16
            offset_y = 18
            next_x = mouse_x + offset_x
            next_y = mouse_y + offset_y
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            next_x = min(max(8, next_x), max(8, screen_w - width - 8))
            next_y = min(max(8, next_y), max(8, screen_h - height - 8))
            root.geometry(f"{width}x{height}+{next_x}+{next_y}")

        def animate() -> None:
            nonlocal tick
            tick += 1
            if mode == "listening":
                phase = tick % 16
                expand = phase if phase <= 8 else 16 - phase
                pad = 13 - expand * 0.4
                canvas.coords(pulse_ring, pad, pad, 44 - pad, 44 - pad)
                color = "#FF4F46" if phase < 8 else "#FF6E66"
                canvas.itemconfigure(pulse_ring, outline=color)
            elif mode == "transcribing":
                phase = tick % 3
                for i, d in enumerate(dots):
                    fill = "#E2E8F4" if i == phase else "#6E7787"
                    canvas.itemconfigure(d, fill=fill)

        def pump() -> None:
            while True:
                try:
                    cmd = self._cmd_q.get_nowait()
                except queue.Empty:
                    break

                if cmd == "show_listening":
                    apply_mode("listening")
                elif cmd == "show_transcribing":
                    apply_mode("transcribing")
                elif cmd == "hide":
                    apply_mode("hidden")
                elif cmd == "stop":
                    self._stop.set()
                    root.quit()
                    return

            animate()
            if mode != "hidden":
                update_position()
            root.after(66, pump)

        self._ready.set()
        root.after(66, pump)
        try:
            root.mainloop()
        finally:
            if pointer_display:
                try:
                    pointer_display.close()
                except Exception:
                    pass
            try:
                root.destroy()
            except Exception:
                pass
