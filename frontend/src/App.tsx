import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { Toaster } from 'src/components/ui/sonner';
import { Header } from 'src/components/layout/Header';
import { Sidebar } from 'src/components/layout/Sidebar';
import { Dashboard } from 'src/pages/Dashboard';
import { NovelDetail } from 'src/pages/NovelDetail';
import { Settings } from 'src/pages/Settings';
import { Logs } from 'src/pages/Logs';
import { MemoryBank } from 'src/pages/MemoryBank';
import { Editor } from 'src/pages/Editor';
import { WorldEditor } from 'src/pages/WorldEditor';
import { Outline } from 'src/pages/Outline';
import { Foreshadowing } from 'src/pages/Foreshadowing';
import { Stats } from 'src/pages/Stats';
import { Showcase } from 'src/pages/Showcase';
import { CommandPalette } from 'src/components/ui/command-palette';
import { ErrorBoundary } from 'src/components/ui/error-boundary';
import { ShortcutsSheet } from 'src/components/ui/shortcuts-sheet';
import { QuickActions } from 'src/components/ui/quick-actions';
import { TopLoader } from 'src/components/ui/top-loader';
import type { AppMode } from 'src/types';

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
      <span className="text-[10px] text-ink-subtle">Novel Workshop · AI 写作引擎</span>
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
          <Sidebar onNovelSelect={() => { if (window.innerWidth < 1024) toggleSidebar(); }} />
        </div>
        <main className="flex-1 overflow-y-auto px-6 py-6 sm:px-8 lg:px-12 lg:py-10" id="main-content">
          <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Dashboard />} />
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
          </ErrorBoundary>
        </main>
      </div>
      <Footer />
      <CommandPalette />
      <ShortcutsSheet />
      <QuickActions />
      <Toaster duration={3000} />
    </div>
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
    const next = !dark;
    setDark(next);
    localStorage.setItem('dark', String(next));
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
      if (localStorage.getItem('dark') === null) setDark(e.matches);
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
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
