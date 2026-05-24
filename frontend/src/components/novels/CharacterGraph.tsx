import { useState, useRef, useCallback, useEffect } from 'react';

interface Character {
  name: string;
  role: string;
  char_key: string;
}

interface Relation {
  c1_name: string;
  c2_name: string;
  relation: string;
}

interface Props {
  characters: Character[];
  relations: Relation[];
}

interface NodePosition {
  x: number;
  y: number;
}

const ROLE_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  '主角': {
    fill: '#FDE68A',
    stroke: '#D97706',
    text: '#92400E',
  },
  '反派': {
    fill: '#FECACA',
    stroke: '#DC2626',
    text: '#991B1B',
  },
  '配角': {
    fill: '#BFDBFE',
    stroke: '#2563EB',
    text: '#1E40AF',
  },
  '导师': {
    fill: '#A7F3D0',
    stroke: '#059669',
    text: '#065F46',
  },
  '路人': {
    fill: '#E5E7EB',
    stroke: '#6B7280',
    text: '#4B5563',
  },
};

const DEFAULT_COLOR = {
  fill: '#E5E7EB',
  stroke: '#9CA3AF',
  text: '#4B5563',
};

function getColorForRole(role: string) {
  // Match by keyword
  for (const [key, val] of Object.entries(ROLE_COLORS)) {
    if (role.includes(key)) return val;
  }
  return DEFAULT_COLOR;
}

export function CharacterGraph({ characters, relations }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredRelation, setHoveredRelation] = useState<number | null>(null);
  const [hoveredChar, setHoveredChar] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });
  const [dragging, setDragging] = useState<{ key: string; offsetX: number; offsetY: number } | null>(null);

  // Initialize positions in a circle layout
  const [positions, setPositions] = useState<Record<string, NodePosition>>({});

  useEffect(() => {
    if (characters.length === 0) return;
    const cx = dimensions.width / 2;
    const cy = dimensions.height / 2;
    const radius = Math.min(dimensions.width, dimensions.height) * 0.35;
    const newPositions: Record<string, NodePosition> = {};

    characters.forEach((ch, i) => {
      const angle = (2 * Math.PI * i) / characters.length - Math.PI / 2;
      newPositions[ch.char_key] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      };
    });

    setPositions(newPositions);
  }, [characters, dimensions]);

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        setDimensions({
          width: Math.max(400, width),
          height: Math.max(300, width * 0.6),
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const handlePointerDown = useCallback(
    (charKey: string, e: React.PointerEvent) => {
      e.preventDefault();
      const svg = svgRef.current;
      if (!svg) return;
      const pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const svgPt = pt.matrixTransform(svg.getScreenCTM()?.inverse());
      const pos = positions[charKey];
      if (!pos) return;
      setDragging({
        key: charKey,
        offsetX: pos.x - svgPt.x,
        offsetY: pos.y - svgPt.y,
      });
      (e.target as Element).setPointerCapture(e.pointerId);
    },
    [positions],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      const svg = svgRef.current;
      if (!svg) return;
      const pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const svgPt = pt.matrixTransform(svg.getScreenCTM()?.inverse());
      setPositions((prev) => ({
        ...prev,
        [dragging.key]: {
          x: svgPt.x + dragging.offsetX,
          y: svgPt.y + dragging.offsetY,
        },
      }));
    },
    [dragging],
  );

  const handlePointerUp = useCallback(() => {
    setDragging(null);
  }, []);

  if (characters.length === 0) {
    return (
      <div className="text-center py-8 text-ink-muted text-xs">
        暂无角色数据
      </div>
    );
  }

  const NODE_RADIUS = 28;

  return (
    <div className="mt-4">
      {/* Role legend */}
      <div className="flex gap-3 mb-3 flex-wrap text-[10px]">
        {Object.entries(ROLE_COLORS).map(([role, colors]) => (
          <span key={role} className="flex items-center gap-1 text-ink-muted">
            <span
              className="w-3 h-3 rounded-full border"
              style={{
                backgroundColor: colors.fill,
                borderColor: colors.stroke,
              }}
            />
            {role}
          </span>
        ))}
      </div>

      <div
        ref={containerRef}
        className="border border-border rounded-xl bg-card overflow-hidden dark:bg-card"
      >
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full touch-none select-none"
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          {/* Relation lines */}
          {relations.map((rel, i) => {
            const c1Key = characters.find((c) => c.name === rel.c1_name)?.char_key;
            const c2Key = characters.find((c) => c.name === rel.c2_name)?.char_key;
            if (!c1Key || !c2Key) return null;
            const p1 = positions[c1Key];
            const p2 = positions[c2Key];
            if (!p1 || !p2) return null;
            const isHovered = hoveredRelation === i;
            const isRelatedToHovered =
              hoveredChar && (rel.c1_name === hoveredChar || rel.c2_name === hoveredChar);

            const midX = (p1.x + p2.x) / 2;
            const midY = (p1.y + p2.y) / 2;

            return (
              <g key={`rel-${i}`}>
                {/* Invisible wider hit area */}
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke="transparent"
                  strokeWidth={16}
                  style={{ cursor: 'pointer' }}
                  onPointerEnter={() => setHoveredRelation(i)}
                  onPointerLeave={() => setHoveredRelation(null)}
                />
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke={
                    isHovered
                      ? '#4F46E5'
                      : isRelatedToHovered
                        ? '#818CF8'
                        : 'var(--color-ink-subtle)'
                  }
                  strokeWidth={isHovered ? 2 : 1}
                  strokeOpacity={isHovered || isRelatedToHovered ? 1 : 0.3}
                  className="transition-all duration-150"
                />
                {/* Relation label */}
                {(isHovered || isRelatedToHovered) && (
                  <g>
                    <rect
                      x={midX - rel.relation.length * 5 - 6}
                      y={midY - 10}
                      width={rel.relation.length * 10 + 12}
                      height={18}
                      rx={4}
                      fill="var(--color-ink)"
                      className="dark:fill-[#E8E4DD]"
                      opacity={0.9}
                    />
                    <text
                      x={midX}
                      y={midY + 3}
                      textAnchor="middle"
                      className="fill-white dark:fill-[#1A1817] text-[10px]"
                      style={{ fontSize: '10px' }}
                    >
                      {rel.relation}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Character nodes */}
          {characters.map((ch) => {
            const pos = positions[ch.char_key];
            if (!pos) return null;
            const colors = getColorForRole(ch.role);
            const isHovered = hoveredChar === ch.name;
            const isDragging = dragging?.key === ch.char_key;

            return (
              <g
                key={ch.char_key}
                style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
                onPointerDown={(e) => handlePointerDown(ch.char_key, e)}
              >
                {/* Glow ring when hovered */}
                {isHovered && (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={NODE_RADIUS + 6}
                    fill="none"
                    stroke={colors.stroke}
                    strokeWidth={2}
                    opacity={0.3}
                  />
                )}
                {/* Node circle */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={NODE_RADIUS}
                  fill={colors.fill}
                  stroke={colors.stroke}
                  strokeWidth={2}
                  className="transition-all duration-150 dark:opacity-90"
                  onPointerEnter={() => setHoveredChar(ch.name)}
                  onPointerLeave={() => setHoveredChar(null)}
                />
                {/* Character name */}
                <text
                  x={pos.x}
                  y={pos.y + 1}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{ fontSize: '11px', fill: colors.text, fontWeight: 600 }}
                  className="pointer-events-none dark:fill-current select-none"
                >
                  {ch.name.length > 3 ? ch.name.slice(0, 3) + '..' : ch.name}
                </text>
                {/* Role label below */}
                <text
                  x={pos.x}
                  y={pos.y + NODE_RADIUS + 12}
                  textAnchor="middle"
                  style={{ fontSize: '9px', fill: colors.text }}
                  className="pointer-events-none opacity-70 select-none"
                >
                  {ch.role}
                </text>
                {/* Hover tooltip with full details */}
                {isHovered && (
                  <g className="pointer-events-none">
                    <rect
                      x={pos.x + NODE_RADIUS + 8}
                      y={pos.y - 14}
                      width={Math.max(100, ch.name.length * 12 + 40)}
                      height={28}
                      rx={4}
                      fill="var(--color-ink)"
                      className="dark:fill-[#E8E4DD]"
                      opacity={0.9}
                    />
                    <text
                      x={pos.x + NODE_RADIUS + 16}
                      y={pos.y + 2}
                      textAnchor="start"
                      className="fill-white dark:fill-[#1A1817]"
                      style={{ fontSize: '10px' }}
                    >
                      {ch.name} · {ch.role}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
