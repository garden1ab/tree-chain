import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Check, AlertCircle, FolderOpen, Plus } from 'lucide-react';
import { useStore } from '../store';
import { uploadScript, createProject, listProjects, loadProjectFile } from '../api';
import type { Project } from '../types';
import clsx from 'clsx';

export default function ImportPanel() {
  const { currentProject, setCurrentProject, setCurrentScript, setActiveTab, addLog, setCharacterConfigs } = useStore();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [projectName, setProjectName] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const p = await listProjects();
      setProjects(p);
    } catch { /* ignore */ }
    setLoadingProjects(false);
  }, []);

  const handleCreateProject = async () => {
    if (!projectName.trim()) return;
    try {
      const p = await createProject(projectName.trim());
      setCurrentProject(p);
      addLog({ level: 'success', message: `Project "${p.name}" created` });
      setShowNewProject(false);
      setProjectName('');
    } catch (e: any) {
      setError(e.message);
    }
  };

  const onDrop = useCallback(async (files: File[]) => {
    if (!currentProject) {
      setError('Create or select a project first');
      return;
    }
    const file = files[0];
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const result = await uploadScript(file, currentProject.id);
      setCurrentScript(result);
      // Build default configs for discovered characters
      const configs = result.characters.map((name) => ({
        character_name: name,
        tts_provider: 'elevenlabs',
        voice_id: '',
        model_id: 'eleven_multilingual_v2',
        stability: 0.5,
        similarity_boost: 0.75,
        style: 0.0,
        use_speaker_boost: true,
        effects_preset: 'none',
        effects_config: {},
        volume_adjustment: 0.0,
      }));
      setCharacterConfigs(configs);
      addLog({
        level: 'success',
        message: `Imported "${file.name}" — ${result.total_lines} lines, ${result.characters.length} characters`,
      });
      setActiveTab('characters');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message);
      addLog({ level: 'error', message: `Import failed: ${e.message}` });
    }
    setUploading(false);
  }, [currentProject]);

  const onProjectFileDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    try {
      const p = await loadProjectFile(file);
      setCurrentProject(p);
      addLog({ level: 'success', message: `Loaded project "${p.name}" from file` });
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.txt'], 'application/json': ['.json'] },
    maxFiles: 1,
    disabled: !currentProject,
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Project selection */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Project</span>
          <button className="btn-ghost flex items-center gap-1.5" onClick={() => { setShowNewProject(true); loadProjects(); }}>
            <Plus className="w-3.5 h-3.5" /> New
          </button>
        </div>
        <div className="p-4">
          {currentProject ? (
            <div className="flex items-center gap-3">
              <FolderOpen className="w-5 h-5 text-forge-400" />
              <div>
                <p className="text-sm font-medium">{currentProject.name}</p>
                <p className="text-xs text-surface-500">{currentProject.description || 'No description'}</p>
              </div>
              <button className="ml-auto btn-ghost text-xs" onClick={() => { setCurrentProject(null); setShowNewProject(true); loadProjects(); }}>
                Switch
              </button>
            </div>
          ) : showNewProject ? (
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  className="input-field flex-1"
                  placeholder="Project name..."
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                />
                <button className="btn-primary" onClick={handleCreateProject}>Create</button>
              </div>
              {projects.length > 0 && (
                <div>
                  <p className="text-xs text-surface-500 mb-2">Or open existing:</p>
                  <div className="space-y-1 max-h-40 overflow-auto">
                    {projects.map((p) => (
                      <button
                        key={p.id}
                        className="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-800/60 text-sm transition-colors"
                        onClick={() => setCurrentProject(p)}
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button className="btn-primary w-full" onClick={() => { setShowNewProject(true); loadProjects(); }}>
              Create or Select Project
            </button>
          )}
        </div>
      </div>

      {/* File upload */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Import Script</span>
        </div>
        <div className="p-4">
          <div
            {...getRootProps()}
            className={clsx(
              'border-2 border-dashed rounded-xl p-10 text-center transition-all duration-300 cursor-pointer',
              !currentProject && 'opacity-40 cursor-not-allowed',
              isDragActive
                ? 'border-forge-500 bg-forge-600/10'
                : 'border-surface-700 hover:border-surface-500 hover:bg-surface-800/30',
            )}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-3">
              {uploading ? (
                <>
                  <div className="w-10 h-10 border-2 border-forge-500 border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm text-surface-400">Processing script...</p>
                </>
              ) : (
                <>
                  <div className="w-14 h-14 rounded-2xl bg-surface-800/80 flex items-center justify-center">
                    <Upload className="w-6 h-6 text-surface-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-surface-300">
                      {isDragActive ? 'Drop your script file' : 'Drag & drop a dialogue script'}
                    </p>
                    <p className="text-xs text-surface-600 mt-1">CSV, TXT, or JSON — with Character and Dialogue columns</p>
                  </div>
                </>
              )}
            </div>
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>

      {/* Script summary */}
      {useStore.getState().currentScript && <ScriptSummary />}

      {/* Load .projectforge */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Load Project File</span>
        </div>
        <div className="p-4">
          <label className="btn-secondary inline-flex items-center gap-2 cursor-pointer">
            <FileText className="w-4 h-4" />
            Load .projectforge
            <input
              type="file"
              accept=".projectforge,.json"
              className="hidden"
              onChange={(e) => e.target.files && onProjectFileDrop(Array.from(e.target.files))}
            />
          </label>
        </div>
      </div>
    </div>
  );
}

function ScriptSummary() {
  const script = useStore((s) => s.currentScript);
  if (!script) return null;

  return (
    <div className="panel animate-slide-up">
      <div className="panel-header">
        <span className="panel-title">Script Loaded</span>
        <span className="badge badge-green"><Check className="w-3 h-3 mr-1" /> Ready</span>
      </div>
      <div className="p-4 grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-surface-500 mb-1">File</p>
          <p className="text-sm font-medium truncate">{script.filename}</p>
        </div>
        <div>
          <p className="text-xs text-surface-500 mb-1">Lines</p>
          <p className="text-sm font-display font-bold text-forge-400">{script.total_lines}</p>
        </div>
        <div>
          <p className="text-xs text-surface-500 mb-1">Characters</p>
          <div className="flex flex-wrap gap-1">
            {script.characters.map((c) => (
              <span key={c} className="badge badge-blue">{c}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
