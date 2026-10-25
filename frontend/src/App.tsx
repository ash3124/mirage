import { useEffect, useState, useSyncExternalStore } from 'react';
import { BrowserRouter, NavLink } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import { getSettings, subscribeSettings } from './state/settings';
import DemoBanner from './components/DemoBanner';
import OfflineNotice from './components/OfflineNotice';
import SettingsDrawer from './components/SettingsDrawer';
import { links } from './data/links';
import { AppRoutes } from './routes';

export default function App() {
  const settings = useSyncExternalStore(subscribeSettings, getSettings, getSettings);
  const [darkMode, setDarkMode] = useState(
    () => localStorage.getItem('mirage-theme') === 'dark',
  );
  const recordingMode = new URLSearchParams(window.location.search).get('record') === '1';
  const demoMode = settings.adapter === 'demo';

  useEffect(() => {
    localStorage.setItem('mirage-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  return (
    <BrowserRouter>
      <div
        className={`min-h-screen bg-misty text-navy${recordingMode ? ' recording-mode' : ''}${
          darkMode ? ' theme-dark' : ''
        }`}
      >
        {demoMode && !recordingMode && <DemoBanner />}
        <OfflineNotice />
        <header className="bg-navy text-misty">
          <nav className="mx-auto flex h-16 max-w-[1184px] items-center justify-between px-5 md:h-[76px] md:px-8">
            <NavLink className="font-serif text-[28px] font-semibold" to="/">
              Mirage
            </NavLink>
            <div className="flex items-center gap-6 text-sm md:text-base">
              <NavLink className="nav-link" to="/studio">
                Protect
              </NavLink>
              <NavLink className="nav-link hidden sm:inline" to="/safety-kit">
                Safety Kit
              </NavLink>
              <NavLink className="nav-link hidden sm:inline" to="/privacy">
                Privacy
              </NavLink>
              <button
                aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                className="theme-toggle"
                onClick={() => setDarkMode((current) => !current)}
                title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                type="button"
              >
                {darkMode ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
              </button>
              {!recordingMode && <SettingsDrawer />}
            </div>
          </nav>
        </header>
        <AppRoutes />
        <footer className="border-t border-lavender px-5 py-8 text-sm text-navy">
          <div className="mx-auto flex max-w-[1120px] flex-wrap gap-x-6 gap-y-3">
            <NavLink className="text-link" to="/privacy">Privacy</NavLink>
            <NavLink className="text-link" to="/safety-kit">Safety Kit</NavLink>
            {links.github && (
              <a className="text-link" href={links.github} rel="noreferrer" target="_blank">
                GitHub
              </a>
            )}
            {links.colab && (
              <a className="text-link" href={links.colab} rel="noreferrer" target="_blank">
                Open in Colab
              </a>
            )}
            {links.demoVideo && (
              <a className="text-link" href={links.demoVideo} rel="noreferrer" target="_blank">
                Watch the demo video
              </a>
            )}
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
}
