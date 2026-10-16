import Anthropic from "@anthropic-ai/sdk";
import { ClassificationResult, InboundEmail } from "./types.js";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

const MODEL_FAST = process.env.MODEL_FAST || "claude-haiku-4-5";

export async function classifyEmail(email: InboundEmail): Promise<ClassificationResult> {
  const prompt = `Classify this customer email for Brilliant Directories directory software support.

Email Subject: ${email.subject}
Email Body:
${email.body}

Categories:
- "HOW_TO": Asking how to configure settings, features, forms, designs.
- "BILLING_REFUND": Invoices, subscription upgrades, failed payments, refund requests.
- "FEATURE_REQUEST": Asking for new functionality, integrations, or custom development.
- "COMPLAINT": Bugs, issues, slow loading, dissatisfaction.
- "QUOTE": Asking for pricing or hourly estimates for custom projects.
- "FOLLOW_UP": Status checks on past tickets or conversations.
- "SPAM": Unsolicited sales, irrelevant backlinks, phishing.
- "GENERAL": Partner inquiries, general business inquiries.

Respond ONLY with a valid JSON object matching this schema:
{
  "category": "HOW_TO" | "BILLING_REFUND" | "FEATURE_REQUEST" | "COMPLAINT" | "QUOTE" | "FOLLOW_UP" | "SPAM" | "GENERAL",
  "intent": "question" | "request" | "complaint" | "compliment" | "other",
  "urgency": 1 to 5 (5 is most urgent),
  "summary": "1-sentence summary of the request"
}`;

  try {
    const response = await anthropic.messages.create({
      model: MODEL_FAST,
      max_tokens: 500,
      messages: [{ role: "user", content: prompt }],
    });

    const block = response.content[0];
    if (block && block.type === "text") {
      let text = block.text.trim();
      if (text.startsWith("```")) {
        text = text.replace(/^```(json)?\n?/, "").replace(/\n?```$/, "");
      }
      const parsed = JSON.parse(text) as ClassificationResult;
      return parsed;
    }
  } catch (err) {
    console.error("[Classifier] Haiku classification failed, falling back to rule-based:", err);
  }

  // Deterministic rule-based fallback
  const sub = email.subject.toLowerCase();
  const body = email.body.toLowerCase();

  let category: ClassificationResult["category"] = "HOW_TO";
  if (sub.includes("refund") || body.includes("refund") || sub.includes("charged") || body.includes("payment")) {
    category = "BILLING_REFUND";
  } else if (sub.includes("broken") || body.includes("error") || body.includes("terrible")) {
    category = "COMPLAINT";
  } else if (sub.includes("quote") || body.includes("estimate") || body.includes("cost")) {
    category = "QUOTE";
  } else if (sub.includes("custom") || body.includes("integrate") || body.includes("feature")) {
    category = "FEATURE_REQUEST";
  } else if (sub.includes("follow") || body.includes("ticket #")) {
    category = "FOLLOW_UP";
  } else if (sub.includes("seo backlinks") || body.includes("guest post")) {
    category = "SPAM";
  }

  return {
    category,
    intent: "question",
    urgency: 3,
    summary: email.subject,
  };
}
