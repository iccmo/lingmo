import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from 'src/components/ui/button';
import { Input } from 'src/components/ui/input';
import { Textarea } from 'src/components/ui/textarea';
import { Card, CardContent } from 'src/components/ui/card';
import { Badge } from 'src/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from 'src/components/ui/tabs';
import { toast } from 'sonner';
import { ConfirmDialog } from 'src/components/ui/ConfirmDialog';
import { throwApiError } from 'src/lib/api-error';

interface Character {
 id: number;
 char_key: string;
 name: string;
 role: string;
 personality: string;
 background: string;
 power_level: string;
 secrets: string;
 status: string;
}

interface Faction {
 id: number;
 name: string;
 description: string;
 leader: string;
 sort_order: number;
}

interface WorldData {
 name: string;
 era: string;
 geography: string;
 power_system: string;
 rules: string[];
 main_arc: string;
 current_arc: string;
 arc_chapter_start: number;
}

interface NovelWorld {
 id: string;
 title: string;
 world: WorldData;
 characters: Character[];
 factions: Faction[];
 character_relations?: Array<{ char_1_id: string; char_2_id: string; c1_name: string; c2_name: string; relation_type: string }>;
}

const ROLES = ['主角', '反派', '配角', '导师', '路人'];
const STATUSES = ['alive', 'injured', 'dead', 'missing'];
const STATUS_LABELS: Record<string, string> = { alive: '存活', injured: '受伤', dead: '死亡', missing: '失踪' };

export function WorldEditor() {
 const { id } = useParams<{ id: string }>();
 const navigate = useNavigate();
 const [data, setData] = useState<NovelWorld | null>(null);
 const [loading, setLoading] = useState(true);
 const [saving, setSaving] = useState(false);

 // ---- World form state ----
 const [world, setWorld] = useState<WorldData>({
 name: '', era: '', geography: '', power_system: '', rules: [],
 main_arc: '', current_arc: '开篇', arc_chapter_start: 1,
 });
 const [newRule, setNewRule] = useState('');

 // ---- Character form state ----
 const [editingChar, setEditingChar] = useState<Partial<Character> | null>(null);
 const [showCharForm, setShowCharForm] = useState(false);

 // ---- Faction form state ----
 const [editingFaction, setEditingFaction] = useState<Partial<Faction> | null>(null);
 const [showFactionForm, setShowFactionForm] = useState(false);
 const [confirmDelete, setConfirmDelete] = useState<{ type: string; key: string; name: string } | null>(null);

	 const loadData = useCallback(async () => {
	 if (!id) return;
	 try {
	 const response = await fetch(`/api/novels/${id}`);
	 await throwApiError(response);
	 const d = await response.json();
	 setData(d);
	 setWorld(d.world);
	 } catch (error) { toast.error(`加载失败: ${(error as Error).message}`); }
	 finally { setLoading(false); }
	 }, [id]);

 useEffect(() => { setLoading(true); loadData(); }, [loadData]);

 // ---- World save ----
 async function saveWorld() {
	 if (!id) return;
	 setSaving(true);
	 try {
	 const response = await fetch(`/api/novels/${id}/world`, {
	 method: 'PUT', headers: { 'Content-Type': 'application/json' },
	 body: JSON.stringify({
	 world_name: world.name, world_era: world.era, world_geo: world.geography,
	 power_system: world.power_system, main_arc: world.main_arc,
	 current_arc: world.current_arc, world_rules: JSON.stringify(world.rules),
	 }),
	 });
	 await throwApiError(response);
	 toast.success('世界观已保存');
	 } catch (error) { toast.error(`保存失败: ${(error as Error).message}`); }
	 finally { setSaving(false); }
	 }

 function addRule() {
 if (!newRule.trim()) return;
 setWorld({ ...world, rules: [...world.rules, newRule.trim()] });
 setNewRule('');
 }

 function removeRule(i: number) {
 setWorld({ ...world, rules: world.rules.filter((_, j) => j !== i) });
 }

 // ---- Character CRUD ----
 function startAddChar() {
 setEditingChar({ name: '', role: '配角', personality: '', background: '', power_level: '', char_key: '' });
 setShowCharForm(true);
 }

 function startEditChar(c: Character) {
 setEditingChar({ ...c });
 setShowCharForm(true);
 }

 async function saveChar() {
 if (!id || !editingChar) return;
	 const c = editingChar;
	 if (!c.char_key?.trim()) { toast.error('角色标识不能为空'); return; }
	 try {
	 let response: Response;
	 if (c.id) {
	 // Update existing
	 response = await fetch(`/api/novels/${id}/characters/${c.char_key}`, {
	 method: 'PUT', headers: { 'Content-Type': 'application/json' },
	 body: JSON.stringify({ name: c.name, role: c.role, personality: c.personality, background: c.background, power_level: c.power_level, status: c.status }),
	 });
	 } else {
	 // Create new
	 response = await fetch(`/api/novels/${id}/characters`, {
	 method: 'POST', headers: { 'Content-Type': 'application/json' },
	 body: JSON.stringify({ char_key: c.char_key, name: c.name, role: c.role, personality: c.personality, background: c.background, power_level: c.power_level }),
	 });
	 }
	 await throwApiError(response);
	 toast.success(c.id ? '角色已更新' : '角色已添加');
	 setShowCharForm(false);
	 setEditingChar(null);
	 loadData();
	 } catch (error) { toast.error(`保存失败: ${(error as Error).message}`); }
	 }

 function deleteChar(charKey: string) {
 const c = data?.characters?.find((ch: any) => ch.char_key === charKey);
 setConfirmDelete({ type: 'character', key: charKey, name: c?.name || charKey });
 }
	 async function doDeleteChar(charKey: string) {
	 try {
	 const response = await fetch(`/api/novels/${id}/characters/${charKey}`, { method: 'DELETE' });
	 await throwApiError(response);
	 toast.success('角色已删除');
	 loadData();
	 } catch (error) { toast.error(`删除失败: ${(error as Error).message}`); }
	 }

 // ---- Faction CRUD ----
 function startAddFaction() {
 setEditingFaction({ name: '', description: '', leader: '', sort_order: (data?.factions?.length || 0) });
 setShowFactionForm(true);
 }

 function startEditFaction(f: Faction) {
 setEditingFaction({ ...f });
 setShowFactionForm(true);
 }

 async function saveFaction() {
 if (!id || !editingFaction) return;
	 const f = editingFaction;
	 if (!f.name?.trim()) { toast.error('势力名称不能为空'); return; }
	 try {
	 const body = { name: f.name, description: f.description || '', leader: f.leader || '', sort_order: f.sort_order || 0 };
	 let response: Response;
	 if (f.id) {
	 response = await fetch(`/api/novels/${id}/factions/${f.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
	 } else {
	 response = await fetch(`/api/novels/${id}/factions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
	 }
	 await throwApiError(response);
	 toast.success(f.id ? '势力已更新' : '势力已添加');
	 setShowFactionForm(false);
	 setEditingFaction(null);
	 loadData();
	 } catch (error) { toast.error(`保存失败: ${(error as Error).message}`); }
	 }

 function deleteFaction(fid: number, name: string) {
 setConfirmDelete({ type: 'faction', key: String(fid), name });
 }
	 async function doDeleteFaction(fid: string) {
	 try {
	 const response = await fetch(`/api/novels/${id}/factions/${fid}`, { method: 'DELETE' });
	 await throwApiError(response);
	 toast.success('势力已删除');
	 loadData();
	 } catch (error) { toast.error(`删除失败: ${(error as Error).message}`); }
	 }

 // ---- Field helpers ----
 function updateWorldField(field: string, value: string | number) {
 setWorld({ ...world, [field]: value });
 }

 function updateCharField(field: string, value: string) {
 if (!editingChar) return;
 setEditingChar({ ...editingChar, [field]: value });
 }

 function updateFactionField(field: string, value: string | number) {
 if (!editingFaction) return;
 setEditingFaction({ ...editingFaction, [field]: value });
 }

 if (loading) {
 return <div className="space-y-4 p-8"><div className="skeleton h-6 w-32" /><div className="skeleton h-8 w-64" /><div className="skeleton h-40 rounded-lg" /></div>;
 }
 if (!data) return <div className="text-center py-20 text-ink-muted">小说未找到</div>;

 return (
 <div className="page-enter">
 <button onClick={() => navigate(`/novels/${id}`)} className="text-xs text-ink-muted hover:text-ink mb-2 block">
 ← 返回小说详情
 </button>
 <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight mb-1">世界观编辑器</h1>
 <p className="text-sm text-ink-muted mb-4">{data.title}</p>

 {/* Quick stats */}
 <div className="grid grid-cols-4 gap-3 mb-6">
 {[
 { v: data.characters?.length || 0, l: '角色', i: '👥' },
 { v: data.factions?.length || 0, l: '势力', i: '' },
 { v: world.rules?.length || 0, l: '规则', i: '📜' },
 { v: world.era || '未设定', l: '时代', i: '⏳' },
 ].map(s => (
 <div key={s.l} className="p-3 rounded-lg bg-card border border-border text-center">
 <div className="text-lg">{s.i}</div>
 <div className="font-heading text-lg font-bold text-ink">{s.v}</div>
 <div className="text-[10px] text-ink-muted">{s.l}</div>
 </div>
 ))}
 </div>

 <Tabs defaultValue="world" className="max-w-[720px]">
 <TabsList className="mb-5">
 <TabsTrigger value="world">世界观</TabsTrigger>
 <TabsTrigger value="characters">角色 ({data.characters?.length || 0})</TabsTrigger>
 <TabsTrigger value="factions">势力 ({data.factions?.length || 0})</TabsTrigger>
 </TabsList>

 {/* ---- World Tab ---- */}
 <TabsContent value="world">
 <div className="grid gap-4">
 <Card className="border-border">
 <CardContent className="p-5 space-y-4">
 <div className="grid grid-cols-2 gap-4">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">世界名称</label>
 <Input value={world.name} onChange={e => updateWorldField('name', e.target.value)} placeholder="如：九天大陆" className="mt-1.5" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">时代</label>
 <Input value={world.era} onChange={e => updateWorldField('era', e.target.value)} placeholder="如：上古/中古/近现代/未来" className="mt-1.5" />
 </div>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">地理</label>
 <Input value={world.geography} onChange={e => updateWorldField('geography', e.target.value)} placeholder="如：大陆分九州，中州为修行圣地" className="mt-1.5" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">修炼体系</label>
 <Textarea value={world.power_system} onChange={e => updateWorldField('power_system', e.target.value)} placeholder="如：练气→筑基→金丹→元婴→化神" rows={2} className="mt-1.5" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">主线剧情</label>
 <Input value={world.main_arc} onChange={e => updateWorldField('main_arc', e.target.value)} placeholder="如：从普通药师到丹帝的逆袭之路" className="mt-1.5" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">当前篇章</label>
 <Input value={world.current_arc} onChange={e => updateWorldField('current_arc', e.target.value)} placeholder="如：开篇/宗门大比/秘境探险" className="mt-1.5" />
 </div>
 {/* World Rules */}
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">世界规则</label>
 <div className="flex gap-2 mt-1.5">
 <Input value={newRule} onChange={e => setNewRule(e.target.value)} placeholder="如：金丹以上不可随意对凡人出手" onKeyDown={e => e.key === 'Enter' && addRule()} />
 <Button size="sm" variant="outline" onClick={addRule}>添加</Button>
 </div>
 {world.rules.length > 0 && (
 <div className="flex flex-wrap gap-1.5 mt-2">
 {world.rules.map((r, i) => (
 <span key={i} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-accent-soft text-ink">
 {r}
 <button onClick={() => removeRule(i)} className="text-ink-subtle hover:text-destructive ml-0.5">×</button>
 </span>
 ))}
 </div>
 )}
 </div>
 <div className="pt-2">
 <Button className="bg-accent hover:bg-accent-hover" onClick={saveWorld} disabled={saving}>
 {saving ? '保存中...' : '保存世界观'}
 </Button>
 </div>
 </CardContent>
 </Card>
 </div>
 </TabsContent>

 {/* ---- Characters Tab ---- */}
 <TabsContent value="characters">
 <div className="flex justify-end mb-3">
 <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={startAddChar}>+ 添加角色</Button>
 </div>

 {showCharForm && editingChar && (
 <Card className="mb-4 border-accent border">
 <CardContent className="p-5 space-y-3">
 <h3 className="font-heading text-lg font-semibold text-ink">{editingChar.id ? '编辑角色' : '新角色'}</h3>
 <div className="grid grid-cols-2 gap-3">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">标识 (英文)</label>
 <Input value={editingChar.char_key || ''} onChange={e => updateCharField('char_key', e.target.value)} placeholder="如: lin-feng" disabled={!!editingChar.id} className="mt-1" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">姓名</label>
 <Input value={editingChar.name || ''} onChange={e => updateCharField('name', e.target.value)} placeholder="如: 林风" className="mt-1" />
 </div>
 </div>
 <div className="grid grid-cols-2 gap-3">
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">角色</label>
 <select value={editingChar.role || '配角'} onChange={e => updateCharField('role', e.target.value)}
 className="w-full mt-1 rounded-md border border-input bg-card text-ink text-sm px-3 py-2">
 {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
 </select>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">状态</label>
 <select value={editingChar.status || 'alive'} onChange={e => updateCharField('status', e.target.value)}
 className="w-full mt-1 rounded-md border border-input bg-card text-ink text-sm px-3 py-2">
 {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
 </select>
 </div>
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">性格</label>
 <Input value={editingChar.personality || ''} onChange={e => updateCharField('personality', e.target.value)} placeholder="如: 坚韧不拔，心思缜密" className="mt-1" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">背景</label>
 <Textarea value={editingChar.background || ''} onChange={e => updateCharField('background', e.target.value)} placeholder="角色背景故事..." rows={2} className="mt-1" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">当前境界</label>
 <Input value={editingChar.power_level || ''} onChange={e => updateCharField('power_level', e.target.value)} placeholder="如: 金丹中期" className="mt-1" />
 </div>
 <div className="flex gap-2 pt-1">
 <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={saveChar}>保存</Button>
 <Button size="sm" variant="ghost" onClick={() => { setShowCharForm(false); setEditingChar(null); }}>取消</Button>
 </div>
 </CardContent>
 </Card>
 )}

 {!data.characters?.length ? (
 <p className="text-sm text-ink-muted py-8 text-center">暂无角色，点击上方按钮添加</p>
 ) : (
 <div className="grid gap-3">
 {data.characters.map(c => (
 <Card key={c.id} className="border-border hover:border-accent/30 transition-colors">
 <CardContent className="p-4">
 <div className="flex items-start justify-between">
 <div className="flex-1">
 <div className="flex items-center gap-2 mb-1">
 <span className="font-heading text-lg font-semibold text-ink">{c.name}</span>
 <Badge variant="outline" className="text-xs">{c.role}</Badge>
 <Badge variant="outline" className="text-xs text-ink-muted">{STATUS_LABELS[c.status] || c.status}</Badge>
 </div>
 {c.personality && <p className="text-xs text-ink-muted">性格：{c.personality}</p>}
 {c.background && <p className="text-xs text-ink-muted mt-0.5">背景：{c.background.length > 60 ? c.background.slice(0, 60) + '...' : c.background}</p>}
 {c.power_level && <p className="text-xs text-ink-muted mt-0.5">境界：{c.power_level}</p>}
 {/* Relations */}
 {data.character_relations && (() => {
 const rels = data.character_relations.filter((r: any) => r.char_1_id === c.id || r.char_2_id === c.id);
 if (rels.length === 0) return null;
 return (
 <div className="flex gap-1 mt-1.5 flex-wrap">
 {rels.slice(0, 3).map((r: any, ri: number) => {
 const other = r.char_1_id === c.id ? r.c2_name : r.c1_name;
 return <span key={ri} className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent-soft/30 text-accent">{r.relation_type} {other}</span>;
 })}
 </div>
 );
 })()}
 </div>
 <div className="flex gap-1 ml-2">
 <Button size="sm" variant="ghost" className="text-xs h-7" onClick={() => startEditChar(c)}>编辑</Button>
 <Button size="sm" variant="ghost" className="text-xs h-7 text-destructive hover:text-destructive dark:hover:text-destructive" onClick={() => deleteChar(c.char_key)}>删除</Button>
 </div>
 </div>
 </CardContent>
 </Card>
 ))}
 </div>
 )}
 </TabsContent>

 {/* ---- Factions Tab ---- */}
 <TabsContent value="factions">
 <div className="flex justify-end mb-3">
 <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={startAddFaction}>+ 添加势力</Button>
 </div>

 {showFactionForm && editingFaction && (
 <Card className="mb-4 border-accent border">
 <CardContent className="p-5 space-y-3">
 <h3 className="font-heading text-lg font-semibold text-ink">{editingFaction.id ? '编辑势力' : '新势力'}</h3>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">势力名称</label>
 <Input value={editingFaction.name || ''} onChange={e => updateFactionField('name', e.target.value)} placeholder="如: 青云宗" className="mt-1" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">首领</label>
 <Input value={editingFaction.leader || ''} onChange={e => updateFactionField('leader', e.target.value)} placeholder="如: 青云真人" className="mt-1" />
 </div>
 <div>
 <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">描述</label>
 <Textarea value={editingFaction.description || ''} onChange={e => updateFactionField('description', e.target.value)} placeholder="势力背景描述..." rows={2} className="mt-1" />
 </div>
 <div className="flex gap-2 pt-1">
 <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={saveFaction}>保存</Button>
 <Button size="sm" variant="ghost" onClick={() => { setShowFactionForm(false); setEditingFaction(null); }}>取消</Button>
 </div>
 </CardContent>
 </Card>
 )}

 {!data.factions?.length ? (
 <p className="text-sm text-ink-muted py-8 text-center">暂无势力，点击上方按钮添加</p>
 ) : (
 <div className="grid gap-3">
 {data.factions.map(f => (
 <Card key={f.id} className="border-border hover:border-accent/30 transition-colors">
 <CardContent className="p-4">
 <div className="flex items-start justify-between">
 <div className="flex-1">
 <div className="flex items-center gap-2 mb-1">
 <span className="font-heading text-base font-semibold text-ink">{f.name}</span>
 {f.leader && <Badge variant="outline" className="text-xs">首领：{f.leader}</Badge>}
 </div>
 {f.description && <p className="text-xs text-ink-muted">{f.description}</p>}
 </div>
 <div className="flex gap-1 ml-2">
 <Button size="sm" variant="ghost" className="text-xs h-7" onClick={() => startEditFaction(f)}>编辑</Button>
 <Button size="sm" variant="ghost" className="text-xs h-7 text-destructive hover:text-destructive dark:hover:text-destructive" onClick={() => deleteFaction(f.id, f.name)}>删除</Button>
 </div>
 </div>
 </CardContent>
 </Card>
 ))}
 </div>
 )}
 </TabsContent>
 </Tabs>

 {confirmDelete && (
   <ConfirmDialog
     open={true}
     title={`删除${confirmDelete.type === 'character' ? '角色' : '势力'}`}
     message={`确定删除「${confirmDelete.name}」吗？此操作不可撤销。`}
     confirmLabel="删除"
     variant="danger"
     onConfirm={() => {
       if (confirmDelete.type === 'character') doDeleteChar(confirmDelete.key);
       else doDeleteFaction(confirmDelete.key);
       setConfirmDelete(null);
     }}
     onCancel={() => setConfirmDelete(null)}
   />
 )}
 </div>
 );


}
