import { useState } from 'react';
import { VisualBiblePanel } from './VisualBiblePanel';
import { StoryboardPanel } from './StoryboardPanel';
import { ProducePanel } from './ProducePanel';

interface Props {
  novelId: string;
  chapters?: { number: number; title: string }[];
}

const SUB_TABS = [
  { key: 'visual', label: '视觉圣经' },
  { key: 'storyboard', label: '分镜脚本' },
  { key: 'produce', label: '制片' },
];

export function FilmStudioTab({ novelId, chapters = [] }: Props) {
  const [subTab, setSubTab] = useState('visual');

  return (
    <div className="space-y-4">
      {/* Sub-tab bar */}
      <div className="flex gap-1 p-1 bg-paper border border-border rounded-lg">
        {SUB_TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setSubTab(tab.key)}
            className={`flex-1 py-2 text-xs font-medium rounded-md transition-all ${
              subTab === tab.key
                ? 'bg-accent text-white shadow-sm'
                : 'text-ink-muted hover:text-ink hover:bg-card'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      <div className="animate-[fadeSlideIn_0.2s_ease-out]">
        {subTab === 'visual' && <VisualBiblePanel novelId={novelId} />}
        {subTab === 'storyboard' && <StoryboardPanel novelId={novelId} chapters={chapters} />}
        {subTab === 'produce' && <ProducePanel novelId={novelId} chapters={chapters} />}
      </div>
    </div>
  );
}
