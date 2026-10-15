import numpy as np

from backend.speech import tts


def test_indicf5_writes_punjabi_wav_with_teacher_prompt(tmp_path, monkeypatch):
    received = {}

    class FakeIndicF5:
        def __call__(self, text, *, ref_audio_path, ref_text):
            received["text"] = text
            received["ref_audio_path"] = ref_audio_path
            received["ref_text"] = ref_text
            return np.array([0, 1000, -1000], dtype=np.int16)

    monkeypatch.setattr(tts, "get_indicf5_model", lambda: FakeIndicF5())
    output_path = tmp_path / "punjabi.wav"

    tts._write_indicf5_wav("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", output_path)

    assert output_path.is_file()
    assert output_path.stat().st_size > 0
    assert received["text"] == "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ"
    assert received["ref_audio_path"] == tts.settings.indicf5_prompt_audio
    assert received["ref_text"] == tts.settings.indicf5_prompt_text


def test_punjabi_is_routed_to_indicf5():
    assert tts.normalize_tts_language("Punjabi") == "pa"
