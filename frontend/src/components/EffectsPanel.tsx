import { useState, useEffect } from 'react';
import { Wand2, Volume2 } from 'lucide-react';
import { useStore } from '../store';
import { getEffectPresets } from '../api';

const PRESET_ICONS: Record<string, string> = {
  radio: '📻', helmet: '⛑️', robot: '🤖', telephone: '☎️',
  megaphone: '📢', vhs: '📼', corrupted_ai: '💀', deep_space: '🌌',
  glitch: '⚡', alien: '👽',
};

export default function EffectsPanel() {
  const { characterConfigs, updateCharacterConfig } = useStore();
  const [descriptions, setDescriptions] = useState<Record<string, string>>({});

  useEffect(() => {
    getEffectPresets().then((d) => setDescriptions(d.descriptions || {})).catch(() => {});
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-display font-bold tracking-wide">Audio Effects</h2>
        <p className="text-xs text-surface-500 mt-0.5">Apply distortion presets and fine-tune per character</p>
      </div>

      {/* Preset grid */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Available Presets</span>
        </div>
        <div className="p-4 grid grid-cols-5 gap-3">
          {Object.entries(descriptions).map(([name, desc]) => (
            <div
              key={name}
              className="p-3 rounded-xl bg-surface-800/40 border border-surface-800/60 hover:border-forge-600/40 transition-all cursor-default"
            >
              <div className="text-xl mb-1">{PRESET_ICONS[name] || '🎵'}</div>
              <p className="text-xs font-medium capitalize">{name.replace('_', ' ')}</p>
              <p className="text-[10px] text-surface-500 mt-0.5 line-clamp-2">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Per-character assignments */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Character Effects</span>
        </div>
        <div className="divide-y divide-surface-800/40">
          {characterConfigs.map((c) => (
            <div key={c.character_name} className="px-4 py-3 flex items-center gap-4">
              <div className="w-7 h-7 rounded-lg bg-forge-600/20 flex items-center justify-center font-display text-xs font-bold text-forge-400">
                {c.character_name[0]}
              </div>
              <span className="text-sm font-medium w-36 truncate">{c.character_name}</span>
              <select
                className="input-field flex-1 text-xs"
                value={c.effects_preset}
                onChange={(e) => updateCharacterConfig(c.character_name, { effects_preset: e.target.value })}
              >
                <option value="none">No Effect</option>
                {Object.keys(descriptions).map((p) => (
                  <option key={p} value={p}>{PRESET_ICONS[p] || ''} {p.replace('_', ' ')}</option>
                ))}
              </select>
              <span className="text-xl w-8 text-center">{PRESET_ICONS[c.effects_preset] || '—'}</span>
            </div>
          ))}
          {characterConfigs.length === 0 && (
            <p className="p-6 text-center text-sm text-surface-500">Import a script to configure effects</p>
          )}
        </div>
      </div>
    </div>
  );
}
