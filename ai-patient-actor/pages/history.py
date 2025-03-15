import streamlit as st
st.set_page_config(page_title="Interaction History", page_icon="📜")

import db_helper as db
from datetime import datetime

st.title("Your Interaction & Feedback History")

# Check if user is logged in
if "user" not in st.session_state:
    st.error("You must be logged in to view your history.")
    st.stop()

user = st.session_state["user"]

# Retrieve interactions for the current user.
interactions = db.get_interactions_by_user(user["id"])

if interactions:
    for interaction in interactions:
        # Format the date in EST am-pm format
        date_str = interaction['created_at'].strftime('%Y-%m-%d %I:%M %p') if interaction['created_at'] else "Unknown date"
        st.markdown(f"**Date:** {date_str}")
        st.markdown("**Transcript:**")
        st.text_area(
            label="Transcript", 
            value=interaction["conversation_script"], 
            height=150, 
            key=f"transcript_{interaction['id']}",
            label_visibility="collapsed"
        )
        st.markdown("**Feedback:**")
        st.text_area(
            label="Feedback", 
            value=interaction["feedback"], 
            height=100, 
            key=f"feedback_{interaction['id']}",
            label_visibility="collapsed"
        )
        st.markdown("---")
else:
    st.info("No interaction history found. Start a new patient encounter!")
