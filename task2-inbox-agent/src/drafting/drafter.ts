import Anthropic from "@anthropic-ai/sdk";
import { Category, InboundEmail, KBSource } from "../email/types.js";
import { knowledgeClient } from "../knowledge-client/client.js";
import { store } from "../feedback/store.js";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

const MODEL_BALANCED = process.env.MODEL_BALANCED || "claude-sonnet-4-5";

export interface DraftResult {
  draft: string;
  sources: KBSource[];
  auto_approved: boolean;
  model: string;
}

export async function draftReply(
  email: InboundEmail,
  category: Category
): Promise<DraftResult> {
  // 1. Fetch factual knowledge from Task 1 Knowledge Brain
  const kbResult = await knowledgeClient.query(
    `${email.subject} ${email.body}`.substring(0, 300),
    3
  );

  // 2. Fetch past approved replies for few-shot in-context learning
  const fewShots = store.getFewShotApproved(category, 2);
  let fewShotText = "";
  if (fewShots.length > 0) {
    fewShotText = "\n\nPAST HIGH-QUALITY APPROVED REPLIES FOR THIS CATEGORY (learn from style):\n";
    for (const fs of fewShots) {
      fewShotText += `Example Final Reply:\n${fs.finalSent}\n---\n`;
    }
  }

  // 3. Format KB context
  let kbContext = kbResult.answer;
  if (kbResult.sources && kbResult.sources.length > 0) {
    kbContext += "\n\nReferenced Articles:";
    for (const s of kbResult.sources) {
      kbContext += `\n- ${s.title}: ${s.excerpt} (${s.url})`;
    }
  }

  const prompt = `You are an AI support consultant writing a customer email reply on behalf of Brilliant Directories.

CUSTOMER EMAIL:
From: ${email.sender_name} <${email.sender_email}>
Subject: ${email.subject}
Body:
${email.body}

CATEGORY: ${category}

KNOWLEDGE BASE CONTEXT (From Task 1):
${kbContext}
${fewShotText}

INSTRUCTIONS:
1. Write a polite, warm, and highly professional response.
2. Address the customer by name ("Hi ${email.sender_name},").
3. Answer their question directly using the knowledge base context. If a setting or menu path is required, state it clearly.
4. Keep the email concise (100–180 words).
5. Never invent features not in the context. If you cannot answer fully, offer to escalate to an engineer.
6. Sign off with:
Best regards,
Brilliant Directories Support Team`;

  try {
    const response = await anthropic.messages.create({
      model: MODEL_BALANCED,
      max_tokens: 800,
      messages: [{ role: "user", content: prompt }],
    });

    const block = response.content[0];
    if (block && block.type === "text") {
      const stats = store.getCategoryStats(category);
      return {
        draft: block.text.trim(),
        sources: kbResult.sources || [],
        auto_approved: stats.auto_approved,
        model: MODEL_BALANCED,
      };
    }
  } catch (err) {
    console.error("[Drafter] Sonnet drafting failed, using fallback:", err);
  }

  // Graceful fallback draft
  return {
    draft: `Hi ${email.sender_name},\n\nThank you for reaching out to Brilliant Directories Support.\n\nRegarding your inquiry on "${email.subject}": ${kbResult.answer}\n\nPlease let us know if you have any further questions.\n\nBest regards,\nBrilliant Directories Support Team`,
    sources: kbResult.sources || [],
    auto_approved: false,
    model: "template-fallback",
  };
}
