import { useEffect, useState, useSyncExternalStore, type FormEvent } from 'react';
import { Settings } from 'lucide-react';
import { api, getAdapter } from '../api';
import { friendlyErrorMessage } from '../api/errorMessages';
import type { HealthResponse } from '../api/types';
import { getSettings, subscribeSettings, updateSettings } from '../state/settings';

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export default function SettingsDrawer() {
  const settings = useSyncExternalStore(subscribeSettings, getSettings, getSettings);
  const [isOpen, setIsOpen] = useState(false);
  const [apiBaseUrl, setApiBaseUrl] = useState(settings.apiBaseUrl);
  const [connection, setConnection] = useState<HealthResponse | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [storageError, setStorageError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setApiBaseUrl(settings.apiBaseUrl);
  }, [settings.apiBaseUrl]);

  useEffect(() => {
    if (!isOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false);
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isOpen]);

  function saveApiBaseUrl(): boolean {
    const trimmedUrl = apiBaseUrl.trim();
    if (!isHttpUrl(trimmedUrl)) {
      setSaved(false);
      setStorageError('Enter a valid http:// or https:// API base URL.');
      return false;
    }

    setStorageError(null);
    try {
      updateSettings({ ...settings, apiBaseUrl: trimmedUrl });
      setApiBaseUrl(trimmedUrl);
      setSaved(true);
      return true;
    } catch (error) {
      setSaved(false);
      const message =
        error instanceof Error ? error.message : 'Settings could not be saved in this browser.';
      setStorageError(message);
      return false;
    }
  }

  async function testConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTesting(true);
    setConnection(null);
    setConnectionError(null);
    setSaved(false);
    if (saveApiBaseUrl()) {
      try {
        const health = await api.health();
        setConnection(health);
      } catch (error) {
        setConnectionError(friendlyErrorMessage(error));
      }
    } else {
      setConnectionError('The API URL could not be saved, so the connection test was skipped.');
    }
    setTesting(false);
  }

  function toggleDemoMode(enabled: boolean) {
    setConnection(null);
    setConnectionError(null);
    setStorageError(null);
    setSaved(false);
    try {
      updateSettings({
        ...settings,
        adapter: enabled ? 'demo' : settings.fallbackAdapter,
      });
    } catch (error) {
      setStorageError(
        error instanceof Error ? error.message : 'Settings could not be saved in this browser.',
      );
    }
  }

  function changeFallbackAdapter(adapter: 'mock' | 'real') {
    setConnection(null);
    setConnectionError(null);
    setStorageError(null);
    setSaved(false);
    try {
      updateSettings({
        ...settings,
        fallbackAdapter: adapter,
        ...(settings.adapter === 'demo' ? {} : { adapter }),
      });
    } catch (error) {
      setStorageError(
        error instanceof Error ? error.message : 'Settings could not be saved in this browser.',
      );
    }
  }

  return (
    <>
      <button
        aria-expanded={isOpen}
        aria-label="Open settings"
        className="nav-link flex min-h-11 min-w-11 items-center justify-center gap-2"
        onClick={() => setIsOpen(true)}
        type="button"
      >
        <Settings aria-hidden="true" size={19} />
        <span className="hidden sm:inline">Settings</span>
      </button>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
          <button
            aria-label="Close settings"
            className="absolute inset-0 bg-navy/40"
            onClick={() => setIsOpen(false)}
            type="button"
          />
          <aside
            aria-labelledby="settings-title"
            aria-modal="true"
            className="relative z-10 h-full w-full max-w-md overflow-y-auto bg-misty p-6 text-navy shadow-xl"
            role="dialog"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="eyebrow">Mirage</p>
                <h2 className="mt-2 font-serif text-3xl" id="settings-title">
                  Settings
                </h2>
              </div>
              <button
                className="text-link min-h-11 px-3"
                onClick={() => setIsOpen(false)}
                type="button"
              >
                Close
              </button>
            </div>

            <form className="mt-8 space-y-4" onSubmit={testConnection}>
              <label className="block">
                <span className="font-semibold">API base URL</span>
                <span className="mt-1 block text-sm text-muted">
                  Paste the backend or tunnel URL. Changes apply without reloading.
                </span>
                <input
                  autoComplete="url"
                  className="mt-3 h-12 w-full rounded border border-peri bg-white px-3 text-navy"
                  inputMode="url"
                  onChange={(event) => setApiBaseUrl(event.currentTarget.value)}
                  placeholder="https://your-api.example.com"
                  type="text"
                  value={apiBaseUrl}
                />
              </label>

              <button
                className="min-h-12 w-full border border-peri px-4 font-semibold text-navy"
                onClick={() => {
                  setConnectionError(null);
                  setConnection(null);
                  saveApiBaseUrl();
                }}
                type="button"
              >
                Save API URL
              </button>
              <button
                className="primary-button min-h-12 w-full disabled:opacity-60"
                disabled={testing}
                type="submit"
              >
                {testing ? 'Testing…' : 'Test connection'}
              </button>
            </form>

            <section className="mt-8 border-t border-lavender pt-6">
              <label className="block">
                <span className="font-semibold">Backend adapter when Demo Mode is off</span>
                <select
                  className="mt-3 h-12 w-full rounded border border-peri bg-white px-3 text-navy"
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    if (value === 'mock' || value === 'real') changeFallbackAdapter(value);
                  }}
                  value={settings.fallbackAdapter}
                >
                  <option value="real">Real backend</option>
                  <option value="mock">Local mock adapter</option>
                </select>
              </label>
              <label className="flex items-start justify-between gap-4">
                <span>
                  <span className="block font-semibold">Demo Mode</span>
                  <span className="mt-1 block text-sm leading-6 text-muted">
                    Use pre-computed sample results instead of the selected backend adapter.
                  </span>
                </span>
                <input
                  aria-label="Demo Mode"
                  checked={settings.adapter === 'demo'}
                  className="mt-1 h-5 w-5 accent-peri"
                  onChange={(event) => toggleDemoMode(event.currentTarget.checked)}
                  type="checkbox"
                />
              </label>
              <p className="mt-4 text-sm text-muted">
                Active adapter: <strong className="text-navy">{getAdapter()}</strong>
              </p>
            </section>

            {saved && (
              <p className="mt-4 text-sm text-protected" role="status">
                API URL saved.
              </p>
            )}
            {connection && (
              <div className="mt-6 bg-white p-4 text-sm" role="status">
                <p className="font-semibold">Connection successful</p>
                <p className="mt-2">Server mode: {connection.mode}</p>
                <p>Simulator: {connection.simulator_enabled ? 'enabled' : 'disabled'}</p>
              </div>
            )}
            {connectionError && (
              <p className="mt-6 bg-lavender px-4 py-3 text-sm text-navy" role="alert">
                {connectionError}
              </p>
            )}
            {storageError && (
              <p className="mt-4 bg-lavender px-4 py-3 text-sm text-navy" role="alert">
                {storageError}
              </p>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
