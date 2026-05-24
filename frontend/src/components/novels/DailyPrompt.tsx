import { useEffect, useState } from 'react';

const PROMPTS = [
  { emoji: '💡', text: '今天的章节，尝试让反派做一件完全出乎读者意料的事', tip: '反派出人意料' },
  { emoji: '🎭', text: '让两个角色在对话中各怀秘密——读者知道一个，但不知道另一个', tip: '双重秘密' },
  { emoji: '🪞', text: '今天的主角，在一件小事上暴露出与平时完全不同的一面', tip: '人物反差' },
  { emoji: '⏳', text: '在章节结尾，让读者意识到前面某段看似普通的描写其实是关键伏笔', tip: '延迟揭示' },
  { emoji: '🌧️', text: '用环境描写暗示情绪——不要直接说"他很悲伤"，让天气替他说话', tip: '环境暗示' },
  { emoji: '🔗', text: '让一个之前出现过的配角带着新信息重新登场，推动剧情', tip: '配角复用' },
  { emoji: '🎯', text: '今天的章节只做一件事：加深读者对主角处境的理解和共情', tip: '深度共情' },
  { emoji: '⚡', text: '把最重要的信息放在章节最后三句话——让读者必须点下一章', tip: '钩子后置' },
  { emoji: '🕯️', text: '写一段没有对话的场景，纯粹用动作和细节推进剧情', tip: '无声叙事' },
  { emoji: '🎪', text: '制造一个"两难选择"——主角无论怎么选都会付出代价', tip: '两难抉择' },
  { emoji: '🪜', text: '把本章的高潮提前到中间，后半段写高潮的余波和角色的反应', tip: '高潮前置' },
  { emoji: '🎨', text: '用五种感官中的至少三种来描写一个关键场景', tip: '感官描写' },
];

export function DailyPrompt() {
  const [prompt, setPrompt] = useState(PROMPTS[0]);

  useEffect(() => {
    // Pick based on day of year for consistency within a day
    const now = new Date();
    const dayOfYear = Math.floor((now.getTime() - new Date(now.getFullYear(), 0, 0).getTime()) / 86400000);
    setPrompt(PROMPTS[dayOfYear % PROMPTS.length]);
  }, []);

  return (
    <div className="mb-6 p-3 bg-gradient-to-r from-accent-soft/50 to-transparent border border-accent/10 rounded-lg">
      <div className="flex items-center gap-2">
        <span className="text-sm">{prompt.emoji}</span>
        <div className="flex-1">
          <p className="text-xs text-ink leading-relaxed">{prompt.text}</p>
        </div>
        <span className="text-[10px] text-accent bg-accent-soft px-1.5 py-0.5 rounded-full shrink-0">
          {prompt.tip}
        </span>
      </div>
    </div>
  );
}
