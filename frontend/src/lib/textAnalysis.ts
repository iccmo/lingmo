/**
 * Client-side text analysis — density & force field (文档 §28-29).
 * Zero API calls. Runs in browser.
 */

export interface DensityReport {
  totalChars: number;
  expectationCount: number;
  density: number;        // expectations per 100 chars
  perParagraph: Array<{ chars: number; expectations: number; density: number }>;
}

export interface ForceReport {
  compression: number;    // 0-1: historical weight per char
  tension: number;        // 0-1: unsatisfied expectations
  torque: number;         // 0-1: expectation reversals
  resonance: number;      // 0-1: repeated elements significance
}

/**
 * Emotional unit density analysis (§28).
 * Counts expectation signals: but/yet/however (contradiction),
 * question marks (uncertainty), ellipsis (trailing), exclamation (surprise),
 * negation (reversal).
 */
export function analyzeDensity(text: string): DensityReport {
  const paragraphs = text.split(/\n\n+/).filter(p => p.trim());
  let totalExpectations = 0;

  const perParagraph = paragraphs.map(p => {
    const trimmed = p.trim();
    const chars = trimmed.length;
    // Count expectation-creating patterns
    const contradictions = (trimmed.match(/但是|可是|然而|却|不过|只是|but|yet|however/gi) || []).length;
    const questions = (trimmed.match(/[？?]/g) || []).length;
    const suspensions = (trimmed.match(/…|\.\.\./g) || []).length;
    const surprises = (trimmed.match(/[！!]/g) || []).length;
    const negations = (trimmed.match(/不是|没有|不会|不能|从未|not|never|no/gi) || []).length;

    const expectations = contradictions + questions + suspensions + surprises + negations;
    totalExpectations += expectations;

    return {
      chars,
      expectations,
      density: chars > 0 ? +(expectations / (chars / 100)).toFixed(1) : 0,
    };
  });

  return {
    totalChars: text.length,
    expectationCount: totalExpectations,
    density: text.length > 0 ? +(totalExpectations / (text.length / 100)).toFixed(1) : 0,
    perParagraph,
  };
}

/**
 * Four-force field analysis (§29).
 */
export function analyzeForces(text: string, historyWeight = 0): ForceReport {
  const sentences = text.split(/[。！？.!?\n]+/).filter(s => s.trim());

  // Compression: historical weight per meaningful unit
  const compression = Math.min(1, (historyWeight || sentences.length * 0.02) / Math.max(1, sentences.length * 0.1));

  // Tension: unsatisfied expectations
  let openQuestions = 0;
  let resolved = 0;
  for (const s of sentences) {
    if (s.match(/[？?]/)) openQuestions++;
    if (s.match(/原来|终于|原来如此|所以|于是|因此|是因为/)) resolved++;
  }
  const tension = Math.min(1, openQuestions / Math.max(1, openQuestions + resolved + 1));

  // Torque: expectation reversals
  const reversals = (text.match(/但是|可是|然而|却|不过|没想到|谁知|不料|竟然|居然|but|yet|however|unexpectedly/gi) || []).length;
  const torque = Math.min(1, reversals / Math.max(1, sentences.length * 0.1));

  // Resonance: repeated elements (2-4 char phrases appearing multiple times)
  const cleanText = text.replace(/[，。！？、；：""''「」『』\s]/g, '');
  const phrases: Record<string, number> = {};
  for (let i = 0; i < cleanText.length - 3; i++) {
    for (let len = 2; len <= 4; len++) {
      const phrase = cleanText.slice(i, i + len);
      if (phrase.length === len) {
        phrases[phrase] = (phrases[phrase] || 0) + 1;
      }
    }
  }
  const repeatedCount = Object.values(phrases).filter(c => c >= 3).length;
  const resonance = Math.min(1, repeatedCount / Math.max(1, sentences.length * 0.05));

  return { compression: +compression.toFixed(2), tension: +tension.toFixed(2), torque: +torque.toFixed(2), resonance: +resonance.toFixed(2) };
}

/**
 * Simple text quality summary combining both analyses.
 */
export function analyzeTextQuality(text: string): { density: DensityReport; forces: ForceReport; grade: string } {
  const density = analyzeDensity(text);
  const forces = analyzeForces(text);

  // Heuristic grade
  let score = 0;
  if (density.density >= 3) score += 3;
  else if (density.density >= 1.5) score += 2;
  else if (density.density >= 0.5) score += 1;

  if (forces.tension >= 0.4) score += 2;
  else if (forces.tension >= 0.2) score += 1;

  if (forces.torque >= 0.3) score += 2;
  else if (forces.torque >= 0.1) score += 1;

  if (forces.resonance >= 0.2) score += 1;

  const grade = score >= 7 ? 'S' : score >= 5 ? 'A' : score >= 3 ? 'B' : score >= 1 ? 'C' : 'D';

  return { density, forces, grade };
}

/**
 * Breathing rhythm analysis (§53).
 * Maps each sentence to its reader breathing phase.
 * [呼] = natural exhale point (meaning complete)
 * [吸] = inhale point (expectation created)
 * [悬] = suspended (meaning delayed, reader holds breath)
 */
export interface BreathPoint {
  text: string;
  phase: 'exhale' | 'inhale' | 'suspend';
  reason: string;
}

export function analyzeBreathing(text: string): BreathPoint[] {
  const sentences = text.split(/(?<=[。！？.!?])/).filter(s => s.trim());
  const points: BreathPoint[] = [];

  for (const s of sentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;

    // Natural exhale: complete statement ending with 。 or .
    if (/[。.]$/.test(trimmed) && !trimmed.match(/[？?！!]/)) {
      points.push({ text: trimmed.slice(0, 40), phase: 'exhale', reason: '意义完成' });
    }
    // Inhale: question or anticipation
    else if (/[？?]$/.test(trimmed)) {
      points.push({ text: trimmed.slice(0, 40), phase: 'inhale', reason: '制造期待' });
    }
    // Suspend: trailing, interrupted, or ends with ...
    else if (/[！!…]$/.test(trimmed) || trimmed.endsWith('…')) {
      points.push({ text: trimmed.slice(0, 40), phase: 'suspend', reason: '意义中断或延迟' });
    }
    // Suspend: starts with 但/可/却/然而
    else if (/^(但是|可是|然而|却|不过|只是|但)/.test(trimmed)) {
      points.push({ text: trimmed.slice(0, 40), phase: 'suspend', reason: '转折制造悬停' });
    }
    else {
      points.push({ text: trimmed.slice(0, 40), phase: 'exhale', reason: '默认完成' });
    }
  }

  return points;
}

/**
 * Whitespace density analysis (§55).
 * Calculates how much the reader must fill in themselves.
 * Density = (implied info count) / (explicit char count) * 100
 */
export interface WhitespaceReport {
  explicitChars: number;
  impliedCount: number;
  density: number;  // 0-100, higher = more reader participation
  assessment: string;
}

export function analyzeWhitespace(text: string): WhitespaceReport {
  const explicitChars = text.replace(/\s/g, '').length;

  // Count implied information signals
  const implications = [
    (text.match(/没说|沉默|不动|没动|没哭|没笑|没说话/g) || []).length,
    (text.match(/…/g) || []).length,
    (text.match(/[？?]/g) || []).length,
    (text.match(/但是|可是|然而|却/g) || []).length,
    (text.match(/后来|那天|当时|有一年/g) || []).length,
  ];
  
  const impliedCount = implications.reduce((a, b) => a + b, 0);
  const density = explicitChars > 0 ? Math.min(100, +(impliedCount / (explicitChars / 100)).toFixed(1)) : 0;

  let assessment: string;
  if (density < 1) assessment = '留白过少——读者参与感弱，信息太满';
  else if (density < 3) assessment = '留白适中——读者有适度参与';
  else if (density < 6) assessment = '留白丰富——读者积极脑补，负空间活跃';
  else assessment = '留白极密——注意不要让读者迷失';

  return { explicitChars, impliedCount, density, assessment };
}

/**
 * Body sense analysis (§46).
 * Counts sensory words to determine how much the reader's body engages.
 */
export interface SenseReport {
  visual: number;
  auditory: number;
  tactile: number;
  olfactory: number;
  gustatory: number;
  bodyTotal: number;
  bodyDensity: number;
  assessment: string;
}

export function analyzeBodySense(text: string): SenseReport {
  const visual = (text.match(/看|见|望|盯|瞪|瞟|瞥|观|视|光|亮|暗|黑|白|红|蓝|绿|色|彩/g) || []).length;
  const auditory = (text.match(/听|闻|声|响|音|说|道|问|答|喊|叫|吼|静|默/g) || []).length;
  const tactile = (text.match(/碰|触|摸|握|抓|按|压|推|拉|冷|热|凉|暖|烫|疼|痛|麻|痒/g) || []).length;
  const olfactory = (text.match(/闻|嗅|香|臭|气|味/g) || []).length;
  const gustatory = (text.match(/尝|吃|喝|甜|酸|苦|辣|咸|涩/g) || []).length;

  const total = visual + auditory + tactile + olfactory + gustatory;
  const chars = text.replace(/\s/g, '').length;
  const density = chars > 0 ? +(total / (chars / 100)).toFixed(1) : 0;

  let assessment: string;
  if (density > 15) assessment = '感官极密——读者身体高度参与';
  else if (density > 8) assessment = '感官丰富——读者有身体共鸣';
  else if (density > 3) assessment = '感官适中——可接受';
  else assessment = '感官稀疏——增加触觉和视觉细节可提升沉浸';

  return {
    visual, auditory, tactile, olfactory, gustatory,
    bodyTotal: total, bodyDensity: density, assessment,
  };
}

/**
 * Ambiguity precision analysis (§56).
 * Detects sentences that support multiple simultaneous interpretations.
 */
export interface AmbiguityReport {
  score: number;
  ambiguousCount: number;
  totalSentences: number;
  topAmbiguous: string[];
  assessment: string;
}

export function analyzeAmbiguity(text: string): AmbiguityReport {
  const sentences = text.split(/[。！？.!?\n]+/).filter(s => s.trim().length > 5);
  const ambiguous: string[] = [];

  for (const s of sentences) {
    let layers = 0;
    // Layer 1: can be read as literal or metaphorical
    if (s.match(/像|好像|仿佛|如同|似乎/) && s.match(/不是|没有|不会/)) layers++;
    // Layer 2: contains negation that could flip meaning
    if ((s.match(/不是|没有|不会|从未/g) || []).length >= 1) layers++;
    // Layer 3: subject could refer to multiple entities
    if (s.match(/她|他|它|他们|她们|那个人|这个人/) && !s.match(/林尘|秦默|慕听澜/)) layers++;
    // Layer 4: open-ended question or trailing
    if (s.match(/[？?…]$/)) layers++;

    if (layers >= 2) ambiguous.push(s.slice(0, 60));
  }

  const score = sentences.length > 0 ? +(ambiguous.length / sentences.length).toFixed(2) : 0;

  return {
    score,
    ambiguousCount: ambiguous.length,
    totalSentences: sentences.length,
    topAmbiguous: ambiguous.slice(0, 5),
    assessment: score > 0.3 ? '歧义丰富——文本层次深' : score > 0.1 ? '歧义适中' : '文本过于直白，增加多层解读空间',
  };
}

/**
 * Emotional lending balance (§70).
 * Tracks emotional impact density to avoid burnout.
 */
export interface EmotionLendingReport {
  impactCount: number;
  impactDensity: number;
  distribution: 'sparse' | 'balanced' | 'dense' | 'overwhelming';
  assessment: string;
}

export function analyzeEmotionLending(text: string): EmotionLendingReport {
  const chars = text.replace(/\s/g, '').length;
  
  // Detect emotional impact signals
  const impacts = [
    ...(text.match(/死|亡|杀|血|伤|痛|哭|泪|恨|悔/g) || []),
    ...(text.match(/抱|握|碰|触|拉|推/g) || []),
    ...(text.match(/说|道|问|答|喊|叫/g) || []),
  ];

  const density = chars > 0 ? +(impacts.length / (chars / 100)).toFixed(1) : 0;
  
  let distribution: EmotionLendingReport['distribution'];
  if (density < 1) distribution = 'sparse';
  else if (density < 5) distribution = 'balanced';
  else if (density < 10) distribution = 'dense';
  else distribution = 'overwhelming';

  return {
    impactCount: impacts.length,
    impactDensity: density,
    distribution,
    assessment: distribution === 'overwhelming' ? '情感冲击过密——读者可能麻木'
      : distribution === 'dense' ? '情感密集——注意间隔恢复'
      : distribution === 'balanced' ? '情感节奏良好'
      : '情感稀疏——可加强',
  };
}

/**
 * Rhetoric precision analysis (§71).
 * Detects generic words that could be replaced with more precise alternatives.
 */
export interface RhetoricReport {
  genericWords: Array<{word: string; count: number; suggestion: string}>;
  precisionScore: number;
  assessment: string;
}

export function analyzeRhetoricPrecision(text: string): RhetoricReport {
  const genericPatterns: Array<{regex: RegExp; word: string; suggestion: string}> = [
    { regex: /很美|很漂亮|很好看/g, word: '很美/很漂亮', suggestion: '用具体细节替代——"她眼角有颗痣，笑起来先弯左边嘴角"' },
    { regex: /很生气|非常愤怒/g, word: '很生气', suggestion: '用身体反应替代——"他把茶杯放在桌上。很轻。但指节是白的"' },
    { regex: /\b说道\b/g, word: '说道', suggestion: '删掉"道"——"说"就够了' },
    { regex: /\b问道\b/g, word: '问道', suggestion: '删掉"道"——"问"就够了' },
    { regex: /\b答道\b/g, word: '答道', suggestion: '删掉"道"——"答"就够了' },
    { regex: /\b有些\b/g, word: '有些', suggestion: '删掉——直接写后面的形容词' },
    { regex: /\b似乎\b/g, word: '似乎', suggestion: '让读者自己判断——不要替读者加"似乎"' },
    { regex: /\b其实\b/g, word: '其实', suggestion: '删掉——不需要告诉读者这是"真相"' },
  ];

  const results: RhetoricReport['genericWords'] = [];
  for (const p of genericPatterns) {
    const matches = text.match(p.regex);
    if (matches && matches.length > 0) {
      results.push({ word: p.word, count: matches.length, suggestion: p.suggestion });
    }
  }

  const totalGeneric = results.reduce((s, r) => s + r.count, 0);
  const chars = text.replace(/\s/g, '').length;
  const precisionScore = chars > 0 ? Math.max(0, 100 - (totalGeneric / (chars / 100)) * 10) : 100;

  return {
    genericWords: results.slice(0, 8),
    precisionScore: Math.round(precisionScore),
    assessment: precisionScore >= 90 ? '用词精准' : precisionScore >= 70 ? '可进一步打磨' : '存在较多泛化用词',
  };
}

/**
 * Opening strength / Reconnection analysis (§52).
 * Analyzes how strongly the first 3 sentences pull the reader in.
 */
export interface OpeningReport {
  strength: number;
  mode: 'neutral' | 'strong' | 'extreme';
  hasBodyHook: boolean;
  hasExpectationHook: boolean;
  hasReversalHook: boolean;
  assessment: string;
}

export function analyzeOpening(text: string): OpeningReport {
  const firstThree = text.split(/[。！？.!?\n]/).slice(0, 3).join('。');
  
  // Body hook: sensory/tactile words
  const hasBodyHook = /碰|触|摸|握|冷|热|疼|痛|看|见|听|闻/.test(firstThree);
  
  // Expectation hook: question or unresolved statement
  const hasExpectationHook = /[？?…]/.test(firstThree) || /但是|可是|然而|不过/.test(firstThree);
  
  // Reversal hook: surprise or negation
  const hasReversalHook = /没有|不是|从未|竟然|居然|原来/.test(firstThree);

  const score = (hasBodyHook ? 1 : 0) + (hasExpectationHook ? 1 : 0) + (hasReversalHook ? 1 : 0);
  
  return {
    strength: score,
    mode: score >= 2 ? 'extreme' : score === 1 ? 'strong' : 'neutral',
    hasBodyHook,
    hasExpectationHook,
    hasReversalHook,
    assessment: score >= 2 ? '开头强——读者被立即拉入'
      : score === 1 ? '开头可——可加强身体或期待钩子'
      : '开头弱——试着用身体感受或未完成的动作开始',
  };
}
