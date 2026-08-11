import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

const requiredAssets = [
  "node_modules/bootstrap/dist/css/bootstrap.min.css",
  "node_modules/bootstrap/dist/js/bootstrap.min.js",
  "node_modules/jquery/dist/jquery.min.js",
  "node_modules/alertifyjs/build/alertify.min.js",
  "node_modules/alertifyjs/build/css/alertify.min.css",
  "node_modules/tablesorter/dist/css/jquery.tablesorter.pager.min.css",
  "node_modules/tablesorter/dist/css/theme.default.min.css",
  "node_modules/tablesorter/dist/js/jquery.tablesorter.min.js",
  "node_modules/tablesorter/dist/js/jquery.tablesorter.widgets.min.js",
  "node_modules/tablesorter/dist/js/extras/jquery.tablesorter.pager.min.js",
  "node_modules/d3/d3.min.js",
];

const missing = [];
for (const relativePath of requiredAssets) {
  try {
    await access(resolve(here, relativePath), constants.R_OK);
  } catch {
    missing.push(relativePath);
  }
}

if (missing.length) {
  console.error("MooSight frontend dependency check failed. Missing assets:");
  for (const asset of missing) {
    console.error(`  - ${asset}`);
  }
  console.error("Run npm install in spiderfoot/static and check dependency compatibility.");
  process.exitCode = 1;
} else {
  console.log(`MooSight frontend dependency check passed (${requiredAssets.length} assets).`);
}
