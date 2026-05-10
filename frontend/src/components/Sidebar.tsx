import { Upload, Users, Wand2, Play, Settings } from 'lucide-react';
import { useStore } from '../store';
import type { TabId } from '../types';
import clsx from 'clsx';

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'import', label: 'Import', icon: Upload },
  { id: 'characters', label: 'Characters', icon: Users },
  { id: 'effects', label: 'Effects', icon: Wand2 },
  { id: 'generate', label: 'Generate', icon: Play },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const activeTab = useStore((s) => s.activeTab);
  const setActiveTab = useStore((s) => s.setActiveTab);
  const script = useStore((s) => s.currentScript);

  return (
    <aside className="w-16 border-r border-surface-800/60 bg-surface-950/40 flex flex-col items-center py-3 gap-1 shrink-0">
      {tabs.map(({ id, label, icon: Icon }) => {
        const active = activeTab === id;
        const disabled = id !== 'import' && id !== 'settings' && !script;
        return (
          <button
            key={id}
            onClick={() => !disabled && setActiveTab(id)}
            disabled={disabled}
            className={clsx(
              'w-11 h-11 rounded-xl flex flex-col items-center justify-center gap-0.5 transition-all duration-200 group relative',
              active
                ? 'bg-forge-600/20 text-forge-400 shadow-inner'
                : disabled
                ? 'text-surface-700 cursor-not-allowed'
                : 'text-surface-500 hover:text-surface-300 hover:bg-surface-800/50',
            )}
          >
            <Icon className="w-4.5 h-4.5" strokeWidth={active ? 2.2 : 1.8} />
            <span className="text-[9px] font-display tracking-wider leading-none">{label.toUpperCase()}</span>
            {active && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-forge-500 rounded-r-full" />
            )}
          </button>
        );
      })}
    </aside>
  );
}
