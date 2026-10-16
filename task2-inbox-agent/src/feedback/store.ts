import { Category, CategoryStats, EmailRecord, FeedbackEvent } from "../email/types.js";

const DEFAULT_CATEGORIES: Category[] = [
  "HOW_TO",
  "BILLING_REFUND",
  "FEATURE_REQUEST",
  "COMPLAINT",
  "QUOTE",
  "FOLLOW_UP",
  "SPAM",
  "GENERAL",
];

class MemoryStore {
  private emails: Map<string, EmailRecord> = new Map();
  private feedbacks: FeedbackEvent[] = [];
  private stats: Map<Category, CategoryStats> = new Map();

  constructor() {
    for (const cat of DEFAULT_CATEGORIES) {
      this.stats.set(cat, {
        category: cat,
        consecutive_perfect: 0,
        total_sent: 0,
        total_edited: 0,
        auto_approved: false,
        auto_revoked_count: 0,
        last_updated: new Date().toISOString(),
      });
    }
  }

  saveEmail(email: EmailRecord): void {
    this.emails.set(email.id, email);
  }

  getEmail(id: string): EmailRecord | undefined {
    return this.emails.get(id);
  }

  getAllEmails(): EmailRecord[] {
    return Array.from(this.emails.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }

  saveFeedback(event: FeedbackEvent): void {
    this.feedbacks.push(event);
  }

  getFewShotApproved(category: Category, limit = 3): FeedbackEvent[] {
    return this.feedbacks
      .filter((f) => f.category === category && f.action === "sent_as_is")
      .slice(-limit);
  }

  getCategoryStats(category: Category): CategoryStats {
    let stat = this.stats.get(category);
    if (!stat) {
      stat = {
        category,
        consecutive_perfect: 0,
        total_sent: 0,
        total_edited: 0,
        auto_approved: false,
        auto_revoked_count: 0,
        last_updated: new Date().toISOString(),
      };
      this.stats.set(category, stat);
    }
    return stat;
  }

  saveCategoryStats(stat: CategoryStats): void {
    stat.last_updated = new Date().toISOString();
    this.stats.set(stat.category, stat);
  }

  getAllStats(): CategoryStats[] {
    return Array.from(this.stats.values());
  }
}

export const store = new MemoryStore();
