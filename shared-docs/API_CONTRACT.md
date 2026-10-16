# API Contract Specifications

## Task 1: Knowledge Brain API

### Endpoint: `POST /api/query`
- **Headers**: `X-API-Key: <task1_key>`
- **Request Body**:
```json
{
  "question": "How do I configure Stripe for member subscriptions?",
  "top_k": 3,
  "include_images": true
}
```
- **Response Body (200 OK)**:
```json
{
  "query_id": "qry_8f93e2b1",
  "question": "How do I configure Stripe for member subscriptions?",
  "answer": "To connect Stripe, navigate to Finance > Payment Gateways in the admin dashboard...",
  "confidence": 0.89,
  "sources": [
    {
      "article_id": "art_stripe_01",
      "title": "Stripe Payment Gateway Setup",
      "url": "https://support.brilliantdirectories.com/support/solutions/articles/123",
      "excerpt": "Enter your Stripe Secret and Publishable keys...",
      "score": 0.91
    }
  ],
  "images": [
    {
      "image_url": "https://support.brilliantdirectories.com/images/stripe_settings.png",
      "caption": "Screenshot of Payment Gateways settings showing API key fields.",
      "article_id": "art_stripe_01",
      "article_title": "Stripe Payment Gateway Setup"
    }
  ],
  "escalated": false,
  "human_task_id": null
}
```

---

## Task 2: Inbox Agent API

### Endpoint: `POST /api/email/inbound`
- **Request Body**:
```json
{
  "sender_email": "client@example.com",
  "sender_name": "Sarah Jones",
  "subject": "Need help adding member categories",
  "body": "Hi, where do I configure new member categories in my directory?"
}
```
- **Response Body (200 OK)**:
```json
{
  "email_id": "em_99a81c",
  "category": "HOW_TO",
  "intent": "question",
  "draft": "Hi Sarah,\n\nTo add a new member category, go to My Members > Member Categories in your admin menu...",
  "auto_approved": false,
  "kb_sources": ["https://support.brilliantdirectories.com/support/solutions/articles/456"]
}
```

---

## Task 3: Meeting to SOW API

### Endpoint: `POST /api/meeting/pipeline`
- **Request Body**:
```json
{
  "client_name": "MedConnect India",
  "project_name": "Doctor Directory Platform",
  "meeting_date": "2026-10-15",
  "transcript": "Alex: Thanks for making the time, Raj...",
  "is_followup": false,
  "parent_meeting_id": null,
  "hourly_rate": 100.0
}
```
- **Response Body (200 OK)**:
```json
{
  "meeting_id": "mtg_348a",
  "status": "DRAFT",
  "requirements": [
    {
      "title": "Stripe Gateway Integration",
      "description": "Configure payment plans",
      "feasibility": "BUILT_IN_SETTING",
      "estimated_hours_min": 0.5,
      "estimated_hours_max": 0.5
    }
  ],
  "sow_markdown": "# Scope of Work...",
  "proposal_markdown": "# Project Proposal: Doctor Directory Platform...",
  "human_approved": false
}
```
