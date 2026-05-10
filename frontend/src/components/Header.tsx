import { Activity, Zap } from 'lucide-react';
import { useStore } from '../store';

export default function Header() {
  const project = useStore((s) => s.currentProject);
  const activeJob = useStore((s) => s.activeJob);

  return (
    <header className="h-12 border-b border-surface-800/60 bg-surface-950/80 backdrop-blur-md flex items-center px-4 gap-4 shrink-0">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-forge-600 flex items-center justify-center">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <h1 className="font-display text-sm font-bold tracking-wider text-surface-100">
          DIALOGUE<span className="text-forge-400">FORGE</span>
        </h1>
      </div>

      <div className="h-5 w-px bg-surface-800 mx-1" />

      {project && (
        <span className="text-xs text-surface-500 font-display tracking-wide">
          {project.name}
        </span>
      )}

      <div className="flex-1" />

      {activeJob && activeJob.status === 'processing' && (
        <div className="flex items-center gap-2 text-xs text-forge-400">
          <Activity className="w-3.5 h-3.5 animate-pulse" />
          <span className="font-display tracking-wide">
            {activeJob.completed_lines}/{activeJob.total_lines} LINES
          </span>
        </div>
      )}

      <div className="flex items-center gap-1.5">
        <div className="status-dot status-dot-active" />
        <span className="text-xs text-surface-500">System Ready</span>
      </div>
    </header>
  );
}
