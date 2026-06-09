import { describe, expect, it } from 'vitest';
import { buildGenerateDirection } from './GenerateDialog';

describe('buildGenerateDirection', () => {
  it('preserves memory injection and creative risk around the chapter direction', () => {
    const direction = buildGenerateDirection('主角拍下古鼎后被伏击', '雨打在铁皮屋顶上的声音', true);

    expect(direction).toContain('【打破常规模式】');
    expect(direction).toContain('读者完全意想不到');
    expect(direction).toContain('【记忆注入】');
    expect(direction).toContain('雨打在铁皮屋顶上的声音');
    expect(direction).toContain('主角拍下古鼎后被伏击');
  });

  it('keeps memory injection even when auto-conceiving without a direction', () => {
    const direction = buildGenerateDirection('', '外婆红烧肉的味道', false);

    expect(direction).toContain('【记忆注入】');
    expect(direction).toContain('外婆红烧肉的味道');
  });
});
