import pytest
import requests_mock as rm

from asr_client import ASRClient, ASRResult, ASRTimeoutError, ASRUnavailableError, ASREmptyError
import requests


ASR_URL = "http://127.0.0.1:8000"
TRANSCRIBE_URL = f"{ASR_URL}/v1/audio/transcriptions"
WAV_PATH = "/tmp/test.wav"


def _create_wav(path: str = WAV_PATH) -> str:
    import numpy as np
    from scipy.io import wavfile
    data = np.zeros(16000, dtype=np.int16)
    wavfile.write(path, 16000, data)
    return path


@pytest.fixture(autouse=True)
def wav_file():
    path = _create_wav()
    yield path
    import os
    if os.path.exists(path):
        os.unlink(path)


def test_successful_transcription():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, json={"text": "你好世界", "duration_ms": 500})
        client = ASRClient(endpoint=ASR_URL, max_retries=0)
        result = client.transcribe(WAV_PATH)
        assert isinstance(result, ASRResult)
        assert result.text == "你好世界"
        assert result.duration_ms == 500


def test_service_unavailable():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, status_code=503)
        client = ASRClient(endpoint=ASR_URL, max_retries=0)
        with pytest.raises(ASRUnavailableError):
            client.transcribe(WAV_PATH)


def test_connection_error():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, exc=requests.exceptions.ConnectionError("refused"))
        client = ASRClient(endpoint=ASR_URL, max_retries=0)
        with pytest.raises(ASRUnavailableError):
            client.transcribe(WAV_PATH)


def test_timeout():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, exc=requests.exceptions.Timeout("timeout"))
        client = ASRClient(endpoint=ASR_URL, max_retries=0)
        with pytest.raises(ASRTimeoutError):
            client.transcribe(WAV_PATH)


def test_empty_result():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, json={"text": "", "duration_ms": 100})
        client = ASRClient(endpoint=ASR_URL, max_retries=0)
        with pytest.raises(ASREmptyError):
            client.transcribe(WAV_PATH)


def test_retry_success():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, [
            {"status_code": 503},
            {"json": {"text": "重试成功", "duration_ms": 300}},
        ])
        client = ASRClient(endpoint=ASR_URL, max_retries=1)
        result = client.transcribe(WAV_PATH)
        assert result.text == "重试成功"


def test_retry_all_fail():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, [
            {"status_code": 503},
            {"status_code": 503},
        ])
        client = ASRClient(endpoint=ASR_URL, max_retries=1)
        with pytest.raises(ASRUnavailableError):
            client.transcribe(WAV_PATH)


def test_error_response_body():
    with rm.Mocker() as m:
        m.post(TRANSCRIBE_URL, json={
            "error": {"code": "MODEL_BUSY", "message": "GPU queue is busy"}
        })
        client = ASRClient(endpoint=ASR_URL, max_retries=0)
        with pytest.raises(ASRUnavailableError, match="GPU queue is busy"):
            client.transcribe(WAV_PATH)


def test_health_check_ok():
    with rm.Mocker() as m:
        m.get(f"{ASR_URL}/v1/models", status_code=200)
        client = ASRClient(endpoint=ASR_URL)
        assert client.health_check() is True


def test_health_check_fail():
    with rm.Mocker() as m:
        m.get(f"{ASR_URL}/v1/models", status_code=500)
        client = ASRClient(endpoint=ASR_URL)
        assert client.health_check() is False
