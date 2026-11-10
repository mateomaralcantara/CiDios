"use client";
import type { MapSpec } from "@/lib/types";

// Proyección equirectangular simple sin cartografía base (sin servicios externos).
export function SchematicMap({ map, active, onSelect }: { map: MapSpec; active?: Set<string>; onSelect?: (name: string) => void }) {
  const W = 640, H = 360, pad = 24;
  const { min_lat, max_lat, min_lon, max_lon } = map.bounds;
  const x = (lon: number) => pad + ((lon - min_lon) / (max_lon - min_lon)) * (W - 2 * pad);
  const y = (lat: number) => pad + ((max_lat - lat) / (max_lat - min_lat)) * (H - 2 * pad);
  const gridLon = []; for (let l = Math.ceil(min_lon / 10) * 10; l <= max_lon; l += 10) gridLon.push(l);
  const gridLat = []; for (let l = Math.ceil(min_lat / 10) * 10; l <= max_lat; l += 10) gridLat.push(l);
  return (
    <figure className="card p-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full ui" role="img" aria-label="Mapa esquemático de lugares relacionados">
        <rect x="0" y="0" width={W} height={H} fill="transparent" />
        {gridLon.map((l) => (<g key={`lo${l}`}><line x1={x(l)} x2={x(l)} y1={pad} y2={H - pad} stroke="var(--line)" />
          <text x={x(l) + 2} y={H - 8} fontSize="13" fill="var(--muted)">{l}°</text></g>))}
        {gridLat.map((l) => (<g key={`la${l}`}><line y1={y(l)} y2={y(l)} x1={pad} x2={W - pad} stroke="var(--line)" />
          <text x={4} y={y(l) - 2} fontSize="13" fill="var(--muted)">{l}°</text></g>))}
        {map.points.map((p) => {
          const on = !active || p.claim_ids.some((c) => active.has(c));
          return (
            <g key={p.name} onClick={() => onSelect?.(p.name)} style={{ cursor: onSelect ? "pointer" : undefined }} opacity={on ? 1 : 0.25}>
              <circle cx={x(p.lon)} cy={y(p.lat)} r={4 + Math.min(p.claim_ids.length, 6)} fill="var(--accent)" fillOpacity="0.35" stroke="var(--accent)" />
              <text x={x(p.lon) + 9} y={y(p.lat) + 5} fontSize="14" fontWeight="600" fill="var(--fg)">{p.name}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="ui muted mt-2 text-center text-xs">{map.notice}</figcaption>
    </figure>
  );
}
