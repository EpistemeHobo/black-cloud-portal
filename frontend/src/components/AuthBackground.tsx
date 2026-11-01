"use client";

import { useId } from "react";

/**
 * Full-screen vector background for the sign-in page: a deep navy-to-violet
 * field, soft colour glows, a dense field of Braille-like dot cells whose
 * patterns join into larger shapes and twinkle like stars.
 * Pure SVG and CSS, so it stays sharp at any size and costs no
 * image download.
 */

const WIDTH = 1600;
const HEIGHT = 1000;
// Braille layout: each cell has 2 columns and 3 rows of dot positions, with one
// empty column and row before the next cell, so the cells read as letters.
// The light tone uses a finer pitch, for smaller, denser dots.
const PITCH = { dark: 6, light: 4 };
const CELL_COLS = 2;
const CELL_ROWS = 3;
const OCTAVES = 4;

/**
 * Layered waves, built recursively: each octave adds a wave at twice the
 * frequency, half the strength and a turned angle on top of the one before.
 * Decides where the dot cells are dense and where they thin out.
 * Returns roughly -2..2.
 */
function rhythm(x: number, y: number, octave = 0): number {
  if (octave === OCTAVES) return 0;
  const scale = 2 ** octave;
  const angle = octave * 0.65;
  const u = x * Math.cos(angle) - y * Math.sin(angle);
  const v = x * Math.sin(angle) + y * Math.cos(angle);
  const wave = Math.sin(u * 0.009 * scale + octave) * Math.cos(v * 0.007 * scale - octave * 0.7);
  return wave / scale + rhythm(x, y, octave + 1);
}

// Peak of the series 1 + 1/2 + 1/4 + ..., used to bring rhythm() into 0..1.
const PEAK = 2 - 2 ** (1 - OCTAVES);

/** A fixed pseudo-random number in 0..1 for a position: the same dots on every load. */
function hash(x: number, y: number, salt = 0): number {
  const n = Math.sin(x * 12.9898 + y * 78.233 + salt * 37.719) * 43758.5453;
  return n - Math.floor(n);
}

// Brightness levels: each becomes one <path>, so thousands of dots stay cheap to draw.
// Two tones: "dark" (sign-in page) has pale dots on a dark field, the strongest
// pure white with a soft halo so it glows; "light" (the rest of the site) has
// small greyish navy dots on plain white.
type Level = { opacity: number; color: string; size: number; halo?: { color: string; opacity: number; size: number } };

const LEVELS: Record<"dark" | "light", Level[]> = {
  dark: [
    { opacity: 0.25, color: "#8f9cff", size: 2.2 },
    { opacity: 0.45, color: "#a9b4ff", size: 2.2 },
    { opacity: 0.7, color: "#cdd3ff", size: 2.2 },
    { opacity: 1, color: "#ffffff", size: 2.4, halo: { color: "#d9ccff", opacity: 0.22, size: 7 } },
  ],
  light: [
    { opacity: 0.09, color: "#6b7a93", size: 1.4 },
    { opacity: 0.15, color: "#53627d", size: 1.4 },
    { opacity: 0.22, color: "#3b4a66", size: 1.4 },
    { opacity: 0.35, color: "#26334d", size: 1.5 },
  ],
};
const LEVEL_COUNT = 4;

// Dots are dealt at random into twinkle groups. Each group is its own layer that
// fades up and down on its own slow cycle, so the field twinkles like stars.
const TWINKLE_GROUPS = [
  { seconds: 4.2 }, { seconds: 6.8 }, { seconds: 3.4 }, { seconds: 5.6 },
  { seconds: 7.4 }, { seconds: 3.9 }, { seconds: 6.1 }, { seconds: 4.8 },
];
// The sign-in page's stars run at twice those cycles.
const SIGNIN_TWINKLE_SPEED = 2;

/** Dot paths by twinkle group, then by brightness level, for a given dot spacing. */
function buildDots(pitch: number, width = WIDTH, height = HEIGHT): string[][] {
  const paths = TWINKLE_GROUPS.map(() => Array.from({ length: LEVEL_COUNT }, () => [] as string[]));
  const cellW = (CELL_COLS + 1) * pitch;
  const cellH = (CELL_ROWS + 1) * pitch;
  for (let top = pitch; top < height; top += cellH) {
    for (let left = pitch; left < width; left += cellW) {
      // Each cell takes its density from the wave field at its centre.
      const t = (rhythm(left + cellW / 2, top + cellH / 2) / PEAK + 1) / 2;
      const density = Math.min(0.95, Math.max(0.04, (t - 0.25) * 1.6));
      for (let row = 0; row < CELL_ROWS; row++) {
        for (let col = 0; col < CELL_COLS; col++) {
          const x = left + col * pitch;
          const y = top + row * pitch;
          if (hash(x, y) > density) continue;
          // Brightness follows the field, with a little variation from dot to dot.
          const glow = Math.min(0.999, Math.max(0, t * 0.9 + (hash(x, y, 1) - 0.5) * 0.35));
          // A zero-length line with round ends draws a dot in about ten characters.
          const group = Math.floor(hash(x, y, 3) * TWINKLE_GROUPS.length);
          paths[group][Math.floor(glow * LEVEL_COUNT)].push(`M${x} ${y}h0`);
        }
      }
    }
  }
  return paths.map((levels) => levels.map((p) => p.join("")));
}

// Same input, same dots: each tone's dots are computed once, the first time
// that tone is drawn.
const dotCache: Partial<Record<"dark" | "light", string[][]>> = {};
function dotsFor(tone: "dark" | "light"): string[][] {
  return (dotCache[tone] ??= buildDots(PITCH[tone]));
}

/** All twinkle groups merged into one path per brightness level, for a still layer. */
function mergedDots(tone: "dark" | "light"): string[] {
  return Array.from({ length: LEVEL_COUNT }, (_, i) => dotsFor(tone).map((group) => group[i]).join(""));
}

/**
 * Speed the twinkling dots up or down: 1 is normal, 2 is twice as fast.
 * Each layer keeps its place in its cycle, so the dots never jump.
 * Does nothing when the twinkle is off (reduced motion).
 */
export function setTwinkleSpeed(rate: number): void {
  for (const animation of document.getAnimations()) {
    if ((animation as CSSAnimation).animationName === "auth-twinkle") {
      animation.updatePlaybackRate(rate);
    }
  }
}

/** The dots of one layer: a path per brightness level, each with its optional halo. */
function DotLevels({ paths, levels, mask }: { paths: string[]; levels: Level[]; mask: string }) {
  return (
    <g mask={mask}>
      {paths.map((d, i) => {
        const level = levels[i];
        return (
          <g key={i}>
            {level.halo && (
              <path d={d} fill="none" stroke={level.halo.color} strokeOpacity={level.halo.opacity}
                strokeWidth={level.halo.size} strokeLinecap="round" />
            )}
            <path d={d} fill="none" stroke={level.color} strokeOpacity={level.opacity}
              strokeWidth={level.size} strokeLinecap="round" />
          </g>
        );
      })}
    </g>
  );
}

/**
 * `tone="dark"` (default) is the sign-in page: a dark gradient with soft glows.
 * `tone="light"` is the rest of the site: plain white, no gradient, dark dots.
 */
export default function AuthBackground({ tone = "dark" }: { tone?: "dark" | "light" }) {
  // Unique ids, so two copies on a page could never share gradients by accident.
  const id = useId().replace(/:/g, "");
  const ref = (name: string) => `url(#${name}-${id})`;
  const levels = LEVELS[tone];

  return (
    <>
      {/* The mask that fades the dots towards the middle is needed by both tones. */}
      {tone === "light" && (
        <svg className="absolute h-0 w-0" aria-hidden>
          <defs>
            <radialGradient id={`dot-fade-${id}`} cx="0.5" cy="0.5" r="0.75">
              <stop offset="0" stopColor="#fff" stopOpacity="0.15" />
              <stop offset="0.45" stopColor="#fff" stopOpacity="0.55" />
              <stop offset="1" stopColor="#fff" stopOpacity="0.9" />
            </radialGradient>
            <mask id={`mask-dots-${id}`} maskUnits="userSpaceOnUse" x="0" y="0" width="1600" height="1000">
              <rect width="1600" height="1000" fill={ref("dot-fade")} />
            </mask>
          </defs>
        </svg>
      )}

      {tone === "dark" && <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        preserveAspectRatio="xMidYMid slice"
        viewBox="0 0 1600 1000"
        aria-hidden
      >
        <defs>
          <linearGradient id={`base-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#090a11" />
            <stop offset="0.55" stopColor="#0f0f19" />
            <stop offset="1" stopColor="#130f1c" />
          </linearGradient>

          <radialGradient id={`glow-top-${id}`} cx="0.5" cy="0" r="0.55">
            <stop offset="0" stopColor="#304261" stopOpacity="0.55" />
            <stop offset="1" stopColor="#304261" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`glow-left-${id}`} cx="0.05" cy="0.75" r="0.5">
            <stop offset="0" stopColor="#2f3055" stopOpacity="0.55" />
            <stop offset="1" stopColor="#2f3055" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`glow-right-${id}`} cx="0.95" cy="0.45" r="0.45">
            <stop offset="0" stopColor="#3b3056" stopOpacity="0.5" />
            <stop offset="1" stopColor="#3b3056" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`glow-bottom-${id}`} cx="0.6" cy="1.05" r="0.45">
            <stop offset="0" stopColor="#2a495f" stopOpacity="0.35" />
            <stop offset="1" stopColor="#2a495f" stopOpacity="0" />
          </radialGradient>

          {/* Where the dots show: strongest at the edges, faint in the middle behind the card. */}
          <radialGradient id={`dot-fade-${id}`} cx="0.5" cy="0.5" r="0.75">
            <stop offset="0" stopColor="#fff" stopOpacity="0.15" />
            <stop offset="0.45" stopColor="#fff" stopOpacity="0.55" />
            <stop offset="1" stopColor="#fff" stopOpacity="0.9" />
          </radialGradient>
          <mask id={`mask-dots-${id}`}>
            <rect width="1600" height="1000" fill={ref("dot-fade")} />
          </mask>
        </defs>

        <rect width="1600" height="1000" fill={ref("base")} />
        <rect width="1600" height="1000" fill={ref("glow-left")} />
        <rect width="1600" height="1000" fill={ref("glow-right")} />
        <rect width="1600" height="1000" fill={ref("glow-top")} />
        <rect width="1600" height="1000" fill={ref("glow-bottom")} />
      </svg>}

      {tone === "dark" ? (
        // Dark: one layer per twinkle group. Each layer only fades (globals.css),
        // which the graphics card does without redrawing thousands of dots.
        dotsFor("dark").map((groupPaths, g) => (
          <svg
            key={g}
            className="auth-twinkle pointer-events-none absolute inset-0 h-full w-full"
            style={{
              animationDuration: `${(TWINKLE_GROUPS[g].seconds / SIGNIN_TWINKLE_SPEED).toFixed(2)}s`,
              animationDelay: `-${(((g * 1.7) % TWINKLE_GROUPS[g].seconds) / SIGNIN_TWINKLE_SPEED).toFixed(2)}s`,
            }}
            preserveAspectRatio="xMidYMid slice"
            viewBox="0 0 1600 1000"
            aria-hidden
          >
            <DotLevels paths={groupPaths} levels={levels} mask={ref("mask-dots")} />
          </svg>
        ))
      ) : (
        // Light: the finer dots, all in one still layer. No twinkle.
        <svg className="pointer-events-none absolute inset-0 h-full w-full"
          preserveAspectRatio="xMidYMid slice" viewBox="0 0 1600 1000" aria-hidden>
          <DotLevels paths={mergedDots("light")} levels={levels} mask={ref("mask-dots")} />
        </svg>
      )}
    </>
  );
}

// The header strip: a wide, short field, so the dots stay small in a 72px bar.
// Its dots twinkle 8 times faster than the sign-in page's.
const HEADER_TWINKLE_SPEED = 8;
const HEADER_WIDTH = 2400;
const HEADER_HEIGHT = 84;
let headerDots: string[][] | undefined;

/**
 * Twinkling Braille dots for the header's empty space, left and right of its
 * content. Uses the sign-in page's pale star colours at a fine pitch. Where to
 * show them is decided by a mask in globals.css (.header-dots).
 */
export function HeaderDots() {
  headerDots ??= buildDots(3, HEADER_WIDTH, HEADER_HEIGHT);
  const levels = LEVELS.dark.map((l) => ({ ...l, size: l.size * 0.55, halo: undefined }));
  return (
    <div className="header-dots pointer-events-none absolute inset-0" aria-hidden>
      {headerDots.map((groupPaths, g) => (
        <svg
          key={g}
          className="auth-twinkle absolute inset-0 h-full w-full"
          style={{
            animationDuration: `${(TWINKLE_GROUPS[g].seconds / HEADER_TWINKLE_SPEED).toFixed(3)}s`,
            animationDelay: `-${(((g * 1.7) % TWINKLE_GROUPS[g].seconds) / HEADER_TWINKLE_SPEED).toFixed(3)}s`,
          }}
          preserveAspectRatio="xMidYMid slice"
          viewBox={`0 0 ${HEADER_WIDTH} ${HEADER_HEIGHT}`}
        >
          {groupPaths.map((d, i) => (
            <path key={i} d={d} fill="none" stroke={levels[i].color} strokeOpacity={levels[i].opacity}
              strokeWidth={levels[i].size} strokeLinecap="round" />
          ))}
        </svg>
      ))}
    </div>
  );
}
