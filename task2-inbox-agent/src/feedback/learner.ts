import { Category, FeedbackEvent } from "../email/types.js";
import { store } from "./store.js";

export const AUTO_APPROVE_THRESHOLD = parseInt(process.env.AUTO_APPROVE_THRESHOLD || "20", 10);
export const AUTO_REVOKE_THRESHOLD = parseInt(process.env.AUTO_REVOKE_THRESHOLD || "3", 10);
export const EDIT_DISTANCE_PERFECT = parseFloat(process.env.EDIT_DISTANCE_PERFECT || "0.05");

/**
 * Computes standard Levenshtein distance between two strings.
 */
export function levenshteinDistance(a: string, b: string): number {
  const an = a.length;
  const bn = b.length;
  if (an === 0) return bn;
  if (bn === 0) return an;

  const matrix: number[][] = [];
  for (let i = 0; i <= bn; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= an; j++) {
    matrix[0][j] = j;
  }

  for (let i = 1; i <= bn; i++) {
    for (let j = 1; j <= an; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1, // substitution
          matrix[i][j - 1] + 1,     // insertion
          matrix[i - 1][j] + 1      // deletion
        );
      }
    }
  }

  return matrix[bn][an];
}

/**
 * Normalised edit distance ratio:
 * 0.0 = identical, 1.0 = completely different.
 */
export function editDistanceRatio(a: string, b: string): number {
  const cleanA = a.trim();
  const cleanB = b.trim();
  const maxLen = Math.max(cleanA.length, cleanB.length);
  if (maxLen === 0) return 0.0;
  return levenshteinDistance(cleanA, cleanB) / maxLen;
}

/**
 * Record human feedback on a draft, updates category statistics,
 * and handles auto-approval / revocation.
 */
export function recordFeedback(
  emailId: string,
  category: Category,
  originalDraft: string,
  finalSent: string
): { editDistance: number; isPerfect: boolean; autoApproved: boolean } {
  const distance = editDistanceRatio(originalDraft, finalSent);
  const isPerfect = distance <= EDIT_DISTANCE_PERFECT;

  let action: FeedbackEvent["action"] = "sent_as_is";
  if (distance > 0.4) {
    action = "replaced";
  } else if (distance > 0.15) {
    action = "major_edit";
  } else if (!isPerfect) {
    action = "minor_edit";
  }

  const event: FeedbackEvent = {
    id: `fb_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    emailId,
    category,
    originalDraft,
    finalSent,
    edit_distance: distance,
    action,
    timestamp: new Date().toISOString(),
  };

  store.saveFeedback(event);

  const stats = store.getCategoryStats(category);

  if (isPerfect) {
    stats.consecutive_perfect += 1;
    stats.total_sent += 1;
  } else {
    stats.consecutive_perfect = 0;
    stats.total_edited += 1;

    // Revoke auto-approval if previously granted and human had to edit
    if (stats.auto_approved) {
      console.warn(`[Learner] Auto-approval REVOKED for category "${category}" (editDistance=${distance.toFixed(3)})`);
      stats.auto_approved = false;
      stats.auto_revoked_count += 1;
    }
  }

  // Grant auto-approval if consecutive perfect threshold reached
  if (!stats.auto_approved && stats.consecutive_perfect >= AUTO_APPROVE_THRESHOLD) {
    stats.auto_approved = true;
    console.log(`[Learner] Auto-approval GRANTED for category "${category}" (${stats.consecutive_perfect} consecutive perfect drafts)`);
  }

  store.saveCategoryStats(stats);

  return {
    editDistance: distance,
    isPerfect,
    autoApproved: stats.auto_approved,
  };
}
