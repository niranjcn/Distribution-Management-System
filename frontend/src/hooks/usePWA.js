import { useState, useEffect, useCallback, useRef } from 'react';

let _deferredPrompt = null;

export function usePWA() {
  const [installable, setInstallable] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [registrationError, setRegistrationError] = useState(null);
  const waitingSwRef = useRef(null);

  const promptInstall = useCallback(async () => {
    if (!_deferredPrompt) return;
    _deferredPrompt.prompt();
    const result = await _deferredPrompt.userChoice;
    if (result.outcome === 'accepted') {
      setInstalled(true);
    }
    _deferredPrompt = null;
    setInstallable(false);
  }, []);

  const dismissUpdate = useCallback(() => {
    setUpdateAvailable(false);
    waitingSwRef.current = null;
  }, []);

  const applyUpdate = useCallback(() => {
    const sw = waitingSwRef.current;
    if (sw) {
      sw.postMessage({ type: 'SKIP_WAITING' });
      waitingSwRef.current = null;
    }
    window.location.reload();
  }, []);

  useEffect(() => {
    const handleBeforeInstall = (e) => {
      e.preventDefault();
      _deferredPrompt = e;
      setInstallable(true);
    };

    const handleAppInstalled = () => {
      setInstalled(true);
      setInstallable(false);
      _deferredPrompt = null;
    };

    const handleSWUpdated = (e) => {
      waitingSwRef.current = e.detail?.sw || null;
      setUpdateAvailable(true);
    };

    const handleSWRegistrationError = (err) => {
      setRegistrationError(err?.message || 'Service worker registration failed');
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    window.addEventListener('appinstalled', handleAppInstalled);
    window.addEventListener('sw-updated', handleSWUpdated);
    window.addEventListener('sw-registration-error', handleSWRegistrationError);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleAppInstalled);
      window.removeEventListener('sw-updated', handleSWUpdated);
      window.removeEventListener('sw-registration-error', handleSWRegistrationError);
    };
  }, []);

  return { installable, installed, updateAvailable, registrationError, promptInstall, dismissUpdate, applyUpdate };
}
