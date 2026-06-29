"""
Lab 11 — Streamlit frontend entry point.

This file satisfies the Lab 11 submission checklist requirement for 'app.py'.
The full implementation lives in streamlit_app.py. Running either file is
equivalent:

    streamlit run app.py
    streamlit run streamlit_app.py

Features (all in streamlit_app.py):
  - Interactive chat with single-agent and multi-agent modes
  - st.feedback("thumbs") widget after every agent response (Lab 11 Task 1)
  - Feedback linked to thread_id and message_id (Lab 11 Task 1)
  - Persistent feedback logging to feedback_log.db (Lab 11 Task 2)
  - Schema: timestamp, user_input, agent_response, feedback_score, optional_comment
"""

# Re-execute the full Streamlit application.
# Streamlit executes app.py top-to-bottom in a special runtime context;
# importing streamlit_app triggers all of its top-level st.* calls in that
# same context, making this a transparent alias.
import streamlit_app  # noqa: F401
