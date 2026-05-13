export interface Project {
  id: string;
  name: string;
  description: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DialogueLine {
  id: string;
  line_number: number;
  character_name: string;
  text: string;
  raw_text: string;
  directives: string[];
  pause_after_ms: number;
}

export interface ScriptUpload {
  script_id: string;
  filename: string;
  total_lines: number;
  characters: string[];
  lines: DialogueLine[];
}

export interface VoiceInfo {
  voice_id: string;
  name: string;
  category: string;
  labels: Record<string, string>;
  preview_url: string | null;
}

export interface CharacterConfig {
  character_name: string;
  tts_provider: string;
  voice_id: string;
  model_id: string;
  stability: number;
  similarity_boost: number;
  style: number;
  use_speaker_boost: boolean;
  effects_preset: string;
  effects_config: Record<string, unknown>;
  volume_adjustment: number;
}

export interface GenerationJob {
  job_id: string;
  project_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused';
  total_lines: number;
  completed_lines: number;
  failed_lines: number;
  created_at: string;
  updated_at: string;
}

export interface LineResult {
  line_id: string;
  line_number: number;
  character_name: string;
  status: string;
  error_message: string | null;
  file_path: string | null;
}

export interface CostEstimate {
  total_characters: number;
  estimated_credits: number;
  estimated_cost_usd: number;
  line_count: number;
}

export interface EffectPreset {
  name: string;
  description: string;
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
  details?: Record<string, unknown>;
}

export type TabId = 'import' | 'characters' | 'effects' | 'generate' | 'settings';
