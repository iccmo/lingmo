import { useState, useCallback } from 'react';

export type PaperType = 'none' | 'parchment' | 'xuan' | 'grid' | 'lined';

export function usePaperTexture() {
  const [paperType, setPaperType] = useState<PaperType>(() => {
    return (localStorage.getItem('lingmo-paper-texture') as PaperType) || 'none';
  });

  const cyclePaper = useCallback(() => {
    const types: PaperType[] = ['none', 'parchment', 'xuan', 'grid', 'lined'];
    const idx = types.indexOf(paperType);
    const next = types[(idx + 1) % types.length];
    setPaperType(next);
    localStorage.setItem('lingmo-paper-texture', next);
  }, [paperType]);

  return { paperType, setPaperType, cyclePaper };
}
