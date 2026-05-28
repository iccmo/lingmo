import { useEffect, useState, useRef } from 'react';

interface Character {
  id: number; name: string; role: string; power_level: string; status: string;
}
interface Relation {
  char_1_id: number; char_2_id: number; c1_name: string; c2_name: string;
  relation_type: string; description?: string;
}
interface PlotPoint { type: string; content: string; is_resolved: number; }

interface GraphNode {
  id: number; name: string; role: string; x: number; y: number; vx: number; vy: number;
  radius: number; color: string;
}
interface GraphEdge { source: number; target: number; type: string; color: string; }

const ROLE_COLORS: Record<string, string> = {
  '主角': '#4F46E5', '反派': '#DC2626', '导师': '#059669', '配角': '#6366F1', '路人': '#9CA3AF',
};
const RELATION_COLORS: Record<string, string> = {
  '盟友': '#34D399', '敌对': '#DC2626', '师徒': '#F59E0B', '恋人': '#EC4899',
  '家人': '#8B5CF6', '朋友': '#3B82F6', '仇敌': '#991B1B', '利用': '#D97706',
};

function roleColor(role: string): string {
  return ROLE_COLORS[role] || '#6B7280';
}
function roleRadius(role: string): number {
  if (role === '主角') return 22;
  if (role === '反派') return 18;
  if (role === '导师') return 15;
  return 12;
}

/** Simple force-directed layout via requestAnimationFrame */
function useForceLayout(
  nodes: GraphNode[], edges: GraphEdge[],
  width: number, height: number,
): GraphNode[] {
  const [positions, setPositions] = useState(nodes);
  const frameRef = useRef(0);

  useEffect(() => {
    if (nodes.length === 0) return;
    const ns = nodes.map(n => ({ ...n }));
    const centerX = width / 2, centerY = height / 2;

    let running = true;
    const W = width, H = height;

    function step() {
      if (!running) return;
      const alpha = 0.3;
      // Repulsion
      for (let i = 0; i < ns.length; i++) {
        for (let j = i + 1; j < ns.length; j++) {
          const dx = ns[j].x - ns[i].x;
          const dy = ns[j].y - ns[i].y;
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const force = 1200 / (dist * dist);
          const fx = (dx / dist) * force * alpha;
          const fy = (dy / dist) * force * alpha;
          ns[i].vx -= fx; ns[i].vy -= fy;
          ns[j].vx += fx; ns[j].vy += fy;
        }
      }
      // Attraction (edges)
      for (const e of edges) {
        const s = ns.find(n => n.id === e.source);
        const t = ns.find(n => n.id === e.target);
        if (!s || !t) continue;
        const dx = t.x - s.x, dy = t.y - s.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = (dist - 80) * 0.005 * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        s.vx += fx; s.vy += fy;
        t.vx -= fx; t.vy -= fy;
      }
      // Center gravity
      for (const n of ns) {
        n.vx += (centerX - n.x) * 0.001 * alpha;
        n.vy += (centerY - n.y) * 0.001 * alpha;
        n.vx *= 0.85; n.vy *= 0.85;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(n.radius, Math.min(W - n.radius, n.x));
        n.y = Math.max(n.radius, Math.min(H - n.radius, n.y));
      }
      setPositions(ns.map(n => ({ ...n })));
      frameRef.current = requestAnimationFrame(step);
    }

    frameRef.current = requestAnimationFrame(step);
    return () => { running = false; cancelAnimationFrame(frameRef.current); };
  }, [nodes.length, edges.length, width, height]);

  return positions;
}

export function PlotNetwork({ novelId }: { novelId: string }) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [plotPoints, setPlotPoints] = useState<PlotPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    fetch(`/api/novels/${novelId}`)
      .then(r => r.json())
      .then(d => {
        setCharacters(d.characters || []);
        setRelations(d.character_relations || []);
        setPlotPoints(d.plot_points || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [novelId]);

  const width = 640, height = 400;

  // Build graph
  const nodes: GraphNode[] = characters.map((c, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, characters.length);
    const r = Math.min(width, height) * 0.35;
    return {
      id: c.id, name: c.name, role: c.role,
      x: width / 2 + Math.cos(angle) * r,
      y: height / 2 + Math.sin(angle) * r,
      vx: 0, vy: 0,
      radius: roleRadius(c.role),
      color: roleColor(c.role),
    };
  });

  const edges: GraphEdge[] = relations.map(r => ({
    source: r.char_1_id, target: r.char_2_id,
    type: r.relation_type,
    color: RELATION_COLORS[r.relation_type] || '#9CA3AF',
  }));

  const positions = useForceLayout(nodes, edges, width, height);

  if (loading) return <div className="skeleton h-64 rounded-lg" />;
  if (characters.length === 0) return null;

  // Get related edges for selected node
  const relatedEdges = selected
    ? edges.filter(e => e.source === selected || e.target === selected)
    : [];
  const relatedNodeIds = new Set<number>();
  if (selected) {
    relatedNodeIds.add(selected);
    for (const e of relatedEdges) {
      relatedNodeIds.add(e.source);
      relatedNodeIds.add(e.target);
    }
  }

  const posMap = new Map(positions.map(p => [p.id, p]));
  
  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">🕸️ 情节网络</h3>
          <p className="text-[11px] text-ink-muted">角色关系 · 势力归属 · 伏笔状态</p>
        </div>
        <div className="flex gap-3 text-[10px] text-ink-subtle">
          <span>{characters.length} 角色</span>
          <span>{relations.length} 关系</span>
          <span>{plotPoints.length} 伏笔</span>
        </div>
      </div>

      <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} className="w-full border border-border rounded-lg bg-paper/50">
        {/* Edges */}
        {edges.map((e, i) => {
          const s = posMap.get(e.source);
          const t = posMap.get(e.target);
          if (!s || !t) return null;
          const isRelated = !selected || (e.source === selected || e.target === selected);
          const isHidden = selected && !isRelated;
          if (isHidden) return null;
          return (
            <g key={i}>
              <line x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke={e.color} strokeWidth={isRelated ? 2 : 1}
                opacity={isRelated ? 0.8 : 0.3}
                className="transition-all duration-300" />
              {/* Edge label */}
              <text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 4}
                textAnchor="middle" fontSize="9" fill={e.color}
                opacity={isRelated ? 0.9 : 0} className="transition-opacity">
                {e.type}
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {positions.map(n => {
          const isSelected = n.id === selected;
          const isRelated = selected ? relatedNodeIds.has(n.id) : true;
          const isHovered = n.id === hovered;
          return (
            <g key={n.id}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => setSelected(isSelected ? null : n.id)}
              className="cursor-pointer transition-all duration-300"
              opacity={selected && !isRelated ? 0.2 : 1}>
              {/* Pulse ring for selected */}
              {isSelected && (
                <circle cx={n.x} cy={n.y} r={n.radius + 6} fill="none"
                  stroke={n.color} strokeWidth="1.5" opacity="0.5"
                  className="animate-ping" />
              )}
              {/* Node circle */}
              <circle cx={n.x} cy={n.y} r={n.radius}
                fill={n.color} fillOpacity={isSelected || isHovered ? 1 : 0.85}
                stroke="var(--color-card)" strokeWidth="2"
                className="transition-all duration-200" />
              {/* Name */}
              <text x={n.x} y={n.y + n.radius + 13} textAnchor="middle"
                fontSize={n.role === '主角' ? 12 : 10}
                fontWeight={n.role === '主角' ? 'bold' : 'normal'}
                fill="var(--color-ink)" className="transition-opacity"
                opacity={isRelated ? 1 : 0.3}>
                {n.name}
              </text>
              {/* Role badge */}
              <text x={n.x} y={n.y + n.radius + 25} textAnchor="middle"
                fontSize="8" fill={n.color} opacity={isRelated ? 1 : 0.3}>
                {n.role}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Selected character detail */}
      {selected && (() => {
        const char = characters.find(c => c.id === selected);
        if (!char) return null;
        const rels = relations.filter(r => r.char_1_id === selected || r.char_2_id === selected);
        const pts = plotPoints.filter(p => p.content.includes(char.name));
        return (
          <div className="mt-3 p-3 bg-paper rounded-lg border border-border text-[11px] animate-[fadeSlideIn_0.15s_ease-out]">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: roleColor(char.role) }} />
              <span className="font-semibold text-ink">{char.name}</span>
              <span className="text-ink-muted">· {char.role}</span>
              {char.power_level && <span className="text-ink-subtle">· {char.power_level}</span>}
            </div>
            {rels.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {rels.map((r, i) => {
                  const other = r.char_1_id === selected ? r.c2_name : r.c1_name;
                  return (
                    <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full border"
                      style={{ borderColor: RELATION_COLORS[r.relation_type] || '#9CA3AF', color: RELATION_COLORS[r.relation_type] || '#6B7280' }}>
                      {r.relation_type} → {other}
                    </span>
                  );
                })}
              </div>
            )}
            {pts.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border">
                <span className="text-ink-subtle">关联伏笔: </span>
                {pts.map((p, i) => (
                  <span key={i} className={p.is_resolved ? 'text-emerald-500' : 'text-amber-500'}>
                    {p.is_resolved ? '✅' : '🔮'} {p.content.slice(0, 30)}{i < pts.length - 1 ? ' · ' : ''}
                  </span>
                ))}
              </div>
            )}
            <button onClick={() => setSelected(null)} className="text-[10px] text-ink-muted hover:text-ink mt-2">清除选择</button>
          </div>
        );
      })()}

      {/* Legend */}
      <div className="flex gap-3 mt-3 pt-2 border-t border-border text-[9px] text-ink-subtle flex-wrap">
        {Object.entries(RELATION_COLORS).slice(0, 6).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1">
            <span className="w-2 h-0.5 rounded" style={{ background: v }} />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}
