"""Streamlit Inbox Agent UI — Task 2."""

from __future__ import annotations

import json
import os

import requests
import streamlit as st

TASK2_API = os.getenv("TASK2_API_URL", "http://localhost:8002")

st.set_page_config(
    page_title="Inbox Agent — AI Tech Consultant",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #0f1117; color: #e8eaf0; }
  .email-card {
    background: #1e2130; border: 1px solid #2d3148; border-radius: 12px;
    padding: 16px; margin-bottom: 12px; cursor: pointer;
  }
  .badge {
    display: inline-block; border-radius: 20px; padding: 2px 10px;
    font-size: 11px; font-weight: 600; margin: 2px;
  }
  .badge-how-to { background: #1e3a5f; color: #60a5fa; }
  .badge-billing { background: #1a3a2a; color: #4ade80; }
  .badge-refund { background: #3a1a1a; color: #f87171; }
  .badge-complaint { background: #3a1a2a; color: #f472b6; }
  .badge-quote { background: #2a2a1a; color: #fbbf24; }
  .badge-other { background: #2a2a2a; color: #9ca3af; }
  .auto-sent { background: #064e3b; color: #6ee7b7; }
  .pending { background: #1e1b4b; color: #a5b4fc; }
  .draft-box {
    background: #141824; border: 1px solid #6366f1; border-radius: 8px;
    padding: 16px; font-size: 14px; line-height: 1.7; white-space: pre-wrap;
  }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar: paste new email ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📬 Inbox Agent")
    st.divider()

    try:
        stats = requests.get(f"{TASK2_API}/api/stats", timeout=5).json()
        c1, c2 = st.columns(2)
        c1.metric("Emails", stats.get("total_emails", 0))
        c2.metric("Drafted", stats.get("total_drafted", 0))
        auto_cats = stats.get("auto_approved_categories", [])
        if auto_cats:
            st.success(f"✅ Auto-send: {', '.join(auto_cats)}")
    except Exception:
        st.warning("⚠️ API unreachable")

    st.divider()
    st.markdown("### ➕ Process New Email")
    sender_name = st.text_input("From name", "John Smith")
    sender_email = st.text_input("From email", "customer@example.com")
    subject = st.text_input("Subject", "How do I add a member?")
    body = st.text_area("Email body", height=150,
                        value="Hi, I'm trying to add a new member to my directory but I can't find the option in the admin panel. Can you help?")

    if st.button("📨 Process Email", type="primary"):
        with st.spinner("Classifying and drafting reply…"):
            try:
                resp = requests.post(
                    f"{TASK2_API}/api/emails/process",
                    json={
                        "sender_name": sender_name,
                        "sender_email": sender_email,
                        "subject": subject,
                        "body": body,
                    },
                    timeout=30,
                )
                data = resp.json()
                st.session_state["last_processed"] = data
                st.success(f"✅ Draft ready! Category: {data.get('category', 'unknown')}")
                if data.get("auto_sent"):
                    st.info("🤖 Auto-sent (this category is trusted)")
            except Exception as e:
                st.error(str(e))

    st.divider()
    if st.button("📂 Load Sample Emails"):
        with open("data/sample_emails.json") as f:
            samples = json.load(f)
        with st.spinner(f"Processing {len(samples)} sample emails…"):
            for email in samples[:5]:  # first 5 for demo
                requests.post(f"{TASK2_API}/api/emails/process", json=email, timeout=30)
        st.success("5 sample emails processed!")
        st.rerun()


# ─── Main area ────────────────────────────────────────────────────────────────
st.markdown("# 📬 Inbox Agent")
tab1, tab2 = st.tabs(["📥 Email Queue", "📊 Learning Stats"])

with tab1:
    col_list, col_draft = st.columns([1, 1.5])

    with col_list:
        st.markdown("### Inbox")
        try:
            emails = requests.get(
                f"{TASK2_API}/api/emails?limit=30", timeout=5
            ).json()
        except Exception:
            emails = []
            st.warning("Could not load emails.")

        for email in emails:
            status_badge = "auto-sent" if email["auto_sent"] else email["status"]
            cat = email.get("category", "other")
            badge_class = f"badge-{cat}" if cat in [
                "how-to", "billing", "refund", "complaint", "quote"
            ] else "badge-other"

            st.markdown(f"""
            <div class="email-card">
              <div style="font-weight:600;font-size:14px;">{email['subject'][:50]}</div>
              <div style="color:#9ca3af;font-size:12px;">
                {email['sender_name']} · {email['received_at'][:10] if email.get('received_at') else ''}
              </div>
              <span class="badge {badge_class}">{cat}</span>
              <span class="badge {'auto-sent' if email['auto_sent'] else 'pending'}">
                {'🤖 auto-sent' if email['auto_sent'] else '⏳ ' + email['status']}
              </span>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"View Draft", key=f"view_{email['id']}"):
                st.session_state["viewing_email"] = email

    with col_draft:
        st.markdown("### Draft Review")

        # Show last processed or selected email
        data = st.session_state.get("last_processed") or {}
        viewing = st.session_state.get("viewing_email")

        if viewing:
            try:
                draft_data = requests.get(
                    f"{TASK2_API}/api/emails/{viewing['id']}/draft", timeout=5
                ).json()
                draft_body = draft_data.get("body", "")
                email_id = viewing["id"]
                draft_id = draft_data.get("draft_id", "")
                category = viewing.get("category", "other")

                st.markdown(f"**To:** {viewing['sender_name']} `{viewing['sender_email']}`")
                st.markdown(f"**Subject:** Re: {viewing['subject']}")
                st.divider()

                edited_draft = st.text_area(
                    "Draft Reply (edit if needed)",
                    value=draft_body,
                    height=300,
                    key=f"draft_edit_{email_id}",
                )

                if draft_data.get("kb_sources"):
                    with st.expander("📚 Knowledge Base Sources"):
                        for s in draft_data["kb_sources"]:
                            st.markdown(f"- [{s['title']}]({s['url']})")

                c1, c2, c3 = st.columns(3)
                if c1.button("✅ Send As-Is", type="primary"):
                    action = "sent_as_is"
                    requests.post(
                        f"{TASK2_API}/api/emails/{email_id}/feedback",
                        json={"action": action, "final_body": draft_body},
                        timeout=10
                    )
                    st.success("Sent! Learning signal: ✅ perfect draft")
                    st.session_state["viewing_email"] = None
                    st.rerun()

                if c2.button("✏️ Send Edited"):
                    action = "edited"
                    requests.post(
                        f"{TASK2_API}/api/emails/{email_id}/feedback",
                        json={"action": action, "final_body": edited_draft},
                        timeout=10
                    )
                    st.success("Sent! Learning signal: ✏️ edited draft")
                    st.session_state["viewing_email"] = None
                    st.rerun()

                if c3.button("🗑️ Discard"):
                    st.session_state["viewing_email"] = None
                    st.rerun()

            except Exception as e:
                st.error(str(e))
        elif data:
            st.markdown(f"**Category:** `{data.get('category')}` | **Urgency:** `{data.get('urgency')}`")
            st.markdown(f"**Summary:** {data.get('summary', '')}")
            st.divider()
            st.markdown(f'<div class="draft-box">{data.get("draft_body", "")}</div>',
                        unsafe_allow_html=True)
        else:
            st.info("Select an email from the queue or process a new one.")

with tab2:
    st.markdown("### 📊 Learning Progress by Category")
    try:
        stats = requests.get(f"{TASK2_API}/api/stats", timeout=5).json()
        for cat_stat in stats.get("category_stats", []):
            progress = min(cat_stat["consecutive_perfect"] / 20, 1.0)
            col1, col2 = st.columns([2, 3])
            col1.markdown(f"**{cat_stat['category']}**")
            col2.progress(progress,
                          text=f"{cat_stat['consecutive_perfect']}/20 perfect drafts")
            if cat_stat["auto_approved"]:
                st.success(f"🤖 `{cat_stat['category']}` — AUTO-SEND ENABLED")
    except Exception:
        st.info("No stats yet. Process some emails first.")
