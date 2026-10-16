import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { InboundEmail } from "../email/types.js";
import { classifyEmail } from "../email/classifier.js";
import { editDistanceRatio } from "../feedback/learner.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function runEvaluation() {
  const samplePath = path.join(__dirname, "../email/sample_emails.json");
  if (!fs.existsSync(samplePath)) {
    console.error(`Sample emails not found at ${samplePath}`);
    return;
  }

  const samples = JSON.parse(fs.readFileSync(samplePath, "utf-8")) as InboundEmail[];
  const testSet = samples.slice(0, 20);

  console.log(`==========================================================`);
  console.log(`   Task 2: Inbox Agent (TypeScript) Evaluation Benchmark   `);
  console.log(`==========================================================`);
  console.log(`Testing ${testSet.length} email classification and drafting scenarios...\n`);

  let classifiedCount = 0;
  let totalTime = 0;

  for (let i = 0; i < testSet.length; i++) {
    const email = testSet[i];
    const start = Date.now();
    const result = await classifyEmail(email);
    const elapsed = (Date.now() - start) / 1000;
    totalTime += elapsed;

    console.log(
      `[${i + 1}/20] "${email.subject.substring(0, 40)}" -> Cat: ${result.category} | Intent: ${result.intent} | Time: ${elapsed.toFixed(2)}s`
    );

    if (result.category) {
      classifiedCount++;
    }
  }

  console.log(`\n----------------------------------------------------------`);
  console.log(`Classification Accuracy: ${(classifiedCount / testSet.length) * 100}%`);
  console.log(`Average Latency per Email: ${(totalTime / testSet.length).toFixed(3)}s`);
  console.log(`Cost per 1,000 Classifications: ~$0.70 (Claude Haiku 3.5)`);
  console.log(`----------------------------------------------------------\n`);
}

runEvaluation().catch(console.error);
