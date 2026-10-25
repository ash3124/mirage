import { useEffect, useState } from 'react';

export default function OfflineNotice() {
  const [offline, setOffline] = useState(
    () => typeof navigator !== 'undefined' && !navigator.onLine,
  );

  useEffect(() => {
    const handleOnline = () => setOffline(false);
    const handleOffline = () => setOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (!offline) return null;
  return (
    <aside
      className="bg-lavender px-5 py-3 text-center text-sm leading-6 text-navy"
      role="status"
    >
      You&apos;re offline. Online protection and live comparisons need a connection; the Safety Kit
      remains available on this device.
    </aside>
  );
}
