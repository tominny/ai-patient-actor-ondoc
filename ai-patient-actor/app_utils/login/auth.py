# app_utils/login/auth.py

import streamlit as st
import bcrypt
from app_utils.db.db import get_connection

def sign_up():
    """
    Renders a sign-up form and, on success, inserts the user into the DB.
    Returns True if the sign-up is completed, or None otherwise.
    """
    st.write("### Sign Up")
    username = st.text_input("Username")
    email = st.text_input("Email")
    institution = st.text_input("Institution")
    role = st.text_input("Role")
    city = st.text_input("City")
    country = st.text_input("Country")
    password = st.text_input("Password", type="password")

    if st.button("Create Account"):
        if not (username and email and password):
            st.error("Please fill in at least username, email, and password.")
            return None

        # Hash the password
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        hashed_pw_str = hashed_pw.decode("utf-8")

        # Insert the new user in DB
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO users (username, email, password, institution, role, city, country)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (username, email, hashed_pw_str, institution, role, city, country),
            )
            st.success("Account created successfully. Please log in.")
            return True
        except Exception as e:
            st.error(f"Error creating account: {e}")
        finally:
            cur.close()
            conn.close()
    return None

def login():
    """
    Renders a login form.
    Returns the user record (tuple) if login is successful, or None otherwise.
    """
    st.write("### Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Log In"):
        if not (username and password):
            st.error("Please enter username and password.")
            return None

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user_row = cur.fetchone()
            if user_row:
                stored_hash = user_row[2]  # password column
                if bcrypt.hashpw(password.encode("utf-8"), stored_hash.encode("utf-8")) == stored_hash.encode("utf-8"):
                    st.success(f"Welcome back, {username}!")
                    return user_row
                else:
                    st.error("Invalid password.")
            else:
                st.error("No user found with that username.")
        except Exception as e:
            st.error(f"Database error: {e}")
        finally:
            cur.close()
            conn.close()

    return None

def show_authentication_flow():
    """
    Allows user to choose 'Login' or 'Sign Up' via a radio button and calls
    the appropriate function. On success, returns a user row (tuple).
    """
    choice = st.radio("Authenticate", ["Login", "Sign Up"], horizontal=True)
    if choice == "Login":
        return login()
    else:
        signup_done = sign_up()
        # If sign-up is successful, we ask them to log in:
        if signup_done:
            st.info("Please log in using your new credentials.")
        return None

def check_if_logged_in():
    """
    Check if the user is already saved in session state.
    Returns True if yes, False otherwise.
    """
    return ("user" in st.session_state and st.session_state["user"] is not None)
