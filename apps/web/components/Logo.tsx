// Logo de CIENCIA Y DIOS: órbitas (ciencia) alrededor de una luz central (lo trascendente).
export function Logo({ size = 64, className = "" }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 128 128" width={size} height={size} className={className} role="img" aria-label="Logo de Ciencia y Dios">
      <defs>
        <linearGradient id="cyd-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#a63a14" />
          <stop offset="1" stopColor="#5a1a07" />
        </linearGradient>
        <radialGradient id="cyd-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#ffe9a8" stopOpacity=".95" />
          <stop offset=".45" stopColor="#f2c14e" stopOpacity=".35" />
          <stop offset="1" stopColor="#f2c14e" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="cyd-gold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffe08a" />
          <stop offset="1" stopColor="#d9962b" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="124" height="124" rx="30" fill="url(#cyd-bg)" />
      <rect x="2" y="2" width="124" height="124" rx="30" fill="none" stroke="#ffffff" strokeOpacity=".12" strokeWidth="2" />
      <circle cx="64" cy="64" r="44" fill="none" stroke="url(#cyd-gold)" strokeWidth="3" />
      <ellipse cx="64" cy="64" rx="40" ry="15" fill="none" stroke="#ffd98a" strokeOpacity=".75" strokeWidth="2.5" transform="rotate(-32 64 64)" />
      <ellipse cx="64" cy="64" rx="40" ry="15" fill="none" stroke="#ffd98a" strokeOpacity=".75" strokeWidth="2.5" transform="rotate(32 64 64)" />
      <circle cx="64" cy="64" r="26" fill="url(#cyd-glow)" />
      <path d="M64 38 L69 59 L90 64 L69 69 L64 90 L59 69 L38 64 L59 59 Z" fill="url(#cyd-gold)" />
      <path d="M64 50 L66.5 61.5 L78 64 L66.5 66.5 L64 78 L61.5 66.5 L50 64 L61.5 61.5 Z" fill="#fff6d8" transform="rotate(45 64 64)" />
      <circle cx="64" cy="64" r="4.5" fill="#fffbe9" />
      <circle cx="98.5" cy="42.5" r="4" fill="#ffe08a" />
    </svg>
  );
}
