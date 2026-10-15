from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from uuid import uuid4
import wave

import numpy as np

from backend.config import settings


# ============================================================
# LANGUAGE NORMALIZATION
# ============================================================

def normalize_tts_language(language: str | None) -> str:
    value = (language or "en").strip().lower()

    aliases = {
        "english": "en",
        "eng": "en",
        "en": "en",

        "hindi": "hi",
        "hin": "hi",
        "hi": "hi",

        "punjabi": "pa",
        "pan": "pa",
        "pa": "pa",
    }

    return aliases.get(value, "en")


# ============================================================
# MODEL PATH
# ============================================================

def get_model_path(language: str) -> str:
    language = normalize_tts_language(language)

    if language == "hi":
        return settings.piper_hi_model

    if language == "pa":
        return settings.piper_pa_model

    return settings.piper_en_model


# ============================================================
# PIPER MODEL
# ============================================================

@lru_cache(maxsize=3)
def get_piper_voice(model_path: str):
    """
    Load and cache a Piper voice.

    The model is loaded only once and reused for
    subsequent requests.
    """

    if not model_path:
        raise RuntimeError(
            "No Piper model is configured for this language."
        )

    path = Path(model_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Piper model not found: {path}"
        )

    from piper import PiperVoice

    print("=" * 70)
    print("Loading Piper TTS model")
    print(f"Model: {path}")
    print("=" * 70)

    return PiperVoice.load(str(path))


@lru_cache(maxsize=1)
def get_indicf5_model():
    """Load the local open-source Punjabi model once per application process."""
    prompt_path = Path(settings.indicf5_prompt_audio)
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"IndicF5 Punjabi prompt audio not found: {prompt_path}"
        )

    from transformers import AutoModel

    print("Loading IndicF5 Punjabi TTS model")
    return AutoModel.from_pretrained(
        settings.indicf5_model_id,
        trust_remote_code=True,
        local_files_only=settings.indicf5_local_files_only,
    )


def _write_indicf5_wav(text: str, output_path: Path) -> None:
    """Synthesize with the bundled Punjabi teacher reference prompt."""
    import soundfile as sf

    audio = np.asarray(
        get_indicf5_model()(
            text,
            ref_audio_path=settings.indicf5_prompt_audio,
            ref_text=settings.indicf5_prompt_text,
        )
    )
    if audio.size == 0:
        raise RuntimeError("IndicF5 returned empty audio.")

    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    else:
        audio = audio.astype(np.float32)
    sf.write(str(output_path), audio, samplerate=24000)


# ============================================================
# TEXT TO SPEECH
# ============================================================

def text_to_speech(
    text: str,
    language: str = "en",
) -> str:
    """
    Convert text to a WAV file using the configured local TTS provider.

    Returns:
        Filename only, so the API can expose it through /audio/.
    """

    text = str(text or "").strip()

    if not text:
        raise ValueError("Cannot synthesize empty text.")
    if not settings.tts_enabled:
        raise RuntimeError("Text-to-speech is disabled.")

    language = normalize_tts_language(language)

    output_dir = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "audio"
        / "output"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = f"tts_{uuid4().hex}.wav"

    output_path = output_dir / filename

    print(f"TTS language={language}, output={output_path}")

    if language == "pa":
        _write_indicf5_wav(text, output_path)
    else:
        model_path = get_model_path(language)
        if not model_path:
            raise RuntimeError(
                f"Piper TTS model is not configured for language: {language}"
            )

        voice = get_piper_voice(model_path)
        with wave.open(str(output_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

    if not output_path.exists():
        raise RuntimeError(
            "TTS provider did not create the output audio file."
        )

    if output_path.stat().st_size == 0:
        raise RuntimeError(
            "TTS provider created an empty audio file."
        )

    print(
        f"TTS complete: {output_path.name} "
        f"({output_path.stat().st_size} bytes)"
    )

    return filename
