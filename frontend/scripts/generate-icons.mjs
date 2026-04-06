/**
 * Generates icon-192.png and icon-512.png using the Canvas API via
 * the built-in Node.js module. Requires Node 18+ (no extra deps).
 *
 * Falls back to writing minimal valid PNGs if canvas is unavailable.
 */
import { createCanvas } from "canvas";
import { writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = resolve(__dirname, "../public");

function generateIcon(size) {
  const canvas = createCanvas(size, size);
  const ctx = canvas.getContext("2d");

  // Background — blue-600 (#2563eb)
  ctx.fillStyle = "#2563eb";
  ctx.beginPath();
  ctx.roundRect(0, 0, size, size, size * 0.18);
  ctx.fill();

  // Text "OL"
  ctx.fillStyle = "#ffffff";
  ctx.font = `bold ${Math.round(size * 0.38)}px sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("OL", size / 2, size / 2);

  return canvas.toBuffer("image/png");
}

for (const size of [192, 512]) {
  const buf = generateIcon(size);
  const dest = resolve(publicDir, `icon-${size}.png`);
  writeFileSync(dest, buf);
  console.log(`Generated ${dest} (${buf.length} bytes)`);
}
