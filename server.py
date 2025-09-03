from flask import Flask, g
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pymysql
import ssl
import os
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()
app = Flask(__name__)
CORS(app)  # Enable CORS
socketio = SocketIO(app, cors_allowed_origins="*")

app.config['UPLOAD_FOLDER'] = '/home/studyhub4293/mysite/static/uploads'

# === DB Connection (Scoped per request) ===
def get_db():
    if 'db' not in g:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = True
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED

        g.db = pymysql.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            cursorclass=pymysql.cursors.DictCursor,
            ssl=ssl_ctx
        )
    return g.db




@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ===================================================
# INIT DATABASE
# ===================================================
def init_db():
    db = get_db()
    cursor = db.cursor()

    # Users_table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users_table (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        user_id VARCHAR(255) UNIQUE,
        email VARCHAR(255) UNIQUE,
        instagram VARCHAR(255),
        phone VARCHAR(20),
        course_name VARCHAR(255),
        about TEXT,
        description TEXT,
        profile_pic VARCHAR(255),
        gender VARCHAR(50),
        year VARCHAR(50),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_online TINYINT(1) DEFAULT 0
    )
    """)

    # Groups
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS `Groups` (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_name VARCHAR(255),
        course VARCHAR(255),
        group_id VARCHAR(255) UNIQUE,
        user_id VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        isFavorite TINYINT(1) DEFAULT 0
    )
    """)

    # Followers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Followers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        followers_id VARCHAR(255),
        followings_id VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Resources
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Resources (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sender_id VARCHAR(255),
        resource_id VARCHAR(255) UNIQUE,
        course_name VARCHAR(255),
        resource_name VARCHAR(255),
        resource_type ENUM('documents','mp4','mp3'),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        isFavorite TINYINT(1) DEFAULT 0
    )
    """)

    # Likes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Likes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        Likers_id VARCHAR(255),
        liked_id VARCHAR(255),
        resource_id VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Comments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Comments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sender_id VARCHAR(255),
        receivers_id VARCHAR(255),
        resource_id VARCHAR(255),
        comment TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Messages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Messages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sender_id VARCHAR(255),
        receivers_id VARCHAR(255),
        group_id VARCHAR(255),
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Users_notes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users_notes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        users_id VARCHAR(255),
        Resource_id VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    db.commit()


# ===================================================
# SOCKET.IO EVENTS
# ===================================================

@socketio.on("get_my_groupe_list")
def handle_get_my_groups(data):
    user_id = data.get("user_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM `Groups` WHERE user_id = %s", (user_id,))
    groups = cursor.fetchall()
    emit("my_groups_response", groups)


@socketio.on("like_resource")
def handle_like_resource(data):
    user_id = data.get("user_id")
    resource_id = data.get("resource_id")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM Likes WHERE Likers_id = %s AND resource_id = %s", (user_id, resource_id))
    if cursor.fetchone():
        cursor.execute("DELETE FROM Likes WHERE Likers_id = %s AND resource_id = %s", (user_id, resource_id))
        db.commit()
        emit("like_response", {"status": "unliked"})
    else:
        cursor.execute(
            "INSERT INTO Likes (Likers_id, resource_id, liked_id, created_at) VALUES (%s, %s, %s, NOW())",
            (user_id, resource_id, user_id)
        )
        db.commit()
        emit("like_response", {"status": "liked"})


@socketio.on("comment_resource")
def handle_comment_resource(data):
    sender_id = data.get("sender_id")
    receivers_id = data.get("receivers_id")
    resource_id = data.get("resource_id")

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO Comments (sender_id, receivers_id, resource_id, created_at) VALUES (%s, %s, %s, NOW())",
        (sender_id, receivers_id, resource_id)
    )
    db.commit()
    emit("comment_response", {"status": "commented"})


@socketio.on("delete_comment")
def handle_delete_comment(data):
    comment_id = data.get("comment_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM Comments WHERE id = %s", (comment_id,))
    db.commit()
    emit("delete_comment_response", {"status": "deleted"})


@socketio.on("trending_resources")
def handle_trending_resources():
    db = get_db()
    cursor = db.cursor()
    sql = """
        SELECT
            r.id,
            r.resource_name,
            r.course_name,
            r.resource_type,
            r.created_at,
            COUNT(l.id) AS like_count
        FROM Resources r
        LEFT JOIN Likes l ON r.id = l.resource_id
        GROUP BY r.id
        ORDER BY like_count DESC, r.created_at DESC
        LIMIT 10;
    """
    cursor.execute(sql)
    resources = cursor.fetchall()
    emit("trending_resources_response", resources)


@socketio.on("suggested_resources")
def handle_suggested_resources(data):
    user_id = data.get("user_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT course_name FROM Users_table WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user or not user.get("course_name"):
        emit("suggested_resources_response", {"error": "User not found or course not set"})
        return
    course_name = user["course_name"]

    sql = """
        SELECT
            r.id,
            r.resource_name,
            r.course_name,
            r.resource_type,
            r.created_at,
            COUNT(l.id) AS like_count
        FROM Resources r
        LEFT JOIN Likes l ON r.id = l.resource_id
        WHERE r.course_name = %s
        GROUP BY r.id
        ORDER BY like_count DESC, r.created_at DESC
        LIMIT 10;
    """
    cursor.execute(sql, (course_name,))
    resources = cursor.fetchall()
    emit("suggested_resources_response", resources)


@socketio.on("all_students")
def handle_all_students():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Users_table")
    students = cursor.fetchall()
    emit("all_students_response", students)


@socketio.on("suggest_students")
def handle_suggest_students(data):
    user_id = data.get("user_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT course_name, year FROM Users_table WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        emit("suggest_students_response", {"error": "User not found"})
        return

    cursor.execute("""
        SELECT * FROM Users_table
        WHERE id != %s AND course_name = %s AND year = %s
        ORDER BY created_at DESC
        LIMIT 10
    """, (user_id, user["course_name"], user["year"]))
    suggested_students = cursor.fetchall()
    emit("suggest_students_response", suggested_students)


@socketio.on("suggest_groups")
def handle_suggest_groups(data):
    user_id = data.get("user_id")
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT course_name FROM Users_table WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        emit("suggest_groups_response", {"error": "User not found"})
        return
    course_name = user["course_name"]

    cursor.execute("SELECT followings_id FROM Followers WHERE followers_id = %s", (user_id,))
    followings = [row["followings_id"] for row in cursor.fetchall()]

    if followings:
        format_strings = ','.join(['%s'] * len(followings))
        sql_users = f"SELECT id FROM Users_table WHERE id IN ({format_strings}) AND course_name = %s"
        cursor.execute(sql_users, (*followings, course_name))
    else:
        cursor.execute("SELECT id FROM Users_table WHERE course_name = %s", (course_name,))
    relevant_users = [row["id"] for row in cursor.fetchall()]

    if not relevant_users:
        emit("suggest_groups_response", [])
        return

    format_users = ','.join(['%s'] * len(relevant_users))
    sql_groups = f"SELECT * FROM Groups WHERE user_id IN ({format_users}) ORDER BY created_at DESC"
    cursor.execute(sql_groups, tuple(relevant_users))
    groups = cursor.fetchall()

    # Add member counts
    for group in groups:
        cursor.execute("SELECT COUNT(*) AS total_members FROM Groups WHERE group_id = %s", (group['group_id'],))
        group['total_members'] = cursor.fetchone()['total_members']

        cursor.execute("""
            SELECT COUNT(*) AS online_members
            FROM Groups gm
            JOIN Users_table u ON gm.user_id = u.id
            WHERE gm.group_id = %s AND u.is_online = 1
        """, (group['group_id'],))
        group['online_members'] = cursor.fetchone()['online_members']

    emit("suggest_groups_response", groups)


@socketio.on("update_favorite")
def handle_update_favorite(data):
    resource_id = data.get('resource_id')
    is_favorite = data.get('isFavorite')

    if resource_id is None or is_favorite not in [0, 1]:
        emit("update_favorite_response", {"error": "Invalid input"})
        return

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE Resources SET isFavorite = %s WHERE resource_id = %s", (is_favorite, resource_id))
    db.commit()
    emit("update_favorite_response", {"message": f"Resource {resource_id} updated to isFavorite={is_favorite}"})


# ===================================================
if __name__ == "__main__":
    with app.app_context():
        init_db()   # Initialize database schema
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
