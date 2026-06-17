import { useEffect, useRef } from 'react';

export default function useAutoRefresh(callback) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    const handler = () => {
      if (typeof savedCallback.current === 'function') {
        savedCallback.current();
      }
    };
    
    // Listen to the custom event emitted by api.js
    window.addEventListener('appDataMutation', handler);
    return () => window.removeEventListener('appDataMutation', handler);
  }, []);
}
