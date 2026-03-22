from app.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.corpus_target_papers > 0
    assert len(settings.corpus_topic) > 0
    assert len(settings.corpus_start_date) == 10  # YYYY-MM-DD
    assert len(settings.corpus_end_date) == 10
    # Model names may be overridden by .env
    assert len(settings.openrouter_chat_model) > 0
    assert len(settings.openrouter_embedding_model) > 0


def test_settings_data_dirs() -> None:
    settings = Settings()
    assert str(settings.raw_dir).endswith("data/raw")
    assert str(settings.processed_dir).endswith("data/processed")
    assert str(settings.index_dir).endswith("data/index")
