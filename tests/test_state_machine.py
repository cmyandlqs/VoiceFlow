import threading
import pytest

from state_machine import StateMachine, AppState, InvalidTransitionError


def test_initial_state():
    sm = StateMachine()
    assert sm.state == AppState.IDLE
    assert sm.is_idle


def test_normal_flow():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    assert sm.state == AppState.RECORDING
    assert sm.is_recording

    sm.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
    assert sm.state == AppState.TRANSCRIBING

    sm.transition(AppState.PASTING, "ASR_SUCCESS")
    assert sm.state == AppState.PASTING

    sm.transition(AppState.IDLE, "PASTE_DONE")
    assert sm.state == AppState.IDLE
    assert sm.is_idle


def test_invalid_transition_from_idle():
    sm = StateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.transition(AppState.TRANSCRIBING, "INVALID")


def test_invalid_transition_from_recording():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    with pytest.raises(InvalidTransitionError):
        sm.transition(AppState.IDLE, "INVALID")


def test_invalid_transition_from_transcribing():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    sm.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
    with pytest.raises(InvalidTransitionError):
        sm.transition(AppState.RECORDING, "INVALID")


def test_error_from_recording():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    sm.transition(AppState.ERROR, "SOME_ERROR")
    assert sm.state == AppState.ERROR
    sm.transition(AppState.IDLE, "RECOVERED")
    assert sm.state == AppState.IDLE


def test_error_from_transcribing():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    sm.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
    sm.transition(AppState.ERROR, "ASR_FAILED")
    assert sm.state == AppState.ERROR
    sm.transition(AppState.IDLE, "RECOVERED")


def test_error_from_pasting():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    sm.transition(AppState.TRANSCRIBING, "HOTKEY_RELEASED")
    sm.transition(AppState.PASTING, "ASR_SUCCESS")
    sm.transition(AppState.ERROR, "PASTE_FAILED")
    assert sm.state == AppState.ERROR
    sm.transition(AppState.IDLE, "RECOVERED")


def test_error_cannot_transition_to_error():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    sm.transition(AppState.ERROR, "ERR")
    with pytest.raises(InvalidTransitionError):
        sm.transition(AppState.ERROR, "ANOTHER_ERR")


def test_force_reset():
    sm = StateMachine()
    sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
    assert sm.state == AppState.RECORDING
    sm.force_reset("FORCE")
    assert sm.state == AppState.IDLE


def test_thread_safety():
    sm = StateMachine()
    results = []

    def try_transition():
        try:
            sm.transition(AppState.RECORDING, "HOTKEY_PRESSED")
            results.append("ok")
        except InvalidTransitionError:
            results.append("rejected")

    threads = [threading.Thread(target=try_transition) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sm.state in [AppState.IDLE, AppState.RECORDING]
    ok_count = results.count("ok")
    assert ok_count == 1
    assert results.count("rejected") == 19
