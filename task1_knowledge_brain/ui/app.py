"""Streamlit chatbot UI for the Knowledge Brain (Task 1).

A clean, dark-themed interface where anyone can ask questions about
Brilliant Directories and see cited sources + relevant screenshots.
"""

from __future__ import annotations

import os
import requests
import streamlit as st

# ─── Config ───────────────────────────────────────────────────────────────────
TASK1_API = os.getenv("TASK1_API_URL", "http://localhost:8001")

st.set_page_config(
    page_title="Knowledge Brain — AI Tech Consultant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  
  .stApp { background: #0f1117; color: #e8eaf0; }
  
  .chat-bubble-user {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 18px 18px 4px 18px;
    padding: 12px 18px;
    margin: 8px 0 8px 20%;
    color: white;
    font-size: 15px;
  }
  .chat-bubble-ai {
    background: #1e2130;
    border: 1px solid #2d3148;
    border-radius: 18px 18px 18px 4px;
    padding: 14px 18px;
    margin: 8px 20% 8px 0;
    color: #e8eaf0;
    font-size: 15px;
    line-height: 1.6;
  }
  .source-chip {
    display: inline-block;
    background: #1a2035;
    border: 1px solid #6366f1;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    color: #a5b4fc;
    margin: 3px;
  }
  .confidence-bar {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981);
  }
  .stat-card {
    background: #1e2130;
    border: 1px solid #2d3148;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
  }
  .escalated-badge {
    background: #fef3c7;
    color: #92400e;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
  }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 Knowledge Brain")
    st.markdown("*Brilliant Directories Help Center*")
    st.divider()

    # KB Stats
    try:
        stats = requests.get(f"{TASK1_API}/api/stats", timeout=5).json()
        col1, col2 = st.columns(2)
        col1.metric("Articles", stats.get("total_articles", 0))
        col2.metric("Chunks", stats.get("total_chunks", 0))
        col1.metric("Images", stats.get("total_images", 0))
        last_sync = stats.get("last_incremental_sync") or stats.get("last_full_sync") or "Never"
        st.caption(f"Last sync: {last_sync[:10] if last_sync != 'Never' else 'Never'}")
    except Exception:
        st.warning("⚠️ API unreachable")

    st.divider()
    top_k = st.slider("Sources to retrieve", 3, 10, 5)
    include_images = st.toggle("Include screenshot answers", value=True)

    st.divider()
    st.markdown("**Admin Controls**")
    api_key = st.text_input("API Key", type="password", value="dev-secret-task1")
    if st.button("🔄 Trigger Incremental Sync"):
        try:
            r = requests.post(
                f"{TASK1_API}/api/scrape/incremental",
                headers={"X-API-Key": api_key}, timeout=10
            )
            st.success(f"Sync started: job_id={r.json().get('job_id', '')[:8]}…")
        except Exception as e:
            st.error(str(e))

    if st.button("🏗️ Full Scrape (slow)"):
        try:
            r = requests.post(
                f"{TASK1_API}/api/scrape/full",
                json={"mode": "full"},
                headers={"X-API-Key": api_key}, timeout=10
            )
            st.success(f"Full scrape started: {r.json().get('job_id', '')[:8]}…")
        except Exception as e:
            st.error(str(e))


# ─── Main chat area ───────────────────────────────────────────────────────────
st.markdown("# 🧠 Knowledge Brain")
st.markdown("Ask anything about Brilliant Directories — settings, payments, design, and more.")
st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_ids" not in st.session_state:
    st.session_state.query_ids = []

# Render history
for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{msg["content"]}</div>',
                    unsafe_allow_html=True)
        meta = msg.get("meta", {})
        # Sources
        if meta.get("sources"):
            source_html = "".join(
                f'<span class="source-chip">📄 <a href="{s["url"]}" target="_blank" '
                f'style="color:#a5b4fc;text-decoration:none;">{s["title"][:40]}</a></span>'
                for s in meta["sources"]
            )
            st.markdown(f"<div>{source_html}</div>", unsafe_allow_html=True)
        # Images
        if meta.get("images"):
            with st.expander(f"🖼️ {len(meta['images'])} screenshot(s)"):
                for img in meta["images"]:
                    st.image(img["image_url"], caption=img["caption"], use_column_width=True)
        # Escalated
        if meta.get("escalated"):
            st.markdown(
                '<span class="escalated-badge">⏳ Escalated to human expert</span>',
                unsafe_allow_html=True
            )
        # Feedback
        if meta.get("query_id"):
            cols = st.columns([1, 1, 1, 1, 1, 5])
            for star, col in zip(range(1, 6), cols):
                if col.button(f"{'⭐' * star}", key=f"star_{i}_{star}"):
                    try:
                        requests.post(
                            f"{TASK1_API}/api/feedback",
                            json={"query_id": meta["query_id"], "rating": star},
                            timeout=5
                        )
                        st.toast(f"Thanks for the {star}-star rating!")
                    except Exception:
                        pass

# Input box
question = st.chat_input("Ask a question about Brilliant Directories…")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("Searching knowledge base…"):
        try:
            resp = requests.post(
                f"{TASK1_API}/api/query",
                json={
                    "question": question,
                    "top_k": top_k,
                    "include_images": include_images,
                },
                timeout=30,
            )
            data = resp.json()
            st.session_state.messages.append({
                "role": "assistant",
                "content": data["answer"],
                "meta": {
                    "sources": data.get("sources", []),
                    "images": data.get("images", []),
                    "confidence": data.get("confidence", 0),
                    "escalated": data.get("escalated", False),
                    "query_id": data.get("query_id"),
                },
            })
        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ Error: {e}",
                "meta": {},
            })

    st.rerun()
