import { writeFile } from "node:fs/promises";
import { collectDataset } from "../src/lib/dataset";

async function main() {
  const dataset = await collectDataset();
  if (!dataset.reports.length)
    throw new Error("No official data retrieved. Snapshot was not modified.");
  await writeFile(
    new URL("../src/data/snapshot.json", import.meta.url),
    `${JSON.stringify(dataset, null, 2)}\n`,
  );
  for (const source of dataset.sources)
    console.log(
      `${source.name}: ${source.status}, ${source.reportCount} reports`,
    );
  console.log(
    `Captured ${dataset.reports.length} official reports at ${dataset.collectedAt}`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
