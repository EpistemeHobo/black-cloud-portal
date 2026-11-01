// A small black hole for the sign-in card, drawn as vector graphics, after the
// look of Interstellar's Gargantua:
//   - a dark shadow ringed by a thin, bright photon ring;
//   - an accretion disk seen almost edge-on, made of many uneven streaks, its
//     near half passing in front of the shadow;
//   - the disk's far side, bent by gravity into a halo over and under the shadow;
//   - the approaching (left) side brighter than the receding side.
// The streaks orbit at Kepler-like speeds: inner bands turn faster than outer
// ones (styles .bh-* in globals.css). Purely decorative.

import { useId } from "react";

// Disk-plane radii. The shadow sits inside INNER; streaks run out to OUTER.
const SHADOW = 24;
const INNER = 31;
const OUTER = 112;
// How flat the disk looks: 1 is face-on, small is edge-on.
const TILT = 0.2;

/** A small seeded random generator, so every render draws the same streaks. */
function random(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Streak = { d: string; width: number; opacity: number; color: string };

/** Hot near the hole, cooling to blue at the rim. */
function colorAt(t: number): string {
  if (t < 0.18) return "#ffffff";
  if (t < 0.4) return "#eef3ff";
  if (t < 0.65) return "#c3d4ff";
  return "#8ea6ff";
}

function arc(r: number, from: number, length: number): string {
  const x0 = r * Math.cos(from), y0 = r * Math.sin(from);
  const x1 = r * Math.cos(from + length), y1 = r * Math.sin(from + length);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r.toFixed(2)} ${r.toFixed(2)} 0 ${length > Math.PI ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

/** Uneven arcs between two radii: the disk's gas, bunched and broken like real swirls. */
function streaks(seed: number, from: number, to: number, count: number): Streak[] {
  const rand = random(seed);
  return Array.from({ length: count }, () => {
    const r = from + (to - from) * Math.pow(rand(), 0.8);
    const t = (r - INNER) / (OUTER - INNER);
    return {
      d: arc(r, rand() * Math.PI * 2, 0.25 + rand() * 1.9),
      width: 0.4 + rand() * (2.6 - 1.8 * t),
      opacity: (0.25 + rand() * 0.6) * (1 - 0.75 * t),
      color: colorAt(t),
    };
  });
}

// Three orbits, fastest inside.
const BANDS = [
  { name: "bh-band-inner", streaks: streaks(7, INNER, 52, 46) },
  { name: "bh-band-mid", streaks: streaks(19, 48, 80, 52) },
  { name: "bh-band-outer", streaks: streaks(31, 74, OUTER, 44) },
];

/** The disk itself: a soft glow plus the turning streak bands. Drawn twice (far half, near half). */
function Disk({ glow }: { glow: string }) {
  return (
    <g transform={`scale(1 ${TILT})`}>
      <circle r={OUTER} fill={`url(#${glow})`} />
      {BANDS.map((band) => (
        <g key={band.name} className={`bh-band ${band.name}`}>
          {/* Keeps the band's box centred on the hole while it turns. */}
          <circle r={OUTER + 2} fill="none" />
          {band.streaks.map((s, i) => (
            // Even width on screen, though the disk is squashed.
            <path key={i} d={s.d} fill="none" stroke={s.color} strokeOpacity={s.opacity}
              strokeWidth={s.width} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
          ))}
        </g>
      ))}
    </g>
  );
}

export default function WarpPortal({ className = "" }: { className?: string }) {
  // The same page can draw more than one black hole, so each gets its own ids.
  const uid = useId().replace(/:/g, "");
  const id = (name: string) => `${uid}-${name}`;
  const url = (name: string) => `url(#${id(name)})`;
  return (
    <svg viewBox="-125 -70 250 140" className={`black-hole ${className}`} aria-hidden focusable="false">
      <defs>
        <radialGradient id={id("haze")}>
          <stop offset="0%" stopColor="#cfdcff" stopOpacity="0.35" />
          <stop offset="50%" stopColor="#5b74e8" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#3b4fd0" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={id("disk-glow")} gradientUnits="userSpaceOnUse" cx="0" cy="0" r={OUTER}>
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
          <stop offset={(INNER - 2) / OUTER} stopColor="#ffffff" stopOpacity="0" />
          <stop offset={INNER / OUTER} stopColor="#ffffff" stopOpacity="0.85" />
          <stop offset="0.45" stopColor="#b8caff" stopOpacity="0.35" />
          <stop offset="1" stopColor="#6f86ff" stopOpacity="0" />
        </radialGradient>
        {/* The far side of the disk, lensed into a halo: brightest over the top. */}
        <linearGradient id={id("halo")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="45%" stopColor="#c9d8ff" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#9fb4ff" stopOpacity="0.6" />
        </linearGradient>
        <radialGradient id={id("shadow")}>
          <stop offset="0%" stopColor="#000000" />
          <stop offset="88%" stopColor="#000000" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0" />
        </radialGradient>
        {/* Doppler beaming: gas coming towards us (left) looks brighter. */}
        <linearGradient id={id("beam")} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#fff" stopOpacity="1" />
          <stop offset="50%" stopColor="#fff" stopOpacity="0.75" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0.32" />
        </linearGradient>
        <mask id={id("beaming")} maskUnits="userSpaceOnUse" x="-125" y="-70" width="250" height="140">
          <rect x="-125" y="-70" width="250" height="140" fill={url("beam")} />
        </mask>
        {/* Only the near half of the disk passes in front of the shadow. */}
        <clipPath id={id("near-half")}>
          <rect x="-125" y="0" width="250" height="70" />
        </clipPath>
        <filter id={id("soft")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" />
        </filter>
        <filter id={id("glow")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <g transform="rotate(-9)">
        <ellipse rx="120" ry="64" fill={url("haze")} />

        {/* Far half of the disk, behind everything else. */}
        <g mask={url("beaming")} filter={url("glow")}><Disk glow={id("disk-glow")} /></g>

        {/* Lensed halo of the far side, wrapping over and under the shadow. */}
        <g className="bh-halo">
          <circle r={SHADOW + 9} fill="none" stroke={url("halo")} strokeWidth="9" filter={url("soft")} opacity="0.7" />
          <circle r={SHADOW + 7} fill="none" stroke={url("halo")} strokeWidth="2.4" opacity="0.9" />
        </g>

        {/* The shadow, then the thin photon ring right at its edge. */}
        <circle r={SHADOW + 2} fill={url("shadow")} />
        <circle r={SHADOW + 2.2} fill="none" stroke="#f4f7ff" strokeWidth="0.9" className="bh-photon-ring" filter={url("glow")} />

        {/* Near half of the disk, crossing in front of the shadow. */}
        <g clipPath={url("near-half")}>
          <g mask={url("beaming")} filter={url("glow")}><Disk glow={id("disk-glow")} /></g>
        </g>
      </g>
    </svg>
  );
}
