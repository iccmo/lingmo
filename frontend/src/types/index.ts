export interface NovelSummary {
  id: string;
  title: string;
  author: string;
  genre: string;
  synopsis: string;
  total_chapters: number;
  total_words: number;
  latest_chapter: { number: number; title: string; generated_at: string } | null;
}

export interface ChapterMeta {
  number: number;
  title: string;
  word_count: number;
  summary: string;
  ending_hook: string;
  quality_score?: number;
  model_used?: string;
  generated_at: string;
}

export interface NovelDetail extends NovelSummary {
  chapters: ChapterMeta[];
  world: { name: string; era: string; power_system: string };
}

export interface DraftOption {
  id: string;
  title: string;
  direction: string;
  preview: string;
  hook: string;
}

export interface SystemStatus {
  novels_count: number;
  total_chapters: number;
  total_words: number;
  server_time: string;
}

export interface PublishResult {
  success: boolean;
  platform: string;
  chapter_number: number;
  url?: string;
  error?: string;
}

export type AppMode = 'auto' | 'creator';
