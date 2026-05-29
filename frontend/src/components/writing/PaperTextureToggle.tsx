import { FileText } from 'lucide-react';
import { usePaperTexture, type PaperType } from 'src/hooks/usePaperTexture';

const labels: Record<PaperType, string> = {
  none: '无纹理',
  parchment: '羊皮纸',
  xuan: '宣纸',
  grid: '方格纸',
  lined: '横线纸',
};

export function PaperTextureToggle() {
  const { paperType, cyclePaper } = usePaperTexture();

  return (
    <button
      onClick={cyclePaper}
      className="flex items-center gap-1.5 px-2 py-1.5 text-sm
                 text-text-muted hover:text-text-primary
                 hover:bg-bg-surface rounded-md transition-colors"
      title={`纸张: ${labels[paperType]} · 点击切换`}
    >
      <FileText size={14} />
    </button>
  );
}
