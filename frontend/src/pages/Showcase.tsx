import { useState, useEffect, useRef } from 'react';
import {
  BookOpen, Bot, Brain, Calendar, ClipboardCheck, Dna, Download, Eye,
  FileSearch, Flame, GitBranch, Globe, Headphones, Keyboard,
  Lightbulb, Mic, Moon, Network, Palette, PenLine, Rocket, ScanSearch,
  Search, Settings, Sparkles, Star, Telescope, TestTubes, Timer,
  TrendingUp, Users, Wand2, Zap,
} from 'lucide-react';

/* ─── 真实功能列表（仅包含已实现的功能）─── */
const FEATURES = [
  { icon: 'Brain', title: '12步生成管线', desc: '约束压缩→技巧选择→批量草拟→LLM评分→精修→去AI味→硬约束验证→人性化→废话检查→一致性校验→伏笔回收→语音预生成', tag: '核心' },
  { icon: 'Search', title: '8维LLM质量评审', desc: '钩子·节奏·对话·可读性·反派·追读意愿·排版规范·灵魂契合。每项1-10分+理由，不达标自动重写', tag: '核心' },
  { icon: 'Flame', title: '灵魂引擎', desc: '30组文学根本矛盾（自由vs命运、爱vs恨、意义vs荒诞），每组配3位大师参考。选矛盾→定立场→写回答，每章注入', tag: '核心' },
  { icon: 'Users', title: '金庸级角色设计', desc: '每个角色必有：出场方式·标志特征·台词样本·核心创伤·表面/隐藏人格·弧线起点→终点·内在矛盾·对比角色', tag: '核心' },
  { icon: 'Globe', title: '世界观编辑器', desc: '世界名称·时代·地理·力量体系·主线篇章·世界法则标签。角色和势力的CRUD管理，一键保存', tag: '核心' },
  { icon: 'GitBranch', title: '伏笔追踪系统', desc: '自动检测已埋/已回收伏笔，超过10章未回收触发警告。按章节分组展示，确保长篇自洽', tag: '核心' },
  { icon: 'ClipboardCheck', title: '平台发布检查', desc: '发布前自动检查：结尾钩子·标题吸睛度·章节长度·质量评分·对话密度·节奏感，一键评估发布就绪度', tag: '核心' },
  { icon: 'Rocket', title: '批量生成', desc: '一次生成最多20章，质量阈值可调。SSE实时推送管道进度，失败自动重试。支持全自动日更模式', tag: '核心' },
  { icon: 'Eye', title: '实时生成监控', desc: '四阶段管道图（构思→修复→润色→评估）+ 进度条 + 计时器。完成/失败状态不自动消失，手动关闭', tag: '' },
  { icon: 'PenLine', title: '沉浸写作编辑器', desc: '三栏布局：章节列表+正文+上下文面板。阅读/编辑无缝切换，Markdown渲染，自动保存', tag: '' },
  { icon: 'Wand2', title: '方向预设', desc: '7种快捷方向（打斗/感情/反转/日常/悬疑/伏笔/高潮），点击即可追加到生成指令。也支持自由文本输入', tag: '' },
  { icon: 'Mic', title: '14种作家声音', desc: '金庸·余华·刘慈欣·东野圭吾·海明威·莫言·张爱玲·鲁迅·村上春树·马尔克斯·古龙·汪曾祺·爆款网文·文学实验', tag: '' },
  { icon: 'BookOpen', title: '24种题材风格', desc: '玄幻/都市/悬疑/科幻/官场/仙侠/武侠/系统流/无限流/女频/历史/游戏...每种独立风格配置', tag: '' },
  { icon: 'Palette', title: '质量趋势分析', desc: 'SVG图表：质量趋势+节奏曲线+情感弧线+对话密度+情绪配方+章节DNA雷达。任意两章并排对比', tag: '' },
  { icon: 'Network', title: '情节网络图', desc: '力导向角色关系图谱。基于角色表和关系数据自动渲染，可视化叙事结构', tag: '' },
  { icon: 'Dna', title: '反AI痕迹检测', desc: '35种中文AI写作模式的正则检测。随机句长变化+段落打破+结尾钩子保护，降低平台识别风险', tag: '' },
  { icon: 'Telescope', title: '故事圣经', desc: '自动从已生成章节提取：角色状态·伏笔·位置历史·时间线·世界规则·一致性日志·代价账簿', tag: '' },
  { icon: 'Download', title: 'TXT/EPUB导出', desc: '一键导出完整小说为TXT（可导入番茄作家后台）或EPUB电子书（带封面+目录+样式）', tag: '' },
  { icon: 'Headphones', title: 'AI听书系统', desc: '章节TTS自动生成，多语音选择，可调速（0.5x-2.0x），书签+播放列表+睡眠定时器', tag: '' },
  { icon: 'Timer', title: '专注冲刺计时器', desc: 'Pomodoro风格写作计时器，15/25/45/60分钟可选。实时速率追踪，完成提醒', tag: '' },
  { icon: 'Zap', title: '写作工作台', desc: '实时流式内容预览·大纲侧栏·质量细分面板·分析图表内嵌·生成管道可视化·方向预设·自动保存', tag: '核心' },
  { icon: 'Sparkles', title: '排版自动规范', desc: 'AI生成后自动修复孤儿引号·统一「」引号格式·英文引号转中文·段落方差检测·格式评分', tag: '' },
  { icon: 'Shield', title: '断点续传+防重', desc: '生成中断自动保存进度·双击防重（前后端双锁）·空内容自动报错·模型切换透明提示', tag: '' },
  { icon: 'TrendingUp', title: '自动参数校准', desc: '每5章根据历史质量趋势自动调整StyleProfile参数·对话密度·钩子间隔·段落范围', tag: '' },
  { icon: 'Globe', title: '免费模型接入', desc: 'FreeLLM集成·13个免费模型（DeepSeek/Kimi/GLM/Qwen等）·代理本地部署·即开即用', tag: '' },
  { icon: 'Keyboard', title: '键盘快捷键', desc: 'Ctrl+Enter生成·Ctrl+S保存·自动保存（5秒防丢）·J/K切换章节·Ctrl+K命令面板', tag: '' },
  { icon: 'Settings', title: '多模型支持', desc: 'DeepSeek V4·OpenAI·通义千问·Kimi·智谱·豆包·百度·讯飞·MiniMax·Google。设置页配置Key+测试连接', tag: '' },
  { icon: 'Moon', title: '深色模式', desc: '跟随系统自动切换明暗主题，全局0.3s平滑过渡。暖光素笺(#F5F0E8)纸墨感设计', tag: '' },
  { icon: 'ScanSearch', title: 'AI建议生成', desc: '创建新小说时，AI根据书名和题材自动生成3个简介候选+5个风格标签建议，点击选用', tag: '' },
  { icon: 'Calendar', title: '写作日历+目标', desc: '7日写作趋势图+每日字数统计。设置日更目标，日历可视化追踪进度', tag: '' },
  { icon: 'TrendingUp', title: '成本追踪', desc: '按小说/模型维度统计API调用成本。Token消耗+费用明细，支持成本预警', tag: '' },
  { icon: 'Lightbulb', title: '备份与恢复', desc: '一键下载全量JSON备份，支持从备份文件恢复。本地优先，数据安全', tag: '' },
];

/* ─── 真实统计数据 ─── */
const STATS = [
  { value: 30, suffix: '组', label: '灵魂矛盾' },
  { value: 24, suffix: '种', label: '题材风格' },
  { value: 32, suffix: '+', label: '专业功能' },
  { value: 8, suffix: '维', label: '质量评审' },
];

/* ─── 三大支柱 ─── */
const HIGHLIGHTS = [
  {
    icon: '🧬',
    title: '灵魂驱动的生成',
    desc: '不是"写一个奇幻故事"。是从30组文学根本矛盾中选出你的核心追问，AI在每一章都围绕这个矛盾写作。金庸级角色设计标准确保每个人物都有出场、标志、创伤和弧线。',
    gradient: 'from-violet-500/15 via-accent/5 to-violet-500/5',
    iconBg: 'bg-violet-50 dark:bg-violet-900/30',
  },
  {
    icon: '🛡️',
    title: '12步质量管线',
    desc: '每章经过约束压缩→技巧选择→批量草拟→6维评分→精修→去AI味→硬约束验证→人性化→废话检查→一致性校验→伏笔回收→语音预生成。不达标自动重写。',
    gradient: 'from-emerald-500/15 via-accent/5 to-emerald-500/5',
    iconBg: 'bg-success-soft dark:bg-emerald-900/30',
  },
  {
    icon: '📖',
    title: '完整创作工具链',
    desc: '世界观编辑器→角色工坊→灵魂引擎→写作编辑器→分析仪表盘→出版检查→导出发布。从一句话简介到可发布的小说，一个工具完成全流程。',
    gradient: 'from-amber-500/15 via-accent/5 to-amber-500/5',
    iconBg: 'bg-warn-soft dark:bg-amber-900/30',
  },
];

/* ─── 动画计数器 ─── */
function CountUp({ target, suffix, duration = 1500 }: { target: number; suffix: string; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || started.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        started.current = true;
        const start = performance.now();
        const step = (now: number) => {
          const elapsed = now - start;
          const progress = Math.min(1, elapsed / duration);
          setCount(Math.floor(progress * target));
          if (progress < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
    }, { threshold: 0.5 });
    observer.observe(el);
    return () => observer.disconnect();
  }, [target, duration]);

  return (
    <div ref={ref} className="font-heading text-[44px] font-bold text-accent leading-none">
      {count}{suffix}
    </div>
  );
}

/* ─── 主组件 ─── */
export function Showcase({ onEnter }: { onEnter?: () => void }) {
  const [scrolled, setScrolled] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isFirstTime, setIsFirstTime] = useState(() => !localStorage.getItem('app-password'));
  const [setupPassword, setSetupPassword] = useState('');
  const [setupConfirm, setSetupConfirm] = useState('');

  function handleEnter() {
    setShowLogin(true);
    setLoginError('');
    setPassword('');
  }

  function handleLogin() {
    const stored = localStorage.getItem('app-password');
    if (!stored) {
      if (setupPassword.length < 4) { setLoginError('密码至少4位'); return; }
      if (setupPassword !== setupConfirm) { setLoginError('两次密码不一致'); return; }
      localStorage.setItem('app-password', setupPassword);
      sessionStorage.setItem('session', 'active');
      setIsFirstTime(false);
      setShowLogin(false);
      if (onEnter) onEnter();
      return;
    }
    if (password === stored) {
      sessionStorage.setItem('session', 'active');
      setShowLogin(false);
      if (onEnter) onEnter();
    } else {
      setLoginError('密码错误');
      setPassword('');
    }
  }

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 60);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  const iconMap: Record<string, React.ElementType> = {
    Brain, Search, Users, Flame, Telescope, ClipboardCheck, Eye, Calendar,
    TestTubes, TrendingUp, Dna, Palette, Network, ScanSearch, PenLine, Mic,
    BookOpen, Wand2, Lightbulb, FileSearch, Bot, Timer, Keyboard, Moon,
    Download, Settings, GitBranch, Globe, Headphones, Rocket, Star, Zap,
  };

  return (
    <div className="min-h-screen bg-paper text-ink font-[family-name:var(--font-ui)]">
      {/* Nav */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'bg-card/90 backdrop-blur border-b border-border shadow-sm' : 'bg-transparent'
      }`}>
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-heading text-xl font-bold tracking-tight flex items-center gap-1.5">
            <Sparkles size={18} className="text-accent" />
            <span className="text-accent">灵墨</span>
            <span className="text-xs text-ink-muted font-normal hidden sm:inline">AI 创作伴侣</span>
          </span>
          <div className="flex items-center gap-3">
            <a href="#features" className="text-sm text-ink-muted hover:text-ink transition-colors hidden sm:inline">功能</a>
            <a href="#pipeline" className="text-sm text-ink-muted hover:text-ink transition-colors hidden sm:inline">管线</a>
            <a href="#how" className="text-sm text-ink-muted hover:text-ink transition-colors hidden sm:inline">工作流</a>
            <button onClick={handleEnter}
              className="relative text-sm px-5 py-2.5 rounded-xl bg-accent text-white hover:bg-accent-hover transition-all font-semibold shadow-lg shadow-accent/25 hover:shadow-accent/40 hover:-translate-y-0.5 active:scale-95">
              进入后台
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-20 px-6 text-center overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-soft/40 via-paper to-purple-500/5 dark:from-accent-soft/20 dark:via-paper dark:to-purple-500/10" />
          <div className="absolute top-10 left-1/4 w-80 h-80 rounded-full blur-3xl opacity-30"
            style={{ background: 'linear-gradient(135deg, var(--color-accent), #7C3AED)', animation: 'heroBlob1 8s ease-in-out infinite' }} />
          <div className="absolute bottom-10 right-1/4 w-96 h-96 rounded-full blur-3xl opacity-25"
            style={{ background: 'linear-gradient(135deg, #8B5CF6, #3B82F6)', animation: 'heroBlob2 10s ease-in-out infinite', animationDelay: '1s' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full blur-3xl opacity-20"
            style={{ background: 'linear-gradient(135deg, #10B981, var(--color-accent))', animation: 'heroBlob3 7s ease-in-out infinite', animationDelay: '2s' }} />
        </div>

        <div className="relative max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-soft text-accent text-xs font-semibold mb-8 border border-accent/10 animate-[fadeSlideIn_0.6s_ease-out]">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            12步生成管线 · 30组灵魂矛盾 · A级质量门槛
          </div>

          <h1 className="font-heading text-[clamp(40px,8vw,72px)] leading-[1.08] font-bold mb-6 tracking-tight animate-[fadeSlideIn_0.6s_ease-out_0.1s_both]">
            用 AI 写出<span className="text-accent relative">神作
              <span className="absolute -bottom-1 left-0 right-0 h-[6px] bg-accent/20 rounded-full" />
            </span>级小说
          </h1>

          <p className="text-lg text-ink-muted max-w-xl mx-auto mb-10 leading-relaxed animate-[fadeSlideIn_0.6s_ease-out_0.2s_both]">
            不仅是续写。选择灵魂矛盾、设计角色命运、注入世界法则——<br />
            <span className="text-ink font-semibold">AI 按你的文学标准打磨每一章，不过 A 级不发布。</span>
          </p>

          <div className="flex gap-3 justify-center animate-[fadeSlideIn_0.6s_ease-out_0.3s_both]">
            <button onClick={handleEnter}
              className="px-8 py-3.5 rounded-xl bg-accent text-white hover:bg-accent-hover transition-all font-semibold text-base shadow-lg shadow-accent/25 active:scale-95">
              🚀 开始创作
            </button>
            <a href="#features"
              className="px-8 py-3.5 rounded-xl border-2 border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-all text-base font-medium">
              浏览功能 ↓
            </a>
          </div>

          <p className="text-xs text-ink-subtle mt-6">DeepSeek · OpenAI · 通义千问 · Kimi · 豆包 · 智谱 · MiniMax · 百度 · 讯飞 · Google</p>
        </div>
      </section>

      {/* Three pillars */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {HIGHLIGHTS.map((h, i) => (
            <div key={i}
              className={`group relative overflow-hidden p-6 rounded-2xl border border-border bg-gradient-to-br ${h.gradient} hover:shadow-lg hover:-translate-y-1 transition-all duration-300`}>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4 ${h.iconBg} transition-transform duration-300 group-hover:scale-110`}>
                {h.icon}
              </div>
              <h3 className="font-heading text-lg font-bold text-ink mb-2">{h.title}</h3>
              <p className="text-sm text-ink-muted leading-relaxed">{h.desc}</p>
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-accent/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </div>
          ))}
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {STATS.map(s => (
            <div key={s.label}
              className="group text-center p-6 bg-card border border-border rounded-2xl hover:border-accent/20 hover:shadow-md transition-all duration-300">
              <CountUp target={s.value} suffix={s.suffix} />
              <div className="text-sm text-ink-muted mt-2 font-medium">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-5xl mx-auto px-6 pb-20">
        <h2 className="font-heading text-[32px] font-bold text-center mb-2">四步开始创作</h2>
        <p className="text-sm text-ink-muted text-center mb-12">从零到发布，一个工具完成全流程</p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          {[
            { step: '01', icon: '⚙️', title: '配置 Key', desc: '设置页填入 DeepSeek API Key。支持10种模型提供商，新用户注册即送免费额度', color: 'from-violet-500/10 to-violet-500/5' },
            { step: '02', icon: '✍️', title: '创建小说', desc: '输入书名、题材、简介。AI自动生成简介候选和风格标签。50个章位自动创建', color: 'from-accent/10 to-accent/5' },
            { step: '03', icon: '💎', title: '注入灵魂', desc: '从30组文学矛盾中选核心追问。按金庸标准设计角色。编辑世界观法则', color: 'from-amber-500/10 to-amber-500/5' },
            { step: '04', icon: '🚀', title: '生成发布', desc: '一键生成章节，12步管线自动打磨。批量生成→质量检查→TXT导出→发布番茄', color: 'from-emerald-500/10 to-emerald-500/5' },
          ].map((s, i) => (
            <div key={i}
              className={`relative p-6 rounded-2xl border border-border bg-gradient-to-br ${s.color} hover:shadow-lg transition-all duration-300 group`}>
              <div className="text-6xl font-heading font-bold text-ink/5 absolute top-3 right-4">{s.step}</div>
              <div className="text-3xl mb-4 relative">{s.icon}</div>
              <h3 className="font-heading text-lg font-bold text-ink mb-2 relative">{s.title}</h3>
              <p className="text-sm text-ink-muted leading-relaxed relative">{s.desc}</p>
              {i < 3 && (
                <div className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 text-xl text-ink-subtle z-10">→</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline — renamed to 12 steps but showing 5 key stages */}
      <section id="pipeline" className="max-w-5xl mx-auto px-6 pb-20">
        <div className="bg-card border border-border rounded-3xl p-8 md:p-10 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-soft/20 to-transparent pointer-events-none" />
          <h2 className="font-heading text-[28px] font-bold text-center mb-2 relative">12步质量管线</h2>
          <p className="text-sm text-ink-muted text-center mb-10 relative">每章经过12道工序，关键节点不过关自动重写</p>

          <div className="relative flex flex-col md:flex-row items-center gap-4 md:gap-0">
            {[
              { name: '构思', desc: '约束压缩\n技巧选择\n批量草拟', color: 'bg-violet-50 dark:bg-violet-900/30' },
              { name: '评审', desc: '6维LLM评分\n低于0.8重写\n连续3次降级', color: 'bg-warn-soft dark:bg-amber-900/30' },
              { name: '打磨', desc: '精修润色\n去AI痕迹\n人性化改写', color: 'bg-info-soft dark:bg-sky-900/30' },
              { name: '校验', desc: '硬约束验证\n一致性检查\n伏笔回收', color: 'bg-success-soft dark:bg-emerald-900/30' },
              { name: '交付', desc: 'TTS语音生成\n成本记录\n追踪归档', color: 'bg-rose-50 dark:bg-rose-900/30' },
            ].map((g, i) => (
              <div key={g.name} className="flex md:flex-col items-center gap-3 md:gap-0 flex-1 w-full">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold shrink-0 transition-all duration-300 hover:scale-110 ${g.color}`}>
                  {i + 1}
                </div>
                <div className="md:text-center md:mt-3">
                  <div className="font-heading text-base font-bold text-ink">{g.name}</div>
                  <div className="text-[12px] text-ink-muted leading-relaxed mt-1 whitespace-pre-line">{g.desc}</div>
                </div>
                {i < 4 && (
                  <div className="text-ink-subtle text-xl md:absolute hidden md:block"
                    style={{ right: `${(4 - i) * 20}%`, top: '25%' }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section id="features" className="max-w-6xl mx-auto px-6 pb-20">
        <h2 className="font-heading text-[32px] font-bold text-center mb-2">全部功能</h2>
        <p className="text-sm text-ink-muted text-center mb-10">27+ 项专为网文作者打造的专业功能</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {FEATURES.map((f, i) => {
            const IconComp = iconMap[f.icon];
            return (
              <div key={i}
                className={`group p-5 rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${
                  f.tag ? 'bg-accent-soft/20 border-accent/15 hover:border-accent/40' : 'bg-card border-border hover:border-accent/20'
                }`}>
                <div className="flex items-start gap-3">
                  <span className="text-2xl shrink-0 text-accent">
                    {IconComp ? <IconComp size={24} /> : null}
                  </span>
                  <div className="min-w-0">
                    <h3 className="font-heading text-sm font-bold text-ink mb-1 flex items-center gap-2">
                      {f.title}
                      {f.tag && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent text-white font-medium shrink-0">{f.tag}</span>
                      )}
                    </h3>
                    <p className="text-[12px] text-ink-muted leading-relaxed">{f.desc}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-6 pb-24 text-center">
        <div className="relative rounded-3xl p-10 md:p-14 overflow-hidden bg-gradient-to-br from-accent via-accent-hover to-indigo-700">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.15),transparent_60%)] pointer-events-none" />
          <div className="relative">
            <h2 className="font-heading text-[32px] md:text-[40px] font-bold mb-3 text-white">开始写你的神作</h2>
            <p className="text-white/70 mb-8 max-w-md mx-auto text-base leading-relaxed">
              30组灵魂矛盾 · 12步质量管线 · 金庸级角色设计 · 6维LLM评审 · 35种AI痕迹检测 · 批量生成 · TXT导出
            </p>
            <button onClick={handleEnter}
              className="px-10 py-4 rounded-xl bg-white text-accent hover:bg-white/95 transition-all font-bold text-lg shadow-2xl active:scale-95">
              免费开始创作
            </button>
            <p className="text-white/50 text-xs mt-5">DeepSeek · OpenAI · 通义千问 · Kimi · 豆包 · 智谱 · 百度 · 讯飞 · MiniMax · Google</p>
          </div>
        </div>
      </section>

      {/* Login Modal */}
      {showLogin && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={() => setShowLogin(false)}>
          <div className="bg-card border border-border rounded-2xl p-8 w-[400px] max-w-[92vw] shadow-2xl animate-[fadeSlideIn_0.2s_ease-out]"
            onClick={e => e.stopPropagation()}>
            <div className="text-center mb-6">
              <Sparkles size={28} className="text-accent mx-auto" />
              <h2 className="font-heading text-xl font-bold text-ink mt-2">
                {isFirstTime ? '设置访问密码' : '登录后台'}
              </h2>
              <p className="text-sm text-ink-muted mt-1">
                {isFirstTime ? '首次使用，请设置一个密码保护你的创作' : '输入密码进入工作台'}
              </p>
            </div>

            {isFirstTime ? (
              <div className="space-y-3">
                <input type="password" value={setupPassword} onChange={e => setSetupPassword(e.target.value)}
                  placeholder="设置密码（至少4位）" onKeyDown={e => e.key === 'Enter' && handleLogin()} autoFocus
                  className="w-full rounded-lg border border-input bg-paper text-ink px-4 py-2.5 text-sm focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
                <input type="password" value={setupConfirm} onChange={e => setSetupConfirm(e.target.value)}
                  placeholder="确认密码" onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  className="w-full rounded-lg border border-input bg-paper text-ink px-4 py-2.5 text-sm focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
              </div>
            ) : (
              <input type="password" value={password} onChange={e => { setPassword(e.target.value); setLoginError(''); }}
                placeholder="输入密码" onKeyDown={e => e.key === 'Enter' && handleLogin()} autoFocus
                className="w-full rounded-lg border border-input bg-paper text-ink px-4 py-2.5 text-sm focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
            )}

            {loginError && <p className="text-xs text-destructive mt-2 text-center">{loginError}</p>}

            <button onClick={handleLogin}
              className="w-full mt-4 py-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors font-medium text-sm">
              {isFirstTime ? '设置密码并进入' : '进入后台'}
            </button>

            {!isFirstTime && (
              <button onClick={() => { if (window.confirm('确定要重置密码吗？')) { localStorage.removeItem('app-password'); setIsFirstTime(true); setPassword(''); setLoginError(''); } }}
                className="w-full mt-2 py-2 rounded-lg text-xs text-ink-subtle hover:text-destructive transition-colors">
                忘记密码？点击重置
              </button>
            )}
            <button onClick={() => setShowLogin(false)}
              className="w-full mt-1 py-2 rounded-lg text-sm text-ink-muted hover:text-ink transition-colors">
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
