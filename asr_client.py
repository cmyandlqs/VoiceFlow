import logging
import time

import requests

logger = logging.getLogger("voice_input.asr")


class ASRTimeoutError(Exception):
    pass


class ASRUnavailableError(Exception):
    pass


class ASREmptyError(Exception):
    pass


class ASRResult:
    def __init__(self, text: str, duration_ms: float, request_id: str = ""):
        self.text = text
        self.duration_ms = duration_ms
        self.request_id = request_id

    def __repr__(self) -> str:
        return f"ASRResult(text={self.text!r}, duration_ms={self.duration_ms})"


class ASRClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:8000",
                 timeout: int = 20, max_retries: int = 1,
                 language: str = "zh", task: str = "transcribe",
                 prompt: str = "", model: str = ""):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.language = language
        self.task = task
        self.prompt = prompt
        self.model = model

    def transcribe(self, wav_path: str) -> ASRResult:
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._do_request(wav_path)
            except (ASRTimeoutError, ASRUnavailableError) as e:
                last_exc = e
                if attempt < self.max_retries:
                    logger.warning("ASR attempt %d failed (%s), retrying...",
                                   attempt + 1, type(e).__name__)
                    time.sleep(0.3)
                continue

        raise last_exc

    def _do_request(self, wav_path: str) -> ASRResult:
        url = f"{self.endpoint}/v1/audio/transcriptions"
        f = open(wav_path, "rb")
        files = {"file": ("audio.wav", f, "audio/wav")}
        data = {"model": self.model}
        if self.language:
            data["language"] = self.language
        if self.prompt:
            data["prompt"] = self.prompt

        try:
            start = time.monotonic()
            resp = requests.post(url, files=files, data=data,
                                 timeout=self.timeout)
            elapsed_ms = (time.monotonic() - start) * 1000
        except requests.exceptions.Timeout as e:
            raise ASRTimeoutError("ASR request timed out") from e
        except requests.exceptions.ConnectionError as e:
            raise ASRUnavailableError("ASR service unreachable") from e
        finally:
            f.close()

        if resp.status_code == 503:
            raise ASRUnavailableError(f"ASR busy: {resp.text}")
        if resp.status_code >= 500:
            raise ASRUnavailableError(f"ASR server error: {resp.status_code}")
        if resp.status_code >= 400:
            raise ASRUnavailableError(f"ASR client error: {resp.status_code}")

        body = resp.json()
        if "error" in body:
            raise ASRUnavailableError(body["error"].get("message", str(body["error"])))

        text = body.get("text", "").strip()
        if not text:
            raise ASREmptyError("ASR returned empty text")

        duration = body.get("duration_ms", elapsed_ms)
        request_id = body.get("request_id", "")

        logger.info("[asr] latency=%.0fms text_len=%d request_id=%s",
                     elapsed_ms, len(text), request_id)
        return ASRResult(text=text, duration_ms=duration, request_id=request_id)

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.endpoint}/v1/models", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False
