import { useState, useCallback } from 'react';

export function useTypewriter() {
  const [enabled, setEnabled] = useState(() => {
    return localStorage.getItem('lingmo-typewriter-mode') === 'true';
  });

  const toggle = useCallback(() => {
    setEnabled(prev => {
      const next = !prev;
      localStorage.setItem('lingmo-typewriter-mode', String(next));
      return next;
    });
  }, []);

  return { enabled, toggle };
}
