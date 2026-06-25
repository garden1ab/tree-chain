import { useState, useEffect } from 'react';
import { RefreshCw, Volume2, Save, ChevronDown, ChevronRight } from 'lucide-react';
import { useStore } from '../store';
import { fetchVoices, syncVoices, listProviders, getProviderVoices } from '../api';
import type { TTSProviderInfo, ProviderVoice } from '../api';
import type { CharacterConfig } from '../types';
import clsx from 'clsx';

export default function CharacterPanel() {
  const { characterConfigs, updateCharacterConfig, voices, setVoices, apiKey, addLog } = useStore();
  const [syncing, setSyncing] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [providers, setProviders] = useState<TTSProviderInfo[]>([]);
  const [providerVoices, setProviderVoices] = useState<Record<string, ProviderVoice[]>>({});

  // Load providers on mount
  useEffect(() => {
    listProviders().then(setProviders).catch(() => {});
  }, []);

  // Load voices for a specific provider
  const loadProviderVoices = async (providerName: string) => {
    if (providerVoices[providerName]) return;
    try {
      const voices = await getProviderVoices(providerName);
      setProviderVoices((prev) => ({ ...prev, [providerName]: voices }));
    } catch {
      addLog({ level: 'error', message: `Failed to load voices for ${providerName}` });
    }
  };

  const handleSync = async () => {
    if (!apiKey) {
      addLog({ level: 'warning', message: 'Set your API key in Settings first' });
      return;
    }
    setSyncing(true);
    try {
      const v = await syncVoices(apiKey);
      setVoices(v);
      addLog({ level: 'success', message: `Synced ${v.length} voices from ElevenLabs` });
    } catch (e: any) {
      addLog({ level: 'error', message: `Voice sync failed: ${e.message}` });
    }
    setSyncing(false);
  };

  useEffect(() => {
    if (apiKey && voices.length === 0) handleSync();
  }, [apiKey]);

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-display font-bold tracking-wide">Character Voices</h2>
          <p className="text-xs text-surface-500 mt-0.5">Assign ElevenLabs voices and configure each character</p>
        </div>
        <button
          className="btn-secondary flex items-center gap-2"
          onClick={handleSync}
          disabled={syncing}
        >
          <RefreshCw className={clsx('w-3.5 h-3.5', syncing && 'animate-spin')} />
          {syncing ? 'Syncing...' : 'Sync Voices'}
        </button>
      </div>

      {characterConfigs.length === 0 ? (
        <div className="panel p-8 text-center text-surface-500 text-sm">
          Import a script first to see characters here
        </div>
      ) : (
        <div className="space-y-2">
          {characterConfigs.map((config) => (
            <CharacterRow
              key={config.character_name}
              config={config}
              voices={voices}
              providers={providers}
              providerVoices={providerVoices}
              onLoadProviderVoices={loadProviderVoices}
              expanded={expanded === config.character_name}
              onToggle={() => setExpanded(expanded === config.character_name ? null : config.character_name)}
              onUpdate={(u) => updateCharacterConfig(config.character_name, u)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface CharacterRowProps {
  config: ReturnType<typeof useStore.getState>['characterConfigs'][0];
  voices: ReturnType<typeof useStore.getState>['voices'];
  providers: TTSProviderInfo[];
  providerVoices: Record<string, ProviderVoice[]>;
  onLoadProviderVoices: (name: string) => void;
  expanded: boolean;
  onToggle: () => void;
  onUpdate: (u: Partial<CharacterConfig>) => void;
}

function CharacterRow({ config, voices, providers, providerVoices, onLoadProviderVoices, expanded, onToggle, onUpdate }: CharacterRowProps) {
  const currentProvider = config.tts_provider || 'elevenlabs';
  const isLocal = currentProvider !== 'elevenlabs';
  const localVoices = providerVoices[currentProvider] || [];
  const selectedVoice = isLocal
    ? localVoices.find((v) => v.voice_id === config.voice_id)
    : voices.find((v) => v.voice_id === config.voice_id);
  const [manualId, setManualId] = useState(false);
  const [effectPresets, setEffectPresets] = useState<string[]>([]);

  // Load provider voices when provider changes
  useEffect(() => {
    if (isLocal) onLoadProviderVoices(currentProvider);
  }, [currentProvider]);

  // Load available effect presets (built-in + custom) once
  useEffect(() => {
    fetch('/api/effects/presets')
      .then((r) => r.json())
      .then((d) => setEffectPresets(d.presets || []))
      .catch(() => {});
  }, []);

  return (
    <div className="panel overflow-hidden">
      {/* Summary row */}
      <button
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-surface-800/30 transition-colors"
        onClick={onToggle}
      >
        {expanded ? <ChevronDown className="w-4 h-4 text-surface-500" /> : <ChevronRight className="w-4 h-4 text-surface-500" />}
        <div className="w-8 h-8 rounded-lg bg-forge-600/20 flex items-center justify-center font-display text-sm font-bold text-forge-400">
          {config.character_name[0]}
        </div>
        <span className="font-medium text-sm flex-1 text-left truncate">{config.character_name}</span>

        {/* Provider selector */}
        <select
          className="input-field w-36 text-xs"
          value={currentProvider}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onUpdate({ tts_provider: e.target.value, voice_id: '' })}
        >
          {providers.map((p) => (
            <option key={p.name} value={p.name}>{p.display_name}</option>
          ))}
        </select>

        {/* Voice selector — dropdown or manual ID input */}
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          {manualId ? (
            <input
              type="text"
              className="input-field w-44 text-xs font-mono"
              placeholder="Paste voice ID or path..."
              value={config.voice_id}
              onChange={(e) => onUpdate({ voice_id: e.target.value })}
            />
          ) : (
            <select
              className="input-field w-44 text-xs"
              value={config.voice_id}
              onChange={(e) => onUpdate({ voice_id: e.target.value })}
            >
              <option value="">Select voice...</option>
              {isLocal
                ? localVoices.map((v) => (
                    <option key={v.voice_id} value={v.voice_id}>{v.name}</option>
                  ))
                : voices.map((v) => (
                    <option key={v.voice_id} value={v.voice_id}>{v.name}</option>
                  ))
              }
            </select>
          )}
          <button
            className={clsx(
              'px-1.5 py-1 rounded text-[10px] font-display tracking-wide uppercase shrink-0 transition-colors',
              manualId
                ? 'bg-forge-600/20 text-forge-400'
                : 'bg-surface-800/50 text-surface-500 hover:text-surface-300'
            )}
            title={manualId ? 'Switch to dropdown' : 'Type a voice ID manually'}
            onClick={() => setManualId(!manualId)}
          >
            {manualId ? 'List' : 'ID'}
          </button>
        </div>

        {/* Model selector — only relevant for ElevenLabs */}
        {currentProvider === 'elevenlabs' && (
          <select
            className="input-field w-40 text-xs"
            value={config.model_id}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onUpdate({ model_id: e.target.value })}
          >
            <option value="eleven_multilingual_v2">Multilingual v2</option>
            <option value="eleven_monolingual_v1">English v1</option>
            <option value="eleven_turbo_v2_5">Turbo v2.5</option>
            <option value="eleven_turbo_v2">Turbo v2</option>
            <option value="eleven_v3">Eleven v3</option>
          </select>
        )}

        <div className={clsx('badge', config.voice_id ? 'badge-green' : 'badge-yellow')}>
          {config.voice_id ? (selectedVoice ? selectedVoice.name : 'Custom ID') : 'Unset'}
        </div>
      </button>

      {/* Expanded settings */}
      {expanded && (
        <div className="border-t border-surface-800/60 p-4 grid grid-cols-2 gap-x-8 gap-y-4 animate-slide-up">
          {config.tts_provider === 'elevenlabs' ? (
            <>
              <SliderControl label="Stability" value={config.stability} onChange={(v) => onUpdate({ stability: v })} />
              <SliderControl label="Similarity Boost" value={config.similarity_boost} onChange={(v) => onUpdate({ similarity_boost: v })} />
              <SliderControl label="Style Exaggeration" value={config.style} onChange={(v) => onUpdate({ style: v })} />
            </>
          ) : (
            <>
              <SliderControl
                label="Exaggeration (emotion)"
                value={config.exaggeration}
                min={0.25} max={2.0} step={0.05}
                onChange={(v) => onUpdate({ exaggeration: v })}
              />
              <SliderControl
                label="CFG / Pace"
                value={config.cfg_weight}
                min={0.2} max={1.0} step={0.05}
                onChange={(v) => onUpdate({ cfg_weight: v })}
              />
              <SliderControl
                label="Temperature"
                value={config.temperature}
                min={0.05} max={5.0} step={0.05}
                onChange={(v) => onUpdate({ temperature: v })}
              />
              <div>
                <label className="text-xs text-surface-400 block mb-1">Random Seed (0 = random)</label>
                <input
                  type="number"
                  className="input-field text-xs"
                  value={config.seed}
                  onChange={(e) => onUpdate({ seed: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div>
                <label className="text-xs text-surface-400 block mb-1">Language</label>
                <select
                  className="input-field text-xs"
                  value={config.language}
                  onChange={(e) => onUpdate({ language: e.target.value })}
                >
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="de">German</option>
                  <option value="it">Italian</option>
                  <option value="pt">Portuguese</option>
                  <option value="pl">Polish</option>
                  <option value="ru">Russian</option>
                  <option value="nl">Dutch</option>
                  <option value="tr">Turkish</option>
                  <option value="ar">Arabic</option>
                  <option value="zh">Chinese</option>
                  <option value="ja">Japanese</option>
                  <option value="ko">Korean</option>
                  <option value="hi">Hindi</option>
                  <option value="id">Indonesian</option>
                  <option value="vi">Vietnamese</option>
                  <option value="th">Thai</option>
                  <option value="uk">Ukrainian</option>
                  <option value="cs">Czech</option>
                  <option value="el">Greek</option>
                  <option value="ms">Malay</option>
                  <option value="ro">Romanian</option>
                </select>
              </div>
            </>
          )}

          <SliderControl label="Volume Adjustment" value={config.volume_adjustment} min={-10} max={10} step={0.5} onChange={(v) => onUpdate({ volume_adjustment: v })} />

          {config.tts_provider === 'elevenlabs' && (
            <div className="flex items-center gap-3">
              <label className="text-xs text-surface-400">Speaker Boost</label>
              <button
                className={clsx(
                  'w-10 h-5 rounded-full transition-colors relative',
                  config.use_speaker_boost ? 'bg-forge-600' : 'bg-surface-700'
                )}
                onClick={() => onUpdate({ use_speaker_boost: !config.use_speaker_boost })}
              >
                <div className={clsx(
                  'w-4 h-4 rounded-full bg-white absolute top-0.5 transition-transform',
                  config.use_speaker_boost ? 'translate-x-5' : 'translate-x-0.5'
                )} />
              </button>
            </div>
          )}

          <div className="col-span-2">
            <label className="text-xs text-surface-400 block mb-1">Effects Preset</label>
            <select
              className="input-field text-xs"
              value={config.effects_preset}
              onChange={(e) => onUpdate({ effects_preset: e.target.value })}
            >
              <option value="none">None</option>
              {effectPresets.map((p: string) => (
                <option key={p} value={p}>
                  {p.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

function SliderControl({
  label, value, min = 0, max = 1, step = 0.01, onChange,
}: {
  label: string; value: number; min?: number; max?: number; step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <label className="text-xs text-surface-400">{label}</label>
        <span className="text-xs font-display text-surface-300">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        className="slider-track"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}
