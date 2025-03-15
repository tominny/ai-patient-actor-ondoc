import streamlit as st
import db_helper as db  # Note the new module name
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def render_auth():
    st.markdown("## Welcome! Please log in or sign up to continue.")
    auth_mode = st.radio("Select Authentication Mode", ["Login", "Sign Up"])
    
    if auth_mode == "Sign Up":
        st.subheader("Sign Up")
        with st.form("signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            institution = st.text_input("Institution")
            role = st.text_input("Role")
            city = st.text_input("City")
            country = st.text_input("Country")
            submitted = st.form_submit_button("Sign Up")
            if submitted:
                if not email or not password:
                    st.error("Email and Password are required.")
                    st.stop()
                hashed = hash_password(password)
                user_data = {
                    "email": email,
                    "password": hashed,
                    "institution": institution,
                    "role": role,
                    "city": city,
                    "country": country
                }
                success = db.create_user(user_data)
                if success:
                    st.success("Sign Up successful!")
                    # Retrieve the created user record (including its id)
                    user = db.get_user(email, hashed)
                    return user
                else:
                    st.error("Sign Up failed. Please try again.")
                    st.stop()
    else:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if not email or not password:
                    st.error("Email and Password are required.")
                    st.stop()
                hashed = hash_password(password)
                user = db.get_user(email, hashed)
                if user:
                    st.success("Login successful!")
                    return user
                else:
                    st.error("User not found or incorrect password. Please sign up first.")
                    st.stop()
