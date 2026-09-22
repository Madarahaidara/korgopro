// ============================================================================
// Diagramme circulaire SVG — répartition des ventes par statut (ou autre)
// Usage : <PieChart data={[{label, value, color}]} />
// ============================================================================
import React from 'react';

export default function PieChart({ data, size = 220, strokeWidth = 38 }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (!total || !data.length) return null;

  // Coordonnées SVG pour un arc
  const r = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;

  const angleBetween = (a, b) => ((b - a) % 360 + 360) % 360;
  const describeArc = (start, end) => {
    // Calcul des angles de chaque segment
    let startAngle = -90; // Commencer par le haut (12h)
    const segments = data.map((d) => {
      const angle = (d.value / total) * 360;
      const endAngle = startAngle + angle;
      const midAngle = (startAngle + endAngle) / 2;
      startAngle = endAngle;
      return { ...d, startAngle, endAngle, midAngle };
    });

    const startRad = (start * Math.PI) / 180;
    const endRad = (end * Math.PI) / 180;
    const x1 = cx + r * Math.cos(startRad);
    const y1 = cy + r * Math.sin(startRad);
    const x2 = cx + r * Math.cos(endRad);
    const y2 = cy + r * Math.sin(endRad);
    const large = angleBetween(start, end) > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      {/* Graphique */}
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
        />
        {segments.map((s, i) => (
          <path
            key={i}
            d={describeArc(s.startAngle, s.endAngle)}
            stroke={s.color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            fill="none"
          />
        ))}
        {/* Centre : total */}
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          style={{ fontSize: 22, fontWeight: 800, fill: '#1e293b' }}
        >
          {Math.round(total / 1000)}k
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          style={{ fontSize: 11, fill: '#475569' }}
        >
          ventes
        </text>
      </svg>

      {/* Légende */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
        {data.map((d, i) => {
          const pct = ((d.value / total) * 100).toFixed(1);
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  background: d.color,
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 13, color: '#475569' }}>{d.label}</span>
              <span style={{ marginLeft: 'auto', fontWeight: 700, color: '#1e293b' }}>
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
