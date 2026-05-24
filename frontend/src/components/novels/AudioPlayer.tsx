import { useAudio, type PlaylistItem } from 'src/lib/AudioContext';

/**
 * AudioPlayer component — replaced by the global MiniPlayer + ListenPage.
 * Kept as a thin wrapper for backward compatibility with existing imports.
 * The sidebar "🎧 听书" link is now the primary entry point.
 */
export function AudioPlayer() {
  return null;
}

/** Hook for chapter list integration — add chapters to playlist from anywhere. */
export function useAddToPlaylist() {
  const { addToPlaylist, playChapter } = useAudio();

  return (
    novelId: string,
    novelTitle: string,
    ch: { number: number; title: string; word_count: number },
    playNow = false,
  ) => {
    const item: PlaylistItem = {
      novelId,
      novelTitle,
      chapterNum: ch.number,
      chapterTitle: ch.title,
    };
    addToPlaylist(item);
    if (playNow) playChapter(item);
  };
}
