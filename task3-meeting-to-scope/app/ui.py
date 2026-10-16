"""Streamlit SOW Builder UI — Task 3."""

from __future__ import annotations

import os

import requests
import streamlit as st

TASK3_API = os.getenv("TASK3_API_URL", "http://localhost:8003")

st.set_page_config(
    page_title="Meeting → SOW | AI Tech Consultant",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #0f1117; color: #e8eaf0; }
  
  .pipeline-step {
    display: flex; align-items: center; gap: 12px;
    background: #1e2130; border-radius: 8px; padding: 10px 16px; margin: 4px 0;
  }
  .step-done { border-left: 3px solid #10b981; }
  .metric-card {
    background: #1e2130; border: 1px solid #2d3148;
    border-radius: 12px; padding: 20px; text-align: center;
  }
  .metric-value {
    font-size: 28px; font-weight: 700;
    background: linear-gradient(135deg, #6366f1, #10b981);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .req-card {
    background: #141824; border: 1px solid #2d3148;
    border-radius: 8px; padding: 12px; margin: 6px 0;
  }
  .badge-setting { color: #10b981; font-weight: 600; }
  .badge-dev { color: #f59e0b; font-weight: 600; }
  .diff-new { border-left: 4px solid #10b981; padding-left: 12px; }
  .diff-changed { border-left: 4px solid #f59e0b; padding-left: 12px; }
  .diff-oos { border-left: 4px solid #ef4444; padding-left: 12px; }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Meeting → SOW")
    st.divider()

    try:
        meetings = requests.get(f"{TASK3_API}/api/meetings?limit=20", timeout=5).json()
        if meetings:
            st.markdown(f"**{len(meetings)} meetings processed**")
    except Exception:
        st.warning("⚠️ API unreachable")
        meetings = []

    st.divider()
    st.markdown("### 📁 Load Sample Transcript")
    transcript_file = st.selectbox("Pick a transcript", [
        "meeting1_medconnect_discovery.txt",
        "meeting2_medconnect_followup.txt",
        "meeting3_stylehub_discovery.txt",
        "Custom (type below)",
    ])

    sample_transcripts = {
        "meeting1_medconnect_discovery.txt": "data/transcripts/meeting1_medconnect_discovery.txt",
        "meeting2_medconnect_followup.txt": "data/transcripts/meeting2_medconnect_followup.txt",
        "meeting3_stylehub_discovery.txt": "data/transcripts/meeting3_stylehub_discovery.txt",
    }

    loaded_transcript = ""
    if transcript_file in sample_transcripts:
        try:
            with open(sample_transcripts[transcript_file]) as f:
                loaded_transcript = f.read()
        except FileNotFoundError:
            pass


# ─── Main ─────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Meeting → Scope of Work")
st.markdown("Paste a meeting transcript. Get a scope, estimate, and proposal in minutes.")

tab_input, tab_results, tab_meetings = st.tabs(["📥 New Meeting", "📄 Results", "📁 Past Meetings"])

with tab_input:
    col1, col2 = st.columns([1, 1])

    with col1:
        client_name = st.text_input("Client Name", "Raj Mehta — MedConnect")
        project_name = st.text_input("Project Name", "MedConnect India Directory")
        meeting_date = st.date_input("Meeting Date")
        hourly_rate = st.number_input("Hourly Rate (USD)", value=75, min_value=10, max_value=500)
        is_followup = st.toggle("This is a follow-up meeting")

        parent_meeting_id = None
        if is_followup and meetings:
            options = {f"{m['project_name']} ({m['id'][:8]})": m["id"] for m in meetings}
            selected = st.selectbox("Original Meeting", list(options.keys()))
            parent_meeting_id = options.get(selected)

    with col2:
        transcript = st.text_area(
            "Meeting Transcript",
            value=loaded_transcript,
            height=400,
            placeholder="Paste the full meeting transcript here…",
        )

    if st.button("🚀 Run Pipeline", type="primary", use_container_width=True):
        if not transcript.strip():
            st.error("Please paste a transcript.")
        else:
            progress = st.progress(0, text="Starting pipeline…")
            with st.spinner("Running 7-agent pipeline…"):
                try:
                    progress.progress(10, "Sending to API…")
                    resp = requests.post(
                        f"{TASK3_API}/api/meetings/process",
                        json={
                            "client_name": client_name,
                            "project_name": project_name,
                            "meeting_date": str(meeting_date),
                            "transcript": transcript,
                            "is_followup": is_followup,
                            "parent_meeting_id": parent_meeting_id,
                            "hourly_rate": float(hourly_rate),
                        },
                        timeout=300,
                    )
                    data = resp.json()
                    progress.progress(100, "Done!")
                    st.session_state["sow_result"] = data
                    st.success(f"✅ Pipeline complete in {data.get('latency_ms_total', 0)/1000:.1f}s")
                    st.info("Switch to the **Results** tab to review and approve.")
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")


with tab_results:
    data = st.session_state.get("sow_result")
    if not data:
        st.info("Run a meeting transcript first.")
    else:
        sow_id = data.get("sow_id", "")

        # ─── Metrics ──────────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"""<div class="metric-card">
            <div class="metric-value">{data.get("total_hours_min",0):.0f}–{data.get("total_hours_max",0):.0f}</div>
            <div>Est. Hours</div></div>""", unsafe_allow_html=True)
        col2.markdown(f"""<div class="metric-card">
            <div class="metric-value">${data.get("total_cost_min",0):,.0f}–${data.get("total_cost_max",0):,.0f}</div>
            <div>Investment</div></div>""", unsafe_allow_html=True)
        col3.markdown(f"""<div class="metric-card">
            <div class="metric-value">{len(data.get("requirements",[]))}</div>
            <div>Requirements</div></div>""", unsafe_allow_html=True)
        col4.markdown(f"""<div class="metric-card">
            <div class="metric-value">{len(data.get("tasks",[]))}</div>
            <div>Tasks</div></div>""", unsafe_allow_html=True)

        st.divider()

        # ─── Pipeline steps ───────────────────────────────────────────────
        with st.expander("🔧 Pipeline Execution Log"):
            for step in data.get("pipeline_steps", []):
                st.markdown(
                    f'<div class="pipeline-step step-done">'
                    f'<span>✅</span><span><b>{step["step"]}</b></span>'
                    f'<span style="color:#9ca3af">{step["elapsed_ms"]}ms</span>'
                    f'<span style="color:#6b7280;font-size:12px">{step.get("detail","")}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # ─── Diff (follow-up only) ─────────────────────────────────────────
        if data.get("diff_summary"):
            st.markdown("### 🔄 Changes from Previous Meeting")
            st.info(data["diff_summary"])

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown("**🆕 New Items**")
                for item in data.get("new_items") or []:
                    st.markdown(f'<div class="diff-new">{item.get("title","")}<br>'
                                f'<small>{item.get("description","")[:80]}</small></div>',
                                unsafe_allow_html=True)

            with col_b:
                st.markdown("**✏️ Changed Items**")
                for item in data.get("changed_items") or []:
                    st.markdown(f'<div class="diff-changed">{item.get("title","")}<br>'
                                f'<small>{item.get("change_summary","")[:80]}</small></div>',
                                unsafe_allow_html=True)

            with col_c:
                st.markdown("**🚫 Out of Scope**")
                for item in data.get("out_of_scope_items") or []:
                    st.markdown(f'<div class="diff-oos">{item.get("title","")}<br>'
                                f'<small>→ Quote separately</small></div>',
                                unsafe_allow_html=True)

            st.divider()

        # ─── Requirements & feasibility ───────────────────────────────────
        st.markdown("### 📋 Requirements & Feasibility")
        feas_map = {f["requirement_title"]: f for f in data.get("feasibility", [])}
        for req in data.get("requirements", []):
            f = feas_map.get(req["title"], {})
            is_setting = f.get("can_be_done_with_setting", False)
            badge = '<span class="badge-setting">✅ Platform Setting</span>' if is_setting else \
                    '<span class="badge-dev">🔧 Custom Dev</span>'
            st.markdown(
                f'<div class="req-card">'
                f'<b>{req["title"]}</b> {badge} '
                f'<span style="color:#6b7280;font-size:11px">[{req.get("priority","?")}]</span><br>'
                f'<span style="font-size:13px;color:#9ca3af">{req.get("description","")}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.divider()

        # ─── Task list ────────────────────────────────────────────────────
        st.markdown("### ⏱️ Task Estimates")
        for task in data.get("tasks", []):
            st.markdown(
                f"**{task['task']}** `{task['type']}` — "
                f"{task.get('hours_min',0)}–{task.get('hours_max',0)}h | "
                f"_{task.get('notes','')[:80]}_"
            )

        st.divider()

        # ─── SOW & Proposal ───────────────────────────────────────────────
        col_sow, col_prop = st.columns(2)
        with col_sow:
            st.markdown("### 📄 Scope of Work (Internal)")
            st.markdown(data.get("sow_markdown", ""))

        with col_prop:
            st.markdown("### 💼 Client Proposal")
            st.markdown(data.get("proposal_markdown", ""))

        st.divider()

        # ─── Approval ─────────────────────────────────────────────────────
        st.markdown("### ✅ Human Approval Required")
        st.warning("Nothing goes to the client until you approve here.")
        col_a, col_b = st.columns(2)
        if col_a.button("✅ Approve & Send to Client", type="primary"):
            try:
                requests.post(f"{TASK3_API}/api/sow/{sow_id}/approve",
                              json={"approved": True}, timeout=10)
                st.success("SOW approved! 🎉")
            except Exception as e:
                st.error(str(e))
        if col_b.button("❌ Reject — Need Revisions"):
            try:
                requests.post(f"{TASK3_API}/api/sow/{sow_id}/approve",
                              json={"approved": False}, timeout=10)
                st.info("SOW rejected. Go back and revise the transcript or re-run.")
            except Exception as e:
                st.error(str(e))


with tab_meetings:
    st.markdown("### 📁 Past Meetings")
    try:
        meetings = requests.get(f"{TASK3_API}/api/meetings?limit=50", timeout=5).json()
        for m in meetings:
            follow_badge = "🔄 Follow-up" if m["is_followup"] else "🆕 Discovery"
            st.markdown(
                f"**{m['project_name']}** — {m['client_name']} "
                f"| {follow_badge} | `{m['id'][:8]}` | {m.get('created_at','')[:10]}"
            )
    except Exception:
        st.warning("Could not load meetings.")
