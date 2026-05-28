import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { BrowserRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';

// Mock fetch so api.novels.list() doesn't hit a real server
beforeEach(() => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify([]), { status: 200 }),
  );
});
afterEach(() => {
  vi.restoreAllMocks();
});

function renderSidebar() {
  return render(
    <BrowserRouter>
      <Sidebar />
    </BrowserRouter>,
  );
}

test('renders sidebar without crashing', () => {
  renderSidebar();
  expect(screen.getByText('工作台')).toBeInTheDocument();
});

test('shows all four module sections', () => {
  renderSidebar();
  expect(screen.getByText('导航')).toBeInTheDocument();
  expect(screen.getByText('小说')).toBeInTheDocument();
  expect(screen.getByText('听书')).toBeInTheDocument();
  expect(screen.getByText('短剧')).toBeInTheDocument();
});

test('shows global nav items', () => {
  renderSidebar();
  expect(screen.getByText('设置')).toBeInTheDocument();
  expect(screen.getByText('日志')).toBeInTheDocument();
  expect(screen.getByText('统计')).toBeInTheDocument();
});

test('shows placeholder when no novel selected for drama module', () => {
  renderSidebar();
  expect(screen.getByText('选择小说后可用')).toBeInTheDocument();
});
