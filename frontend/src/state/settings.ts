export type AdapterName = 'demo' | 'mock' | 'real';

export interface AppSettings {
  apiBaseUrl: string;
  adapter: AdapterName;
  fallbackAdapter: 'mock' | 'real';
}

const storageKey = 'mirage-settings';
const adapters: AdapterName[] = ['demo', 'mock', 'real'];
const configuredAdapter = import.meta.env.VITE_ADAPTER;
const environmentAdapter: AdapterName =
  configuredAdapter === 'demo' || configuredAdapter === 'real' || configuredAdapter === 'mock'
    ? configuredAdapter
    : import.meta.env.VITE_DEMO_DEFAULT === 'true'
      ? 'demo'
      : 'mock';
const queryAdapter: AdapterName | null =
  new URLSearchParams(window.location.search).get('demo') === '0' ? 'real' : null;

function readInitialSettings(): AppSettings {
  const fallbackAdapter =
    queryAdapter === 'real' || environmentAdapter !== 'mock' ? 'real' : 'mock';
  const defaultSettings: AppSettings = {
    apiBaseUrl: import.meta.env.VITE_API_BASE || window.location.origin,
    adapter: queryAdapter ?? environmentAdapter,
    fallbackAdapter,
  };
  const stored = localStorage.getItem(storageKey);
  if (!stored) return defaultSettings;

  try {
    const value: unknown = JSON.parse(stored);
    if (typeof value !== 'object' || value === null) return defaultSettings;
    const candidate = value as Partial<AppSettings>;
    return {
      apiBaseUrl:
        typeof candidate.apiBaseUrl === 'string'
          ? candidate.apiBaseUrl
          : defaultSettings.apiBaseUrl,
      adapter:
        queryAdapter ??
        (adapters.includes(candidate.adapter as AdapterName)
          ? (candidate.adapter as AdapterName)
          : defaultSettings.adapter),
      fallbackAdapter:
        queryAdapter === 'real'
          ? 'real'
          : candidate.fallbackAdapter === 'mock' || candidate.fallbackAdapter === 'real'
            ? candidate.fallbackAdapter
            : defaultSettings.fallbackAdapter,
    };
  } catch {
    return defaultSettings;
  }
}

let settings = readInitialSettings();
const listeners = new Set<() => void>();

export function getSettings(): AppSettings {
  return settings;
}

export function subscribeSettings(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function updateSettings(next: AppSettings): void {
  localStorage.setItem(storageKey, JSON.stringify(next));
  settings = next;
  listeners.forEach((listener) => listener());
}
