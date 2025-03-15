import psycopg2
from psycopg2.extras import RealDictCursor

DSN = "postgresql://neondb_owner:npg_Uq37OGZBPLhm@ep-shy-snow-a8stpvle-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"

def get_connection():
    conn = psycopg2.connect(DSN)
    return conn

def create_users_table():
    """
    Creates the 'users' table if it doesn't already exist.
    This ensures that user data is preserved across app restarts.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,
            institution VARCHAR(255),
            role VARCHAR(255),
            city VARCHAR(255),
            country VARCHAR(255)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def create_interactions_table():
    """
    Creates the interactions table (if not already present). This table stores
    each conversation transcript and its associated feedback for a given user.
    The created_at timestamp is set using the fixed EST timezone.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.interactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            conversation_script TEXT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'EST'),
            FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def create_user(user_data):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.users (email, password, institution, role, city, country)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_data["email"],
            user_data["password"],
            user_data.get("institution"),
            user_data.get("role"),
            user_data.get("city"),
            user_data.get("country")
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print("Error creating user:", e)
        return False

def get_user(email, password):
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM public.users WHERE email=%s AND password=%s
        """, (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user
    except Exception as e:
        print("Error retrieving user:", e)
        return None

def save_interaction(user_id, conversation_script, feedback):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.interactions (user_id, conversation_script, feedback)
            VALUES (%s, %s, %s)
        """, (user_id, conversation_script, feedback))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print("Error saving interaction:", e)
        return False

def get_interactions_by_user(user_id):
    """
    Retrieves all interaction records for the specified user_id, ordered
    by creation time (most recent first).
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM public.interactions
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        interactions = cur.fetchall()
        cur.close()
        conn.close()
        return interactions
    except Exception as e:
        print("Error retrieving interactions:", e)
        return []

# Initialize tables on module import.
create_users_table()
create_interactions_table()
