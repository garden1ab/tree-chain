import { useState } from 'react';
import { Key, Eye, EyeOff, CheckCircle2, XCircle, Trash2, Download } from 'lucide-react';
import { useStore } from '../store';
import { validateApiKey, saveApiKey, saveProjectFile } from '../api';
import clsx from 'clsx';

export default function SettingsPanel() {
  const { apiKey, setApiKey, currentProject, addLog } = useStore();
  const [tempKey, setTempKey] = useState(apiKey);
  const [show, setShow] = useState(false);
  const [validating, setValidating] = useState(false);
  const [valid, setValid] = useState<boolean | null>(null);
  const [label, setLabel] = useState('Default');

  const handleValidate = async () => {
    setValidating(true);
    try {
      const ok = await validateApiKey(tempKey);
      setValid(ok);
      if (ok) {
        setApiKey(tempKey);
        addLog({ level: 'success', message: 'API key validated successfully' });
      } else {
        addLog({ level: 'error', message: 'API key validation failed' });
      }
    } catch (e: any) {
      setValid(false);
      addLog({ level: 'error', message: `Validation error: ${e.message}` });
    }
    setValidating(false);
  };

  const handleSaveKey = async () => {
    try {
      await saveApiKey(tempKey, label);
      setApiKey(tempKey);
      addLog({ level: 'success', message: 'API key saved (encrypted)' });
    } catch (e: any) {
      addLog({ level: 'error', message: `Failed to save key: ${e.message}` });
    }
  };

  const handleExportProject = async () => {
    if (!currentProject) return;
    try {
      const blob = await saveProjectFile(currentProject.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentProject.name}.projectforge`;
      a.click();
      URL.revokeObjectURL(url);
      addLog({ level: 'success', message: 'Project exported' });
    } catch (e: any) {
      addLog({ level: 'error', message: `Export failed: ${e.message}` });
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-display font-bold tracking-wide">Settings</h2>
        <p className="text-xs text-surface-500 mt-0.5">API keys, project export, and configuration</p>
      </div>

      {/* API Key */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">ElevenLabs API Key</span>
          {valid === true && <span className="badge badge-green"><CheckCircle2 className="w-3 h-3 mr-1" /> Valid</span>}
          {valid === false && <span className="badge badge-red"><XCircle className="w-3 h-3 mr-1" /> Invalid</span>}
        </div>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
              <input
                type={show ? 'text' : 'password'}
                className="input-field pl-9 pr-9"
                placeholder="sk_..."
                value={tempKey}
                onChange={(e) => { setTempKey(e.target.value); setValid(null); }}
              />
              <button
                className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300"
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div className="flex gap-2">
            <input
              className="input-field flex-1"
              placeholder="Label (optional)"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
            <button className="btn-secondary" onClick={handleValidate} disabled={validating || !tempKey}>
              {validating ? 'Checking...' : 'Validate'}
            </button>
            <button className="btn-primary" onClick={handleSaveKey} disabled={!tempKey}>
              Save
            </button>
          </div>
        </div>
      </div>

      {/* Project export */}
      {currentProject && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Project File</span>
          </div>
          <div className="p-4">
            <button className="btn-secondary flex items-center gap-2" onClick={handleExportProject}>
              <Download className="w-4 h-4" />
              Export as .projectforge
            </button>
            <p className="text-xs text-surface-600 mt-2">
              Saves character mappings, voice settings, effects, and script metadata
            </p>
          </div>
        </div>
      )}

      {/* About */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">About</span>
        </div>
        <div className="p-4 text-xs text-surface-500 space-y-1">
          <p>DialogueForge v1.0.0</p>
          <p>Character dialogue audio generation platform</p>
          <p>Powered by ElevenLabs TTS API</p>
        </div>
      </div>
    </div>
  );
}
