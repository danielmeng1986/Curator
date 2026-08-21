-- BT-067: persistent, provider-derived AI Review translation cache.
CREATE TABLE IF NOT EXISTS ai_review_translation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    source_text TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    target_locale TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    format_version INTEGER NOT NULL DEFAULT 1,
    detected_source_language TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_sha256, target_locale, provider, provider_model, format_version)
);
CREATE INDEX IF NOT EXISTS idx_ai_review_translation_lookup
    ON ai_review_translation_cache(target_locale, provider, provider_model, source_sha256);
