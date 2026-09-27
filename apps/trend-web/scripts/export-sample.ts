/* 예시 사전(SAMPLE_RECORDS)을 JSON 으로 내보낸다 → Python 시드(scripts/seed_dictionary.py). 실행: pnpm dlx tsx scripts/export-sample.ts */
import { mkdirSync, writeFileSync } from "node:fs";
import { SAMPLE_RECORDS, SAMPLE_QUEUE } from "../lib/sample/dictionary";

mkdirSync("../data/seed", { recursive: true });
writeFileSync("../data/seed/dictionary.json", JSON.stringify({ records: SAMPLE_RECORDS, queue: SAMPLE_QUEUE }, null, 1));
console.log(`exported ${SAMPLE_RECORDS.length} records, ${SAMPLE_QUEUE.length} queued`);
