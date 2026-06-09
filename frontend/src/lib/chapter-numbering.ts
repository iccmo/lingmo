import type { ChapterMeta } from 'src/types';

export function getNextWritableChapterNumber(chapters: ChapterMeta[] = []): number {
  const generatedNumbers = chapters
    .filter((chapter) => (chapter.word_count || 0) > 0)
    .map((chapter) => chapter.number || 0);

  return Math.max(0, ...generatedNumbers) + 1;
}
