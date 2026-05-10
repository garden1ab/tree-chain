import { useState } from 'react';
import { Terminal, ChevronUp, ChevronDown, Trash2 } from 'lucide-react';
import { useStore } from '../store';
import clsx from 'clsx';

const LEVEL_STYLES = {
  info: 'text-forge-400',
  warning: 'text-amber-400',
  error: 'text-red-400',
  success: 'text-emerald-400',
};

const LEVEL_DOTS = {
  info: 'bg-forge-400',
  warning: 'bg-amber-400',
  error: 'bg-red-400',
  success: 'bg-emerald-400',
};

export default function LogsPanel() {
  const [expanded, setExpanded] = useState(false);
  const logs = useStore((s) => s.logs);
  const clearLogs = useStore((s) => s.clearLogs);

  return (
    <div className={clsx(
      'border-t border-surface-800/60 bg-surface-950/80 backdrop-blur-md transition-all duration-300 shrink-0',
      expanded ? 'h-52' : 'h-9',
    )}>
      {/* Bar */}
      <button
        className="w-full h-9 px-4 flex items-center gap-2 hover:bg-surface-800/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <Terminal className="w-3.5 h-3.5 text-surface-500" />
        <span className="text-[10px] font-display tracking-widest text-surface-500 uppercase">Logs</span>
        {logs.length > 0 && (
          <span className="text-[10px] font-display text-surface-600">({logs.length})</span>
        )}
        <div className="flex-1" />
        {expanded && (
          <button
            className="p-1 hover:text-surface-300 text-surface-600"
            onClick={(e) => { e.stopPropagation(); clearLogs(); }}
          >
            <Trash2 className="w-3 h-3" />
          </button>
        )}
        {expanded ? <ChevronDown className="w-3.5 h-3.5 text-surface-500" /> : <ChevronUp className="w-3.5 h-3.5 text-surface-500" />}
      </button>

      {/* Log entries */}
      {expanded && (
        <div className="h-[calc(100%-2.25rem)] overflow-auto px-4 py-1 space-y-0.5">
          {logs.length === 0 ? (
            <p className="text-xs text-surface-600 py-4 text-center">No log entries yet</p>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2 py-0.5 text-xs font-mono">
                <span className="text-surface-700 w-16 shrink-0">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <div className={clsx('w-1.5 h-1.5 rounded-full mt-1.5 shrink-0', LEVEL_DOTS[log.level])} />
                <span className={LEVEL_STYLES[log.level]}>{log.message}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
