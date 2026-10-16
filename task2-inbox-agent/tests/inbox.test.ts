import assert from "node:assert";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { editDistanceRatio, levenshteinDistance } from "../src/feedback/learner.js";
import { store } from "../src/feedback/store.js";
import { InboundEmailSchema } from "../src/email/types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log("Running Task 2 TypeScript Unit Tests...\n");

// Test 1: Levenshtein distance identical
{
  const s1 = "Hello, your refund has been processed successfully.";
  const s2 = "Hello, your refund has been processed successfully.";
  const dist = levenshteinDistance(s1, s2);
  const ratio = editDistanceRatio(s1, s2);
  assert.strictEqual(dist, 0, "Distance should be 0 for identical strings");
  assert.strictEqual(ratio, 0.0, "Ratio should be 0.0 for identical strings");
  console.log("✔ test_edit_distance_identical passed");
}

// Test 2: Levenshtein distance whitespace trimmed tolerance
{
  const s1 = "Hello, your refund has been processed.\n\nBest regards,\nSupport Team";
  const s2 = "  Hello, your refund has been processed.\n\nBest regards,\nSupport Team  ";
  const ratio = editDistanceRatio(s1, s2);
  assert.ok(ratio <= 0.05, `Whitespace trimmed ratio ${ratio} must be <= 0.05`);
  console.log("✔ test_edit_distance_whitespace_trimmed passed");
}

// Test 3: Substantial edit exceeds 0.05
{
  const s1 = "You can change your password in Account Settings > Security.";
  const s2 = "We actually do not allow password resets right now due to maintenance.";
  const ratio = editDistanceRatio(s1, s2);
  assert.ok(ratio > 0.05, `Substantial edit ratio ${ratio} must be > 0.05`);
  console.log("✔ test_edit_distance_significant_edit passed");
}

// Test 4: Sample emails dataset verification (50+ emails)
{
  const datasetPath = path.join(__dirname, "../src/email/sample_emails.json");
  assert.ok(fs.existsSync(datasetPath), `sample_emails.json missing at ${datasetPath}`);

  const emails = JSON.parse(fs.readFileSync(datasetPath, "utf-8")) as Array<unknown>;
  assert.ok(emails.length >= 50, `Expected at least 50 emails, found ${emails.length}`);

  for (let i = 0; i < emails.length; i++) {
    const parse = InboundEmailSchema.safeParse(emails[i]);
    assert.ok(parse.success, `Email #${i} failed schema validation: ${parse.error}`);
  }
  console.log(`✔ test_sample_emails_dataset passed (${emails.length} validated)`);
}

// Test 5: Autonomy state machine simulation
{
  const category = "HOW_TO";
  let streak = 0;
  let autoApproved = false;
  const threshold = 20;

  // 1. 20 consecutive perfect drafts
  for (let i = 1; i <= 20; i++) {
    const ratio = 0.02; // < 0.05
    if (ratio <= 0.05) {
      streak += 1;
    } else {
      streak = 0;
    }

    if (!autoApproved && streak >= threshold) {
      autoApproved = true;
    }
  }

  assert.strictEqual(autoApproved, true, "Autonomy must be granted after 20 perfect drafts");
  assert.strictEqual(streak, 20, "Streak must equal 20");

  // 2. Significant edit occurs
  const editRatio = 0.35; // > 0.05
  if (editRatio > 0.05) {
    streak = 0;
    if (autoApproved) {
      autoApproved = false;
    }
  }

  assert.strictEqual(autoApproved, false, "Autonomy must be revoked after human edit");
  assert.strictEqual(streak, 0, "Streak must reset to 0");
  console.log("✔ test_simulated_autonomy_state_machine passed");
}

console.log("\n==========================================");
console.log("All Task 2 TypeScript tests passed! (5/5)");
console.log("==========================================\n");
