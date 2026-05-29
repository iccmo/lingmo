import { useState, useEffect, useCallback } from 'react';

export function useFocusMode() {
  const [isFocused, setIsFocused] = useState(false);

  const enterFocus = useCallback(() => {
    setIsFocused(true);
    document.body.classList.add('focus-mode');
  }, []);

  const exitFocus = useCallback(() => {
    setIsFocused(false);
    document.body.classList.remove('focus-mode');
  }, []);

  const toggleFocus = useCallback(() => {
    if (isFocused) {
      exitFocus();
    } else {
      enterFocus();
    }
  }, [isFocused, enterFocus, exitFocus]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'F11') {
        e.preventDefault();
        toggleFocus();
      }
      if (e.key === 'Escape' && isFocused) {
        exitFocus();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isFocused, toggleFocus, exitFocus]);

  return {
    isFocused,
    enterFocus,
    exitFocus,
    toggleFocus,
  };
}
