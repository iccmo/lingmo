import { useState, useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { api } from 'src/lib/api';
import { waitForNovelTaskCompletion } from 'src/lib/task-status';
import type { ChapterMeta } from 'src/types';
import { AlertTriangle, Bot, ClipboardList, Microscope, Sparkles } from 'lucide-react';

interface DeepMetrics {
 showTellRatio: number;
 sentenceVariety: number;
 dialogueVariety: number;
 openingStrength: number;
 sensoryBreadth: number;
 repetitionScore: number;
 paragraphRhythm: number;
 antiAIScore: number;
 goldenLines: string[];
 infoDumpRatio: number;
 povConsistency: number;
 timelineGaps: number;
 agencyScore: number;
 costScore: number;
 toolPersonWarnings: { character: string; issue: string }[];
 bodyReactionLines: string[]; // sentences that trigger physical reader response
 unreliableDetails: string[]; // small details that seem inconsistent (delayed reveals)
 timeTraces: string[]; // environmental time markers (not explicit time jumps)
 suggestions: string[];
}

export function analyzeDeep(text: string): DeepMetrics {
 const suggestions: string[] = [];

 // ---- Show vs Tell ----
 const tellPatterns = /是|很|非常|觉得|感觉|认为|显得|似乎|好像|变得|变得很/g;
 const showPatterns = /说|做|走|看|听|闻|触|推|拉|握|抓|点头|摇头|微笑|皱眉|叹气/g;
 const tellCount = (text.match(tellPatterns) || []).length;
 const showCount = (text.match(showPatterns) || []).length;
 const showTellRatio = showCount / Math.max(1, tellCount);
 if (showTellRatio < 0.5) suggestions.push('倾向"告诉"而非"展示"——减少"很/非常/觉得"类词，用动作和细节代替形容');
 else if (showTellRatio > 2) suggestions.push('"展示"充分，描写生动，继续保持');

 // ---- Sentence variety ----
 const sentences = text.split(/[。！？!?]/).filter(s => s.trim().length > 0);
 const lengths = sentences.map(s => s.length);
 const avgLen = lengths.reduce((a, b) => a + b, 0) / Math.max(1, lengths.length);
 const variance = lengths.reduce((s, l) => s + (l - avgLen) ** 2, 0) / Math.max(1, lengths.length);
 const sentenceVariety = Math.round(Math.sqrt(variance));
 if (sentenceVariety < 15) suggestions.push('句子长度过于均匀——尝试混合长句和短句，增强节奏感');
 else if (sentenceVariety > 40) suggestions.push('句子长短变化丰富，节奏感强');

 // ---- Dialogue variety ----
 const speechVerbs = text.match(/说道|问道|答道|喊道|叫道|骂道|笑道|怒道|冷冷道|淡淡道|轻声道|大声道|回道|解释道|问道/g) || [];
 // Also check for "XX说" and "XX道" patterns
 const simpleSpeech = text.match(/[^，。！？\s]{1,3}[说道]/g) || [];
 const uniqueVerbs = new Set(speechVerbs.map(v => v.replace(/^.{0,2}/, ''))).size;
 const dialogueVariety = uniqueVerbs + (simpleSpeech.length > 5 ? 0 : 3);
 if (dialogueVariety < 4) suggestions.push('对话标签过于单调——多使用"反问/冷笑/低声/怒斥"等多样化表达');
 else if (dialogueVariety >= 8) suggestions.push('对话标签丰富，人物语言有区分度');

 // ---- Opening strength ----
 const firstPara = sentences.slice(0, 3).join('');
 let openingStrength = 50;
 if (/[？?]/.test(firstPara)) openingStrength += 15; // Starts with question
 if (/突然|猛然|忽然|瞬间/.test(firstPara)) openingStrength += 10; // Starts with action
 if (/[！!]/.test(firstPara)) openingStrength += 5;
 if (firstPara.length > 100) openingStrength += 10; // Substantial opening
 if (firstPara.length < 20) openingStrength -= 20; // Too short
 openingStrength = Math.min(100, Math.max(0, openingStrength));
 if (openingStrength < 40) suggestions.push('开头段落吸引力不足——尝试用疑问句/动作描写/悬念开头');

 // ---- Sensory breadth ----
 const sight = (text.match(/看|见|望|观|瞧|瞄|盯|瞥|红|蓝|绿|白|黑|光|暗|亮/g) || []).length;
 const sound = (text.match(/听|闻|声|响|说|喊|叫|唱|哭|笑|静|吵/g) || []).length;
 const touch = (text.match(/触|摸|碰|冷|热|凉|暖|硬|软|粗糙|光滑/g) || []).length;
 const smell = (text.match(/闻|香|臭|气味|芬芳|刺鼻/g) || []).length;
 const taste = (text.match(/尝|甜|苦|酸|辣|咸|味|吃|喝/g) || []).length;
 const senses = [sight > 0, sound > 0, touch > 0, smell > 0, taste > 0].filter(Boolean).length;
 const sensoryBreadth = senses;
 if (sensoryBreadth < 2) suggestions.push('感官描写单一——加入声音/触感/气味，让读者身临其境');
 else if (sensoryBreadth >= 4) suggestions.push('多感官描写出色，读者代入感强');

 // ---- Repetition ----
 // Find repeated phrases (3+ consecutive characters)
 const phrases = new Map<string, number>();
 for (let i = 0; i < text.length - 3; i++) {
 const phrase = text.slice(i, i + 4);
 phrases.set(phrase, (phrases.get(phrase) || 0) + 1);
 }
 let repeatCount = 0;
 for (const [, count] of phrases) {
 if (count > 3) repeatCount++;
 }
 const repetitionScore = Math.max(0, 100 - repeatCount * 2);
 if (repetitionScore < 70) suggestions.push(`检测到${repeatCount}处重复句式——尝试变换表达方式`);

 // ---- Paragraph rhythm ----
 const paragraphs = text.split('\n').filter(p => p.trim().length > 0);
 const paraLens = paragraphs.map(p => p.length);
 const paraAvg = paraLens.reduce((a, b) => a + b, 0) / Math.max(1, paraLens.length);
 const paraVar = paraLens.reduce((s, l) => s + (l - paraAvg) ** 2, 0) / Math.max(1, paraLens.length);
 const paragraphRhythm = Math.round(Math.sqrt(paraVar));
 if (paragraphRhythm < 30) suggestions.push('段落长度过于均匀——网文需要长短交替（短落=紧张，长段=舒缓）');
 else if (paragraphRhythm > 80) suggestions.push('段落长短变化丰富，阅读体验好');

 // ---- Writing style freshness (not AI detection) ----
 // NOTE: This is NOT an AI detector. It flags common patterns that make
 // writing feel formulaic — whether written by AI or human. Context-aware:
 // patterns inside dialogue quotes are excluded from detection.
 const narrationText = text.replace(/[「「""''“”].*?[」」""''""]/g, '');

 let freshness = 100;
 const formulaicPatterns: [RegExp, string, number][] = [
 [/总而言之|综上所述|值得注意的是|不可否认|毫无疑问/g, '套话词汇', 8],
 [/不仅.*而且|既.*又|一方面.*另一方面/g, '模板句式', 6],
 [/在.*的过程中|在.*的同时|随着.*的发展/g, '冗长介词', 5],
 [/让人感到|令人感到|使人感到/g, '间接感受', 5],
 [/深深地|无比地|极度地|异常地/g, '副词堆砌', 4],
 [/他的眼神中|她的目光里|他的心里/g, '模板描写', 3],
 ];
 let deductions = 0;
 const findings: string[] = [];
 for (const [pattern, label, penalty] of formulaicPatterns) {
 // Only check narration, not dialogue
 const count = (narrationText.match(pattern) || []).length;
 if (count > 0) {
 deductions += Math.min(penalty * 2, count * penalty);
 findings.push(`${label}(x${count})`);
 }
 }
 freshness = Math.max(0, 100 - deductions);
 if (freshness < 65) suggestions.push(`文风偏模板化（${findings.slice(0, 3).join('、')}）——尝试打破句式惯性`);
 else if (freshness >= 85) suggestions.push('句式多样，文风鲜活，没有明显的套话痕迹');
 else if (freshness >= 65) suggestions.push('文风基本自然，偶有套话但不影响阅读');

 // ---- POV Consistency ----
 // Detect whose perspective each paragraph is from
 const povMarkers = paragraphs.map(p => {
 const thirdPerson = p.match(/他|她|林风|苏婉/g) || [];
 const firstPerson = p.match(/我/g) || [];
 return { thirdCount: thirdPerson.length, firstCount: firstPerson.length };
 });
 let povSwitches = 0;
 let lastDominant = '';
 for (const pov of povMarkers) {
 const current = pov.thirdCount > pov.firstCount ? 'third' : 'first';
 if (lastDominant && current !== lastDominant && pov.thirdCount > 0 && pov.firstCount > 0) {
 povSwitches++;
 }
 if (pov.thirdCount > 3 || pov.firstCount > 3) lastDominant = current;
 }
 const povConsistency = Math.max(0, 100 - povSwitches * 15);
 if (povSwitches >= 3) suggestions.push(`POV切换${povSwitches}次——考虑在同一场景内保持一致的视角`);
 else if (povSwitches === 0 && paragraphs.length > 3) suggestions.push('POV保持稳定，读者不会困惑谁在叙述');

 // ---- Timeline ----
 const timeMarkers = text.match(/昨天|今天|明天|第二天|次日|三天后|一周后|一个月后|数日后|几周后|几个月后|那年|次年|当晚|当晚\/次日/g) || [];
 const timelineGaps = timeMarkers.length;
 if (timelineGaps > 10) suggestions.push('大量时间跳跃标记——确保读者能跟上时间线');
 else if (timelineGaps >= 3 && timelineGaps <= 8) suggestions.push(`时间线基本清晰（${timelineGaps}处时间标记）`);

 // ---- Protagonist agency ----
 const choiceMarkers = (text.match(/选择|决定|主动|拒绝|坚持|承担|反击|布局|设局|赌|押上|亲自|站出来|不退|不让|迎上|留下|守住/g) || []).length;
 const passiveMarkers = (text.match(/被迫|只能|不得不|只好|任由|被.*推着|听天由命|无能为力/g) || []).length;
 const agencyScore = Math.max(0, Math.min(100, 45 + choiceMarkers * 12 - passiveMarkers * 10));
 if (agencyScore < 60) suggestions.unshift('主角主动性不足——让主角在压力下做一个明确选择，并承担选择后果');
 else if (agencyScore >= 80) suggestions.unshift('主角主动性强，剧情由选择推动而不是被事件推着走');

 // ---- Cost / consequence ----
 const gainMarkers = (text.match(/获得|得到|突破|胜利|赢|成功|掌握|晋升|救下|夺回|拿到|找到|觉醒/g) || []).length;
 const costMarkers = (text.match(/代价|失去|受伤|流血|反噬|后患|追杀|暴露|牺牲|裂痕|误会|欠下|耗尽|昏迷|疼|痛|伤/g) || []).length;
 const costScore = Math.max(0, Math.min(100, 50 + Math.min(costMarkers, gainMarkers + 2) * 12 - Math.max(0, gainMarkers - costMarkers) * 10));
 if (gainMarkers > 0 && costScore < 65) suggestions.unshift('胜利代价偏轻——每次获得都要留下伤口、债务、暴露风险或关系裂痕');
 else if (costScore >= 80 && gainMarkers > 0) suggestions.unshift('代价兑现充分，爽点有后患，读者会相信胜利来之不易');

 // ---- Character Personification ----
 const toolPersonWarnings: { character: string; issue: string }[] = [];
 // Extract character names from the text (capitalized 2-3 char Chinese names)
 const charNames = [...new Set(text.match(/[一-鿿]{2,3}(?=他|她|说|道|想|看|走|来|去|站|坐)/g) || [])];
 for (const name of charNames.slice(0, 5)) {
 // Find sentences mentioning this character
 const sentencesWithChar = sentences.filter(s => s.includes(name) && s.length > 10);
 if (sentencesWithChar.length < 2) continue;
 // Check if any sentence is a "personal moment" (not purely functional)
 const hasPersonalMoment = sentencesWithChar.some(s =>
 /笑|哭|叹|沉默|犹豫|停顿|怔|愣|握|颤抖|深吸|呼出|闭眼|睁开|望|凝视|抚摸|整理|擦|喝|吃|坐|站|走|停/.test(s) &&
 !/告诉|通知|报告|汇报|说明|解释|询问|回答|答应|命令|指示|交代|布置|安排/.test(s)
 );
 if (!hasPersonalMoment) {
 const functionalCount = sentencesWithChar.filter(s =>
 /告诉|通知|报告|汇报|说明|解释|询问|回答|答应|命令|指示|交代|转交|传递/.test(s)
 ).length;
 if (functionalCount >= sentencesWithChar.length * 0.6) {
 toolPersonWarnings.push({ character: name, issue: `仅做功能性动作（传话/汇报/听命），缺少个人时刻` });
 }
 }
 }
 if (toolPersonWarnings.length > 0) {
 suggestions.push(`${toolPersonWarnings.map(c => `${c.character}：${c.issue}`).join('；')}`);
 } else if (charNames.length >= 2) {
 suggestions.push('角色均有个人时刻，不是情节的工具人');
 }

 // ---- Body-Reaction Sentences ----
 const bodyReactionLines: string[] = [];
 for (const s of sentences) {
 const t = s.trim();
 if (t.length < 10 || t.length > 150) continue;
 // Physical reactions that readers feel: stomach, breath, heart, skin
 if (/胃.*收缩|呼吸.*停|深吸|屏住|心跳.*漏|血.*凉|后背.*凉|汗毛.*竖|头皮.*麻|鼻子.*酸/.test(t)) {
 bodyReactionLines.push(t.slice(0, 60));
 }
 }
 if (bodyReactionLines.length === 0) suggestions.push('缺少让读者身体有反应的句子——加入胃收紧、呼吸停滞、汗毛竖立等身体细节');
 else if (bodyReactionLines.length >= 2) suggestions.push(`有${bodyReactionLines.length}处身体反应句，读者会感同身受`);

 // ---- Unreliable Details (delayed-reveal seeds) ----
 const unreliableDetails: string[] = [];
 for (const s of sentences) {
 const t = s.trim();
 if (t.length < 10 || t.length > 120) continue;
 // Small contradictions or details that hint at hidden meaning
 if (/数字.*不对|时间.*记错了|明明.*却|说.*但|其实|看起来.*实际上|表面.*真正/.test(t)) {
 unreliableDetails.push(t.slice(0, 60));
 }
 }
 if (unreliableDetails.length === 0 && sentences.length > 20) {
 suggestions.push('缺少不可靠细节——埋一个微小的矛盾或疑点，让读者在后面突然意识到');
 }

 // ---- Time Traces (environmental time passage) ----
 const timeTraces: string[] = [];
 for (const s of sentences) {
 const t = s.trim();
 if (t.length < 8 || t.length > 100) continue;
 // Environmental changes that mark time without stating it
 if (/花.*枯|光.*暗|茶.*凉|灰.*积|叶.*落|蜡.*尽|锈|霉|旧|褪色|斑驳/.test(t)) {
 timeTraces.push(t.slice(0, 60));
 }
 }
 if (timeTraces.length === 0 && sentences.length > 30) {
 suggestions.push('缺少无痕时间流逝——用花枯了、茶凉了、灰积了暗示时间，而非写「三天后」');
 } else if (timeTraces.length >= 1) {
 suggestions.push(`有${timeTraces.length}处环境时间痕迹，时间在缝隙里流过`);
 }

 // ---- Golden lines ----
 const goldenLines: string[] = [];
 for (const s of sentences) {
 const t = s.trim();
 if (t.length < 8 || t.length > 80) continue;
 const isGolden =
 (/不是.*而是|与其.*不如|宁愿.*也不/.test(t)) ||
 (/像|如同|宛若|仿佛.*般/.test(t) && t.length > 15) ||
 (/从来|永远|一定|绝不|必须|只有|只要.*就/.test(t) && t.length > 10) ||
 (/[！!]$/.test(t) && t.length > 10);
 if (isGolden) goldenLines.push(t.slice(0, 50));
 }

 // ---- Info-dump detection ----
 const infoDumpParas = paragraphs.filter(p => {
 const trimmed = p.trim();
 if (trimmed.length < 30) return false;
 const hasDialogue = /[「「""''“”‘’说问道答]/.test(trimmed);
 const hasAction = /[打攻击杀砍刺射爆走跑跳飞推拉]/.test(trimmed);
 return !hasDialogue && !hasAction && trimmed.length > 80;
 });
 const infoDumpRatio = Math.round((infoDumpParas.length / Math.max(1, paragraphs.length)) * 100);
 if (infoDumpRatio > 30) suggestions.push(`信息密度过高（${infoDumpRatio}%段落为纯说明）——用对话或动作场景替代部分说明`);
 else if (infoDumpRatio < 10 && paragraphs.length > 5) suggestions.push('信息展示方式合理，说明段落控制得当');

 return {
 showTellRatio: Math.round(showTellRatio * 100) / 100,
 sentenceVariety,
 dialogueVariety,
 openingStrength,
 sensoryBreadth,
 repetitionScore,
 paragraphRhythm,
 antiAIScore: freshness,
 goldenLines: goldenLines.slice(0, 3),
 infoDumpRatio,
 povConsistency,
 timelineGaps,
 agencyScore,
 costScore,
 toolPersonWarnings,
 bodyReactionLines,
 unreliableDetails,
 timeTraces,
 suggestions: suggestions.slice(0, 6),
 };
}

function scoreColor(val: number, good: number, bad: number): string {
 if (val >= good) return 'text-success';
 if (val <= bad) return 'text-destructive';
 return 'text-warn';
}

function extractDimension(suggestion: string, fallbackIndex: number): string {
 const dimMatch = suggestion.match(/建议重点提升：(.+)/) || suggestion.match(/发现.*处(.+)/) || suggestion.match(/(.+?)——/);
 return dimMatch ? dimMatch[1] : `问题${fallbackIndex + 1}`;
}

export function buildDeepRevisionCritique(chapterNum: number, metrics: DeepMetrics, suggestion: string, index = 0): { dimension: string; critique: string } {
 const dimension = extractDimension(suggestion, index);
 const directives = [
  `重写第${chapterNum}章，重点改进：${dimension}。`,
  '保持剧情主线、人物关系、已发生事实不变。',
 ];

 if (metrics.agencyScore < 60 || suggestion.includes('主动性')) {
  directives.push('补强主角主动性：必须让主角在压力下做一个清晰选择，例如拒绝退让、亲自反击、主动布局、押上关键资源，并写出他为什么承担这个选择。');
 }

 if (metrics.costScore < 65 || suggestion.includes('代价')) {
  directives.push('补强胜利代价：每次获得、突破、救下、赢下或拿到线索，都必须留下具体后果，例如受伤流血、欠债、暴露身份、被追杀、关系裂痕或后续麻烦。');
 }

 directives.push(`诊断原文：${suggestion}`);
 return { dimension, critique: directives.join('') };
}

export function DeepQuality({ novelId, chapters }: { novelId: string; chapters?: ChapterMeta[] }) {
 const [selectedCh, setSelectedCh] = useState<number | null>(null);
 const [_content, setContent] = useState('');
 const [metrics, setMetrics] = useState<DeepMetrics | null>(null);
 const [loading, setLoading] = useState(false);
 const [optimizing, setOptimizing] = useState(false);

 const gen = (chapters || []).filter(c => c.word_count > 0);

 const loadMetrics = useCallback(async (chapterNum: number) => {
 setLoading(true);
 try {
 const d = await api.novels.chapter(novelId, chapterNum);
 setContent(d.content || '');
 setMetrics(analyzeDeep(d.content || ''));
 } finally {
 setLoading(false);
 }
 }, [novelId]);

 useEffect(() => {
 if (!selectedCh) return;
 loadMetrics(selectedCh).catch(() => {});
 }, [selectedCh, loadMetrics]);

 if (gen.length < 1) return null;

 return (
 <div className="p-4 bg-card border border-border rounded-xl">
 <h3 className="font-heading text-base font-semibold text-ink mb-3"><Microscope size={12} className="inline" /> 深度质量分析</h3>
 <p className="text-[11px] text-ink-muted mb-3">
 展示/讲述比 · 主动性 · 代价兑现 · 开头力度 · 感官广度 · 重复检测
 </p>

 {/* Chapter selector */}
 <div className="flex gap-1.5 mb-4 flex-wrap">
 {gen.slice(-15).map(c => (
 <button key={c.number} onClick={() => setSelectedCh(c.number)}
 className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
 selectedCh === c.number ? 'bg-accent-soft text-accent border-accent/30' : 'border-border text-ink-muted hover:text-ink'
 }`}>
 第{c.number}章
 </button>
 ))}
 </div>

 {loading && (
 <div className="space-y-2 py-4">
 {[90, 75, 60, 85].map((w, i) => <div key={i} className="skeleton h-4 rounded" style={{ width: `${w}%` }} />)}
 </div>
 )}

 {metrics && !loading && (
 <div className="space-y-4">
 {/* Metrics grid */}
 <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
 {[
 { label: '展示/讲述比', value: metrics.showTellRatio.toFixed(1), good: 1.0, bad: 0.4, tip: '>1=展示为主，<1=讲述为主' },
 { label: '句子多样性', value: String(metrics.sentenceVariety), good: 25, bad: 12, tip: '标准差，越高越丰富' },
 { label: '对话标签', value: String(metrics.dialogueVariety), good: 6, bad: 3, tip: '独特说话动词数' },
 { label: '开头力度', value: String(metrics.openingStrength), good: 60, bad: 35, tip: '首段吸引力评分' },
 { label: '感官广度', value: `${metrics.sensoryBreadth}/5`, good: 3.5, bad: 1.5, tip: '视/听/触/嗅/味' },
 { label: '重复检测', value: String(metrics.repetitionScore), good: 85, bad: 60, tip: '100=无重复句式' },
 { label: '段落节奏', value: String(metrics.paragraphRhythm), good: 40, bad: 25, tip: '段落长度方差' },
 { label: '文风鲜活度', value: String(metrics.antiAIScore), good: 85, bad: 60, tip: '句式多样性·非AI检测' },
 { label: '信息密度', value: `${metrics.infoDumpRatio}%`, good: 20, bad: 35, tip: '纯说明段占比' },
 { label: 'POV稳定', value: String(metrics.povConsistency || 100), good: 85, bad: 55, tip: '视角切换频率' },
 { label: '时间标记', value: String(metrics.timelineGaps || 0), good: 8, bad: 15, tip: '时间跳跃次数' },
 { label: '主角主动性', value: String(metrics.agencyScore), good: 80, bad: 60, tip: '选择/反击/承担后果' },
 { label: '代价兑现', value: String(metrics.costScore), good: 80, bad: 60, tip: '收益是否伴随后患' },
 { label: '角色人化', value: metrics.toolPersonWarnings.length === 0 ? '' : `${metrics.toolPersonWarnings.length}<AlertTriangle size={12} className="text-warn inline" />`, good: 0.1, bad: 2, tip: '工具人警告数' },
 { label: '身体共鸣', value: String(metrics.bodyReactionLines.length), good: 2, bad: 0.1, tip: '读者身体有反应的句子' },
 { label: '不可靠细节', value: String(metrics.unreliableDetails.length), good: 1, bad: 0.1, tip: '延迟引爆的疑点' },
 { label: '时间痕迹', value: String(metrics.timeTraces.length), good: 1, bad: 0.1, tip: '环境暗示的时间流逝' },
 ].map(m => (
 <div key={m.label} className="p-3 rounded-lg bg-paper border border-border">
 <div className="text-[10px] text-ink-muted mb-0.5">{m.label}</div>
 <div className={`text-lg font-bold ${scoreColor(Number(m.value), m.good, m.bad)}`}>
 {m.value}
 </div>
 <div className="text-[9px] text-ink-subtle mt-0.5">{m.tip}</div>
 </div>
 ))}
 </div>

 {/* Disclaimer */}
 <div className="pt-3 border-t border-border">
 <p className="text-[9px] text-ink-subtle leading-relaxed">
 <AlertTriangle size={12} className="text-warn inline" /> <strong>文风鲜活度不是AI检测器。</strong>它只统计叙述段落中6种常见套话句式的出现频率。这些句式人类作家也会用（尤其翻译体）。低分不一定意味着「是AI写的」，高分也不等于「一定不是AI」。把它当作风格参考，而非真伪判断。
 </p>
 </div>

 {/* Tool person warnings */}
 {metrics.toolPersonWarnings.length > 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-warn mb-2"><AlertTriangle size={12} className="text-warn inline" /> 工具人警告</p>
 <div className="space-y-1">
 {metrics.toolPersonWarnings.map((w, i) => (
 <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-warn-soft/30 border border-amber-100 dark:border-amber-900/30 text-[10px]">
 <span><Bot size={12} className="inline" /></span>
 <div>
 <span className="text-ink font-medium">{w.character}</span>
 <span className="text-ink-muted ml-1">{w.issue}</span>
 </div>
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Body reaction lines */}
 {metrics.bodyReactionLines.length > 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-ink mb-2">🫀 身体反应句</p>
 {metrics.bodyReactionLines.map((l, i) => (
 <p key={i} className="text-[10px] text-success leading-relaxed mb-1">「{l}」</p>
 ))}
 </div>
 )}
 {metrics.bodyReactionLines.length === 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-[10px] text-warn"><AlertTriangle size={12} className="text-warn inline" /> 无身体反应句——读者缺少生理共鸣</p>
 </div>
 )}

 {/* Unreliable details */}
 {metrics.unreliableDetails.length > 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-ink mb-2">🪤 不可靠细节</p>
 {metrics.unreliableDetails.map((l, i) => (
 <p key={i} className="text-[10px] text-purple-600 dark:text-purple-400 leading-relaxed mb-1">「{l}」</p>
 ))}
 </div>
 )}

 {/* Time traces */}
 {metrics.timeTraces.length > 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-ink mb-2">⏳ 无痕时间流逝</p>
 {metrics.timeTraces.map((l, i) => (
 <p key={i} className="text-[10px] text-info leading-relaxed mb-1">「{l}」</p>
 ))}
 </div>
 )}

 {/* Golden lines */}
 {metrics.goldenLines.length > 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-ink mb-2"><Sparkles size={12} className="inline" /> 金句摘录</p>
 <div className="space-y-1">
 {metrics.goldenLines.map((line, i) => (
 <div key={i} className="p-2 rounded-lg bg-accent-soft/30 border border-accent/10 text-xs text-ink italic leading-relaxed">
 「{line}」
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Suggestions */}
 {metrics.suggestions.length > 0 && (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-ink mb-2"><ClipboardList size={12} className="inline" /> 改进建议</p>
 <div className="space-y-1.5">
 {metrics.suggestions.map((s, i) => (
 <div key={i} className={`flex items-start gap-2 text-[11px] p-2 rounded-lg ${
 s.includes('出色') || s.includes('丰富') || s.includes('继续保持')
 ? 'bg-success-soft/50 dark:bg-emerald-900/10 border border-emerald-100 dark:border-emerald-900/30 text-success '
 : 'bg-warn-soft/50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/30 text-amber-700 dark:text-amber-300 '
 }`}>
 <span className="shrink-0">{s.includes('出色') || s.includes('丰富') ? '' : ''}</span>
 <span>{s}</span>
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Auto-optimize button */}
 {selectedCh && metrics && (() => {
 const weakItems = metrics.suggestions.filter(s => !s.includes('出色') && !s.includes('丰富') && !s.includes('继续保持'));
 if (weakItems.length === 0) return null;
 return (
 <div className="pt-3 border-t border-border">
 <p className="text-xs font-semibold text-ink mb-2">🔧 一键优化</p>
 <p className="text-[10px] text-ink-muted mb-2">
 基于检测结果，针对性重写本章。每次优化一个维度。
 </p>
 <div className="space-y-1.5">
 {weakItems.slice(0, 3).map((s, i) => {
 const { dimension: dim, critique: dir } = buildDeepRevisionCritique(selectedCh, metrics, s, i);
 return (
 <button key={i} onClick={async () => {
 const ch = gen.find(c => c.number === selectedCh);
 if (!ch) return;
 try {
 setOptimizing(true);
 await api.novels.reviseChapter(novelId, selectedCh, dir);
 toast.info(`已触发第${selectedCh}章「${dim.slice(0,15)}」修订，等待完成...`);
 await waitForNovelTaskCompletion(
 () => api.novels.generationStatus(novelId),
 { intervalMs: 2000, maxPolls: 180 },
 );
 await loadMetrics(selectedCh);
 toast.success(`第${selectedCh}章修订完成，深度分析已刷新`);
 } catch (e) {
 toast.error('优化失败: ' + (e as Error).message);
 } finally {
 setOptimizing(false);
 }
 }}
 disabled={optimizing}
 className="w-full text-left text-[10px] px-3 py-2 rounded-lg bg-accent-soft/20 border border-accent/10 hover:bg-accent-soft/30 transition-colors flex items-center gap-2">
 <span className="text-accent">🔧</span>
 <span className="text-ink flex-1">{dim.slice(0, 60)}</span>
 <span className="text-ink-subtle">{optimizing ? '修订中...' : '优化 →'}</span>
 </button>
 );
 })}
 </div>
 </div>
 );
 })()}
 </div>
 )}
 </div>
 );
}
