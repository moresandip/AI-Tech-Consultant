import { KBSource } from "../email/types.js";

const TASK1_API_URL = process.env.TASK1_API_URL || "http://localhost:8001";
const TASK1_API_KEY = process.env.TASK1_API_KEY || "dev-secret-task1";

export interface KBQueryResponse {
  query_id?: string;
  question: string;
  answer: string;
  confidence: number;
  sources: KBSource[];
  images?: Array<{
    image_url: string;
    caption: string;
    article_id: string;
  }>;
  escalated?: boolean;
}

export class KnowledgeClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl = TASK1_API_URL, apiKey = TASK1_API_KEY) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  async query(question: string, topK = 3): Promise<KBQueryResponse> {
    const url = `${this.baseUrl}/api/query`;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": this.apiKey,
        },
        body: JSON.stringify({
          question,
          top_k: topK,
          include_images: true,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = (await response.json()) as KBQueryResponse;
        return data;
      }

      console.warn(`[KnowledgeClient] Query failed with status ${response.status}`);
    } catch (err) {
      console.warn(`[KnowledgeClient] Could not reach Knowledge Brain at ${url}:`, (err as Error).message);
    }

    // Graceful offline fallback
    return {
      question,
      answer: "No specific knowledge base article found for this query.",
      confidence: 0.0,
      sources: [],
      escalated: false,
    };
  }
}

export const knowledgeClient = new KnowledgeClient();
