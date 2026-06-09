import { describe, expect, it } from 'vitest';
import type { ChapterMeta } from 'src/types';
import { getNextWritableChapterNumber } from './chapter-numbering';

function chapter(number: number, wordCount: number): ChapterMeta {
  return {
    number,
    title: `第${number}章`,
    word_count: wordCount,
    summary: '',
    ending_hook: '',
    generated_at: '2026-06-05T00:00:00Z',
  };
}

describe('getNextWritableChapterNumber', () => {
  it('appends after the latest generated chapter number even when placeholders fill a gap', () => {
    expect(getNextWritableChapterNumber([
      chapter(1, 1200),
      chapter(2, 0),
      chapter(3, 1400),
    ])).toBe(4);
  });

  it('returns 1 when there are no generated chapters', () => {
    expect(getNextWritableChapterNumber([chapter(1, 0)])).toBe(1);
  });
});
