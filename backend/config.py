from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Subject Specific AI Assistant"
    app_version: str = "1.0.0"

    host: str = "0.0.0.0"
    port: int = 8000

    # ============================================================
    # TEXT LLM
    # ============================================================

    llm_base_url: str = "http://host.docker.internal:1234/v1"
    llm_model: str = "qwen/qwen3.5-9b"
    llm_api_key: str = "lm-studio"
    llm_temperature: float = 0.2

    # ============================================================
    # VISION LLM
    # ============================================================

    # Qwen3-VL-4B Q4_K_M tested successfully through LM Studio.
    vision_model: str = "qwen/qwen3-vl-4b"
    vision_temperature: float = 0.2
    vision_max_tokens: int = 500
    vision_timeout_seconds: int = 180

    # ============================================================
    # QDRANT
    # ============================================================

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "school_books"

    # ============================================================
    # EMBEDDINGS
    # ============================================================

    embedding_model: str = "intfloat/multilingual-e5-large"

    # ============================================================
    # SPEECH TO TEXT
    # ============================================================

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # ============================================================
    # TEXT TO SPEECH
    # ============================================================

    piper_en_model: str = "/app/tools/piper/models/en_US-lessac-medium.onnx"
    piper_hi_model: str = ""
    piper_pa_model: str = ""
    tts_enabled: bool = True

    # IndicF5 is a local open-source model used for natural Punjabi speech.
    # The reference clip is distributed with the project's IndicF5 source.
    indicf5_model_id: str = "ai4bharat/IndicF5"
    indicf5_prompt_audio: str = "/app/IndicF5/prompts/PAN_F_HAPPY_00002.wav"
    indicf5_prompt_text: str = (
        "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ "
        "ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
    )
    indicf5_local_files_only: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
