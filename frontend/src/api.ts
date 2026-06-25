import axios from 'axios';
import type {
  ScriptUpload, VoiceInfo, CharacterConfig, GenerationJob,
  LineResult, CostEstimate, Project,
} from './types';

const api = axios.create({ baseURL: '/api' });

// --- Scripts ---
export async function uploadScript(file: File, projectId: string): Promise<ScriptUpload> {
  const form = new FormData();
  form.append('file', file);
  form.append('project_id', projectId);
  const { data } = await api.post('/scripts/upload', form);
  return data;
}

export async function getScript(scriptId: string): Promise<ScriptUpload> {
  const { data } = await api.get(`/scripts/${scriptId}`);
  return data;
}

// --- Voices ---
export async function fetchVoices(apiKey: string): Promise<VoiceInfo[]> {
  const { data } = await api.get('/voices', { params: { api_key: apiKey } });
  return data.voices;
}

export async function syncVoices(apiKey: string): Promise<VoiceInfo[]> {
  const { data } = await api.post('/voices/sync', { api_key: apiKey });
  return data.voices;
}

export async function getCharacterConfigs(projectId: string): Promise<CharacterConfig[]> {
  const { data } = await api.get(`/voices/configs/${projectId}`);
  return data;
}

export async function updateCharacterConfigs(projectId: string, configs: CharacterConfig[]) {
  const { data } = await api.put(`/voices/configs/${projectId}`, { configs });
  return data;
}

export async function saveApiKey(key: string, label: string) {
  const { data } = await api.post('/voices/apikey', { api_key: key, label });
  return data;
}

export async function validateApiKey(key: string): Promise<boolean> {
  const { data } = await api.post('/voices/apikey/validate', { api_key: key });
  return data.valid;
}

export async function listApiKeys() {
  const { data } = await api.get('/voices/apikeys');
  return data;
}

export async function deleteApiKey(keyId: string) {
  await api.delete(`/voices/apikey/${keyId}`);
}

// --- Providers ---
export interface TTSProviderInfo {
  name: string;
  display_name: string;
  requires_api_key: boolean;
  supports_voice_cloning: boolean;
}

export interface ProviderVoice {
  voice_id: string;
  name: string;
  category: string;
  description: string;
}

export async function listProviders(): Promise<TTSProviderInfo[]> {
  const { data } = await api.get('/providers/');
  return data;
}

export async function getProviderVoices(providerName: string): Promise<ProviderVoice[]> {
  const { data } = await api.get(`/providers/${providerName}/voices`);
  return data;
}

export async function validateProvider(providerName: string): Promise<{ valid: boolean; message: string }> {
  const { data } = await api.post(`/providers/${providerName}/validate`);
  return data;
}

// --- Generation ---
export async function startGeneration(
  projectId: string, scriptId: string, apiKey: string, exportMode: string
): Promise<GenerationJob> {
  const { data } = await api.post('/generate', {
    project_id: projectId,
    script_id: scriptId,
    export_mode: exportMode,
    output_format: 'wav',
  });
  return data;
}

export async function getJobStatus(jobId: string): Promise<GenerationJob> {
  const { data } = await api.get(`/jobs/${jobId}`);
  return data;
}

export async function getJobLines(jobId: string): Promise<LineResult[]> {
  const { data } = await api.get(`/jobs/${jobId}/lines`);
  return data;
}

export async function listJobs(): Promise<GenerationJob[]> {
  const { data } = await api.get('/jobs');
  return data;
}

export async function exportJob(jobId: string): Promise<Blob> {
  const { data } = await api.get(`/export/${jobId}`, { responseType: 'blob' });
  return data;
}

export async function estimateCost(scriptId: string): Promise<CostEstimate> {
  const { data } = await api.post('/estimate', { script_id: scriptId });
  return data;
}

// --- Projects ---
export async function createProject(name: string, description?: string): Promise<Project> {
  const { data } = await api.post('/projects/', { name, description });
  return data;
}

export async function listProjects(): Promise<Project[]> {
  const { data } = await api.get('/projects/');
  return data;
}

export async function saveProjectFile(projectId: string): Promise<Blob> {
  const { data } = await api.post(`/projects/save/${projectId}`, null, { responseType: 'blob' });
  return data;
}

export async function loadProjectFile(file: File): Promise<Project> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/projects/load', form);
  return data;
}

// --- Effects ---
export async function getEffectPresets() {
  const { data } = await api.get('/effects/presets');
  return data;
}

export async function previewEffect(audioBase64: string, preset: string, config?: Record<string, unknown>) {
  const { data } = await api.post('/effects/preview', {
    audio_base64: audioBase64,
    preset,
    config: config || {},
  });
  return data.audio_base64;
}

// --- Health ---
export async function checkHealth() {
  const { data } = await api.get('/health');
  return data;
}
