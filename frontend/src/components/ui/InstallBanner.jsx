import { useState, useEffect } from 'react';
import { usePWA } from '../../hooks/usePWA';

const DISMISSED_KEY = 'pwa-install-dismissed';

export default function InstallBanner() {
  const { installable, installed, updateAvailable, promptInstall, dismissUpdate, applyUpdate } = usePWA();
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISSED_KEY) === 'true');

  useEffect(() => {
    if (dismissed) localStorage.setItem(DISMISSED_KEY, 'true');
  }, [dismissed]);

  if (dismissed && !updateAvailable && !installed) return null;
  if (!installable && !installed && !updateAvailable) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50">
      {updateAvailable && (
        <div className="flex items-center gap-4 bg-white border border-gray-200 rounded-xl shadow-lg px-5 py-3">
          <span className="text-sm text-gray-700">A new version is available</span>
          <button
            onClick={applyUpdate}
            className="text-sm font-medium bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Update
          </button>
          <button
            onClick={dismissUpdate}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Dismiss
          </button>
        </div>
      )}
      {installable && !updateAvailable && (
        <div className="flex items-center gap-4 bg-white border border-gray-200 rounded-xl shadow-lg px-5 py-3">
          <span className="text-sm text-gray-700">Install the app for quick access</span>
          <button
            onClick={() => { promptInstall(); setDismissed(true); }}
            className="text-sm font-medium bg-green-700 text-white px-4 py-1.5 rounded-lg hover:bg-green-800 transition-colors"
          >
            Install
          </button>
          <button
            onClick={() => setDismissed(true)}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Dismiss
          </button>
        </div>
      )}
      {installed && !updateAvailable && !installable && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-2">
          <p className="text-sm text-green-700">App installed successfully</p>
        </div>
      )}
    </div>
  );
}
