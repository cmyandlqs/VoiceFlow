import logging
import tempfile
import os
import threading
import time

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

logger = logging.getLogger("voice_input.audio")


class MicNotFoundError(Exception):
    pass


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1,
                 max_seconds: int = 60):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._recording = False
        self._stop_event = threading.Event()
        self._max_timer = None

    def start(self) -> None:
        if self._recording:
            logger.warning("Already recording, ignoring start()")
            return
        try:
            self._frames = []
            self._stop_event.clear()
            self._recording = True
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._max_timer = threading.Timer(self.max_seconds, self._auto_stop)
            self._max_timer.daemon = True
            self._max_timer.start()
            logger.info("Recording started (sr=%d, max=%ds)", self.sample_rate, self.max_seconds)
        except sd.PortAudioError as e:
            self._recording = False
            logger.error("Failed to open audio stream: %s", e)
            raise MicNotFoundError("No microphone available") from e

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info, status) -> None:
        if status:
            logger.warning("Audio callback status: %s", status)
        self._frames.append(indata.copy())

    def _auto_stop(self) -> None:
        if self._recording:
            logger.info("Max duration reached, auto-stopping")
            self._do_stop()

    def stop(self) -> tuple[np.ndarray, str]:
        if not self._recording:
            raise RuntimeError("Not recording, cannot stop")
        return self._do_stop()

    def _do_stop(self) -> tuple[np.ndarray, str]:
        self._recording = False
        if self._max_timer:
            self._max_timer.cancel()
            self._max_timer = None
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            data = np.array([], dtype=np.int16)
        else:
            data = np.concatenate(self._frames, axis=0).flatten()

        duration = len(data) / self.sample_rate if len(data) > 0 else 0
        logger.info("Recording stopped: %.2fs, %d samples", duration, len(data))

        wav_path = ""
        if len(data) > 0:
            wav_path = self._save_wav(data)

        return data, wav_path

    def _save_wav(self, data: np.ndarray) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wavfile.write(tmp.name, self.sample_rate, data)
        tmp.close()
        logger.debug("WAV saved: %s", tmp.name)
        return tmp.name

    @property
    def is_recording(self) -> bool:
        return self._recording
