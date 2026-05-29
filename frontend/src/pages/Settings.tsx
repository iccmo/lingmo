import { useEffect, useState } from 'react';
import { Card, CardContent } from 'src/components/ui/card';
import { Button } from 'src/components/ui/button';
import { Input } from 'src/components/ui/input';
import { Badge } from 'src/components/ui/badge';
import { toast } from 'sonner';
import { Download, Upload, Trash2 } from 'lucide-react';

interface Provider {
 id: string;
 name: string;
 base_url: string;
 api_key: string;
 models: string[];
 is_enabled: number;
 priority: number;
}

function maskKey(key: string): string {
 if (!key || key === '***') return '未配置';
 // Backend returns masked keys like "***399d"
 if (key.startsWith('***') && key.length >= 7) return key;
 // Full keys: show first 6 + last 4
 return key.slice(0, 6) + '••••' + key.slice(-4);
}

export function Settings() {
 const [providers, setProviders] = useState<Provider[]>([]);
 const [editing, setEditing] = useState<string | null>(null);
 const [form, setForm] = useState({ api_key: '', base_url: '' });
 const [testing, setTesting] = useState<string | null>(null);
 const [testResults, setTestResults] = useState<Record<string, { ok: boolean; error?: string; model?: string }>>({});
 const [loading, setLoading] = useState(true);
 // Film settings
 const [filmSettings, setFilmSettings] = useState({ image_provider: 'placeholder', image_api_key: '', dalle3_api_key: '', music_provider: 'ambient', suno_api_key: '', comfyui_url: 'http://127.0.0.1:8188', comfyui_checkpoint: 'sd_xl_base_1.0.safetensors', comfyui_ipadapter_model: 'ip-adapter-faceid-plusv2_sd15.bin', comfyui_lora_strength: '0.8', comfyui_steps: '25', comfyui_cfg: '7.0' });
 const [filmSaving, setFilmSaving] = useState(false);
 const [filmKeyInput, setFilmKeyInput] = useState('');
 const [dalle3KeyInput, setDalle3KeyInput] = useState('');
 const [sunoKeyInput, setSunoKeyInput] = useState('');
 // Subtitle style settings
 const [subtitleStyle, setSubtitleStyle] = useState({
 subtitle_font_size: '36',
 subtitle_font_color: '#FFFFFF',
 subtitle_bg_color: '#000000',
 subtitle_bg_opacity: '160',
 subtitle_position: 'bottom',
 });

 useEffect(() => {
 fetch('/api/providers')
 .then(r => r.json())
 .then(data => {
 setProviders(data);
 // Auto-test configured providers
 for (const p of data) {
 if (p.api_key) handleTestSilent(p);
 }
 })
 .catch(() => toast.error('加载供应商失败'))
 .finally(() => setLoading(false));
 // Fetch film settings
 fetch('/api/novels/film-settings')
 .then(r => r.json())
 .then(data => {
 setFilmSettings({ image_provider: data.image_provider || 'placeholder', image_api_key: data.image_api_key || '', dalle3_api_key: data.dalle3_api_key || '', music_provider: data.music_provider || 'ambient', suno_api_key: data.suno_api_key || '', comfyui_url: data.comfyui_url || 'http://127.0.0.1:8188', comfyui_checkpoint: data.comfyui_checkpoint || 'sd_xl_base_1.0.safetensors', comfyui_ipadapter_model: data.comfyui_ipadapter_model || 'ip-adapter-faceid-plusv2_sd15.bin', comfyui_lora_strength: data.comfyui_lora_strength || '0.8', comfyui_steps: data.comfyui_steps || '25', comfyui_cfg: data.comfyui_cfg || '7.0' });
 setSubtitleStyle({
 subtitle_font_size: data.subtitle_font_size || '36',
 subtitle_font_color: data.subtitle_font_color || '#FFFFFF',
 subtitle_bg_color: data.subtitle_bg_color || '#000000',
 subtitle_bg_opacity: data.subtitle_bg_opacity || '160',
 subtitle_position: data.subtitle_position || 'bottom',
 });
 })
 .catch(() => {});
 }, []);

 async function handleTestSilent(p: Provider) {
 try {
 const r = await fetch(`/api/providers/${p.id}/test`, { method: 'POST' });
 const d = await r.json();
 setTestResults(prev => ({ ...prev, [p.id]: d }));
 } catch {
 setTestResults(prev => ({ ...prev, [p.id]: { ok: false, error: '网络错误' } }));
 }
 }

 async function handleSave(pid: string) {
 try {
 await fetch(`/api/providers/${pid}`, {
 method: 'PUT',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ api_key: form.api_key || undefined, base_url: form.base_url }),
 });
 toast.success('配置已保存');
 setEditing(null);
 const r = await fetch('/api/providers');
 setProviders(await r.json());
 } catch (e: unknown) {
 toast.error('保存失败: ' + (e as Error).message);
 }
 }

 async function handleTest(p: Provider) {
 setTesting(p.id);
 try {
 const r = await fetch(`/api/providers/${p.id}/test`, { method: 'POST' });
 const d = await r.json();
 setTestResults(prev => ({ ...prev, [p.id]: d }));
 if (d.ok) {
 toast.success(`${p.name} 连接成功 — ${d.model || 'OK'}`);
 } else {
 toast.error(`${p.name} 连接失败: ${d.error || '未知错误'}`);
 }
 } catch (e: unknown) {
 setTestResults(prev => ({ ...prev, [p.id]: { ok: false, error: '网络错误' } }));
 toast.error('测试失败: ' + (e as Error).message);
 } finally {
 setTesting(null);
 }
 }

 function startEdit(p: Provider) {
 setEditing(p.id);
 setForm({ api_key: '', base_url: p.base_url });
 }

 async function handleFilmSave() {
 setFilmSaving(true);
 try {
 const body: Record<string, string> = { image_provider: filmSettings.image_provider, music_provider: filmSettings.music_provider };
 if (filmKeyInput) body.image_api_key = filmKeyInput;
 if (dalle3KeyInput) body.dalle3_api_key = dalle3KeyInput;
 if (sunoKeyInput) body.suno_api_key = sunoKeyInput;
 // Include subtitle style
 Object.assign(body, subtitleStyle);
 // Include ComfyUI settings
 if (filmSettings.image_provider === 'comfyui') {
 body.comfyui_url = filmSettings.comfyui_url;
 body.comfyui_checkpoint = filmSettings.comfyui_checkpoint;
 body.comfyui_ipadapter_model = filmSettings.comfyui_ipadapter_model;
 body.comfyui_lora_strength = filmSettings.comfyui_lora_strength;
 body.comfyui_steps = filmSettings.comfyui_steps;
 body.comfyui_cfg = filmSettings.comfyui_cfg;
 }
 await fetch('/api/novels/film-settings', {
 method: 'PUT',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify(body),
 });
 toast.success('影视配置已保存');
 setFilmKeyInput('');
 setDalle3KeyInput('');
 setSunoKeyInput('');
 // Refresh
 const r = await fetch('/api/novels/film-settings');
 const data = await r.json();
 setFilmSettings({ image_provider: data.image_provider || 'placeholder', image_api_key: data.image_api_key || '', dalle3_api_key: data.dalle3_api_key || '', music_provider: data.music_provider || 'ambient', suno_api_key: data.suno_api_key || '', comfyui_url: data.comfyui_url || 'http://127.0.0.1:8188', comfyui_checkpoint: data.comfyui_checkpoint || 'sd_xl_base_1.0.safetensors', comfyui_ipadapter_model: data.comfyui_ipadapter_model || 'ip-adapter-faceid-plusv2_sd15.bin', comfyui_lora_strength: data.comfyui_lora_strength || '0.8', comfyui_steps: data.comfyui_steps || '25', comfyui_cfg: data.comfyui_cfg || '7.0' });
 } catch {
 toast.error('保存失败');
 } finally {
 setFilmSaving(false);
 }
 }

 const configuredCount = providers.filter(p => p.api_key).length;

 if (loading) {
 return (
 <div className="space-y-4 page-enter">
 <div className="skeleton h-7 w-20" />
 <div className="skeleton h-5 w-48" />
 <div className="space-y-3 mt-6">
 {[1,2,3].map(i => <div key={i} className="skeleton h-32 rounded-lg" />)}
 </div>
 </div>
 );
 }

 return (
 <div className="page-enter">
 <div className="mb-8">
 <h1 className="font-heading text-[28px] font-semibold text-ink">设置</h1>
 <p className="text-sm text-ink-muted mt-1">
 管理 AI 模型供应商 · 已配置 {configuredCount}/{providers.length}
 </p>
 </div>

 {/* Global defaults */}
 <Card className="border-border mb-6 max-w-[640px]">
 <CardContent className="p-5">
 <h3 className="font-heading text-base font-semibold text-ink mb-3">默认设置</h3>
 <div className="grid grid-cols-2 gap-4">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">默认字数目标</label>
 <Input
 className="mt-1.5"
 type="number"
 defaultValue={localStorage.getItem('default-goal') || '50000'}
 onChange={e => localStorage.setItem('default-goal', e.target.value)}
 />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">默认题材</label>
 <select
 className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2"
 defaultValue={localStorage.getItem('default-genre') || '玄幻'}
 onChange={e => localStorage.setItem('default-genre', e.target.value)}>
 {['玄幻','都市','悬疑','科幻','历史','官场','仙侠','武侠','系统流','无限流'].map(g => (
 <option key={g} value={g}>{g}</option>
 ))}
 </select>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">默认 AI 模型</label>
 <select
 className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2"
 defaultValue={localStorage.getItem('default-provider') || 'deepseek'}
 onChange={e => localStorage.setItem('default-provider', e.target.value)}>
 {providers.filter(p => p.api_key).map(p => (
 <option key={p.id} value={p.id}>{p.name}</option>
 ))}
 {providers.filter(p => p.api_key).length === 0 && (
 <option value="">请先配置 API Key</option>
 )}
 </select>
 </div>
 </div>
 </CardContent>
 </Card>

 {/* Providers */}
 <h2 className="font-heading text-xl font-semibold text-ink mb-3">模型供应商</h2>
 <div className="space-y-3 max-w-[640px]">
 {providers.map(p => (
 <Card key={p.id} className={`border-border transition-all ${editing === p.id ? 'ring-1 ring-accent/30' : ''}`}>
 <CardContent className="p-4">
 <div className="flex items-center justify-between mb-2">
 <div className="flex items-center gap-3">
 {(() => {
 const tr = testResults[p.id];
 const hasKey = !!p.api_key;
 if (!hasKey) return <div className="w-2 h-2 rounded-full bg-zinc-300 dark:bg-zinc-600" />;
 if (!tr) return <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />;
 return <div className={`w-2 h-2 rounded-full ${tr.ok ? 'bg-success-soft0' : 'bg-destructive-soft0'}`} />;
 })()}
 <span className="font-heading text-base font-semibold text-ink">{p.name}</span>
 <Badge variant="outline" className="text-[10px]">{p.id}</Badge>
 {(() => {
 const tr = testResults[p.id];
 if (!p.api_key) return <Badge variant="outline" className="text-[10px] text-zinc-400">未配置</Badge>;
 if (!tr) return <Badge variant="outline" className="text-[10px] text-warn border-warn/20">检测中...</Badge>;
 if (tr.ok) return <Badge variant="outline" className="text-[10px] text-success border-success/20 ">✓ 已连接</Badge>;
 return <Badge variant="outline" className="text-[10px] text-destructive border-destructive/20 ">✗ 连接失败</Badge>;
 })()}
 </div>
 <div className="flex gap-1">
 {p.api_key && (
 <Button size="sm" variant="ghost" className="text-xs h-7"
 onClick={() => handleTest(p)} disabled={testing === p.id}>
 {testing === p.id ? '测试中...' : '🔌 测试连接'}
 </Button>
 )}
 {editing !== p.id && (
 <Button size="sm" variant="ghost" className="text-xs h-7"
 onClick={() => startEdit(p)}>
 {p.api_key ? '编辑' : '配置'}
 </Button>
 )}
 </div>
 </div>

 <div className="text-[11px] text-ink-muted space-y-0.5">
 <div className="flex gap-4">
 <span>端点: <code className="text-[11px] bg-paper px-1 rounded">{p.base_url}</code></span>
 </div>
 <div className="flex gap-4">
 <span>Key: <code className="text-[11px] bg-paper px-1 rounded">{maskKey(p.api_key)}</code></span>
 </div>
 <div className="flex gap-4">
 <span>模型: {p.models?.length ? p.models.join(', ') : '默认'}</span>
 <span>优先级: {p.priority}</span>
 </div>
 {/* Test result detail */}
 {testResults[p.id] && (
 <div className={`text-[11px] ${testResults[p.id].ok ? 'text-success' : 'text-destructive'}`}>
 {testResults[p.id].ok
 ? `测试通过 — ${testResults[p.id].model || 'OK'}`
 : `${testResults[p.id].error || '连接失败'}`
 }
 </div>
 )}
 </div>

 {editing === p.id && (
 <div className="space-y-3 mt-3 pt-3 border-t border-border">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
 API Key <span className="text-ink-subtle font-normal">（留空保持不变）</span>
 </label>
 <Input
 placeholder="sk-..."
 className="mt-1"
 type="password"
 value={form.api_key}
 onChange={e => setForm({ ...form, api_key: e.target.value })}
 />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">Base URL</label>
 <Input
 className="mt-1"
 value={form.base_url}
 onChange={e => setForm({ ...form, base_url: e.target.value })}
 />
 </div>
 <div className="flex gap-2">
 <Button size="sm" className="bg-accent hover:bg-accent-hover"
 onClick={() => handleSave(p.id)}>保存</Button>
 <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>取消</Button>
 </div>
 </div>
 )}
 </CardContent>
 </Card>
 ))}
 </div>

 {/* Film Studio settings */}
 <div className="mt-8 max-w-[640px]">
 <h2 className="font-heading text-xl font-semibold text-ink mb-3">影视制作</h2>
 <Card className="border-border">
 <CardContent className="p-5">
 <p className="text-xs text-ink-muted mb-4">
 配置 AI 画图和配乐服务。画图支持 Placeholder/SD3/DALL·E 3，配乐支持 FFmpeg ambient/Suno AI。
 </p>
 <div className="space-y-4">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">画图引擎</label>
 <select
 className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2"
 value={filmSettings.image_provider}
 onChange={e => setFilmSettings({ ...filmSettings, image_provider: e.target.value })}
 >
 <option value="placeholder">Placeholder（渐变占位图）</option>
 <option value="stability">Stability AI（SD3 真实画面）</option>
 <option value="dalle3">DALL·E 3（OpenAI 真实画面）</option>
 <option value="comfyui">ComfyUI（本地 IP-Adapter 角色一致性）</option>
 </select>
 </div>
 {filmSettings.image_provider === 'stability' && (
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
 Stability API Key
 <span className="text-ink-subtle font-normal ml-1">
 {filmSettings.image_api_key ? `当前: ${filmSettings.image_api_key}` : '未配置'}
 </span>
 </label>
 <Input
 className="mt-1.5"
 type="password"
 placeholder="sk-..."
 value={filmKeyInput}
 onChange={e => setFilmKeyInput(e.target.value)}
 />
 <a
 href="https://platform.stability.ai/account/keys"
 target="_blank"
 rel="noopener noreferrer"
 className="inline-block mt-1 text-[11px] text-accent hover:underline"
 >
 获取 Stability AI API Key →
 </a>
 </div>
 )}
 {filmSettings.image_provider === 'dalle3' && (
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
 OpenAI API Key
 <span className="text-ink-subtle font-normal ml-1">
 {filmSettings.dalle3_api_key ? `当前: ${filmSettings.dalle3_api_key}` : '未配置'}
 </span>
 </label>
 <Input
 className="mt-1.5"
 type="password"
 placeholder="sk-..."
 value={dalle3KeyInput}
 onChange={e => setDalle3KeyInput(e.target.value)}
 />
 <a
 href="https://platform.openai.com/api-keys"
 target="_blank"
 rel="noopener noreferrer"
 className="inline-block mt-1 text-[11px] text-accent hover:underline"
 >
 获取 OpenAI API Key →
 </a>
 </div>
 )}
 {filmSettings.image_provider === 'comfyui' && (
 <div className="space-y-3 p-3 rounded-lg bg-paper border border-border">
 <div className="flex items-center justify-between">
 <h4 className="text-xs font-semibold text-ink-muted uppercase tracking-wide">ComfyUI 配置</h4>
 <button
 onClick={async () => {
 try {
 const r = await fetch('/api/novels/comfyui/test');
 const d = await r.json();
 if (d.connected) {
 toast.success(`ComfyUI 已连接 — ${d.system?.python_version || 'OK'}`);
 } else {
 toast.error(d.reason || 'ComfyUI 不可用');
 }
 } catch {
 toast.error('ComfyUI 连接失败');
 }
 }}
 className="text-[10px] px-2 py-1 rounded border border-border text-ink-muted hover:text-accent hover:border-accent/30 transition-colors"
 >
 测试连接
 </button>
 </div>
 <div>
 <label className="text-[11px] text-ink-muted">服务地址</label>
 <Input
 className="mt-1"
 placeholder="http://127.0.0.1:8188"
 value={filmSettings.comfyui_url}
 onChange={e => setFilmSettings({ ...filmSettings, comfyui_url: e.target.value })}
 />
 </div>
 <div>
 <label className="text-[11px] text-ink-muted">SD Checkpoint</label>
 <Input
 className="mt-1"
 placeholder="sd_xl_base_1.0.safetensors"
 value={filmSettings.comfyui_checkpoint}
 onChange={e => setFilmSettings({ ...filmSettings, comfyui_checkpoint: e.target.value })}
 />
 </div>
 <div>
 <label className="text-[11px] text-ink-muted">IP-Adapter 模型</label>
 <Input
 className="mt-1"
 placeholder="ip-adapter-faceid-plusv2_sd15.bin"
 value={filmSettings.comfyui_ipadapter_model}
 onChange={e => setFilmSettings({ ...filmSettings, comfyui_ipadapter_model: e.target.value })}
 />
 </div>
 <div className="grid grid-cols-3 gap-2">
 <div>
 <label className="text-[11px] text-ink-muted">IP-Adapter 权重</label>
 <Input
 className="mt-1"
 type="number"
 min="0" max="1" step="0.1"
 value={filmSettings.comfyui_lora_strength}
 onChange={e => setFilmSettings({ ...filmSettings, comfyui_lora_strength: e.target.value })}
 />
 </div>
 <div>
 <label className="text-[11px] text-ink-muted">采样步数</label>
 <Input
 className="mt-1"
 type="number"
 min="1" max="100" step="1"
 value={filmSettings.comfyui_steps}
 onChange={e => setFilmSettings({ ...filmSettings, comfyui_steps: e.target.value })}
 />
 </div>
 <div>
 <label className="text-[11px] text-ink-muted">CFG Scale</label>
 <Input
 className="mt-1"
 type="number"
 min="1" max="30" step="0.5"
 value={filmSettings.comfyui_cfg}
 onChange={e => setFilmSettings({ ...filmSettings, comfyui_cfg: e.target.value })}
 />
 </div>
 </div>
 <p className="text-[10px] text-ink-subtle">
 需要本地运行 ComfyUI 并安装 IP-Adapter 自定义节点。角色参考图可在视觉圣经页面生成。
 </p>
 </div>
 )}
 <div className="pt-3 mt-1 border-t border-border">
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">配乐引擎</label>
 <select
 className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2"
 value={filmSettings.music_provider}
 onChange={e => setFilmSettings({ ...filmSettings, music_provider: e.target.value })}
 >
 <option value="ambient">FFmpeg Ambient（本地合成氛围音）</option>
 <option value="suno">Suno AI（高质量 AI 配乐）</option>
 </select>
 </div>
 {filmSettings.music_provider === 'suno' && (
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
 Suno API Key
 <span className="text-ink-subtle font-normal ml-1">
 {filmSettings.suno_api_key ? `当前: ${filmSettings.suno_api_key}` : '未配置'}
 </span>
 </label>
 <Input
 className="mt-1.5"
 type="password"
 placeholder="Suno API Key..."
 value={sunoKeyInput}
 onChange={e => setSunoKeyInput(e.target.value)}
 />
 <p className="text-[10px] text-ink-subtle mt-1">
 Suno API 为异步生成，配乐步骤可能需要等待 1-5 分钟
 </p>
 </div>
 )}
 </div>
 <div className="mt-4 flex gap-2">
 <Button
 size="sm"
 className="bg-accent hover:bg-accent-hover"
 onClick={handleFilmSave}
 disabled={filmSaving}
 >
 {filmSaving ? '保存中...' : '保存影视配置'}
 </Button>
 </div>
 </CardContent>
 </Card>

 {/* Subtitle style settings */}
 <Card className="border-border mt-4">
 <CardContent className="p-5">
 <h3 className="font-heading text-sm font-semibold text-ink mb-3">字幕样式</h3>
 <div className="grid grid-cols-2 gap-4">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">字号</label>
 <input
 type="range"
 min="20" max="60" step="2"
 className="w-full mt-1.5"
 value={subtitleStyle.subtitle_font_size}
 onChange={e => setSubtitleStyle({ ...subtitleStyle, subtitle_font_size: e.target.value })}
 />
 <span className="text-[10px] text-ink-subtle">{subtitleStyle.subtitle_font_size}px</span>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">位置</label>
 <select
 className="w-full mt-1.5 rounded-md border border-input bg-card text-ink text-sm px-3 py-2"
 value={subtitleStyle.subtitle_position}
 onChange={e => setSubtitleStyle({ ...subtitleStyle, subtitle_position: e.target.value })}
 >
 <option value="bottom">底部</option>
 <option value="center">居中</option>
 <option value="top">顶部</option>
 </select>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">文字颜色</label>
 <div className="flex items-center gap-2 mt-1.5">
 <input
 type="color"
 className="w-8 h-8 rounded border border-border cursor-pointer"
 value={subtitleStyle.subtitle_font_color}
 onChange={e => setSubtitleStyle({ ...subtitleStyle, subtitle_font_color: e.target.value })}
 />
 <span className="text-xs text-ink-muted font-mono">{subtitleStyle.subtitle_font_color}</span>
 </div>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">背景颜色</label>
 <div className="flex items-center gap-2 mt-1.5">
 <input
 type="color"
 className="w-8 h-8 rounded border border-border cursor-pointer"
 value={subtitleStyle.subtitle_bg_color}
 onChange={e => setSubtitleStyle({ ...subtitleStyle, subtitle_bg_color: e.target.value })}
 />
 <span className="text-xs text-ink-muted font-mono">{subtitleStyle.subtitle_bg_color}</span>
 </div>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">背景透明度</label>
 <input
 type="range"
 min="0" max="255" step="5"
 className="w-full mt-1.5"
 value={subtitleStyle.subtitle_bg_opacity}
 onChange={e => setSubtitleStyle({ ...subtitleStyle, subtitle_bg_opacity: e.target.value })}
 />
 <span className="text-[10px] text-ink-subtle">{Math.round(Number(subtitleStyle.subtitle_bg_opacity) / 255 * 100)}%</span>
 </div>
 </div>
 {/* Preview */}
 <div className="mt-4 p-3 rounded-lg bg-zinc-900 text-center relative overflow-hidden" style={{ height: 80 }}>
 <div
 className="inline-block px-3 py-1 rounded text-sm font-medium"
 style={{
 backgroundColor: subtitleStyle.subtitle_bg_color + Math.round(Number(subtitleStyle.subtitle_bg_opacity)).toString(16).padStart(2, '0'),
 color: subtitleStyle.subtitle_font_color,
 fontSize: Math.min(Number(subtitleStyle.subtitle_font_size), 20),
 position: 'absolute',
 left: '50%',
 transform: 'translateX(-50%)',
 ...(subtitleStyle.subtitle_position === 'top' ? { top: 8 } :
 subtitleStyle.subtitle_position === 'center' ? { top: '50%', transform: 'translate(-50%, -50%)' } :
 { bottom: 8 }),
 }}
 >
 字幕预览效果
 </div>
 </div>
 </CardContent>
 </Card>
 </div>

 {/* Backup & Restore */}
 <div className="mt-8 max-w-[640px]">
 <h2 className="font-heading text-xl font-semibold text-ink mb-3">备份与恢复</h2>
 <Card className="border-border">
 <CardContent className="p-4">
 <div className="flex gap-3 flex-wrap">
 <button onClick={async () => {
 try {
 const r = await fetch('/api/novels');
 const novels = await r.json();
 const data = { novels, exportedAt: new Date().toISOString(), version: '1.0' };
 const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
 const url = URL.createObjectURL(blob);
 const a = document.createElement('a');
 a.href = url; a.download = `novel-workshop-backup-${new Date().toISOString().slice(0,10)}.json`;
 a.click(); URL.revokeObjectURL(url);
 toast.success('备份已下载');
 } catch { toast.error('备份失败'); }
 }}
 className="text-xs px-3 py-2 rounded-lg border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors">
 <Download size={13} className="mr-1" /> 下载备份
 </button>
 <label className="text-xs px-3 py-2 rounded-lg border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors cursor-pointer">
 <Upload size={13} className="mr-1" /> 恢复备份
 <input type="file" accept=".json" className="hidden"
 onChange={async e => {
 const file = e.target.files?.[0];
 if (!file) return;
 try {
 const text = await file.text();
 const data = JSON.parse(text);
 if (!data.novels || !Array.isArray(data.novels)) {
 toast.error('无效的备份文件'); return;
 }
 toast.info(`正在恢复 ${data.novels.length} 部小说...`);
 let restored = 0;
 for (const novel of data.novels) {
 try {
 await fetch('/api/novels', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify(novel),
 });
 restored++;
 } catch { /* skip duplicates */ }
 }
 toast.success(`已恢复 ${restored} 部小说`);
 window.location.reload();
 } catch { toast.error('恢复失败：文件格式错误'); }
 }} />
 </label>
 </div>
 <p className="text-[10px] text-ink-subtle mt-3">
 备份包含所有小说元数据和章节。恢复时不会覆盖已存在的同名小说。
 </p>
 <div className="flex gap-2 mt-3">
 <button onClick={() => {
 const data: Record<string, any> = {};
 for (let i = 0; i < localStorage.length; i++) {
 const key = localStorage.key(i);
 if (key) data[key] = localStorage.getItem(key);
 }
 const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
 const url = URL.createObjectURL(blob);
 const a = document.createElement('a');
 a.href = url; a.download = `novel-workshop-all-data-${new Date().toISOString().slice(0,10)}.json`;
 a.click(); URL.revokeObjectURL(url);
 toast.success('全部数据已导出');
 }}
 className="text-[10px] px-3 py-2 rounded-lg border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors">
 📦 导出全部数据（含配置）
 </button>
 <button onClick={() => {
 if (confirm('确定清除所有本地数据？包括小说配置、灵魂设定、角色设计等。此操作不可撤销。')) {
 localStorage.clear();
 toast.success('数据已清除');
 window.location.reload();
 }
 }}
 className="text-[10px] px-3 py-2 rounded-lg border border-destructive/20 text-destructive hover:bg-destructive-soft transition-colors">
 <Trash2 size={13} className="mr-1" /> 清除所有数据
 </button>
 </div>
 </CardContent>
 </Card>
 </div>

 {/* API Key guide */}
 <div className="mt-8 max-w-[640px]">
 <h2 className="font-heading text-xl font-semibold text-ink mb-3">获取 API Key</h2>
 <div className="grid gap-1">
 {[
 ['OpenAI', 'https://platform.openai.com/api-keys', '需海外信用卡'],
 ['DeepSeek', 'https://platform.deepseek.com/api_keys', '国内注册，推荐'],
 ['通义千问', 'https://dashscope.console.aliyun.com/apiKey', '阿里云账号'],
 ['Kimi', 'https://platform.moonshot.cn/console/api-keys', '手机号注册'],
 ['智谱', 'https://open.bigmodel.cn/usercenter/apikeys', '手机号注册'],
 ['豆包', 'https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey', '火山引擎'],
 ['百度文心', 'https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application', '百度智能云'],
 ['讯飞星火', 'https://console.xfyun.cn/services/spark', '讯飞平台'],
 ['MiniMax', 'https://platform.minimax.chat/user-center/basic-information/interface-key', '手机号注册'],
 ].map(([name, url, tip]) => (
 <a key={name} href={url} target="_blank" rel="noopener noreferrer"
 className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-paper transition-colors group">
 <span className="text-sm text-ink font-medium w-20 shrink-0">{name}</span>
 <span className="text-xs text-accent group-hover:underline truncate flex-1">{url}</span>
 <span className="text-[10px] text-ink-subtle shrink-0">{tip}</span>
 </a>
 ))}
 </div>
 </div>
 </div>
 );
}
