UPDATE ai_instruction_profile
SET dataset_type = 'album_analysis', updated_at = CURRENT_TIMESTAMP
WHERE uuid = '00000000-0000-4000-8000-000000000001' AND dataset_type = 'album';
