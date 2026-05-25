import { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Toaster } from 'src/components/ui/sonner';
import { Header } from 'src/components/layout/Header';
import { Sidebar } from 'src/components/layout/Sidebar';
import { Dashboard } from 'src/pages/Dashboard';
import { Showcase } from 'src/pages/Showcase';
import { CommandPalette } from 'src/components/ui/command-palette';
import { ErrorBoundary } from 'src/components/ui/error-boundary';
import { ShortcutsSheet } from 'src/components/ui/shortcuts-sheet';
import { QuickActions } from 'src/components/ui/quick-actions';
import { TopLoader } from 'src/components/ui/top-loader';
import { AudioProvider } from 'src/lib/AudioContext';
import { MiniPlayer } from 'src/components/novels/MiniPlayer';
import type { AppMode } from 'src/types';

// Lazy-loaded routes
const NovelDetail = lazy(() => import('src/pages/NovelDetail').then(m => ({ default: m.NovelDetail })));
const Settings = lazy(() => import('src/pages/Settings').then(m => ({ default: m.Settings })));
const Logs = lazy(() => import('src/pages/Logs').then(m => ({ default: m.Logs })));
const MemoryBank = lazy(() => import('src/pages/MemoryBank').then(m => ({ default: m.MemoryBank })));
const Editor = lazy(() => import('src/pages/Editor').then(m => ({ default: m.Editor })));
const WorldEditor = lazy(() => import('src/pages/WorldEditor').then(m => ({ default: m.WorldEditor })));
const Outline = lazy(() => import('src/pages/Outline').then(m => ({ default: m.Outline })));
const Foreshadowing = lazy(() => import('src/pages/Foreshadowing').then(m => ({ default: m.Foreshadowing })));
const Stats = lazy(() => import('src/pages/Stats').then(m => ({ default: m.Stats })));
const ListenPage = lazy(() => import('src/pages/ListenPage').then(m => ({ default: m.ListenPage })));

function PageLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="skeleton h-8 w-40 rounded" />
    </div>
  );
}

function Footer() {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const r = await fetch('/api/status');
        if (!cancelled) setOnline(r.ok);
      } catch {
        if (!cancelled) setOnline(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  return (
    <footer className="h-8 bg-card/50 border-t border-border flex items-center justify-between px-4 shrink-0">
      <span className="text-[10px] text-ink-subtle">灵墨 · AI 创作伴侣</span>
      <span className="flex items-center gap-1.5 text-[10px] text-ink-subtle">
        <span className={`relative flex h-1.5 w-1.5 ${online ? '' : 'opacity-40'}`}>
          {online ? (
            <>
              <span className="animate-pulse absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
            </>
          ) : (
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-zinc-400" />
          )}
        </span>
        {online ? '已连接' : '离线'}
      </span>
    </footer>
  );
}

function AppLayout({ mode, setMode, dark, toggleDark, sidebarOpen, toggleSidebar }: {
  mode: AppMode;
  setMode: (m: AppMode) => void;
  dark: boolean;
  toggleDark: () => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}) {
  return (
    <AudioProvider>
    <div className="h-screen flex flex-col font-[family-name:var(--font-ui)] bg-paper">
      <TopLoader />
      <Header mode={mode} onModeChange={setMode} dark={dark} onDarkToggle={toggleDark}
        sidebarOpen={sidebarOpen} onSidebarToggle={toggleSidebar} />
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 lg:hidden" onClick={toggleSidebar} />
      )}
      <div className="flex flex-1 overflow-hidden">
        <div className={`shrink-0 overflow-hidden transition-all duration-300 ease-in-out
          lg:relative ${sidebarOpen ? 'fixed inset-y-0 left-0 z-50 lg:static' : ''}
          ${sidebarOpen ? 'w-[200px] min-w-[200px]' : 'w-0 min-w-0'}`}>
          <Sidebar onNovelSelect={() => { if (window.innerWidth < 1024) toggleSidebar(); }} onClose={toggleSidebar} />
        </div>
        <main className="flex-1 overflow-y-auto px-3 py-4 sm:px-6 sm:py-6 md:px-8 lg:px-12 lg:py-10" id="main-content">
          <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/listen" element={<ListenPage />} />
            <Route path="/novels/:id" element={<NovelDetail mode={mode} />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/novels/:id/memory" element={<MemoryBank />} />
            <Route path="/novels/:id/edit" element={<Editor />} />
            <Route path="/novels/:id/world" element={<WorldEditor />} />
            <Route path="/novels/:id/outline" element={<Outline />} />
            <Route path="/novels/:id/foreshadowing" element={<Foreshadowing />} />
          </Routes>
          </Suspense>
          </ErrorBoundary>
        </main>
      </div>
      <Footer />
      <MiniPlayer />
      <CommandPalette />
      <ShortcutsSheet />
      <QuickActions />
      <Toaster duration={3000} />
    </div>
    </AudioProvider>
  );
}

function AppContent() {
  const location = useLocation();
  const [mode, setMode] = useState<AppMode>('creator');
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('dark');
    if (saved !== null) return saved === 'true';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  const [sidebarOpen, setSidebarOpen] = useState(() => localStorage.getItem('sidebar') !== 'false');
  const [entered, setEntered] = useState(() => sessionStorage.getItem('session') === 'active');

  function toggleDark() {
    const saved = localStorage.getItem('dark');
    if (saved === null || saved === 'false') {
      // light → dark
      setDark(true);
      localStorage.setItem('dark', 'true');
    } else if (saved === 'true') {
      // dark → auto
      setDark(window.matchMedia('(prefers-color-scheme: dark)').matches);
      localStorage.setItem('dark', 'auto');
    } else {
      // auto → light
      setDark(false);
      localStorage.setItem('dark', 'false');
    }
  }
  function toggleSidebar() {
    const next = !sidebarOpen;
    setSidebarOpen(next);
    localStorage.setItem('sidebar', String(next));
  }
  function handleEnter() {
    setEntered(true);
    localStorage.setItem('entered', 'true');
  }

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      const saved = localStorage.getItem('dark');
      if (saved === null || saved === 'auto') setDark(e.matches);
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Load settings from server DB on mount (merge with localStorage, server wins)
  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(data => {
      if (data && typeof data === 'object') {
        Object.entries(data).forEach(([k, v]) => {
          if (!localStorage.getItem(k) && v) {
            localStorage.setItem(k, v as string);
          }
        });
        // Apply dark mode from server if available
        if (data.dark === 'true' && !dark) setDark(true);
        if (data.dark === 'false' && dark) setDark(false);
      }
    }).catch(() => {});
  }, []);

  // Periodic settings sync to server
  useEffect(() => {
    const sync = () => {
      const settings: Record<string, string> = {};
      ['dark', 'tts-voice', 'audio-volume', 'audio-autocontinue', 'audio-playmode', 'audio-eq', 'sidebar'].forEach(k => {
        const v = localStorage.getItem(k);
        if (v) settings[k] = v;
      });
      fetch('/api/settings/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      }).catch(() => {});
    };
    sync();
    const interval = setInterval(sync, 60000);
    return () => clearInterval(interval);
  }, []);

  // Showcase at /showcase or / (landing page when not entered)
  if (location.pathname === '/showcase' || (location.pathname === '/' && !entered)) {
    return <Showcase onEnter={handleEnter} />;
  }

  return (
    <AppLayout mode={mode} setMode={setMode} dark={dark} toggleDark={toggleDark}
      sidebarOpen={sidebarOpen} toggleSidebar={toggleSidebar} />
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
