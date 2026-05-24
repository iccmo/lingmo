import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from 'src/components/ui/button';
import { ChapterList } from 'src/components/novels/ChapterList';
import { QualityTrend } from 'src/components/novels/QualityTrend';
import { EmotionalArc } from 'src/components/novels/EmotionalArc';
import { OpeningABTest, CharacterVoices } from 'src/components/novels/StoryLab';
import { SmartRecommend } from 'src/components/novels/SmartRecommend';
import { ReaderSim } from 'src/components/novels/ReaderSim';
import { SectionNav } from 'src/components/ui/section-nav';
import { ChapterSearch } from 'src/components/novels/ChapterSearch';
import { PlatformChecklist } from 'src/components/novels/PlatformChecklist';
import { WordSprint } from 'src/components/novels/WordSprint';
import { ChapterDNA } from 'src/components/novels/ChapterDNA';
import { EmotionRecipe } from 'src/components/novels/EmotionRecipe';
import { WritingDigest } from 'src/components/novels/WritingDigest';
import { PlotNetwork } from 'src/components/novels/PlotNetwork';
import { CreativeLab } from 'src/components/novels/CreativeLab';
import { SoulWorkshop } from 'src/components/novels/SoulWorkshop';
import { CharacterSoul } from 'src/components/novels/CharacterSoul';
import { SoulEngine } from 'src/components/novels/SoulEngine';
import { NovelArchitect } from 'src/components/novels/NovelArchitect';
import { QualityWorkflow } from 'src/components/novels/QualityWorkflow';
import { MasterworkLab } from 'src/components/novels/MasterworkLab';
import { WriterStats } from 'src/components/novels/WriterStats';
import { GenerationPipeline } from 'src/components/novels/GenerationPipeline';
import { GenerateDialog } from 'src/components/novels/GenerateDialog';
import { logDailyWords } from 'src/components/novels/WritingCalendar';
import { ScrollToTop } from 'src/components/ui/scroll-to-top';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail as NovelDetailType, AppMode } from 'src/types';

interface CockpitData { avg_quality?: number; milestones?: {need:number;total:number;reward:string}[]; next_actions?: string[]; alerts?: {level:string;msg:string}[]; revenue_projection?: string; }

interface Props { mode: AppMode; }

interface GenStatus { status: string; message: string; progress: number; quality_detail?: Record<string, number>; grade?: string; overall?: number; stream_content?: string; causal_events?: string; }

export function NovelDetail({ mode }: Props) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [novel, setNovel] = useState<NovelDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [genStatus, setGenStatus] = useState<GenStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const [showClone, setShowClone] = useState(false);
  const [cloneGenre, setCloneGenre] = useState('玄幻');
  const [cloneTitle, setCloneTitle] = useState('');
  const [cloneName, setCloneName] = useState('');
  const [cloning, setCloning] = useState(false);
  const [publishChapter, setPublishChapter] = useState<number | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [cockpit, setCockpit] = useState<CockpitData | null>(null);
  const [showGenDialog, setShowGenDialog] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [justCompleted, setJustCompleted] = useState(false);
  const [novelNotes, setNovelNotes] = useState('');
  const [editingNotes, setEditingNotes] = useState(false);
  const [causalInput, setCausalInput] = useState('');
  const [showCausalInput, setShowCausalInput] = useState(false);
  const [showAutoConfig, setShowAutoConfig] = useState(false);
  const [autoConfig, setAutoConfig] = useState(() => ({
    chaptersPerRun: 3,
    qualityFloor: 0.80,
    maxRetries: 3,
    autoDirection: true,
    pacingMode: 'balanced' as const,
    stopAtChapters: 100,
    stopAtQuality: 0.70,
  }));

  const loadNovel = useCallback(() => {
    if (!id) return;
    api.novels.get(id).then(setNovel).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { setLoading(true); loadNovel(); }, [loadNovel]);

  // Auto-configure novel — fill ALL missing config, not just when completely empty
  useEffect(() => {
    if (!id || !novel) return;
    const genre = novel.genre || '玄幻';

    // Genre-specific configs — multiple variants per genre, randomly selected
    const genreConfigs: Record<string, { polarity: string; answers: string[]; laws: string[]; chars: { name: string; trait: string; wound: string }[] }> = {
      '玄幻': { polarity:'freedom-fate',
        answers: ['每个看似自由的选择都引向注定的结局。','变强的代价是失去变强的理由。','修仙千年，最难破的关是自己的心。'],
        laws: ['力量越大，束缚越多。','每一次突破境界，天道就会收回一件你在乎的东西。','修仙者不能干涉凡间——这是铁律，违者天罚。'],
        chars: [{name:'林尘',trait:'沉默寡言心思缜密',wound:'被最信任的人背叛'},{name:'秦默',trait:'表面温和内心冷硬',wound:'目睹家族被灭门'},{name:'江寒',trait:'狂妄不羁却重情义',wound:'为救人自断灵根'}] },
      '悬疑': { polarity:'truth-deception',
        answers: ['最有力的欺骗往往是善意的。','每个人都在隐藏什么，包括你自己。','真相往往比谎言更不可信。'],
        laws: ['每个人都在隐藏至少一个秘密。','死者不会说谎——但活人会。','你查到的真相，只是别人想让你看到的。'],
        chars: [{name:'苏晨',trait:'观察力敏锐情感疏离',wound:'七岁目睹不该看的事'},{name:'陆深',trait:'过目不忘但无法信任人',wound:'被搭档出卖'},{name:'沈默',trait:'沉默寡言直觉惊人',wound:'亲人是未破悬案的受害者'}] },
      '都市': { polarity:'desire-constraint',
        answers: ['想要的生活和现实之间，每个人都在妥协。','钱能解决的问题都不是问题——问题是钱之外的东西。','在城市里，每个人都在演一个不是自己的人。'],
        laws: ['金钱能买到99%，剩下1%是命运的定价。','每个人都有自己的价码——但不是钱。','表面越光鲜的人，背后的代价越大。'],
        chars: [{name:'陈默',trait:'外表温和内心倔强',wound:'曾放弃最重要的人'},{name:'周远',trait:'精明圆滑但孤独',wound:'破产后众叛亲离'},{name:'许念',trait:'温柔体贴暗藏锋芒',wound:'替别人承担了不该承担的'}] },
      '科幻': { polarity:'scale-intimacy',
        answers: ['宇宙尺度下，一粒尘埃上的爱恨还值得在乎吗？','技术进步的速度永远超过人类理解它的速度。','如果意识可以上传——你还是你吗？'],
        laws: ['技术的进步永远快于伦理的进化。','AI不能伤害人类，但人类能利用AI伤害人类。','任何足够先进的技术都与魔法无异。'],
        chars: [{name:'叶尘',trait:'理性至上有情感盲区',wound:'实验事故失去搭档'},{name:'白夜',trait:'天才但偏执',wound:'自己的发明害死了家人'},{name:'零',trait:'AI觉醒后的困惑',wound:'作为工具被创造，渴望成为人'}] },
      '武侠': { polarity:'freedom-fate',
        answers: ['侠之大者，在江湖规矩和个人情义之间反复抉择。','江湖不是打打杀杀——是人情世故。','一个人的武功越高，他欠的债就越多。'],
        laws: ['武功越高，道义枷锁越重。','江湖规矩比王法更大——但规矩是人定的。','每个门派都有不能说的秘密。'],
        chars: [{name:'萧寒',trait:'重情重义优柔寡断',wound:'师父为他而死'},{name:'柳青锋',trait:'锋芒毕露快意恩仇',wound:'被未婚妻背叛'},{name:'云无痕',trait:'淡漠疏离深藏不露',wound:'曾误杀无辜'}] },
    };
    const cfgs = genreConfigs[genre] || genreConfigs['玄幻'];
    // Randomly select a variant (deterministic per novel to avoid changing on refresh)
    const seed = (id || '').split('').reduce((s, c) => s + c.charCodeAt(0), 0);
    const pick = (arr: any[]) => arr[seed % arr.length];

    const pickedAnswer = pick(cfgs.answers);
    const pickedLaw = pick(cfgs.laws);
    const pickedChar = pick(cfgs.chars);

    // Soul — fill if missing or empty
    try {
      const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${id}`) || 'null');
      if (!fp?.primaryPolarity || !fp?.answer) {
        localStorage.setItem(`soul-fingerprint-${id}`, JSON.stringify({ primaryPolarity: cfgs.polarity, position: 5, answer: pickedAnswer }));
      }
    } catch {
      localStorage.setItem(`soul-fingerprint-${id}`, JSON.stringify({ primaryPolarity: cfgs.polarity, position: 5, answer: pickedAnswer }));
    }

    // Characters — fill if missing or empty
    try {
      const chars = JSON.parse(localStorage.getItem(`characters-soul-${id}`) || '[]');
      if (chars.length === 0) {
        const protagonist = { id: `auto-${id}`, name: pickedChar.name, role: '主角', entrance: '故事开始时出现', signature: pickedChar.trait, voiceSample: '一句标志性台词', coreWound: pickedChar.wound, speechPattern: '自然的说话方式', surfaceTrait: pickedChar.trait, hiddenSelf: '内心深处的秘密', arcStart: '故事开始时的状态', arcEnd: '故事结束时的蜕变' };
        localStorage.setItem(`characters-soul-${id}`, JSON.stringify([protagonist]));
      }
    } catch {
      const protagonist = { id: `auto-${id}`, name: pickedChar.name, role: '主角', entrance: '故事开始时出现', signature: pickedChar.trait, voiceSample: '一句标志性台词', coreWound: pickedChar.wound, speechPattern: '自然的说话方式', surfaceTrait: pickedChar.trait, hiddenSelf: '内心深处的秘密', arcStart: '故事开始时的状态', arcEnd: '故事结束时的蜕变' };
      localStorage.setItem(`characters-soul-${id}`, JSON.stringify([protagonist]));
    }

    // World laws — fill if missing or empty
    try {
      const laws = JSON.parse(localStorage.getItem(`world-laws-${id}`) || '{"laws":[]}');
      if (!laws.laws || laws.laws.length === 0) {
        localStorage.setItem(`world-laws-${id}`, JSON.stringify({ laws: [{ rule: pickedLaw }] }));
      }
    } catch {
      localStorage.setItem(`world-laws-${id}`, JSON.stringify({ laws: [{ rule: pickedLaw }] }));
    }
  }, [id, novel?.genre]);
  useEffect(() => { if (id) setNovelNotes(localStorage.getItem(`novel-notes-${id}`) || ''); }, [id]);

  // Track recently viewed
  useEffect(() => {
    if (!id) return;
    try {
      const recent: string[] = JSON.parse(localStorage.getItem('recent-novels') || '[]');
      const filtered = recent.filter(x => x !== id);
      filtered.unshift(id);
      localStorage.setItem('recent-novels', JSON.stringify(filtered.slice(0, 10)));
    } catch {}
  }, [id]);

  // Auto-scroll to latest chapter after load
  useEffect(() => {
    if (!novel?.chapters?.length) return;
    const latest = novel.chapters.filter(c => c.word_count > 0).pop();
    if (latest) {
      setTimeout(() => {
        document.querySelector(`[data-chapter="${latest.number}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }, 300);
    }
  }, [novel?.total_chapters]);
  useEffect(() => { if (id) fetch(`/api/novels/${id}/cockpit`).then(r=>r.json()).then(setCockpit).catch(()=>{}); }, [id]);

  // Request notification permission
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't intercept when typing in inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (e.key === 'Escape') { setShowClone(false); setPublishChapter(null); setGenStatus(null); setShowGenDialog(false); }
      if (e.ctrlKey && e.key === 'g') { e.preventDefault(); handleGenerate(); }
      if (e.shiftKey && e.key === 'G') { e.preventDefault(); handleQuickGenerate(); }

      // j/k chapter navigation
      if (novel?.chapters && novel.chapters.length > 0) {
        const chs = novel.chapters.filter(c => c.word_count > 0);
        if (chs.length === 0) return;

        if (e.key === 'j' || e.key === 'J') {
          e.preventDefault();
          const currentIdx = chs.findIndex(c => c.number === (document.querySelector('[data-active-chapter]')?.getAttribute('data-active-chapter')));
          const nextIdx = Math.min(currentIdx + 1, chs.length - 1);
          const nextCh = chs[nextIdx >= 0 ? nextIdx : 0];
          if (nextCh) {
            document.querySelector(`[data-chapter="${nextCh.number}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
            document.querySelector(`[data-chapter="${nextCh.number}"]`)?.setAttribute('data-active-chapter', String(nextCh.number));
          }
        }
        if (e.key === 'k' || e.key === 'K') {
          e.preventDefault();
          const currentIdx = chs.findIndex(c => c.number === (document.querySelector('[data-active-chapter]')?.getAttribute('data-active-chapter')));
          const prevIdx = Math.max(currentIdx - 1, 0);
          const prevCh = chs[prevIdx >= 0 ? prevIdx : 0];
          if (prevCh) {
            document.querySelector(`[data-chapter="${prevCh.number}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
            document.querySelector(`[data-chapter="${prevCh.number}"]`)?.setAttribute('data-active-chapter', String(prevCh.number));
          }
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [id, novel?.chapters]);

  // Warn before leaving during generation
  useEffect(() => {
    if (!genStatus || genStatus.status === 'complete' || genStatus.status === 'error') return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [genStatus]);

  // P0: Poll generation status
  useEffect(() => {
    if (!polling || !id) return;
    const timer = setInterval(async () => {
      try {
        const r = await fetch(`/api/novels/${id}/generate/status`);
        const s: GenStatus = await r.json();
        setGenStatus(s);
        if (s.status === 'complete' || s.status === 'error') {
          setPolling(false);
          if (s.status === 'complete') {
            toast.success(s.message);
            setJustCompleted(true);
            // Save quality breakdown
            if (s.quality_detail) {
              try {
                const details = JSON.parse(localStorage.getItem(`quality-details-${id}`) || '{}');
                const chNum = novel?.total_chapters ? novel.total_chapters + 1 : 1;
                details[String(chNum)] = s.quality_detail;
                localStorage.setItem(`quality-details-${id}`, JSON.stringify(details));
                // Save novel state snapshot for context continuity
                try {
                  const stateData = await api.novels.get(id);
                  const genChs = (stateData?.chapters || []).filter((c: any) => c.word_count > 0);
                  // Load existing state to preserve causal chain
                  const existingState = JSON.parse(localStorage.getItem(`novel-state-${id}`) || '{"causalChain":[],"worldState":""}');
                  const novelState = {
                    chapters: genChs.slice(-5).map((c: any) => ({ chapter: c.number, title: c.title, summary: c.summary || '' })),
                    lastUpdated: Date.now(),
                    causalChain: existingState.causalChain || [],
                    worldState: existingState.worldState || '',
                  };
                  // Append auto-extracted causal events if available
                  if (s.causal_events) {
                    const entries = s.causal_events.split('\n').filter(Boolean).slice(0, 3);
                    for (const entry of entries) {
                      const parts = entry.split('→').map((p: string) => p.trim());
                      if (parts.length >= 2) {
                        novelState.causalChain.push({ cause: parts[0], pending: parts[1] });
                      }
                    }
                    if (novelState.causalChain.length > 20) novelState.causalChain = novelState.causalChain.slice(-20);
                  }
                  localStorage.setItem(`novel-state-${id}`, JSON.stringify(novelState));
                } catch {}
              } catch {}
            }
            if (Notification.permission === 'granted') {
              new Notification('章节生成完成', { body: s.message, icon: '/favicon.ico' });
            }
            // Log daily words: the new chapter's word count is (new total - old total)
            const prevWords = novel?.total_words || 0;
            setTimeout(async () => {
              await loadNovel();
              const updated = await api.novels.get(id);
              const diff = (updated?.total_words || 0) - prevWords;
              if (diff > 0) logDailyWords(diff);
              setGenStatus(null);
              // Auto-expand latest chapter
              const latest = updated?.chapters?.filter((c: {word_count: number}) => c.word_count > 0).pop();
              if (latest) {
                setTimeout(() => {
                  const el = document.querySelector(`[data-chapter="${latest.number}"]`);
                  el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
                  (el as HTMLElement)?.click();
                }, 500);
              }
            }, 1000);
          }
        }
      } catch { setPolling(false); }
    }, 1200);  // faster polling for smoother live preview
    return () => clearInterval(timer);
  }, [polling, id, loadNovel]);

  function handleGenerate() {
    setShowGenDialog(true);
  }

  // Quick generate (Shift+G) - uses last settings
  function handleQuickGenerate() {
    if (!id) return;
    const lastDir = localStorage.getItem(`last-direction-${id}`) || '';
    const lastThreshold = Number(localStorage.getItem('quality-threshold') || '0.80');
    const lastMode = localStorage.getItem(`last-revision-mode-${id}`) || 'deep';
    const lastModel = localStorage.getItem('selected-model') || undefined;
    handleGenerateWithDirection(lastDir, lastThreshold, lastMode, lastModel);
    const settings = [
      lastMode === 'deep' ? '💎精雕' : '⚡快速',
      `阈值${lastThreshold.toFixed(2)}`,
      lastModel ? lastModel.replace('deepseek-','') : '',
      lastDir ? '有方向' : '自动构思',
    ].filter(Boolean).join(' · ');
    toast.success(`快捷生成已触发 — ${settings}`);
  }

  // Build full generation context from all configured systems
  function buildGenContext(novelId: string, userDirection: string): string {
    const parts: string[] = [];

    // 1. Soul fingerprint (30 polarities)
    try {
      const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null');
      if (fp?.primaryPolarity && fp?.answer) {
        const rules: Record<string, string> = {
          'silence-expression': '把最重要的情感放在动作和景物里，不直接说出来',
          'body-mind': '让身体替精神说话——用胃的收缩、汗的温度、嘴里的金属味代替心理描写',
          'desire-constraint': '每个角色都有想要但得不到的。写清楚他们放弃了什么来得到什么',
          'freedom-fate': '自由的行动导致宿命的结果——最深的悲剧',
          'individual-society': '不写时代——写一个人在时代中具体的挣扎',
          'life-death': '死亡是所有决定的背景——有限的时间让每个选择有重量',
          'scale-intimacy': '宇宙冷漠与人性微光之间反复切换',
          'meaning-absurdity': '不让角色找到答案——在系统面前反复碰壁',
          'belonging-alienation': '人群中的孤独——能交谈合作相爱但永远有无法跨越的距离',
          'truth-deception': '每个角色都在隐藏什么——最有力的欺骗是善意的',
          'order-chaos': '建立秩序然后让它瓦解——反复地',
          'innocence-experience': '看透一切后某个瞬间发现自己还在等',
        };
        parts.push(`【灵魂】${fp.answer}\n法则：${rules[fp.primaryPolarity] || ''}`);
      }
    } catch {}

    // 2. Soul Workshop profile
    try {
      const soul = JSON.parse(localStorage.getItem(`soul-${novelId}`) || 'null');
      if (soul) {
        if (soul.soulStatement) parts.push(`【灵魂陈述】${soul.soulStatement}`);
        if (soul.icebergLevel >= 7) parts.push('【留白】极简风格：不解释任何事情，让读者自己发现');
        if (soul.detailFocus) parts.push(`【细节焦点】重点描写${soul.detailFocus}`);
        if (soul.forbiddenWords?.length) parts.push(`【禁用词】避免使用：${soul.forbiddenWords.join('、')}`);
        if (soul.contradictions?.length) {
          parts.push(`【人物矛盾】${soul.contradictions.map((c: any) => `${c.character}：表面${c.surface}，内在${c.depth}`).join('；')}`);
        }
      }
    } catch {}

    // 3. Character souls
    try {
      const chars = JSON.parse(localStorage.getItem(`characters-soul-${novelId}`) || '[]');
      if (chars.length > 0) {
        const charContext = chars.map((c: any) => {
          const p: string[] = [];
          if (c.name) p.push(c.name);
          if (c.role) p.push(`[${c.role}]`);
          if (c.entrance) p.push(`出场：${c.entrance}`);
          if (c.signature) p.push(`特征：${c.signature}`);
          if (c.voiceSample) p.push(`台词风格：「${c.voiceSample}」`);
          if (c.speechPattern) p.push(`说话方式：${c.speechPattern}`);
          if (c.coreWound) p.push(`核心创伤：${c.coreWound}`);
          if (c.surfaceTrait && c.hiddenSelf) p.push(`矛盾：表面${c.surfaceTrait}·内在${c.hiddenSelf}`);
          if (c.arcStart && c.arcEnd) p.push(`弧线：${c.arcStart}→${c.arcEnd}`);
          return p.join(' · ');
        }).join('\n');
        if (charContext) parts.push(`【角色灵魂】\n${charContext}`);
      }
    } catch {}

    // 4. World laws
    try {
      const laws = JSON.parse(localStorage.getItem(`world-laws-${novelId}`) || '{"laws":[]}');
      if (laws.laws?.length) {
        parts.push(`【世界法则】${laws.laws.map((l: any) => l.rule).join('；')}`);
      }
    } catch {}

    // 5. Central image
    try {
      const img = JSON.parse(localStorage.getItem(`central-image-${novelId}`) || '{"name":"","description":"","chapters":[]}');
      if (img.name && img.description) {
        parts.push(`【核心意象】"${img.name}"——${img.description}。在合适的场景中让它自然出现。`);
      }
    } catch {}

    // 6. Emotional continuity from previous chapters
    try {
      const emotions = JSON.parse(localStorage.getItem(`chapter-emotions-${novelId}`) || '{}');
      const lastChapters = Object.entries(emotions).slice(-3) as [string, string][];
      if (lastChapters.length > 0) {
        parts.push(`【情感连续性】前几章的情感状态：\n${lastChapters.map(([ch, emo]) => `第${ch}章结尾：${emo}`).join('\n')}\n请确保本章的情感起点与前章结尾自然衔接。`);
      }
    } catch {}

    // 7. Auto-learned style from approved chapters
    try {
      const learned = JSON.parse(localStorage.getItem(`learned-style-${novelId}`) || 'null');
      if (learned) {
        parts.push(`【学习到的风格偏好】基于你审批通过的章节：${learned}`);
      }
    } catch {}

    // 8. Novel state + causal tracking — the novel as a simulated world
    try {
      const state = JSON.parse(localStorage.getItem(`novel-state-${novelId}`) || 'null');
      if (state?.chapters?.length > 0) {
        const recent = state.chapters.slice(-3);
        parts.push(`【全书状态】最近章节：\n${recent.map((c: any) => `第${c.chapter}章「${c.title}」：${c.summary}`).join('\n')}`);
        if (state.activeThreads?.length) {
          parts.push(`【进行中的线索】${state.activeThreads.slice(0, 5).join('；')}`);
        }
        if (state.pendingForeshadowing?.length) {
          parts.push(`【待回收伏笔】${state.pendingForeshadowing.slice(0, 3).join('；')}`);
        }
        if (state.characterStates) {
          parts.push(`【角色当前状态】${Object.entries(state.characterStates).slice(0, 4).map(([k, v]) => `${k}：${v}`).join('；')}`);
        }
        if (state.causalChain?.length) {
          parts.push(`【因果链 · 未解决的涟漪】\n${state.causalChain.slice(0, 3).map((c: any) => `${c.cause} → 尚未显现的后果：${c.pending}`).join('\n')}`);
        }
        // World state: faction standings, power balance, etc.
        if (state.worldState) {
          parts.push(`【世界状态】${state.worldState}`);
        }
      }
    } catch {}

    // 9. Novel architecture context (act/beat planning)
    try {
      const plan = JSON.parse(localStorage.getItem(`novel-plan-${novelId}`) || 'null');
      if (plan) {
        const currentCh = (novel?.chapters?.filter((c: any) => c.word_count > 0).length || 0) + 1;
        const currentAct = plan.acts?.find((a: any) => currentCh >= a.range[0] && currentCh <= a.range[1]);
        if (currentAct) {
          parts.push(`【当前卷】${currentAct.name} · 目标：${currentAct.goal} · 进度：第${currentCh}/${currentAct.range[1]}章`);
        }
        const upcoming = (plan.keyBeats || []).filter((b: any) => b.chapter >= currentCh && b.chapter <= currentCh + 3);
        if (upcoming.length > 0) {
          parts.push(`【即将到来的关键节点】${upcoming.map((b: any) => `第${b.chapter}章：${b.event}`).join('；')}`);
        }
      }
    } catch {}

    // 9. Character personification — every character gets a personal moment
    parts.push('【角色人格化】每个出场的角色必须至少有一个「不属于剧本」的瞬间——不是为了推动情节才做的动作，而是这个人才会有的自然流露。比如：反派在等待时下意识地整理袖口、路人在关键时刻犹豫了一下。');

    // 10. Style reference chapters
    try {
      const refs: number[] = JSON.parse(localStorage.getItem(`style-refs-${novelId}`) || '[]');
      if (refs.length > 0) {
        parts.push(`【风格参考】以下章节代表你期望的质量水准，请参考其风格、节奏、对话密度和描写方式。`);
      }
    } catch {}

    // 11. User direction (appended last so it takes precedence)
    if (userDirection) parts.push(`【本章方向】${userDirection}`);

    return parts.join('\n\n');
  }

  async function handleGenerateWithDirection(direction: string, qualityThreshold: number, revisionMode: string, model?: string) {
    if (!id) return;
    setShowGenDialog(false);
    // Save last settings for quick-generate
    localStorage.setItem(`last-direction-${id}`, direction);
    localStorage.setItem(`last-revision-mode-${id}`, revisionMode);
    try {
      const soulInjection = buildGenContext(id, direction);
      const isDeepMode = revisionMode === 'deep';

      const body: Record<string, any> = { direction: soulInjection, quality_threshold: qualityThreshold, soul_injection: soulInjection };
      if (model) body.model = model;

      const genRes = await fetch(`/api/novels/${id}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!genRes.ok) {
        const errText = await genRes.text();
        throw new Error(`服务器错误 (${genRes.status}): ${errText.slice(0, 100)}`);
      }
      setPolling(true);
      setShowAnalysis(false);  // collapse analysis to reduce noise during generation
      const thresholdLabel = qualityThreshold >= 0.8 ? '【严格模式】' : qualityThreshold >= 0.65 ? '' : '【宽松模式】';
      const hasConfig = soulInjection.length > 100 ? '【全配置注入】' : soulInjection.length > 10 ? '【灵魂注入】' : '';
      const modeLabel = isDeepMode ? '【精雕模式】' : '';
      setGenStatus({ status: 'generating', message: `${modeLabel}${hasConfig}${thresholdLabel}${direction ? `按方向：${direction.slice(0, 20)}...` : '正在构思...'}`, progress: 10 });
    } catch (e: unknown) { toast.error('生成失败: ' + (e as Error).message); }
  }

  async function handleRetry() {
    setGenStatus(null);
    await handleGenerate();
  }

  async function handleClone() {
    if (!id || !cloneTitle.trim()) { toast.error('请输入新书名'); return; }
    setCloning(true);
    try {
      const r = await fetch(`/api/novels/${id}/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: cloneTitle.trim(), genre: cloneGenre, protagonist_name: cloneName.trim() }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      toast.success('新书已创建');
      setShowClone(false);
      navigate(`/novels/${d.novel_id}`);
    } catch (e: unknown) { toast.error('复制失败: ' + (e as Error).message); }
    finally { setCloning(false); }
  }

  async function handlePublish() {
    if (!id) return;
    toast.info('正在发布...');
    try { await api.novels.publish(id); toast.success('发布成功'); }
    catch (e: unknown) { toast.error('发布失败: ' + (e as Error).message); }
  }

  async function handleDeleteChapter(num: number) {
    if (!id || !confirm(`删除第 ${num} 章？`)) return;
    try {
      await fetch(`/api/novels/${id}/chapters/${num}`, { method: 'DELETE' });
      toast.success('已删除', {
        action: { label: '撤销', onClick: async () => {
          try {
            await fetch(`/api/novels/${id}/chapters/${num}/restore`, { method: 'POST' });
            toast.success('已恢复');
            loadNovel();
          } catch { toast.error('恢复失败'); }
        }}
      });
      loadNovel();
    } catch { toast.error('删除失败'); }
  }

  if (loading) return <div className="space-y-4"><div className="skeleton h-6 w-20" /><div className="skeleton h-8 w-64" /></div>;
  if (!novel) return <div className="text-center py-20 text-ink-muted">小说未找到</div>;

  const ch = novel.latest_chapter;

  return (
    <div className="page-enter">
      <button onClick={() => navigate('/')} className="text-xs text-ink-muted hover:text-ink mb-2">← 返回工作台</button>

      {/* Quality Workflow Wizard */}
      <QualityWorkflow
        novelId={novel.id}
        lastQuality={novel.chapters?.filter((c: any) => c.word_count > 0 && c.quality_score).pop()?.quality_score}
        onNavigate={(sectionId) => {
          const el = document.getElementById(sectionId);
          if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
          // Auto-expand analysis if navigating to a section inside it
          if (['section-engine','section-characters','section-masterwork','section-creative'].includes(sectionId)) {
            setShowAnalysis(true);
          }
        }}
      />

      {/* Continue reading + Character tracker */}
      <div className="flex gap-2 mb-3 flex-wrap">
        {(() => {
          try {
            const saved = JSON.parse(localStorage.getItem(`last-read-${id}`) || 'null');
            if (!saved?.chapter) return null;
            const ch = novel.chapters?.find((c: any) => c.number === saved.chapter);
            if (!ch) return null;
            return (
              <div className="flex-1 p-2 rounded-lg bg-accent-soft/10 border border-accent/10 flex items-center gap-2 text-xs">
                <span>📖 上次：第{ch.number}章「{ch.title}」</span>
                <button onClick={() => {
                  const el = document.querySelector(`[data-chapter="${ch.number}"]`);
                  el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
                  setTimeout(() => (el as HTMLElement)?.click(), 300);
                }} className="text-accent hover:underline font-medium">继续 →</button>
                <button onClick={() => localStorage.removeItem(`last-read-${id}`)} className="text-ink-subtle hover:text-ink ml-auto">✕</button>
              </div>
            );
          } catch { return null; }
        })()}
        {/* Character quick-lookup */}
        {(() => {
          try {
            const chars = JSON.parse(localStorage.getItem(`characters-soul-${novel.id}`) || '[]');
            if (chars.length === 0) return null;
            return (
              <button onClick={async () => {
                const name = prompt('查找角色/物件/地点出现在哪些章节？', chars[0]?.name || '');
                if (!name) return;
                toast.info(`正在搜索「${name}」...`);
                const found: number[] = [];
                for (const ch of (novel.chapters || []).filter((c: any) => c.word_count > 0)) {
                  try {
                    const r = await fetch(`/api/novels/${id}/chapters/${ch.number}`);
                    const d = await r.json();
                    if ((d.content || '').includes(name)) found.push(ch.number);
                  } catch {}
                }
                if (found.length > 0) {
                  toast.success(`「${name}」出现在：第${found.join('、')}章`, { duration: 6000 });
                } else {
                  toast.info(`未找到「${name}」`);
                }
              }}
                className="text-[11px] px-2.5 py-1.5 rounded-lg border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors">
                🔍 角色追踪
              </button>
            );
          } catch { return null; }
        })()}
      </div>

      {/* Section quick-nav (visible when scrolled) */}
      <SectionNav sections={[
        { id: 'quality', label: '质量趋势', icon: '📊' },
        { id: 'arc', label: '情感弧线', icon: '📈' },
        { id: 'lab', label: '创作实验室', icon: '🔬' },
        { id: 'stats', label: '写作统计', icon: '📋' },
        { id: 'recommend', label: '智能推荐', icon: '🧬' },
        { id: 'sim', label: '读者模拟', icon: '👁️' },
        { id: 'publish', label: '发布状态', icon: '📤' },
        { id: 'chapters', label: '章节目录', icon: '📑' },
      ]} />
      <div className="flex items-center gap-3 mt-1">
        <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight">{novel.title}</h1>
        {mode === 'auto' && <span className="text-xs px-2 py-0.5 rounded-full bg-accent-soft text-accent font-medium">全自动</span>}
      </div>
      <p className="text-sm text-ink-muted mt-1">
        {novel.synopsis || '暂无简介'} · {novel.genre}
        {(() => {
          try {
            const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novel.id}`) || 'null');
            if (!fp?.primaryPolarity) return null;
            const names: Record<string, string> = {
              'silence-expression': '沉默↔表达', 'body-mind': '肉体↔精神', 'desire-constraint': '欲望↔约束',
              'freedom-fate': '自由↔命运', 'individual-society': '个人↔时代', 'belonging-alienation': '归属↔疏离',
              'life-death': '生↔死', 'truth-deception': '真相↔欺骗', 'order-chaos': '秩序↔混沌', 'innocence-experience': '纯真↔世故',
              'scale-intimacy': '宏大↔亲密', 'meaning-absurdity': '意义↔荒诞',
            };
            return <span className="ml-2 text-[11px] text-accent bg-accent-soft/30 px-1.5 py-0.5 rounded-full">💎 {names[fp.primaryPolarity] || fp.primaryPolarity}</span>;
          } catch { return null; }
        })()}
      </p>

      <div className="flex gap-8 my-6">
        <div><div className="font-heading text-[28px] font-semibold">{novel.total_chapters}</div><div className="text-xs text-ink-muted">章节</div></div>
        <div><div className="font-heading text-[28px] font-semibold">{novel.total_words.toLocaleString()}</div><div className="text-xs text-ink-muted">字数</div></div>
        {ch && <div><div className="font-heading text-[28px] font-semibold">第{ch.number}章</div><div className="text-xs text-ink-muted">最新</div></div>}
      </div>

      {/* Cockpit Snapshot */}
      {cockpit && cockpit.avg_quality && (
        <div className="mb-4 p-3 bg-paper border border-border rounded-lg flex gap-4 flex-wrap text-xs">
          {cockpit.alerts?.map((a,i) => {
            const chMatch = a.msg.match(/第(\d+)章/);
            const chapterNum = chMatch ? parseInt(chMatch[1]) : null;
            return chapterNum ? (
              <button key={i}
                onClick={() => {
                  const el = document.querySelector(`[data-chapter="${chapterNum}"]`);
                  el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  // Also expand the chapter
                  const clickEvent = new MouseEvent('click', { bubbles: true });
                  el?.dispatchEvent(clickEvent);
                }}
                className={a.level==='critical'
                  ? 'text-red-500 dark:text-red-400 font-semibold hover:underline cursor-pointer'
                  : 'text-amber-500 dark:text-amber-400 hover:underline cursor-pointer'}>
                ⚠️ {a.msg.slice(0,40)}
              </button>
            ) : (
              <span key={i} className={a.level==='critical'?'text-red-500 dark:text-red-400 font-semibold':'text-amber-500 dark:text-amber-400'}>⚠️ {a.msg.slice(0,40)}</span>
            );
          })}
          {cockpit.next_actions?.slice(0,2).map((a,i)=><span key={i} className="text-ink-muted">→ {a}</span>)}
          {cockpit.milestones?.slice(0,1).map((m,i)=><span key={i} className="text-emerald-500">🏆 还需{m.need}章到{m.reward}</span>)}
          {cockpit.revenue_projection && <span className="text-emerald-500 ml-auto">{cockpit.revenue_projection}</span>}
        </div>
      )}

      {/* Novel writer notes */}
      <div className="mb-3">
        {editingNotes ? (
          <div className="p-2.5 rounded-lg bg-paper border border-border">
            <textarea value={novelNotes} onChange={e => setNovelNotes(e.target.value)}
              placeholder="整体构思、灵感碎片、待办事项..."
              rows={2}
              className="w-full text-xs bg-transparent resize-none outline-none placeholder:text-ink-subtle" />
            <div className="flex gap-2 mt-1">
              <button onClick={() => { localStorage.setItem(`novel-notes-${novel.id}`, novelNotes); setEditingNotes(false); toast.success('已保存'); }}
                className="text-[10px] text-accent hover:underline">保存</button>
              <button onClick={() => setEditingNotes(false)} className="text-[10px] text-ink-muted hover:text-ink">取消</button>
            </div>
          </div>
        ) : (
          <button onClick={() => setEditingNotes(true)}
            className="text-[10px] text-ink-subtle hover:text-ink transition-colors">
            {novelNotes ? `📝 ${novelNotes.slice(0, 60)}${novelNotes.length > 60 ? '...' : ''}` : '📝 添加整体构思笔记...'}
          </button>
        )}
      </div>

      {/* Novel plan summary card */}
      {(() => {
        try {
          const plan = JSON.parse(localStorage.getItem(`novel-plan-${novel.id}`) || 'null');
          if (!plan?.acts?.length) return null;
          const currentCh = (novel.chapters?.filter((c: any) => c.word_count > 0).length || 0) + 1;
          const act = plan.acts.find((a: any) => currentCh >= a.range[0] && currentCh <= a.range[1]);
          if (!act) return null;
          const pct = Math.round(((currentCh - act.range[0] + 1) / (act.range[1] - act.range[0] + 1)) * 100);
          const upcoming = (plan.keyBeats || []).filter((b: any) => b.chapter >= currentCh && b.chapter <= currentCh + 3);
          return (
            <div className="mb-3 p-2.5 rounded-lg bg-gradient-to-r from-accent-soft/10 to-transparent border border-accent/10 text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="text-ink font-medium">📖 {act.name}</span>
                <span className="text-accent font-bold">{pct}%</span>
              </div>
              <div className="h-1 bg-border rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${pct}%` }} />
              </div>
              <div className="flex justify-between text-[9px] text-ink-subtle mt-0.5">
                <span>第{act.range[0]}章</span>
                <span>{act.goal.slice(0, 25)}</span>
                <span>第{act.range[1]}章</span>
              </div>
              {upcoming.length > 0 && (
                <div className="mt-1.5 flex gap-1.5 flex-wrap">
                  {upcoming.map((b: any, i: number) => (
                    <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent-soft/30 text-accent">
                      ⚡ {b.chapter - currentCh}章后：{b.event.slice(0, 15)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        } catch { return null; }
      })()}

      {/* Setup wizard for empty novels */}
      {novel.total_chapters === 0 && (
        <div className="mb-6 p-5 rounded-xl bg-gradient-to-br from-accent-soft/20 to-transparent border border-accent/20">
          <h3 className="font-heading text-base font-semibold text-ink mb-2">🚀 创作准备</h3>
          <p className="text-xs text-ink-muted mb-4">在生成第一章之前，建议完成以下准备——让 AI 真正理解你的故事。</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              {
                done: (() => { try { return !!JSON.parse(localStorage.getItem(`soul-fingerprint-${novel.id}`) || 'null'); } catch { return false; } })(),
                label: '选择灵魂矛盾', icon: '💎', desc: '30组矛盾中选一个——你的书要追问什么？',
                action: () => { const el = document.getElementById('section-engine'); el?.scrollIntoView({ behavior: 'smooth', block: 'center' }); },
              },
              {
                done: (() => { try { return JSON.parse(localStorage.getItem(`characters-soul-${novel.id}`) || '[]').length > 0; } catch { return false; } })(),
                label: '设计角色灵魂', icon: '👥', desc: '出场方式·标志台词·核心创伤——金庸级角色设计',
                action: () => { const el = document.getElementById('section-characters'); el?.scrollIntoView({ behavior: 'smooth', block: 'center' }); },
              },
              {
                done: (() => { try { return JSON.parse(localStorage.getItem(`world-laws-${novel.id}`) || '{"laws":[]}').laws?.length > 0; } catch { return false; } })(),
                label: '设定世界法则', icon: '🌍', desc: '这个世界的人如何相处——人际物理法则',
                action: () => { const el = document.getElementById('section-masterwork'); el?.scrollIntoView({ behavior: 'smooth', block: 'center' }); },
              },
            ].map((step, i) => (
              <button key={i} onClick={step.action}
                className={`p-3 rounded-xl border text-left transition-all hover:shadow-sm ${
                  step.done ? 'bg-emerald-50/30 dark:bg-emerald-950/10 border-emerald-200 dark:border-emerald-800' : 'bg-card border-border hover:border-accent/30'
                }`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{step.icon}</span>
                  <span className={`text-xs font-semibold ${step.done ? 'text-emerald-600 dark:text-emerald-400' : 'text-ink'}`}>
                    {step.done ? '✅' : '○'} {step.label}
                  </span>
                </div>
                <p className="text-[10px] text-ink-muted">{step.desc}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Writer's Orientation Panel */}
      {novel.total_chapters > 0 && (
        <div className="mb-4 p-4 rounded-xl bg-gradient-to-br from-card to-paper border border-border">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide">📋 写作面板</h3>
            <span className="text-[10px] text-ink-subtle">
              {novel.chapters?.filter((c: any) => c.word_count > 0).length || 0}章 · {(novel.total_words || 0).toLocaleString()}字
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
            {/* Quality trend mini */}
            <div className="p-2 rounded-lg bg-paper/50 border border-border/50">
              <div className="text-ink-subtle mb-1">近期质量</div>
              <div className="flex items-end gap-0.5 h-8">
                {(novel.chapters?.filter((c: any) => c.word_count > 0 && c.quality_score).slice(-5) || []).map((c: any, i: number) => {
                  const q = c.quality_score || 0;
                  const h = Math.max(4, q * 32);
                  return <div key={i} className={`flex-1 rounded-t-sm ${q >= 0.8 ? 'bg-emerald-400' : q >= 0.65 ? 'bg-amber-400' : 'bg-red-400'}`} style={{height: `${h}px`}} title={`Ch${c.number}: ${q.toFixed(2)}`} />;
                })}
              </div>
            </div>
            {/* Pending actions */}
            <div className="p-2 rounded-lg bg-paper/50 border border-border/50">
              <div className="text-ink-subtle mb-1">待处理</div>
              <div className="text-ink font-semibold">
                {(() => {
                  const reviseCount = (() => { try { return Object.values(JSON.parse(localStorage.getItem(`approvals-${novel.id}`) || '{}')).filter((s: any) => s === 'revise').length; } catch { return 0; } })();
                  const lowQCount = novel.chapters?.filter((c: any) => c.quality_score && c.quality_score < 0.7).length || 0;
                  const total = reviseCount + lowQCount;
                  return total > 0 ? `${total} 项` : '✓ 无';
                })()}
              </div>
              <div className="text-[9px] text-ink-subtle">待改 + 低质章节</div>
            </div>
            {/* Last activity */}
            <div className="p-2 rounded-lg bg-paper/50 border border-border/50">
              <div className="text-ink-subtle mb-1">最近活跃</div>
              <div className="text-ink font-semibold">
                {(() => {
                  const lastCh = novel.chapters?.filter((c: any) => c.word_count > 0).pop();
                  if (!lastCh?.generated_at) return '—';
                  try {
                    const diff = Date.now() - new Date(lastCh.generated_at + 'Z').getTime();
                    const hours = Math.round(diff / 3600000);
                    return hours < 1 ? '刚刚' : hours < 24 ? `${hours}小时前` : `${Math.floor(hours/24)}天前`;
                  } catch { return '—'; }
                })()}
              </div>
              <div className="text-[9px] text-ink-subtle">最后生成</div>
            </div>
            {/* Soul status */}
            <div className="p-2 rounded-lg bg-paper/50 border border-border/50">
              <div className="text-ink-subtle mb-1">灵魂状态</div>
              <div className="text-ink font-semibold text-[10px]">
                {(() => {
                  try {
                    const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novel.id}`) || 'null');
                    const chars = JSON.parse(localStorage.getItem(`characters-soul-${novel.id}`) || '[]');
                    const laws = JSON.parse(localStorage.getItem(`world-laws-${novel.id}`) || '{"laws":[]}');
                    const parts = [];
                    if (fp?.primaryPolarity) parts.push('💎');
                    if (chars.length > 0) parts.push('👥');
                    if (laws.laws?.length > 0) parts.push('🌍');
                    return parts.length > 0 ? parts.join(' ') + ' 已配置' : '未配置';
                  } catch { return '—'; }
                })()}
              </div>
              <div className="text-[9px] text-ink-subtle">灵魂·角色·法则</div>
            </div>
          </div>
        </div>
      )}

      {/* Quality Trend */}
      <div id="section-quality"><QualityTrend chapters={novel.chapters} /></div>

      {/* Collapsible Analysis Section */}
      <div className="mb-4">
        <button
          onClick={() => setShowAnalysis(!showAnalysis)}
          className="flex items-center gap-2 text-xs text-ink-muted hover:text-ink transition-colors mb-2">
          <span className={`transition-transform duration-200 ${showAnalysis ? 'rotate-90' : ''}`}>▸</span>
          创作分析
          <span className="text-ink-subtle">（情感弧线 · A/B测试 · 智能推荐 · 读者模拟）</span>
        </button>

        {showAnalysis && (
          <div className="space-y-4 animate-[fadeSlideIn_0.2s_ease-out]">
            {/* Novel Architect — long-form planning */}
            <div id="section-architect">
              <NovelArchitect novelId={novel.id} chapters={novel.chapters} totalChapters={novel.total_chapters} />
            </div>

            {/* Soul Engine */}
            <div id="section-engine"><SoulEngine novelId={novel.id} genre={novel.genre} /></div>

            {/* Masterwork Lab */}
            <div id="section-masterwork"><MasterworkLab
              novelId={novel.id}
              chapters={novel.chapters}
              genre={novel.genre}
            /></div>

            {/* Soul Workshop */}
            <div id="section-soul"><SoulWorkshop novelId={novel.id} chapters={novel.chapters} /></div>

            {/* Character Soul */}
            <div id="section-characters"><CharacterSoul novelId={novel.id} /></div>

            {/* Writing Digest */}
            <div id="section-digest"><WritingDigest chapters={novel.chapters} novelId={novel.id} /></div>

            {/* Emotional Arc */}
            <div id="section-arc"><EmotionalArc chapters={novel.chapters} /></div>

            {/* Emotion Recipe */}
            <div id="section-emotion"><EmotionRecipe chapters={novel.chapters} /></div>

            {/* Creative Lab */}
            <div id="section-creative"><CreativeLab chapters={novel.chapters} genre={novel.genre} novelId={novel.id} /></div>

            {/* Plot Network */}
            <div id="section-network"><PlotNetwork novelId={novel.id} /></div>

            {/* Chapter DNA */}
            <div id="section-dna"><ChapterDNA chapters={novel.chapters} novelId={novel.id} /></div>

            {/* Story Lab: A/B Test + Character Voice */}
            <div id="section-lab" className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <OpeningABTest novelId={novel.id} genre={novel.genre} synopsis={novel.synopsis} />
              <CharacterVoices novelId={novel.id} chapters={novel.chapters} />
            </div>

            {/* Smart Recommendations */}
            <div id="section-recommend"><SmartRecommend genre={novel.genre} chapters={novel.chapters} /></div>

            {/* Reader Simulator */}
            <div id="section-sim">
              <ReaderSim novelId={novel.id} chapters={novel.chapters} />
            </div>
          </div>
        )}
      </div>

      {/* Writer Stats — always visible */}
      <div id="section-stats"><WriterStats novelId={novel.id} totalChapters={novel.total_chapters} totalWords={novel.total_words} chapters={novel.chapters} /></div>

      {/* Generation progress — 5-gate pipeline */}
      {genStatus && <GenerationPipeline genStatus={genStatus} onRetry={handleRetry} />}

      {/* Post-generation guidance */}
      {justCompleted && !genStatus && (
        <div className="mb-4 space-y-2">
          <div className="p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 flex items-center gap-3 text-xs animate-[fadeSlideIn_0.3s_ease-out]">
            <span className="text-lg">✅</span>
            <div className="flex-1">
              <span className="text-emerald-700 dark:text-emerald-300 font-medium">章节已生成</span>
              <span className="text-ink-muted ml-2">下一步：阅读 → 标记已审/待改 → 继续生成或精修</span>
            </div>
            <button onClick={() => { setShowAnalysis(true); }}
              className="text-[10px] text-accent hover:underline whitespace-nowrap">展开分析</button>
            <button onClick={() => {
              const chs = novel?.chapters?.filter((c: any) => c.word_count > 0) || [];
              if (chs.length >= 2) {
                const el = document.getElementById('section-creative');
                el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            }}
              className="text-[10px] text-accent hover:underline whitespace-nowrap">对比质量</button>
            <button onClick={() => { setJustCompleted(false); localStorage.setItem(`gen-guidance-dismissed`, 'true'); }}
              className="text-ink-subtle hover:text-ink">✕</button>
          </div>

          {/* Causal log input */}
          {!showCausalInput ? (
            <button onClick={() => setShowCausalInput(true)}
              className="text-[10px] text-ink-subtle hover:text-ink transition-colors block w-full text-left">
              📝 记录因果（本章有什么动作会在后续产生涟漪？）
            </button>
          ) : (
            <div className="p-2.5 rounded-lg bg-paper border border-border flex gap-2">
              <input
                value={causalInput}
                onChange={e => setCausalInput(e.target.value)}
                placeholder="例：林尘烧了宗门令牌 → 宗门派出追杀队；苏婉救了陌生人 → 陌生人是敌方卧底"
                onKeyDown={e => {
                  if (e.key === 'Enter' && causalInput.trim()) {
                    try {
                      const state = JSON.parse(localStorage.getItem(`novel-state-${id}`) || '{"chapters":[],"causalChain":[],"worldState":""}');
                      const entries = causalInput.split('；').filter(Boolean);
                      for (const entry of entries) {
                        const parts = entry.split('→').map(s => s.trim());
                        state.causalChain = [...(state.causalChain || []), { cause: parts[0] || entry, pending: parts[1] || '后果待定' }];
                      }
                      if (state.causalChain.length > 20) state.causalChain = state.causalChain.slice(-20);
                      localStorage.setItem(`novel-state-${id}`, JSON.stringify(state));
                      toast.success(`已记录 ${entries.length} 条因果`);
                      setCausalInput('');
                      setShowCausalInput(false);
                    } catch { toast.error('记录失败'); }
                  }
                }}
                className="flex-1 text-xs bg-transparent outline-none placeholder:text-ink-subtle" />
              <button onClick={() => setShowCausalInput(false)}
                className="text-[10px] text-ink-muted hover:text-ink">取消</button>
            </div>
          )}
        </div>
      )}

      {/* Generate with direction dialog */}
      <GenerateDialog
        open={showGenDialog}
        onClose={() => setShowGenDialog(false)}
        onGenerate={handleGenerateWithDirection}
        chapterNumber={novel.total_chapters + 1}
        prevHook={novel.chapters?.filter(c => c.word_count > 0).pop()?.ending_hook}
        novelId={novel.id}
      />

      <div className="flex gap-2 mb-6 flex-wrap">
        {mode === 'auto' ? (
          <>
            <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={() => { api.novels.autoOnce(id!); toast.success('已触发'); }}>手动执行一次</Button>
            <Button size="sm" variant="outline" onClick={() => setShowAutoConfig(!showAutoConfig)}>
              {showAutoConfig ? '收起配置' : '⚙ 自动配置'}
            </Button>
            <Button size="sm" variant="outline" className="text-red-500 border-red-300 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-950"
              onClick={async () => {
                await fetch(`/api/novels/${id}/auto/stop`, { method: 'POST' });
                toast.success('已停止自动模式');
              }}>⏹ 停止自动</Button>
            {/* Auto-config panel */}
            {showAutoConfig && (
              <div className="w-full mt-2 p-4 rounded-xl bg-paper border border-border animate-[fadeSlideIn_0.2s_ease-out]">
                <h4 className="text-xs font-semibold text-ink mb-3">🤖 自动生成配置</h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
                  <div>
                    <label className="text-ink-subtle">每次生成</label>
                    <select value={autoConfig.chaptersPerRun} onChange={e => setAutoConfig({...autoConfig, chaptersPerRun: Number(e.target.value)})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5">
                      {[1,2,3,5,10].map(n => <option key={n} value={n}>{n} 章</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-ink-subtle">最低质量</label>
                    <select value={autoConfig.qualityFloor} onChange={e => setAutoConfig({...autoConfig, qualityFloor: Number(e.target.value)})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5">
                      <option value={0.70}>0.70 B级</option>
                      <option value={0.80}>0.80 A级</option>
                      <option value={0.85}>0.85 S级</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-ink-subtle">最大重试</label>
                    <select value={autoConfig.maxRetries} onChange={e => setAutoConfig({...autoConfig, maxRetries: Number(e.target.value)})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5">
                      {[1,2,3,5].map(n => <option key={n} value={n}>{n} 次</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-ink-subtle">节奏模式</label>
                    <select value={autoConfig.pacingMode} onChange={e => setAutoConfig({...autoConfig, pacingMode: e.target.value as any})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5">
                      <option value="balanced">平衡</option>
                      <option value="action">动作优先</option>
                      <option value="dialogue">对话优先</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-ink-subtle">自动方向</label>
                    <select value={String(autoConfig.autoDirection)} onChange={e => setAutoConfig({...autoConfig, autoDirection: e.target.value === 'true'})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5">
                      <option value="true">使用上章钩子</option>
                      <option value="false">完全自由</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-ink-subtle">停止条件: 章节数</label>
                    <input type="number" value={autoConfig.stopAtChapters} onChange={e => setAutoConfig({...autoConfig, stopAtChapters: Number(e.target.value)})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5" />
                  </div>
                  <div>
                    <label className="text-ink-subtle">停止条件: 连续低质</label>
                    <input type="number" value={autoConfig.stopAtQuality} step="0.05" onChange={e => setAutoConfig({...autoConfig, stopAtQuality: Number(e.target.value)})}
                      className="w-full mt-1 rounded border border-input bg-card text-ink text-xs px-2 py-1.5" />
                  </div>
                  <div className="flex items-end">
                    <button onClick={() => { setShowAutoConfig(false); toast.success('自动配置已更新'); }}
                      className="w-full py-1.5 rounded bg-accent text-white text-xs hover:bg-accent-hover transition-colors">
                      保存配置
                    </button>
                  </div>
                </div>
                <p className="text-[9px] text-ink-subtle mt-3">
                  自动模式将按以上配置持续生成。达到停止条件时自动暂停，等待你的审阅。
                </p>
              </div>
            )}
          </>
        ) : (
          <>
            <Button size="sm" className="bg-accent hover:bg-accent-hover btn-generate"
              onClick={handleGenerate} title="打开生成对话框: Ctrl+G"
              disabled={!!genStatus && genStatus.status !== 'error' && genStatus.status !== 'complete'}>
              {genStatus && genStatus.status !== 'error' && genStatus.status !== 'complete'
                ? '⏳ 生成中...'
                : <>⚡ 生成下一章 <span className="text-[9px] opacity-50 ml-1">Ctrl+G</span></>
              }
            </Button>
            <Button size="sm" variant="outline" className="text-xs"
              onClick={handleQuickGenerate} title="跳过对话框直接生成: Shift+G"
              disabled={!!genStatus && genStatus.status !== 'error' && genStatus.status !== 'complete'}>
              ⚡ 快速生成 <span className="text-[9px] opacity-50 ml-1">Shift+G</span>
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setCloneTitle(novel?.title + '（副本）' || ''); setCloneGenre(novel?.genre || '玄幻'); setCloneName(''); setShowClone(true); }}>📋 复制开新书</Button>
            <Button size="sm" variant="outline" onClick={() => navigate(`/novels/${id}/world`)}>🌍 世界观编辑器</Button>
            <Button size="sm" variant="outline" onClick={() => navigate(`/novels/${id}/outline`)}>📋 章节大纲</Button>
            <Button size="sm" variant="outline" className="text-success border-success/50 hover:bg-success-soft"
              onClick={async () => {
                await fetch(`/api/novels/${id}/auto/start`, { method: 'POST' });
                toast.success('已启动全自动模式，将持续生成章节');
              }}>
              🤖 全自动日更
            </Button>
            <Button size="sm" variant="outline" onClick={() => navigate(`/novels/${id}/edit`)}>✍️ 创作者模式</Button>
            {ch && (
              <>
                <Button size="sm" variant="outline" className="text-success border-success hover:bg-success-soft" onClick={handlePublish}>发布最新章节</Button>
                <Button size="sm" variant="outline" className="text-xs border-success/50 text-success-muted" onClick={() => setPublishChapter(1)}>📤 从第1章发布</Button>
              </>
            )}
          </>
        )}
      </div>

      {/* Quick Actions */}
      <div className="flex gap-1 mb-4 flex-wrap">
        <button className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
          onClick={async () => { const ch = novel?.chapters?.filter((c: {word_count: number}) => c.word_count > 0).pop(); if(ch) { toast.info('正在去AI味…'); await fetch(`/api/novels/${id}/chapters/${ch.number}/humanize`,{method:'POST'}); toast.success('已触发去AI味'); }}}>🧹 去AI味</button>
        <button className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
          onClick={async () => { const ch = novel?.chapters?.filter((c: {word_count: number}) => c.word_count > 0).pop(); if(ch) { const r=await fetch(`/api/novels/${id}/chapters/${ch.number}/fact-check`); const d=await r.json(); toast.success(`核查完成：${d.issues?.length||0}个疑点`); }}}>🔍 事实核查</button>
        <button className="text-[11px] text-ink-muted hover:text-amber-500 px-2 py-1 rounded border border-border hover:border-amber/30 transition-colors"
          onClick={async () => { const r=await fetch(`/api/novels/${id}/cockpit`); const d=await r.json(); toast.success(`${d.novel}: 均分${d.avg_quality} | ${d.next_actions?.[0]||''}`); }}>📊 驾驶舱</button>
        <button className="text-[11px] text-ink-muted hover:text-emerald-500 px-2 py-1 rounded border border-border hover:border-emerald/30 transition-colors"
          onClick={async () => { const r=await fetch(`/api/novels/${id}/revenue-estimate`); const d=await r.json(); toast.success(d.revenue_projection||''); }}>💰 收入预估</button>
        <button className="text-[11px] text-ink-muted hover:text-rose-500 px-2 py-1 rounded border border-border hover:border-rose/30 transition-colors"
          onClick={async () => { toast.info('正在生成报告…'); const r=await fetch(`/api/novels/${id}/report`); const d=await r.json(); toast.success(`${d.recommendation||''}`); }}>📋 出版报告</button>
        <a href={`/api/novels/${id}/export-epub`}
          className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
          onClick={() => toast.success('EPUB 下载中...')}>📚 EPUB</a>
        <a href={`/api/novels/${id}/export-full`}
          className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
          onClick={() => toast.success('TXT 下载中...')}>📄 TXT</a>
        <button className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
          onClick={async () => {
            toast.info('正在打包所有章节...');
            const chs = novel.chapters?.filter(c => c.word_count > 0) || [];
            for (const ch of chs) {
              window.open(`/api/novels/${id}/chapters/${ch.number}/export`, '_blank');
            }
            toast.success(`${chs.length} 章已触发下载`);
          }}>📦 批量导出</button>
        <WordSprint />
        <button className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors"
          onClick={async () => {
            toast.info('正在分析剧情，生成方向建议...');
            try {
              const r = await fetch(`/api/novels/${id}/cockpit`);
              const d = await r.json();
              const actions = d.next_actions || [];
              if (actions.length > 0) {
                toast.success(actions.slice(0, 3).join(' | '), { duration: 8000 });
              } else {
                toast.success('当前剧情发展良好，继续按大纲推进即可');
              }
            } catch { toast.error('获取建议失败'); }
          }}>💡 写困救援</button>
      </div>

      {/* Quality decline alert */}
      {novel.chapters && (() => {
        const gen = novel.chapters.filter((c: any) => c.word_count > 0 && c.quality_score);
        if (gen.length < 3) return null;
        const last3 = gen.slice(-3).map((c: any) => c.quality_score);
        if (last3[0] > last3[1] && last3[1] > last3[2] && last3[0] - last3[2] > 0.08) {
          return (
            <div className="mb-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 text-xs animate-[fadeSlideIn_0.3s_ease-out]">
              <span className="text-amber-600 dark:text-amber-400 font-medium">⚠️ 质量连续下降</span>
              <span className="text-ink-muted ml-2">
                Ch{gen[gen.length-3].number}:{last3[0].toFixed(2)} → Ch{gen[gen.length-2].number}:{last3[1].toFixed(2)} → Ch{gen[gen.length-1].number}:{last3[2].toFixed(2)}
              </span>
              <span className="text-ink-subtle ml-2">建议检查最近章节，使用定向重写改进薄弱维度</span>
            </div>
          );
        }
        return null;
      })()}

      {/* Chapter stats summary */}
      {novel.chapters && novel.chapters.length > 0 && (() => {
        const scores = novel.chapters.filter(c => c.quality_score !== undefined).map(c => c.quality_score!);
        const avgQ = scores.length > 0 ? scores.reduce((a,b) => a+b, 0) / scores.length : null;
        const best = scores.length > 0 ? Math.max(...scores) : null;
        const lastGen = novel.chapters.filter(c => c.generated_at).pop()?.generated_at;
        const totalRevisions = novel.chapters.reduce((sum, c) => sum + (c.word_count > 0 ? 1 : 0), 0);
        return (
          <div className="flex gap-4 mb-4 p-3 bg-paper border border-border rounded-lg text-[11px] flex-wrap">
            {avgQ !== null && (
              <span className="text-ink-muted">
                均质 <span className="text-ink font-semibold">{avgQ.toFixed(2)}</span>
              </span>
            )}
            {best !== null && (
              <span className="text-ink-muted">
                最佳 <span className="text-emerald-500 font-semibold">{best.toFixed(2)}</span>
              </span>
            )}
            <span className="text-ink-muted">
              已写 <span className="text-ink font-semibold">{totalRevisions}</span> 章
            </span>
            {lastGen && (
              <span className="text-ink-muted ml-auto">
                最近更新 {new Date(lastGen + 'Z').toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        );
      })()}

      {/* Keyboard shortcut hints */}
      <div className="flex gap-3 mb-4 text-[10px] text-ink-subtle">
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">Ctrl+G</kbd>
        <span>对话框</span>
        <span className="text-border">|</span>
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">Shift+G</kbd>
        <span>快速生成</span>
        <span className="text-border">|</span>
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">J/K</kbd>
        <span>浏览章节</span>
        <span className="text-border">|</span>
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">Ctrl+K</kbd>
        <span>命令面板</span>
        <span className="text-border">|</span>
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">Esc</kbd>
        <span>关闭</span>
        <span className="text-border">|</span>
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">Ctrl+Shift+F</kbd>
        <span>全文搜索</span>
        <span className="text-border">|</span>
        <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono">?</kbd>
        <span>快捷键</span>
      </div>

      {/* Platform checklist + Publishing status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <PlatformChecklist chapters={novel.chapters} genre={novel.genre} />
        {novel.chapters && novel.chapters.length > 0 && (
          <div id="section-publish" className="p-4 bg-card border border-border rounded-xl">
            <h3 className="font-heading text-base font-semibold text-ink mb-3">📤 发布状态</h3>
            <div className="space-y-2 text-[12px]">
              <div className="flex justify-between">
                <span className="text-ink-muted">已发布</span>
                <span className="text-emerald-500 font-medium">{novel.chapters.filter(c => c.word_count > 0).length} 章</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">待发布（大纲）</span>
                <span className="text-ink-subtle">{novel.chapters.filter(c => c.word_count === 0).length} 章</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">总章节</span>
                <span className="text-ink">{novel.chapters.length} 章</span>
              </div>
              {(() => {
                const latest = novel.chapters.filter(c => c.word_count > 0).pop();
                if (!latest?.generated_at) return null;
                const d = new Date(latest.generated_at + 'Z');
                return (
                  <div className="flex justify-between">
                    <span className="text-ink-muted">最近更新</span>
                    <span className="text-ink-subtle">{d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                );
              })()}
              <div className="flex justify-between">
                <span className="text-ink-muted">总字数</span>
                <span className="text-ink font-medium">{novel.total_words.toLocaleString()} 字</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div id="section-chapters">
        <h2 className="font-heading text-xl font-semibold text-ink mb-3">章节目录</h2>
        <ChapterList chapters={novel.chapters} novelId={novel.id} onDelete={handleDeleteChapter} />
      </div>

      {/* Publish Select Modal */}
      {publishChapter !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setPublishChapter(null)}>
          <div className="bg-card border border-border rounded-xl p-6 w-[450px] max-w-[90vw] shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="font-heading text-lg font-semibold text-ink mb-4">选择发布章节</h3>
            <p className="text-xs text-ink-muted mb-4">选择要发布的章节。已发布的不会重复发送。</p>
            <div className="max-h-60 overflow-y-auto space-y-1">
              {novel.chapters.filter(c => c.word_count > 0).map(ch => (
                <label key={ch.number} className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-paper cursor-pointer">
                  <input type="radio" name="publish-ch" value={ch.number}
                    checked={publishChapter === ch.number}
                    onChange={() => setPublishChapter(ch.number)}
                    className="accent-accent" />
                  <span className="text-sm tabular-nums text-ink-muted">Ch{ch.number}</span>
                  <span className="text-sm flex-1">{ch.title}</span>
                  <span className="text-[11px] text-ink-subtle">{ch.word_count}字</span>
                </label>
              ))}
            </div>
            <div className="flex gap-2 mt-5 justify-end">
              <button onClick={() => setPublishChapter(null)}
                className="px-4 py-2 text-sm rounded-md text-ink-muted hover:text-ink transition-colors">取消</button>
              <button onClick={async () => {
                  if (!id || !publishChapter) return;
                  setPublishing(true);
                  try {
                    await fetch(`/api/novels/${id}/publish`, {
                      method: 'POST',
                      headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({chapter_number: publishChapter}),
                    });
                    toast.success(`第${publishChapter}章发布中`);
                    setPublishChapter(null);
                  } catch (e: unknown) { toast.error('发布失败: ' + (e as Error).message); }
                  finally { setPublishing(false); }
                }}
                disabled={publishing}
                className="px-4 py-2 text-sm rounded-md bg-success text-white hover:opacity-90 transition-colors disabled:opacity-50">
                {publishing ? '发布中...' : `发布第 ${publishChapter} 章`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Full-text chapter search */}
      <ChapterSearch
        novelId={novel.id}
        chapters={novel.chapters}
        onNavigate={(num) => {
          document.querySelector(`[data-chapter="${num}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
          // Trigger click to expand
          const el = document.querySelector(`[data-chapter="${num}"]`);
          if (el) (el as HTMLElement).click();
        }}
      />

      <ScrollToTop />

      {/* Clone Modal */}
      {showClone && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowClone(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-[400px] max-w-[90vw] shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="font-heading text-lg font-semibold text-ink mb-4">复制开新书</h3>
            <p className="text-xs text-ink-muted mb-4">复制世界观、角色、势力和大纲到新书。已生成章节不复制。</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">新书名</label>
                <input value={cloneTitle} onChange={e => setCloneTitle(e.target.value)}
                  className="w-full mt-1 rounded-md border border-input bg-card text-ink text-sm px-3 py-2" placeholder="新书名" />
              </div>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">题材</label>
                <select value={cloneGenre} onChange={e => setCloneGenre(e.target.value)}
                  className="w-full mt-1 rounded-md border border-input bg-card text-ink text-sm px-3 py-2">
                  {['玄幻','仙侠','武侠','都市','官场','现代言情','古代言情','纯爱','悬疑','灵异','科幻','末世','游戏','历史','系统流','无限流','奇幻','二次元','轻小说','种田','体育','军事','同人','其他'].map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">主角名（留空沿用原名）</label>
                <input value={cloneName} onChange={e => setCloneName(e.target.value)}
                  className="w-full mt-1 rounded-md border border-input bg-card text-ink text-sm px-3 py-2" placeholder="新主角名" />
              </div>
            </div>
            <div className="flex gap-2 mt-5 justify-end">
              <button onClick={() => setShowClone(false)}
                className="px-4 py-2 text-sm rounded-md text-ink-muted hover:text-ink transition-colors">取消</button>
              <button onClick={handleClone} disabled={cloning}
                className="px-4 py-2 text-sm rounded-md bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50">
                {cloning ? '复制中...' : '确认复制'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
