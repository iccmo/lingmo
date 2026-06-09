import { render, screen, waitFor } from '@testing-library/react';
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

test('shows global module sections', () => {
  renderSidebar();
  expect(screen.getByText('导航')).toBeInTheDocument();
  expect(screen.getByText('小说')).toBeInTheDocument();
  expect(screen.getByText('听书')).toBeInTheDocument();
});

test('shows global nav items', () => {
  renderSidebar();
  expect(screen.getByText('设置')).toBeInTheDocument();
  expect(screen.getByText('日志')).toBeInTheDocument();
  expect(screen.getByText('统计')).toBeInTheDocument();
});

test('does not render novel links when the list is empty', async () => {
  renderSidebar();
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByText(/章$/)).not.toBeInTheDocument();
});
