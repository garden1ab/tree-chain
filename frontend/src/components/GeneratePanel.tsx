import { useState, useEffect, useRef } from 'react';
import { Play, Download, AlertCircle, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { useStore } from '../store';
import { startGeneration, getJobStatus, estimateCost, exportJob, listJobs } from '../api';
import clsx from 'clsx';

export default function GeneratePanel() {
  const {
    currentProject, currentScript, characterConfigs, apiKey,
    activeJob, setActiveJob, outputFormat, setOutputFormat, addLog,
    jobs, setJobs,
  } = useStore();
  const [estimating, setEstimating] = useState(false);
  const [estimate, setEstimate] = useState<{ total_characters: number; estimated_cost_usd: number; line_count: number } | null>(null);
  const [generating, setGenerating] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const allConfigured = characterConfigs.length > 0 && characterConfigs.every((c) => c.voice_id);

  const handleEstimate = async () => {
    if (!currentScript) return;
    setEstimating(true);
    try {
      const est = await estimateCost(currentScript.script_id);
      setEstimate(est);
    } catch (e: any) {
      addLog({ level: 'error', message: `Estimation failed: ${e.message}` });
    }
    setEstimating(false);
  };

  const handleGenerate = async () => {
    if (!currentProject || !currentScript || !apiKey) return;
    setGenerating(true);
    try {
      const job = await startGeneration(currentProject.id, currentScript.script_id, apiKey, outputFormat);
      setActiveJob(job);
      addLog({ level: 'info', message: `Generation started — Job ${job.job_id.slice(0, 8)}` });
      startPolling(job.job_id);
    } catch (e: any) {
      addLog({ level: 'error', message: `Generation failed: ${e.message}` });
    }
    setGenerating(false);
  };

  const startPolling = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId);
        setActiveJob(status);
        if (status.status === 'completed' || status.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          addLog({
            level: status.status === 'completed' ? 'success' : 'error',
            message: `Job ${status.status}: ${status.completed_lines}/${status.total_lines} lines`,
          });
        }
      } catch { /* retry */ }
    }, 1500);
  };

  useEffect(() => {
    listJobs().then(setJobs).catch(() => {});
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleExport = async () => {
    if (!activeJob) return;
    try {
      const blob = await exportJob(activeJob.job_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dialogueforge_${activeJob.job_id.slice(0, 8)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      addLog({ level: 'success', message: 'Export downloaded' });
    } catch (e: any) {
      addLog({ level: 'error', message: `Export failed: ${e.message}` });
    }
  };

  const progress = activeJob ? (activeJob.total_lines > 0 ? (activeJob.completed_lines / activeJob.total_lines) * 100 : 0) : 0;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-display font-bold tracking-wide">Generate Audio</h2>
        <p className="text-xs text-surface-500 mt-0.5">Queue bulk generation via ElevenLabs TTS</p>
      </div>

      {/* Preflight checks */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Preflight</span>
        </div>
        <div className="p-4 space-y-2">
          <Check ok={!!currentProject} label="Project selected" />
          <Check ok={!!currentScript} label="Script imported" />
          <Check ok={!!apiKey} label="API key configured" />
          <Check ok={allConfigured} label="All characters have voices assigned" />
        </div>
      </div>

      {/* Cost estimation */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Cost Estimate</span>
          <button className="btn-ghost text-xs" onClick={handleEstimate} disabled={estimating || !currentScript}>
            {estimating ? 'Estimating...' : 'Calculate'}
          </button>
        </div>
        {estimate && (
          <div className="p-4 grid grid-cols-3 gap-4">
            <Stat label="Characters" value={estimate.total_characters.toLocaleString()} />
            <Stat label="Lines" value={estimate.line_count.toString()} />
            <Stat label="Est. Cost" value={`$${estimate.estimated_cost_usd.toFixed(4)}`} accent />
          </div>
        )}
      </div>

      {/* Output format */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Output</span>
        </div>
        <div className="p-4 flex gap-2">
          {['zip', 'combined', 'individual'].map((f) => (
            <button
              key={f}
              className={clsx(
                'px-4 py-2 rounded-lg text-xs font-medium transition-all capitalize',
                outputFormat === f ? 'bg-forge-600 text-white' : 'bg-surface-800 text-surface-400 hover:text-surface-200'
              )}
              onClick={() => setOutputFormat(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Generate button */}
      <button
        className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2"
        disabled={generating || !allConfigured || !apiKey || !currentScript}
        onClick={handleGenerate}
      >
        {generating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
        {generating ? 'Starting...' : 'Generate All Lines'}
      </button>

      {/* Active job progress */}
      {activeJob && (
        <div className="panel animate-slide-up">
          <div className="panel-header">
            <span className="panel-title">
              Job {activeJob.job_id.slice(0, 8)}
            </span>
            <span className={clsx('badge', {
              'badge-yellow': activeJob.status === 'pending',
              'badge-blue': activeJob.status === 'processing',
              'badge-green': activeJob.status === 'completed',
              'badge-red': activeJob.status === 'failed',
            })}>
              {activeJob.status === 'processing' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
              {activeJob.status === 'completed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
              {activeJob.status === 'failed' && <AlertCircle className="w-3 h-3 mr-1" />}
              {activeJob.status}
            </span>
          </div>
          <div className="p-4 space-y-3">
            <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-forge-600 to-forge-400 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-surface-500">
              <span>{activeJob.completed_lines} / {activeJob.total_lines} lines</span>
              {activeJob.failed_lines > 0 && (
                <span className="text-red-400">{activeJob.failed_lines} failed</span>
              )}
              <span>{progress.toFixed(0)}%</span>
            </div>
            {activeJob.status === 'completed' && (
              <button className="btn-primary w-full flex items-center justify-center gap-2" onClick={handleExport}>
                <Download className="w-4 h-4" /> Download Output
              </button>
            )}
          </div>
        </div>
      )}

      {/* Job history */}
      {jobs.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Recent Jobs</span>
          </div>
          <div className="divide-y divide-surface-800/40">
            {jobs.slice(0, 10).map((j) => (
              <div key={j.job_id} className="px-4 py-2.5 flex items-center gap-3 text-xs">
                <StatusIcon status={j.status} />
                <span className="font-display text-surface-400 w-20">{j.job_id.slice(0, 8)}</span>
                <span className="text-surface-500 flex-1">{j.completed_lines}/{j.total_lines} lines</span>
                <span className="text-surface-600">{new Date(j.created_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Clock className="w-4 h-4 text-surface-600" />}
      <span className={ok ? 'text-surface-300' : 'text-surface-600'}>{label}</span>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <p className="text-xs text-surface-500 mb-0.5">{label}</p>
      <p className={clsx('text-sm font-display font-bold', accent ? 'text-forge-400' : 'text-surface-200')}>{value}</p>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  const cls = {
    completed: 'status-dot-active',
    processing: 'status-dot-pending',
    pending: 'status-dot-idle',
    failed: 'status-dot-error',
  }[status] || 'status-dot-idle';
  return <div className={`status-dot ${cls}`} />;
}
