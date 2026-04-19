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

        width = 132
        height = 52
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
        root.configure(bg="#ECEFF4")

        canvas = tk.Canvas(
            root,
            width=width,
            height=height,
            bg="#ECEFF4",
            bd=0,
            highlightthickness=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)

        # Soft shadow
        canvas.create_oval(5, 7, 53, 49, fill="#D5DBE6", outline="")
        canvas.create_rectangle(29, 7, 105, 49, fill="#D5DBE6", outline="")
        canvas.create_oval(81, 7, 127, 49, fill="#D5DBE6", outline="")

        # Capsule body
        canvas.create_oval(4, 4, 52, 48, fill="#F8FAFD", outline="#DDE3EE", width=1)
        canvas.create_rectangle(28, 4, 104, 48, fill="#F8FAFD", outline="#DDE3EE", width=1)
        canvas.create_oval(80, 4, 128, 48, fill="#F8FAFD", outline="#DDE3EE", width=1)

        pulse_ring = canvas.create_oval(15, 15, 37, 37, outline="#FF8A84", width=2)
        core_dot = canvas.create_oval(20, 20, 32, 32, fill="#FF5B52", outline="")
        dots = [
            canvas.create_oval(74, 22, 82, 30, fill="#A7B2C3", outline=""),
            canvas.create_oval(86, 22, 94, 30, fill="#A7B2C3", outline=""),
            canvas.create_oval(98, 22, 106, 30, fill="#A7B2C3", outline=""),
        ]
        label = canvas.create_text(51, 26, text="REC", fill="#5E6A7F", anchor="w")

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
                canvas.itemconfigure(label, text="REC", fill="#4F5D75")
                canvas.itemconfigure(core_dot, state="normal")
                canvas.itemconfigure(pulse_ring, state="normal")
                for d in dots:
                    canvas.itemconfigure(d, state="hidden")
            else:
                canvas.itemconfigure(label, text="ASR", fill="#5E6A7F")
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
                pad = 15 - expand * 0.45
                canvas.coords(pulse_ring, pad, pad, 52 - pad, 52 - pad)
                color = "#FF7A72" if phase < 8 else "#FF9A95"
                canvas.itemconfigure(pulse_ring, outline=color)
            elif mode == "transcribing":
                phase = tick % 3
                for i, d in enumerate(dots):
                    fill = "#617089" if i == phase else "#B5C0CF"
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
