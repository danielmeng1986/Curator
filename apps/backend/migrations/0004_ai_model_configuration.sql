-- BT-045: portable, versioned llama.cpp model configurations.
CREATE TABLE IF NOT EXISTS ai_model_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL CHECK(provider_type='llama_cpp'),
    model_identifier TEXT NOT NULL,
    model_repository TEXT,
    model_file TEXT NOT NULL,
    vision_prompt_version TEXT NOT NULL,
    writer_prompt_version TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    context_size INTEGER NOT NULL,
    threads INTEGER NOT NULL,
    gpu_layers INTEGER NOT NULL,
    max_tokens INTEGER NOT NULL,
    temperature REAL NOT NULL,
    image_max_tokens INTEGER NOT NULL,
    additional_parameters_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
