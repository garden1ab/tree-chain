import { create } from 'zustand';
import type {
  Project, ScriptUpload, VoiceInfo, CharacterConfig,
  GenerationJob, LogEntry, TabId,
} from './types';

interface AppState {
  // Navigation
  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;

  // Project
  currentProject: Project | null;
  setCurrentProject: (p: Project | null) => void;

  // Script
  currentScript: ScriptUpload | null;
  setCurrentScript: (s: ScriptUpload | null) => void;

  // Voices
  voices: VoiceInfo[];
  setVoices: (v: VoiceInfo[]) => void;

  // Character configs
  characterConfigs: CharacterConfig[];
  setCharacterConfigs: (c: CharacterConfig[]) => void;
  updateCharacterConfig: (name: string, updates: Partial<CharacterConfig>) => void;

  // API Key
  apiKey: string;
  setApiKey: (k: string) => void;

  // Jobs
  activeJob: GenerationJob | null;
  setActiveJob: (j: GenerationJob | null) => void;
  jobs: GenerationJob[];
  setJobs: (j: GenerationJob[]) => void;

  // Logs
  logs: LogEntry[];
  addLog: (entry: Omit<LogEntry, 'timestamp'>) => void;
  clearLogs: () => void;

  // Output
  outputFormat: string;
  setOutputFormat: (f: string) => void;
}

export const useStore = create<AppState>((set) => ({
  activeTab: 'import',
  setActiveTab: (tab) => set({ activeTab: tab }),

  currentProject: null,
  setCurrentProject: (p) => set({ currentProject: p }),

  currentScript: null,
  setCurrentScript: (s) => set({ currentScript: s }),

  voices: [],
  setVoices: (v) => set({ voices: v }),

  characterConfigs: [],
  setCharacterConfigs: (c) => set({ characterConfigs: c }),
  updateCharacterConfig: (name, updates) =>
    set((state) => ({
      characterConfigs: state.characterConfigs.map((c) =>
        c.character_name === name ? { ...c, ...updates } : c
      ),
    })),

  apiKey: '',
  setApiKey: (k) => set({ apiKey: k }),

  activeJob: null,
  setActiveJob: (j) => set({ activeJob: j }),
  jobs: [],
  setJobs: (j) => set({ jobs: j }),

  logs: [],
  addLog: (entry) =>
    set((state) => ({
      logs: [
        { ...entry, timestamp: new Date().toISOString() },
        ...state.logs,
      ].slice(0, 500),
    })),
  clearLogs: () => set({ logs: [] }),

  outputFormat: 'zip',
  setOutputFormat: (f) => set({ outputFormat: f }),
}));
