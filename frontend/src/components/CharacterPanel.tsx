import { useState, useEffect } from 'react';
import { RefreshCw, Volume2, Save, ChevronDown, ChevronRight } from 'lucide-react';
import { useStore } from '../store';
import { fetchVoices, syncVoices } from '../api';
import clsx from 'clsx';

export default function CharacterPanel() {
  const { characterConfigs, updateCharacterConfig, voices, setVoices, apiKey, addLog } = useStore();
  const [syncing, setSyncing] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

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
  expanded: boolean;
  onToggle: () => void;
  onUpdate: (u: Partial<typeof config>) => void;
}

function CharacterRow({ config, voices, expanded, onToggle, onUpdate }: CharacterRowProps) {
  const selectedVoice = voices.find((v) => v.voice_id === config.voice_id);

  return (
    <div className="panel overflow-hidden">
      {/* Summary row */}
      <button
        className="w-full px-4 py-3 flex items-center gap-4 hover:bg-surface-800/30 transition-colors"
        onClick={onToggle}
      >
        {expanded ? <ChevronDown className="w-4 h-4 text-surface-500" /> : <ChevronRight className="w-4 h-4 text-surface-500" />}
        <div className="w-8 h-8 rounded-lg bg-forge-600/20 flex items-center justify-center font-display text-sm font-bold text-forge-400">
          {config.character_name[0]}
        </div>
        <span className="font-medium text-sm flex-1 text-left">{config.character_name}</span>

        {/* Voice selector inline */}
        <select
          className="input-field w-56 text-xs"
          value={config.voice_id}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onUpdate({ voice_id: e.target.value })}
        >
          <option value="">Select voice...</option>
          {voices.map((v) => (
            <option key={v.voice_id} value={v.voice_id}>{v.name}</option>
          ))}
        </select>

        {/* Model selector inline */}
        <select
          className="input-field w-48 text-xs"
          value={config.model_id}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onUpdate({ model_id: e.target.value })}
        >
          <option value="eleven_multilingual_v2">Multilingual v2</option>
          <option value="eleven_monolingual_v1">English v1</option>
          <option value="eleven_turbo_v2_5">Turbo v2.5</option>
          <option value="eleven_turbo_v2">Turbo v2</option>
        </select>

        <div className={clsx('badge', config.voice_id ? 'badge-green' : 'badge-yellow')}>
          {config.voice_id ? 'Configured' : 'Unset'}
        </div>
      </button>

      {/* Expanded settings */}
      {expanded && (
        <div className="border-t border-surface-800/60 p-4 grid grid-cols-2 gap-x-8 gap-y-4 animate-slide-up">
          <SliderControl label="Stability" value={config.stability} onChange={(v) => onUpdate({ stability: v })} />
          <SliderControl label="Similarity Boost" value={config.similarity_boost} onChange={(v) => onUpdate({ similarity_boost: v })} />
          <SliderControl label="Style Exaggeration" value={config.style} onChange={(v) => onUpdate({ style: v })} />
          <SliderControl label="Volume Adjustment" value={config.volume_adjustment} min={-10} max={10} step={0.5} onChange={(v) => onUpdate({ volume_adjustment: v })} />

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

          <div>
            <label className="text-xs text-surface-400 block mb-1">Effects Preset</label>
            <select
              className="input-field text-xs"
              value={config.effects_preset}
              onChange={(e) => onUpdate({ effects_preset: e.target.value })}
            >
              <option value="none">None</option>
              <option value="radio">Radio</option>
              <option value="helmet">Helmet</option>
              <option value="robot">Robot</option>
              <option value="telephone">Telephone</option>
              <option value="megaphone">Megaphone</option>
              <option value="vhs">VHS</option>
              <option value="corrupted_ai">Corrupted AI</option>
              <option value="deep_space">Deep Space</option>
              <option value="glitch">Glitch</option>
              <option value="alien">Alien</option>
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
