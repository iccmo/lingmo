import { useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';

const FEATURES = [
  { icon: '🧠', title: '5-Gate 质量管线', desc: '构思→草拟→评审→润色→质检，每章经五道关卡淘汰，不达标自动重写', tag: '核心' },
  { icon: '🔍', title: 'LLM 质量评审', desc: '6维度+题材特化：钩子强度·节奏感·对话自然度·可读性·反派压迫感·追读意愿，0-1精确到百分位', tag: '核心' },
  { icon: '👤', title: 'AI 读者角色扮演', desc: '4种读者人格（老书虫/追更狂魔/女频编辑/硬核设定控）用自然语言给你的章节写读后感', tag: '核心' },
  { icon: '🔥', title: '段落级读者热力图', desc: '逐段预测读者反应：🔥兴奋/🤔好奇/😂爆笑/😢感动/😌舒适/😰紧张，彩色标注', tag: '核心' },
  { icon: '🔮', title: '伏笔追踪系统', desc: '自动检测已埋/已回收伏笔，超过10章未回收触发警告，确保长篇自洽', tag: '核心' },
  { icon: '📋', title: '番茄算法检查', desc: '发布前六项检查：钩子·标题·长度·质量·对话·题材，一键评估发布就绪度', tag: '核心' },
  { icon: '📱', title: '手机阅读模拟', desc: '5种真机尺寸（iPhone SE→Pro Max→Pixel 7→iPad Mini），字体调节·暗色模式·滑动翻页', tag: '核心' },
  { icon: '📅', title: '智能发布策略', desc: '自动识别最强章，推荐最佳发布时间和节奏，适配番茄/起点/纵横三大平台', tag: '核心' },
  { icon: '🔬', title: '开局 A/B 测试', desc: '金庸/余华/爆款网文三种声音生成不同开头，并排对比质量分+钩子+预览', tag: '核心' },
  { icon: '📈', title: '情感弧线可视化', desc: 'SVG双线图：张力曲线+钩子曲线，自动标注高潮点和过渡点，定位读者流失风险', tag: '' },
  { icon: '👁️', title: '读者留存模拟', desc: '逐章计算流失概率（质量低-40%·钩子弱-15%·字数少-20%），预测最终留存率', tag: '' },
  { icon: '🧬', title: '章节DNA对比', desc: '六维雷达图：节奏/对话/描写/动作/情感/钩子，任意两章并排对比差异百分比', tag: '' },
  { icon: '🎭', title: '情绪配方分析', desc: '每章拆解六种情绪占比（紧张·好奇·爽感·感动·幽默·恐惧），检测情绪单一风险', tag: '' },
  { icon: '🕸️', title: '情节网络图', desc: '力导向角色关系图谱，点击角色显示所有关系+关联伏笔，100章长篇的叙事地图', tag: '' },
  { icon: '🔍', title: '反套路检测器', desc: '8种网文套路自动检测，每项给出反套路建议。含作者DNA报告（强项/弱项/适合题材）', tag: '' },
  { icon: '✏️', title: '章节内联编辑', desc: '阅读→编辑无缝切换，展开章节直接修改正文并保存，无需跳转到独立编辑器', tag: '' },
  { icon: '🎭', title: '14种作家声音', desc: '金庸·余华·刘慈欣·东野圭吾·海明威·莫言·张爱玲·鲁迅·村上春树·马尔克斯·古龙·汪曾祺·爆款网文·文学实验', tag: '' },
  { icon: '📚', title: '24种题材风格', desc: '玄幻/都市/悬疑/科幻/官场/仙侠/武侠/系统流/无限流/女频/历史/游戏...每种独立风格配置', tag: '' },
  { icon: '📝', title: '智能标题优化', desc: '章节标题评分+质量趋势+字数走向。低分标题hover显示AI建议的替代标题', tag: '' },
  { icon: '📌', title: '章节分组管理', desc: '自动识别「第X卷/部/篇」标记，卷间可折叠。章节审批流转（已审/待改/草稿）+置顶', tag: '' },
  { icon: '🎣', title: '一键智能续写', desc: '自动读取上章结尾钩子注入上下文，也支持手动输入8种快捷方向（打斗/感情/反转...）', tag: '' },
  { icon: '💡', title: '写困救援', desc: '卡文时一键获取3条具体剧情方向建议（基于你的角色和伏笔，非泛泛建议）', tag: '' },
  { icon: '🔍', title: '全文搜索', desc: 'Ctrl+Shift+F 跨所有章节正文搜索，结果按章节分组+匹配片段预览+点击直达', tag: '' },
  { icon: '🤖', title: '全自动日更', desc: '一键启动自动模式，后台持续生成章节。配合发布流程，真正做到无人值守日更', tag: '' },
  { icon: '⏱️', title: '专注冲刺计时器', desc: 'Pomodoro风格写作计时器，15/25/45/60分钟可选，实时速率追踪，完成提醒', tag: '' },
  { icon: '⌨️', title: '极速操作', desc: 'Ctrl+K 命令面板·Ctrl+G 生成·J/K 浏览章节·Ctrl+Shift+F 全文搜索·? 快捷键速查', tag: '' },
  { icon: '🌓', title: '深色模式', desc: '跟随系统自动切换明暗主题，全局0.3s平滑过渡动画，自定义滚动条。首次访问无需手动设置', tag: '' },
  { icon: '📤', title: 'EPUB 导出', desc: '一键导出完整小说为 EPUB 电子书，带封面+目录+样式，可直接上传 Kindle 或阅读平台', tag: '' },
  { icon: '🔐', title: '密码保护', desc: '浏览器本地密码登录，关闭标签页自动退出。无需服务器，你的创作只有你能访问', tag: '' },
];

const STATS = [
  { value: 14, suffix: '', label: '作家声音' },
  { value: 24, suffix: '', label: '题材风格' },
  { value: 29, suffix: '+', label: '专业功能' },
  { value: 5, suffix: '关', label: '质量保证' },
];

/* Animated counter */
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

export function Showcase({ onEnter }: { onEnter?: () => void }) {
  const navigate = useNavigate();
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
      // First time: set password
      if (setupPassword.length < 4) { setLoginError('密码至少4位'); return; }
      if (setupPassword !== setupConfirm) { setLoginError('两次密码不一致'); return; }
      localStorage.setItem('app-password', setupPassword);
      sessionStorage.setItem('session', 'active');
      setIsFirstTime(false);
      setShowLogin(false);
      if (onEnter) onEnter();
      return;
    }
    // Verify password
    if (password === stored) {
      sessionStorage.setItem('session', 'active');
      setShowLogin(false);
      if (onEnter) onEnter();
    } else {
      setLoginError('密码错误');
      setPassword('');
    }
  }

  function handleLogout() {
    sessionStorage.removeItem('session');
  }

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 60);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  return (
    <div className="min-h-screen bg-paper text-ink font-[family-name:var(--font-ui)]">
      {/* Nav */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'bg-card/90 backdrop-blur border-b border-border shadow-sm' : 'bg-transparent'
      }`}>
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="font-heading text-xl font-bold tracking-tight">
            ✧ <span className="text-accent">小说工坊</span>
          </span>
          <div className="flex items-center gap-3">
            <a href="#features" className="text-sm text-ink-muted hover:text-ink transition-colors hidden sm:inline">功能</a>
            <a href="#how" className="text-sm text-ink-muted hover:text-ink transition-colors hidden sm:inline">工作流</a>
            <button onClick={handleEnter}
              className="text-sm px-4 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-all font-medium shadow-sm hover:shadow-md">
              进入后台
            </button>
          </div>
        </div>
      </nav>

      {/* Hero with animated particles */}
      <section className="relative pt-32 pb-20 px-6 text-center overflow-hidden">
        {/* Animated background particles */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/4 w-72 h-72 bg-accent/8 rounded-full blur-3xl animate-pulse" style={{animationDuration: '4s'}} />
          <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-purple-500/8 rounded-full blur-3xl animate-pulse" style={{animationDuration: '5s', animationDelay: '1s'}} />
          <div className="absolute top-1/3 left-1/2 w-48 h-48 bg-emerald-500/8 rounded-full blur-3xl animate-pulse" style={{animationDuration: '3s', animationDelay: '2s'}} />
          {/* Floating dots */}
          {[...Array(12)].map((_, i) => (
            <div key={i} className="absolute w-1 h-1 rounded-full bg-accent/20"
              style={{
                left: `${10 + (i * 7) % 80}%`,
                top: `${10 + (i * 13) % 80}%`,
                animation: `fadeSlideIn ${2 + (i % 3)}s ease-in-out infinite`,
                animationDelay: `${i * 0.3}s`,
              }} />
          ))}
        </div>

        <div className="relative max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-soft text-accent text-xs font-semibold mb-8 border border-accent/10">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            30组灵魂矛盾 · A级质量门槛 · 全配置注入生成
          </div>

          <h1 className="font-heading text-[clamp(40px,8vw,72px)] leading-[1.08] font-bold mb-6 tracking-tight">
            用 AI 写出<span className="text-accent relative">
              神作
              <span className="absolute -bottom-1 left-0 right-0 h-[6px] bg-accent/20 rounded-full" />
            </span>级小说
          </h1>

          <p className="text-lg text-ink-muted max-w-xl mx-auto mb-10 leading-relaxed">
            不仅是 AI 续写。选择灵魂矛盾、设计角色命运、注入世界法则——<br/>
            <span className="text-ink font-semibold">AI 按你的文学标准打磨每一章，不过 A 级不发布。</span>
          </p>

          <div className="flex gap-3 justify-center">
            <button onClick={handleEnter}
              className="px-8 py-3.5 rounded-xl bg-accent text-white hover:bg-accent-hover transition-all font-semibold text-base shadow-lg shadow-accent/25 btn-generate active:scale-95">
              🚀 开始创作
            </button>
            <a href="#features"
              className="px-8 py-3.5 rounded-xl border-2 border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-all text-base font-medium">
              浏览功能 ↓
            </a>
          </div>

          <p className="text-xs text-ink-subtle mt-6">30组灵魂矛盾 · A级质量门槛 · DeepSeek / OpenAI / 通义千问</p>
        </div>
      </section>

      {/* Stats with animation */}
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
        <h2 className="font-heading text-[32px] font-bold text-center mb-2">三步开始创作</h2>
        <p className="text-sm text-ink-muted text-center mb-12">从零到发布，比想象中更简单</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { step: '01', icon: '⚙️', title: '配置 API Key', desc: '在设置页填入 DeepSeek API Key，新用户免费500万tokens。也支持OpenAI、通义千问等', color: 'from-violet-500/10 to-violet-500/5' },
            { step: '02', icon: '✍️', title: '创建小说', desc: '输入书名、题材、一句话简介。AI自动构建世界观、角色体系、势力格局和章节大纲', color: 'from-accent/10 to-accent/5' },
            { step: '03', icon: '⚡', title: '生成 & 发布', desc: '一键生成章节，5道质量关卡自动打磨。满意后发布到番茄小说平台，开始赚取收益', color: 'from-emerald-500/10 to-emerald-500/5' },
          ].map((s, i) => (
            <div key={i}
              className={`relative p-6 rounded-2xl border border-border bg-gradient-to-br ${s.color} hover:shadow-lg transition-all duration-300 group`}>
              <div className="text-6xl font-heading font-bold text-ink/5 absolute top-3 right-4">{s.step}</div>
              <div className="text-3xl mb-4 relative">{s.icon}</div>
              <h3 className="font-heading text-lg font-bold text-ink mb-2 relative">{s.title}</h3>
              <p className="text-sm text-ink-muted leading-relaxed relative">{s.desc}</p>
              {i < 2 && (
                <div className="hidden md:block absolute -right-4 top-1/2 -translate-y-1/2 text-2xl text-ink-subtle z-10">→</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="bg-card border border-border rounded-3xl p-8 md:p-10 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-soft/20 to-transparent pointer-events-none" />
          <h2 className="font-heading text-[28px] font-bold text-center mb-2 relative">五道质量关卡</h2>
          <p className="text-sm text-ink-muted text-center mb-10 relative">每一章必须通过全部关卡，不达标自动重写</p>

          <div className="relative flex flex-col md:flex-row items-center gap-4 md:gap-0">
            {[
              { icon: '💡', name: '构思', desc: '分析前文剧情\n构思章节走向' },
              { icon: '✍️', name: '草拟', desc: '生成正文初稿\n多版本候选对比' },
              { icon: '🔬', name: '评审', desc: '6维LLM评分\n低于0.5分重写' },
              { icon: '✨', name: '润色', desc: '去AI味处理\n提升文学质感' },
              { icon: '🛡️', name: '质检', desc: '事实核查纠错\n终审放行发布' },
            ].map((g, i) => (
              <div key={g.name} className="flex md:flex-col items-center gap-3 md:gap-0 flex-1 w-full">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center text-3xl shrink-0 transition-all duration-300 hover:scale-110 ${
                  i === 0 ? 'bg-violet-50 dark:bg-violet-900/30' :
                  i === 1 ? 'bg-sky-50 dark:bg-sky-900/30' :
                  i === 2 ? 'bg-amber-50 dark:bg-amber-900/30' :
                  i === 3 ? 'bg-emerald-50 dark:bg-emerald-900/30' :
                  'bg-rose-50 dark:bg-rose-900/30'
                }`}>
                  {g.icon}
                </div>
                <div className="md:text-center md:mt-3">
                  <div className="font-heading text-base font-bold text-ink">{g.name}</div>
                  <div className="text-[12px] text-ink-muted leading-relaxed mt-1 whitespace-pre-line">{g.desc}</div>
                </div>
                {i < 4 && (
                  <div className="text-ink-subtle text-xl md:absolute md:right-0 md:top-1/2 md:-translate-y-1/2 hidden md:block"
                    style={{ right: `${(4 - i) * 20}%` }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-6xl mx-auto px-6 pb-20">
        <h2 className="font-heading text-[32px] font-bold text-center mb-2">全部功能</h2>
        <p className="text-sm text-ink-muted text-center mb-10">29+ 项专为网文作者打造的专业功能</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {FEATURES.map((f, i) => (
            <div key={i}
              className={`group p-5 rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${
                f.tag ? 'bg-accent-soft/20 border-accent/15 hover:border-accent/40' : 'bg-card border-border hover:border-accent/20'
              }`}>
              <div className="flex items-start gap-3">
                <span className="text-2xl shrink-0">{f.icon}</span>
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
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="max-w-3xl mx-auto px-6 pb-24 text-center">
        <div className="relative rounded-3xl p-10 md:p-14 overflow-hidden bg-gradient-to-br from-accent via-accent-hover to-indigo-700">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.15),transparent_60%)] pointer-events-none" />
          <div className="relative">
            <h2 className="font-heading text-[32px] md:text-[40px] font-bold mb-3 text-white">开始写你的神作</h2>
            <p className="text-white/70 mb-8 max-w-md mx-auto text-base leading-relaxed">
              AI 读者角色扮演 · 段落热力图 · 反套路检测 · 伏笔追踪 · 情节网络图 · 章节DNA对比 · 情绪配方 · 留存模拟 · 手机预览 · 发布策略
            </p>
            <button onClick={handleEnter}
              className="px-10 py-4 rounded-xl bg-white text-accent hover:bg-white/95 transition-all font-bold text-lg shadow-2xl active:scale-95">
              ⚡ 免费开始创作
            </button>
            <p className="text-white/50 text-xs mt-5">29+ 专业功能 · 14作家声音 · 24题材风格 · DeepSeek / OpenAI / 通义千问</p>
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
              <span className="text-3xl">✧</span>
              <h2 className="font-heading text-xl font-bold text-ink mt-2">
                {isFirstTime ? '设置访问密码' : '登录后台'}
              </h2>
              <p className="text-sm text-ink-muted mt-1">
                {isFirstTime ? '首次使用，请设置一个密码保护你的创作' : '输入密码进入工作台'}
              </p>
            </div>

            {isFirstTime ? (
              <div className="space-y-3">
                <input
                  type="password"
                  value={setupPassword}
                  onChange={e => setSetupPassword(e.target.value)}
                  placeholder="设置密码（至少4位）"
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  autoFocus
                  className="w-full rounded-lg border border-input bg-paper text-ink px-4 py-2.5 text-sm
                    focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
                <input
                  type="password"
                  value={setupConfirm}
                  onChange={e => setSetupConfirm(e.target.value)}
                  placeholder="确认密码"
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  className="w-full rounded-lg border border-input bg-paper text-ink px-4 py-2.5 text-sm
                    focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
              </div>
            ) : (
              <input
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); setLoginError(''); }}
                placeholder="输入密码"
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                autoFocus
                className="w-full rounded-lg border border-input bg-paper text-ink px-4 py-2.5 text-sm
                  focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all" />
            )}

            {loginError && (
              <p className="text-xs text-red-500 mt-2 text-center">{loginError}</p>
            )}

            <button onClick={handleLogin}
              className="w-full mt-4 py-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors font-medium text-sm">
              {isFirstTime ? '🔐 设置密码并进入' : '进入后台'}
            </button>

            {!isFirstTime && (
              <button onClick={() => {
                if (confirm('确定要重置密码吗？这将清除当前密码，你可以设置新密码。')) {
                  localStorage.removeItem('app-password');
                  setIsFirstTime(true);
                  setPassword('');
                  setLoginError('');
                }
              }}
                className="w-full mt-2 py-2 rounded-lg text-xs text-ink-subtle hover:text-red-500 transition-colors">
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

      {/* Footer */}
      <footer className="border-t border-border py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-[12px] text-ink-subtle">
          <div className="flex items-center gap-2">
            <span className="font-heading text-base font-semibold text-ink">✧ 小说工坊</span>
            <span className="text-ink-subtle">AI 写作引擎</span>
          </div>
          <div className="flex gap-6">
            <span>番茄小说适配</span>
            <span>起点中文网适配</span>
            <span>纵横中文网适配</span>
          </div>
          <span>© 2026 Novel Workshop</span>
        </div>
      </footer>
    </div>
  );
}
