import { z } from "zod";

export const CategoryEnum = z.enum([
  "HOW_TO",
  "BILLING_REFUND",
  "FEATURE_REQUEST",
  "COMPLAINT",
  "QUOTE",
  "FOLLOW_UP",
  "SPAM",
  "GENERAL",
]);

export type Category = z.infer<typeof CategoryEnum>;

export const IntentEnum = z.enum([
  "question",
  "request",
  "complaint",
  "compliment",
  "other",
]);

export type Intent = z.infer<typeof IntentEnum>;

export const InboundEmailSchema = z.object({
  sender_email: z.string().email(),
  sender_name: z.string().default("Customer"),
  subject: z.string().min(1),
  body: z.string().min(1),
});

export type InboundEmail = z.infer<typeof InboundEmailSchema>;

export interface ClassificationResult {
  category: Category;
  intent: Intent;
  urgency: number; // 1 to 5
  summary: string;
}

export interface KBSource {
  article_id: string;
  title: string;
  url: string;
  excerpt: string;
  score: number;
}

export interface EmailRecord {
  id: string;
  sender_email: string;
  sender_name: string;
  subject: string;
  body: string;
  category: Category;
  intent: Intent;
  urgency: number;
  draft_body: string;
  final_body?: string;
  kb_sources: KBSource[];
  auto_approved: boolean;
  status: "DRAFT" | "SENT_AS_IS" | "EDITED" | "AUTO_SENT" | "DISCARDED";
  created_at: string;
  updated_at: string;
}

export interface FeedbackEvent {
  id: string;
  email_id: string;
  category: Category;
  original_draft: string;
  final_sent: string;
  edit_distance: number;
  action: "sent_as_is" | "minor_edit" | "major_edit" | "replaced";
  timestamp: string;
}

export interface CategoryStats {
  category: Category;
  consecutive_perfect: number;
  total_sent: number;
  total_edited: number;
  auto_approved: boolean;
  auto_revoked_count: number;
  last_updated: string;
}
