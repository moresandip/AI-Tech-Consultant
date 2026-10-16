import express, { Request, Response } from "express";
import cors from "cors";
import dotenv from "dotenv";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

import { InboundEmailSchema, EmailRecord } from "./email/types.js";
import { classifyEmail } from "./email/classifier.js";
import { draftReply } from "./drafting/drafter.js";
import { recordFeedback } from "./feedback/learner.js";
import { store } from "./feedback/store.js";

dotenv.config({ path: path.resolve(process.cwd(), "../.env") });
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 8002;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "../public")));

// ─── Health ──────────────────────────────────────────────────────────────────
app.get(["/health", "/api/health"], (_req: Request, res: Response) => {
  res.json({ status: "ok", service: "inbox-agent-ts", runtime: "Node.js + TypeScript" });
});

// ─── Process Inbound Email ───────────────────────────────────────────────────
app.post("/api/email/inbound", async (req: Request, res: Response) => {
  const parseResult = InboundEmailSchema.safeParse(req.body);
  if (!parseResult.success) {
    res.status(400).json({ error: "Invalid inbound email schema", details: parseResult.error });
    return;
  }

  const inbound = parseResult.data;
  console.log(`[Inbox] Processing inbound email: "${inbound.subject}" from ${inbound.sender_email}`);

  // Step 1: Classify with Claude Haiku 3.5
  const classification = await classifyEmail(inbound);

  // Step 2: Draft with Claude Sonnet 4.5 using KB API
  const draftResult = await draftReply(inbound, classification.category);

  // Step 3: Check if category has attained auto-approval
  const categoryStats = store.getCategoryStats(classification.category);
  const isAutoApproved = categoryStats.auto_approved;

  const emailRecord: EmailRecord = {
    id: `em_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
    sender_email: inbound.sender_email,
    sender_name: inbound.sender_name,
    subject: inbound.subject,
    body: inbound.body,
    category: classification.category,
    intent: classification.intent,
    urgency: classification.urgency,
    draft_body: draftResult.draft,
    kb_sources: draftResult.sources,
    auto_approved: isAutoApproved,
    status: isAutoApproved ? "AUTO_SENT" : "DRAFT",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  store.saveEmail(emailRecord);

  res.json({
    email_id: emailRecord.id,
    category: emailRecord.category,
    intent: emailRecord.intent,
    urgency: emailRecord.urgency,
    draft: emailRecord.draft_body,
    auto_approved: emailRecord.auto_approved,
    status: emailRecord.status,
    kb_sources: emailRecord.kb_sources,
  });
});

// ─── Email Queue ─────────────────────────────────────────────────────────────
app.get("/api/email/queue", (_req: Request, res: Response) => {
  const emails = store.getAllEmails();
  res.json(emails);
});

// ─── Human Feedback & Edit Distance ──────────────────────────────────────────
app.post("/api/email/feedback", (req: Request, res: Response) => {
  const { email_id, final_body, action } = req.body;
  if (!email_id) {
    res.status(400).json({ error: "Missing email_id" });
    return;
  }

  const email = store.getEmail(email_id);
  if (!email) {
    res.status(404).json({ error: "Email not found" });
    return;
  }

  const finalSent = (final_body || email.draft_body) as string;
  const result = recordFeedback(email.id, email.category, email.draft_body, finalSent);

  email.final_body = finalSent;
  email.status = result.isPerfect ? "SENT_AS_IS" : "EDITED";
  email.updated_at = new Date().toISOString();
  store.saveEmail(email);

  res.json({
    email_id: email.id,
    category: email.category,
    edit_distance: result.editDistance,
    is_perfect: result.isPerfect,
    auto_approved: result.autoApproved,
    status: email.status,
  });
});

// ─── Autonomy Statistics ─────────────────────────────────────────────────────
app.get("/api/email/stats", (_req: Request, res: Response) => {
  res.json(store.getAllStats());
});

// ─── Seed from 50 Sample Emails ──────────────────────────────────────────────
app.post("/api/email/seed", async (_req: Request, res: Response) => {
  const samplePath = path.join(__dirname, "email/sample_emails.json");
  if (!fs.existsSync(samplePath)) {
    res.status(404).json({ error: "sample_emails.json not found" });
    return;
  }

  const raw = fs.readFileSync(samplePath, "utf-8");
  const samples = JSON.parse(raw) as Array<{
    sender_email: string;
    sender_name: string;
    subject: string;
    body: string;
  }>;

  // Process first 5 asynchronously into queue
  const seeded = [];
  for (const s of samples.slice(0, 5)) {
    const classification = await classifyEmail(s);
    const draftResult = await draftReply(s, classification.category);
    const stats = store.getCategoryStats(classification.category);

    const record: EmailRecord = {
      id: `em_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
      sender_email: s.sender_email,
      sender_name: s.sender_name,
      subject: s.subject,
      body: s.body,
      category: classification.category,
      intent: classification.intent,
      urgency: classification.urgency,
      draft_body: draftResult.draft,
      kb_sources: draftResult.sources,
      auto_approved: stats.auto_approved,
      status: stats.auto_approved ? "AUTO_SENT" : "DRAFT",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    store.saveEmail(record);
    seeded.push(record);
  }

  res.json({ message: `Seeded ${seeded.length} emails`, seeded });
});

app.listen(PORT, () => {
  console.log(`[Task 2: Inbox Agent (TypeScript)] Server running on http://localhost:${PORT}`);
});
