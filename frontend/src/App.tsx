import { useEffect } from 'react';
import { useStore } from './store';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ImportPanel from './components/ImportPanel';
import CharacterPanel from './components/CharacterPanel';
import EffectsPanel from './components/EffectsPanel';
import GeneratePanel from './components/GeneratePanel';
import SettingsPanel from './components/SettingsPanel';
import LogsPanel from './components/LogsPanel';

export default function App() {
  const activeTab = useStore((s) => s.activeTab);

  const panels: Record<string, React.ReactNode> = {
    import: <ImportPanel />,
    characters: <CharacterPanel />,
    effects: <EffectsPanel />,
    generate: <GeneratePanel />,
    settings: <SettingsPanel />,
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-auto p-5">
            <div className="animate-fade-in">{panels[activeTab]}</div>
          </div>
          <LogsPanel />
        </main>
      </div>
    </div>
  );
}
