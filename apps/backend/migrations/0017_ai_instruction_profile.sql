CREATE TABLE IF NOT EXISTS ai_instruction_profile (
  id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE, name TEXT NOT NULL UNIQUE,
  worker_kind TEXT NOT NULL, dataset_type TEXT NOT NULL, lifecycle_state TEXT NOT NULL DEFAULT 'Draft'
    CHECK(lifecycle_state IN ('Draft','Published','Disabled')),
  is_default INTEGER NOT NULL DEFAULT 0 CHECK(is_default IN (0,1)), version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_instruction_profile_version (
  id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE, profile_uuid TEXT NOT NULL,
  version INTEGER NOT NULL, global_instruction TEXT NOT NULL, dataset_instruction TEXT NOT NULL,
  vision_prompt_template TEXT NOT NULL, writer_prompt_template TEXT NOT NULL, output_language TEXT NOT NULL,
  naming_policy_json TEXT NOT NULL, vision_schema_version TEXT NOT NULL, writer_schema_version TEXT NOT NULL,
  validator_policy_version TEXT NOT NULL, instruction_transport TEXT NOT NULL DEFAULT 'composed_prompt',
  composition_version TEXT NOT NULL DEFAULT 'composed-v1', content_hash TEXT NOT NULL,
  created_by_token_uuid TEXT, created_at TEXT NOT NULL, UNIQUE(profile_uuid,version),
  FOREIGN KEY(profile_uuid) REFERENCES ai_instruction_profile(uuid)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_instruction_profile_default
  ON ai_instruction_profile(worker_kind,dataset_type) WHERE is_default=1 AND lifecycle_state='Published';
