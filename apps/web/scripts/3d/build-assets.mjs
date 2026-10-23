// Rebuilds the sculpted GLB assets in public/models: Blender sculpts the raw meshes
// (build_assets.py), then gltfpack meshopt-compresses them. Positions stay float so each
// mesh's geometry can be used without its node's dequantisation transform; 12-bit normals
// keep chrome reflections free of banding. Set BLENDER to override the binary path.
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const app = resolve(here, "../..");
const output = join(app, "public/models");
const blender = process.env.BLENDER ?? "/Applications/Blender.app/Contents/MacOS/Blender";
const gltfpack = join(app, "node_modules/.bin/gltfpack");

const raw = mkdtempSync(join(tmpdir(), "finboy-models-"));
try {
  execFileSync(
    blender,
    ["--background", "--factory-startup", "--python", join(here, "build_assets.py"), "--", raw],
    { stdio: ["ignore", "inherit", "inherit"] },
  );
  mkdirSync(output, { recursive: true });
  for (const file of readdirSync(raw).filter((name) => name.endsWith(".glb"))) {
    const target = join(output, file);
    execFileSync(
      gltfpack,
      ["-i", join(raw, file), "-o", target, "-cc", "-ce", "ext", "-kn", "-vpf", "-vp", "16", "-vn", "12"],
      { stdio: "inherit" },
    );
    console.log(`${file}: ${(statSync(target).size / 1024).toFixed(0)} KiB`);
  }
} finally {
  rmSync(raw, { recursive: true, force: true });
}
