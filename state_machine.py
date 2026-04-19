import threading
import logging
from enum import Enum, auto
from datetime import datetime

logger = logging.getLogger("voice_input.state")


class AppState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    PASTING = auto()
    ERROR = auto()


VALID_TRANSITIONS: dict[AppState, set[AppState]] = {
    AppState.IDLE: {AppState.RECORDING},
    AppState.RECORDING: {AppState.TRANSCRIBING, AppState.ERROR},
    AppState.TRANSCRIBING: {AppState.PASTING, AppState.ERROR},
    AppState.PASTING: {AppState.IDLE, AppState.ERROR},
    AppState.ERROR: {AppState.IDLE},
}


class InvalidTransitionError(Exception):
    pass


class StateMachine:
    def __init__(self):
        self._state = AppState.IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> AppState:
        return self._state

    @property
    def is_idle(self) -> bool:
        return self._state == AppState.IDLE

    @property
    def is_recording(self) -> bool:
        return self._state == AppState.RECORDING

    def transition(self, new_state: AppState, event: str = "") -> None:
        with self._lock:
            old = self._state
            if new_state not in VALID_TRANSITIONS.get(old, set()):
                msg = f"Invalid transition: {old.name} -> {new_state.name} (event: {event})"
                logger.warning(msg)
                raise InvalidTransitionError(msg)
            self._state = new_state
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info("[%s] %s -> %s (event: %s)", ts, old.name, new_state.name, event)

    def force_reset(self, event: str = "FORCE_RESET") -> None:
        with self._lock:
            old = self._state
            self._state = AppState.IDLE
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info("[%s] %s -> IDLE (event: %s)", ts, old.name, event)
