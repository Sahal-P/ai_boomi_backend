import { copyFile, chmod } from "node:fs/promises";
import { constants } from "node:fs";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
for (const path of [".env", "apps/api/.env", "apps/web/.env.local"]) {
  const source =
    path === "apps/web/.env.local"
      ? "apps/web/.env.example"
      : `${path}.example`;
  try {
    await copyFile(
      new URL(source, root),
      new URL(path, root),
      constants.COPYFILE_EXCL,
    );
    await chmod(new URL(path, root), 0o600);
    console.log(`Created ${path}`);
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
    console.log(`Kept existing ${path}`);
  }
}
console.log(`Environment ready in ${fileURLToPath(root)}`);
