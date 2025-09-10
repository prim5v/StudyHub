from flask import Flask, g, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet
eventlet.monkey_patch()  # disable eventlet's greendns
import pymysql
import ssl
import os
from dotenv import load_dotenv
import uuid
import hashlib
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import threading, requests, time, os
import base64, uuid, os, tempfile
import traceback





# ---------------------------
# Cloudinary Config
# ---------------------------


cloudinary.config(
    cloud_name="dl9ismfbn",
    api_key="793953662339596",
    api_secret="nIsVkHOs6yMXAHaEVagmMRKS9UE",
    secure=True
)



# ---------------------------
# Socket.IO Route for Upload
# ---------------------------


# Load environment variables from .env
load_dotenv()
app = Flask(__name__)
CORS(app)  # Enable CORS
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


app.config['UPLOAD_FOLDER'] = '/home/studyhub4293/mysite/static/uploads'








# === DB Connection (Scoped per request) ===
def get_db():
    if 'db' not in g:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

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



# Debug function to detect circular references



# Safe emit helper
def emit_safe(event, data):
    try:
        emit(event, data)
    except Exception as e:
        print(f"⚠️ Emit failed: {repr(e)}")

@socketio.on("upload_resource")
def handle_upload(data):
    try:
        print("🔹 Received upload request:", data.keys())

        sender_id = data.get("sender_id")
        course_name = data.get("course")
        resource_name = data.get("title")
        resource_type = data.get("resource_type")
        file_name = data.get("file_name")
        file_data = data.get("file_data")
        group_id = data.get("group_id")

        if not file_data or not file_name:
            print("❌ Missing file or data in request")
            emit_safe("upload_response", {"success": False, "error": "Missing file or data"})
            return

        print(f"Sender: {sender_id}, Course: {course_name}, Resource: {resource_name}, File: {file_name}, Group: {group_id}")
        print(f"File data length: {len(file_data)} characters")

        # Write temp file safely
        temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file_name}")
        try:
            with open(temp_path, "wb") as f:
                f.write(base64.b64decode(file_data))
            print(f"✅ Temp file written successfully at {temp_path}")
        except Exception as e:
            print(f"❌ Failed to write temp file: {repr(e)}")
            emit_safe("upload_response", {"success": False, "error": f"Temp file write error: {str(e)}"})
            return

        # Upload to Cloudinary
        try:
            upload_result = cloudinary.uploader.upload(temp_path, resource_type='raw')
            resource_url = upload_result.get("secure_url")
            print(f"✅ Uploaded to Cloudinary: {resource_url}")
        except Exception as e:
            print(f"❌ Cloudinary upload failed: {repr(e)}")
            traceback.print_exc()
            emit_safe("upload_response", {"success": False, "error": f"Cloudinary upload error: {str(e)}"})
            return
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    print(f"✅ Temp file removed: {temp_path}")
                except Exception as e:
                    print(f"⚠️ Failed to remove temp file: {repr(e)}")

        # Insert resource into DB
        try:
            db = get_db()
            cursor = db.cursor()
            resource_id = str(uuid.uuid4())
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            is_group = 1 if group_id else 0

            cursor.execute(
                """
                INSERT INTO Resources 
                (sender_id, resource_id, course_name, resource_name, resource_type, resource_url, created_at, is_group, group_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (sender_id, resource_id, course_name, resource_name, resource_type, resource_url, created_at, is_group, group_id)
            )
            db.commit()
            print(f"✅ Resource inserted into DB: {resource_id}")
        except Exception as e:
            print(f"❌ DB insert failed: {repr(e)}")
            traceback.print_exc()
            emit_safe("upload_response", {"success": False, "error": f"DB insert error: {str(e)}"})
            return

        # Emit success response safely
        emit_safe("upload_response", {
            "success": True,
            "resource_id": resource_id,
            "resource_url": resource_url,
            "resource_type": resource_type,
            "is_group": is_group,
            "group_id": group_id
        })
        print("✅ Upload process completed successfully")

    except Exception as e:
        print(f"❌ Unexpected exception occurred: {repr(e)}")
        traceback.print_exc()
        emit_safe("upload_response", {"success": False, "error": f"Unexpected error: {str(e)}"})





@socketio.on("get_group_resources")
def handle_get_group_resources(data):
    try:
        group_id = data.get("group_id")
        if not group_id:
            emit("group_resources_response", {"success": False, "error": "group_id required"})
            return

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT 
                r.id,
                r.sender_id,
                r.resource_id,
                r.course_name,
                r.resource_name,
                r.resource_type,
                r.resource_url,
                r.created_at,
                r.is_group,
                r.group_id,
                r.isFavorite,
                u.name AS uploader_name,
                u.email AS uploader_email,
                u.instagram AS uploader_instagram,
                u.phone AS uploader_phone,
                u.course_name AS uploader_course,
                u.profile_pic AS uploader_profile_pic,
                u.gender AS uploader_gender,
                u.year AS uploader_year,
                u.is_online AS uploader_online,
                u.is_verified AS uploader_verified
            FROM Resources r
            JOIN Users_table u ON r.sender_id = u.user_id
            WHERE r.is_group = 1 AND r.group_id = %s
            ORDER BY r.created_at DESC
        """, (group_id,))

        resources = cursor.fetchall()

        # Serialize datetime fields
        for r in resources:
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()

        emit("group_resources_response", {"success": True, "resources": resources})

    except Exception as e:
        emit("group_resources_response", {"success": False, "error": str(e)})


@socketio.on("get_group_members")
def handle_get_group_members(data):
    try:
        group_id = data.get("group_id")
        if not group_id:
            emit("group_members_response", {"success": False, "error": "group_id required"})
            return

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT 
                gm.id AS membership_id,
                gm.group_id,
                gm.user_id,
                gm.role,
                gm.joined_at,
                u.name AS user_name,
                u.email AS user_email,
                u.instagram,
                u.phone,
                u.course_name,
                u.profile_pic,
                u.gender,
                u.year,
                u.is_online,
                u.is_verified
            FROM group_members gm
            JOIN Users_table u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s
        """, (group_id,))

        members = cursor.fetchall()

        # Serialize datetime fields
        for m in members:
            if isinstance(m.get("joined_at"), datetime):
                m["joined_at"] = m["joined_at"].isoformat()

        emit("group_members_response", {"success": True, "members": members})

    except Exception as e:
        emit("group_members_response", {"success": False, "error": str(e)})




@socketio.on("get_my_groupe_list")
def handle_get_my_groups(data):
    user_id = data.get("user_id")
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)  # use dict cursor for JSON-friendly data

    # Fetch groups created by the user
    cursor.execute("SELECT group_id, group_name, created_at FROM `Groups` WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    groups = cursor.fetchall()

    # Serialize datetime
    for group in groups:
        if group.get("created_at"):
            group["created_at"] = group["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    # Emit as { groups: [...] } so frontend can parse it correctly
    emit("my_groups_response", {"groups": groups})


@socketio.on("like_resource")
def handle_like_resource(data):
    user_id = data.get("user_id")         # The logged-in user (liker)
    resource_id = data.get("resource_id") # The resource being liked

    if not user_id or not resource_id:
        emit("like_response", {"error": "Invalid input"})
        return

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # ✅ Find the owner of the resource
    cursor.execute("SELECT sender_id FROM Resources WHERE resource_id = %s", (resource_id,))
    result = cursor.fetchone()
    if not result:
        emit("like_response", {"error": "Resource not found"})
        return

    liked_id = result["sender_id"]

    # ✅ Check if already liked
    cursor.execute(
        "SELECT id FROM Likes WHERE Likers_id = %s AND resource_id = %s",
        (user_id, resource_id)
    )
    like_row = cursor.fetchone()

    if like_row:
        # Unlike (remove like)
        cursor.execute("DELETE FROM Likes WHERE id = %s", (like_row["id"],))
        db.commit()
        status = "unliked"
    else:
        # Like (insert new record)
        cursor.execute(
            "INSERT INTO Likes (Likers_id, liked_id, resource_id, created_at) VALUES (%s, %s, %s, NOW())",
            (user_id, liked_id, resource_id)
        )
        db.commit()
        status = "liked"

    # ✅ Get updated like count
    cursor.execute("SELECT COUNT(*) AS like_count FROM Likes WHERE resource_id = %s", (resource_id,))
    like_count = cursor.fetchone()["like_count"]

    # ✅ Check if current user has liked
    cursor.execute(
        "SELECT 1 FROM Likes WHERE Likers_id = %s AND resource_id = %s",
        (user_id, resource_id)
    )
    has_liked = cursor.fetchone() is not None

    emit("like_response", {
        "status": status,
        "like_count": like_count,
        "has_liked": has_liked,   # 👈 frontend uses this to show filled/empty heart
        "resource_id": resource_id
    })

@socketio.on("add_comment")
def handle_add_comment(data):
    user_id = data.get("user_id")  # sender
    resource_id = data.get("resource_id")
    content = data.get("content")

    if not user_id or not resource_id or not content:
        emit("comment_response", {"error": "Missing required fields"})
        return

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Insert the comment
    cursor.execute("""
        INSERT INTO Comments (sender_id, resource_id, comment, created_at)
        VALUES (%s, %s, %s, NOW())
    """, (user_id, resource_id, content))
    db.commit()

    comment_id = cursor.lastrowid

    # Fetch comment with user info
    cursor.execute("""
        SELECT c.id, c.comment, c.created_at, u.name AS user_name, c.resource_id
        FROM Comments c
        JOIN Users_table u ON c.sender_id = u.id
        WHERE c.id = %s
    """, (comment_id,))
    comment = cursor.fetchone()

    if comment and comment.get("created_at"):
        comment["created_at"] = comment["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    emit("comment_response", {"comment": comment}, broadcast=True)


@socketio.on("delete_comment")
def handle_delete_comment(data):
    comment_id = data.get("comment_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM Comments WHERE id = %s", (comment_id,))
    db.commit()
    emit("delete_comment_response", {"status": "deleted", "comment_id": comment_id})


@socketio.on("trending_resources")
def handle_trending_resources(data=None):
    user_id = None
    if isinstance(data, dict):
        user_id = data.get("user_id")

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    sql = """
        SELECT
    r.id,
    r.resource_id,
    r.resource_name,
    r.course_name,
    r.resource_type,
    r.created_at,
    r.sender_id,
    u.name AS uploader_name,
    COUNT(DISTINCT l.id) AS like_count,
    COUNT(DISTINCT c.id) AS comment_count,
    MAX(CASE WHEN l.Likers_id = %s THEN 1 ELSE 0 END) AS has_liked
FROM Resources r
LEFT JOIN Likes l ON r.resource_id = l.resource_id
LEFT JOIN Comments c ON r.resource_id = c.resource_id
LEFT JOIN Users_table u ON r.sender_id = u.user_id   -- 👈 now correct
GROUP BY r.id
ORDER BY like_count DESC, r.created_at DESC

    """

    cursor.execute(sql, (user_id,))
    resources = cursor.fetchall()

    # Convert datetime to string
    for r in resources:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    emit("trending_resources_response", resources)

@socketio.on("get_resource")
def handle_get_resource(data):
    resource_id = data.get("resource_id")
    user_id = data.get("user_id")  # UUID of logged-in user

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # ----------------------------
    # Fetch resource + uploader (JOIN on user_id instead of id)
    # ----------------------------
    cursor.execute("""
        SELECT r.id, r.resource_id, r.course_name, r.resource_name,
               r.resource_type, r.resource_url, r.created_at, r.isFavorite,
               u.user_id AS uploader_id, u.name AS uploader_name
        FROM Resources r
        JOIN Users_table u ON r.sender_id = u.user_id   -- ✅ FIXED
        WHERE r.resource_id = %s
    """, (resource_id,))
    resource = cursor.fetchone()

    if not resource:
        emit("get_resource_response", {"error": "Resource not found"})
        return

    # Convert datetime to string
    if isinstance(resource["created_at"], (datetime, date)):
        resource["created_at"] = resource["created_at"].isoformat()

    # ----------------------------
    # Count likes
    # ----------------------------
    cursor.execute("""
        SELECT COUNT(*) AS like_count
        FROM Likes
        WHERE resource_id = %s
    """, (resource_id,))
    like_data = cursor.fetchone()
    like_count = like_data["like_count"] if like_data else 0

    # ----------------------------
    # Check if current user liked this resource (UUID check)
    # ----------------------------
    cursor.execute("""
        SELECT 1
        FROM Likes
        WHERE resource_id = %s AND likers_id = %s   -- ✅ FIXED to UUID
        LIMIT 1
    """, (resource_id, user_id))
    has_liked = cursor.fetchone() is not None

    # ----------------------------
    # Fetch comments (JOIN on user_id instead of id)
    # ----------------------------
    cursor.execute("""
        SELECT c.id, c.comment, c.created_at,
               u.user_id AS user_id, u.name AS user_name, u.profile_pic
        FROM Comments c
        JOIN Users_table u ON c.sender_id = u.user_id   -- ✅ FIXED
        WHERE c.resource_id = %s
        ORDER BY c.created_at DESC
    """, (resource_id,))
    comments = cursor.fetchall()

    # Convert comment datetimes to strings
    for comment in comments:
        if isinstance(comment["created_at"], (datetime, date)):
            comment["created_at"] = comment["created_at"].isoformat()

    # ----------------------------
    # Final response
    # ----------------------------
    emit("get_resource_response", {
        "resource": {
            "id": resource["id"],
            "resource_id": resource["resource_id"],
            "title": resource["resource_name"],
            "subject": resource["course_name"],
            "type": resource["resource_type"],
            "url": resource["resource_url"],   # ✅ cloudinary URL included
            "created_at": resource["created_at"],
            "isFavorite": resource["isFavorite"],
            "likes": like_count,
            "hasLiked": has_liked,
            "uploadedBy": {
                "id": resource["uploader_id"],
                "name": resource["uploader_name"]
            },
            "comments": comments
        }
    })





@socketio.on("suggested_resources")
def handle_suggested_resources(data):
    user_id = data.get("user_id")
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT course_name FROM Users_table WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user or not user.get("course_name"):
        emit("suggested_resources_response", {"resources": []})
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

    # JSON-safe datetime
    for r in resources:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    emit("suggested_resources_response", {"resources": resources})


@socketio.on("all_students")
def handle_all_students():
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)  # Ensure dict cursor
    cursor.execute("SELECT * FROM Users_table")
    students = cursor.fetchall()

    # Convert any datetime fields to string
    for s in students:
        for key, value in s.items():
            if isinstance(value, (datetime.datetime, datetime.date)):
                s[key] = value.strftime("%Y-%m-%d %H:%M:%S")

    emit("all_students_response", {"students": students})


@socketio.on("suggest_students")
def handle_suggest_students(data):
    user_id = data.get("user_id")  # <-- logged-in user's user_id
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Get current user's course and year
    cursor.execute(
        "SELECT course_name, year FROM Users_table WHERE user_id = %s", 
        (user_id,)
    )
    user = cursor.fetchone()
    if not user:
        emit("suggest_students_response", {"students": []})
        return

    # Fetch suggested students (exclude self) and include follow info
    cursor.execute("""
        SELECT 
            u.*,
            EXISTS(
                SELECT 1 FROM Followers f 
                WHERE f.followers_id = %s AND f.followings_id = u.user_id
            ) AS is_following,
            (SELECT COUNT(*) FROM Followers f2 WHERE f2.followings_id = u.user_id) AS followers_count
        FROM Users_table u
        WHERE u.user_id != %s AND u.course_name = %s AND u.year = %s
        ORDER BY u.created_at DESC
        LIMIT 10
    """, (user_id, user_id, user["course_name"], user["year"]))
    
    suggested_students = cursor.fetchall()

    # Convert datetime fields to strings
    for s in suggested_students:
        for key, value in s.items():
            if isinstance(value, datetime):
                s[key] = value.strftime("%Y-%m-%d %H:%M:%S")
    
    # Emit results
    emit("suggest_students_response", {"students": suggested_students})


@socketio.on("suggest_groups")
def handle_suggest_groups(data):
    user_uuid = data.get("user_id")  # frontend sends UUID (e.g., "74e0ff6f")
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # ✅ Step 1: Get numeric DB id from UUID
    cursor.execute("SELECT id, course_name FROM Users_table WHERE user_id = %s", (user_uuid,))
    user = cursor.fetchone()
    if not user:
        emit("suggest_groups_response", {"groups": []})
        return

    numeric_id = user["id"]
    course_name = user["course_name"]

    # ✅ Step 2: Find followings using numeric id
    cursor.execute("SELECT followings_id FROM Followers WHERE followers_id = %s", (numeric_id,))
    followings = [row["followings_id"] for row in cursor.fetchall()]

    # ✅ Step 3: Get relevant users (numeric IDs)
    if followings:
        format_strings = ','.join(['%s'] * len(followings))
        sql_users = f"SELECT id FROM Users_table WHERE id IN ({format_strings}) AND course_name = %s"
        cursor.execute(sql_users, (*followings, course_name))
    else:
        cursor.execute("SELECT id FROM Users_table WHERE course_name = %s", (course_name,))
    relevant_users = [row["id"] for row in cursor.fetchall()]

    if not relevant_users:
        emit("suggest_groups_response", {"groups": []})
        return

    # ✅ Step 4: Fetch groups created by relevant users
    format_users = ','.join(['%s'] * len(relevant_users))
    sql_groups = f"SELECT * FROM `Groups` WHERE user_id IN ({format_users}) ORDER BY created_at DESC"
    cursor.execute(sql_groups, tuple(relevant_users))
    groups = cursor.fetchall()

    # ✅ Step 5: Add member counts and serialize datetime
    for group in groups:
        cursor.execute("SELECT COUNT(*) AS total_members FROM  group_members WHERE group_id = %s", (group['group_id'],))
        group['total_members'] = cursor.fetchone()['total_members']

        cursor.execute("""
            SELECT COUNT(*) AS online_members
            FROM group_members gm
            JOIN Users_table u ON gm.user_id = u.id
            WHERE gm.group_id = %s AND u.is_online = 1
        """, (group['group_id'],))
        group['online_members'] = cursor.fetchone()['online_members']

        if group.get("created_at"):
            group["created_at"] = group["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    emit("suggest_groups_response", {"groups": groups})


@socketio.on("update_favorite")
def handle_update_favorite(data):
    resource_id = data.get('resource_id')
    is_favorite = data.get('isFavorite')

    # Validate input
    if resource_id is None or is_favorite not in [0, 1]:
        emit("update_favorite_response", {"error": "Invalid input"})
        return

    try:
        db = get_db()
        cursor = db.cursor()

        # Ensure proper types
        is_favorite_int = int(is_favorite)
        resource_id_str = str(resource_id)

        # Execute the update safely
        cursor.execute(
            "UPDATE Resources SET isFavorite = %s WHERE resource_id = %s",
            (is_favorite_int, resource_id_str)
        )
        db.commit()

        emit(
            "update_favorite_response",
            {"message": f"Resource {resource_id_str} updated to isFavorite={is_favorite_int}"}
        )
    except Exception as e:
        emit("update_favorite_response", {"error": str(e)})




# ===================================================
# HELPER: FETCH RECENT ACTIVITIES
# ===================================================
def fetch_recent_activities(user_id):
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    query = """
        (
            SELECT 'resource' AS type, r.resource_id AS ref_id, r.resource_name AS title,
                   u.name AS actor_name, u.profile_pic AS actor_pic, r.created_at
            FROM Resources r
            JOIN Users_table u ON r.sender_id = u.user_id
        )
        UNION ALL
        (
            SELECT 'comment' AS type, c.id AS ref_id, 
                   CONCAT(u.name, ' commented on ', r.resource_name, ': ', c.comment) AS title,
                   u.name AS actor_name, u.profile_pic AS actor_pic, c.created_at
            FROM Comments c
            JOIN Users_table u ON c.sender_id = u.user_id
            JOIN Resources r ON c.resource_id = r.resource_id
        )
        UNION ALL
        (
            SELECT 'like' AS type, l.id AS ref_id, 
                   CONCAT(u.name, ' liked ', r.resource_name) AS title,
                   u.name AS actor_name, u.profile_pic AS actor_pic, l.created_at
            FROM Likes l
            JOIN Users_table u ON l.Likers_id = u.user_id
            JOIN Resources r ON l.resource_id = r.resource_id
        )
        UNION ALL
        (
            SELECT 'group' AS type, g.group_id AS ref_id, CONCAT(u.name, ' created group: ', g.group_name) AS title,
                   u.name AS actor_name, u.profile_pic AS actor_pic, g.created_at
            FROM `Groups` g
            JOIN Users_table u ON g.user_id = u.user_id
        )
        ORDER BY created_at DESC
        LIMIT 20
    """

    cursor.execute(query)
    activities = cursor.fetchall()

    # Convert all datetime fields to string
    for a in activities:
        if isinstance(a['created_at'], datetime):
            a['created_at'] = a['created_at'].strftime("%Y-%m-%d %H:%M:%S")

    return activities


# ===================================================
# SOCKET.IO EVENTS
# ===================================================
@socketio.on("join")
def on_join(data):
    user_id = data.get("user_id")
    join_room(user_id)
    emit("joined", {"msg": f"User {user_id} joined activity feed"}, room=user_id)


@socketio.on("get_recent_activities")
def handle_recent_activities(data):
    user_id = data.get("user_id")
    activities = fetch_recent_activities(user_id)
    emit("recent_activities", {"activities": activities}, room=user_id)


# === Your existing socket events (likes, comments, groups, etc) remain unchanged ===
# (I left them as they were in your code above)



# --- Helper Functions ---
def generate_user_id():
    return str(uuid.uuid4())[:8]  # 8-char unique ID

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def assign_profile_pic(name, gender):
    if gender and gender.lower() == "male":
        return f"https://avatar.iran.liara.run/public/boy?username={name}"
    elif gender and gender.lower() == "female":
        return f"https://avatar.iran.liara.run/public/girl?username={name}"
    else:
        # default avatar if gender not specified
        return f"https://avatar.iran.liara.run/public/boy?username={name}"

# --- Socket Events ---

# ✅ Sign Up
@socketio.on("signup")
def handle_signup(data):
    try:
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")  # frontend must send
        instagram = data.get("instagram")
        phone = data.get("phone")
        course_name = data.get("course_name")
        about = data.get("about")
        description = data.get("description")
        gender = data.get("gender")
        year = data.get("year")

        if not name or not email or not password:
            return jsonify({"status": "error", "message": "Missing required fields"})

        user_id = generate_user_id()
        profile_pic = assign_profile_pic(name, gender)
        hashed_pw = hash_password(password)

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO Users_table 
            (name, user_id, email, instagram, phone, course_name, about, description, profile_pic, gender, year, created_at, last_seen, is_online, password)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW(),0,%s)
        """, (name, user_id, email, instagram, phone, course_name, about, description, profile_pic, gender, year, hashed_pw))

        db.commit()

        emit("signup_response", {"status": "success", "user_id": user_id})
    except Exception as e:
        emit("signup_response", {"status": "error", "message": str(e)})

# ✅ Login
@socketio.on("login")
def handle_login(data):
    try:
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            emit("login_response", {"status": "error", "message": "Missing fields"})
            return

        hashed_pw = hash_password(password)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM Users_table WHERE email=%s AND password=%s", (email, hashed_pw))
        user = cursor.fetchone()

        if user:
            # update online status
            cursor.execute("UPDATE Users_table SET is_online=1, last_seen=NOW() WHERE id=%s", (user["id"],))
            db.commit()


            emit("login_response", {
                "status": "success",
                "user": {
                    "id": user["id"],
                    "user_id": user["user_id"],
                    "name": user["name"],
                    "email": user["email"],
                    "instagram": user["instagram"],
                    "phone": user["phone"],
                    "profile_pic": user["profile_pic"],
                    "gender": user["gender"],
                    "course_name": user["course_name"],
                    "year": user["year"],
                    "about": user["about"],
                    "description": user["description"]
                }
            })
        else:
            emit("login_response", {"status": "error", "message": "Invalid credentials"})
    except Exception as e:
        emit("login_response", {"status": "error", "message": str(e)})

# ✅ Logout (optional)
@socketio.on("logout")
def handle_logout(data):
    try:
        user_id = data.get("user_id")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE Users_table SET is_online=0, last_seen=NOW() WHERE user_id=%s", (user_id,))
        db.commit()


        emit("logout_response", {"status": "success"})
    except Exception as e:
        emit("logout_response", {"status": "error", "message": str(e)})




# ---------------- FOLLOW ----------------
@socketio.on('follow')
def handle_follow(data):
    follower = data.get("follower_id")   # current user_id
    following = data.get("following_id") # user_id to follow

    if not follower or not following:
        emit("follow_response", {"status": "error", "message": "Missing follower or following id"})
        return

    db = get_db()
    cursor = db.cursor()
    try:
        # Prevent duplicate follows
        cursor.execute(
            "SELECT * FROM Followers WHERE followers_id=%s AND followings_id=%s",
            (follower, following)
        )
        if cursor.fetchone():
            emit("follow_response", {"status": "error", "message": "Already following"})
            return

        # Insert follow record
        cursor.execute(
            "INSERT INTO Followers (followers_id, followings_id) VALUES (%s, %s)",
            (follower, following)
        )
        db.commit()

        # Get updated follower count
        cursor.execute(
            "SELECT COUNT(*) AS followers_count FROM Followers WHERE followings_id=%s",
            (following,)
        )
        count = cursor.fetchone()["followers_count"]

        # Send response to frontend
        emit("follow_response", {
            "status": "success",
            "message": "Followed successfully",
            "followers_count": count,
            "following_id": following
        })

    except Exception as e:
        db.rollback()
        emit("follow_response", {"status": "error", "message": str(e)})




# ---------------- UNFOLLOW ----------------
@socketio.on('unfollow')
def handle_unfollow(data):
    follower = data.get("follower_id")
    following = data.get("following_id")

    if not follower or not following:
        emit("unfollow_response", {"status": "error", "message": "Missing follower or following id"})
        return

    db = get_db()
    cursor = db.cursor()
    try:
        # Delete follow record
        cursor.execute(
            "DELETE FROM Followers WHERE followers_id=%s AND followings_id=%s",
            (follower, following)
        )
        db.commit()

        # Get updated follower count
        cursor.execute(
            "SELECT COUNT(*) AS followers_count FROM Followers WHERE followings_id=%s",
            (following,)
        )
        count = cursor.fetchone()["followers_count"]

        # Send response to frontend
        emit("unfollow_response", {
            "status": "success",
            "message": "Unfollowed successfully",
            "followers_count": count,
            "following_id": following
        })

    except Exception as e:
        db.rollback()
        emit("unfollow_response", {"status": "error", "message": str(e)})

@socketio.on("get_user_profile")
def handle_get_user_profile(data):
    user_id = data.get("user_id")       # profile being viewed
    follower_id = data.get("logged_in_user_id")  # currently logged-in user

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Fetch user info
    cursor.execute("SELECT * FROM Users_table WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        emit("get_user_profile_response", {"error": "User not found"})
        return

    # Check if logged-in user is following this profile
    cursor.execute(
        "SELECT 1 FROM Followers WHERE followers_id=%s AND followings_id=%s",
        (follower_id, user_id)
    )
    user["is_following"] = cursor.fetchone() is not None

    # Get followers count
    cursor.execute(
        "SELECT COUNT(*) AS followers_count FROM Followers WHERE followings_id=%s",
        (user_id,)
    )
    user["followers_count"] = cursor.fetchone()["followers_count"]

    # Get following count
    cursor.execute(
        "SELECT COUNT(*) AS following_count FROM Followers WHERE followers_id=%s",
        (user_id,)
    )
    user["following_count"] = cursor.fetchone()["following_count"]

    # Convert datetime fields to string
    for k, v in user.items():
        if isinstance(v, datetime):
            user[k] = v.isoformat()

    emit("get_user_profile_response", {"user": user})


# ---------------- Followers List ----------------
@socketio.on("get_user_followers")
def handle_get_user_followers(data):
    user_id = data.get("user_id")  # profile being viewed
    logged_in_user_id = data.get("logged_in_user_id")  # who is viewing the profile

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            u.user_id, u.name, u.profile_pic,
            EXISTS(
                SELECT 1 
                FROM Followers f2 
                WHERE f2.followers_id=%s AND f2.followings_id=u.user_id
            ) AS is_following
        FROM Followers f
        JOIN Users_table u ON u.user_id = f.followers_id
        WHERE f.followings_id = %s
        ORDER BY f.created_at DESC
    """, (logged_in_user_id, user_id))
    
    followers = cursor.fetchall()

    # Convert datetime fields if any
    for f in followers:
        for k, v in f.items():
            if isinstance(v, datetime):
                f[k] = v.isoformat()
        f["is_following"] = bool(f["is_following"])  # convert 0/1 to True/False

    emit("get_user_followers_response", {"followers": followers})


# ---------------- Following List ----------------
@socketio.on("get_user_following")
def handle_get_user_following(data):
    user_id = data.get("user_id")  # profile being viewed
    logged_in_user_id = data.get("logged_in_user_id")  # who is viewing the profile

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            u.user_id, u.name, u.profile_pic,
            EXISTS(
                SELECT 1 
                FROM Followers f2 
                WHERE f2.followers_id=%s AND f2.followings_id=u.user_id
            ) AS is_following
        FROM Followers f
        JOIN Users_table u ON u.user_id = f.followings_id
        WHERE f.followers_id = %s
        ORDER BY f.created_at DESC
    """, (logged_in_user_id, user_id))
    
    following = cursor.fetchall()

    # Convert datetime fields if any
    for f in following:
        for k, v in f.items():
            if isinstance(v, datetime):
                f[k] = v.isoformat()
        f["is_following"] = bool(f["is_following"])  # convert 0/1 to True/False

    emit("get_user_following_response", {"following": following})


# Send a message
# @socketio.on('send_message')
# def handle_send_message(data):
#     sender_id = data.get('sender_id')
#     receiver_id = data.get('receiver_id')
#     group_id = data.get('group_id')
#     message = data.get('message')

#     db = get_db()
#     cursor = db.cursor()

#     created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#     # Save message to DB
#     cursor.execute("""
#         INSERT INTO Messages (sender_id, receivers_id, group_id, message, created_at)
#         VALUES (%s, %s, %s, %s, %s)
#     """, (sender_id, receiver_id or '', group_id, message, created_at))
#     db.commit()
#     message_id = cursor.lastrowid

#     msg_data = {
#         'id': message_id,
#         'sender_id': sender_id,
#         'receiver_id': receiver_id,
#         'group_id': group_id,
#         'message': message,
#         'created_at': created_at,
#         'time': created_at,
#     }

#     # Emit message to the room
#     room_name = receiver_id if group_id == 'UNI' else group_id
#     emit('new_message', msg_data, room=room_name)

# Fetch private conversations

# --- Helper: serialize datetime ---
def serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

# --- Private Conversations ---
@socketio.on('get_private_conversations')
def handle_get_private_conversations(data):
    user_id = data.get('user_id')
    print(f"Fetching private conversations for user: {user_id}")
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT conversation_id, user1_id, user2_id, created_at
        FROM Conversations
        WHERE user1_id=%s OR user2_id=%s
        ORDER BY created_at DESC
    """, (user_id, user_id))
    convos = cursor.fetchall()

    for convo in convos:
        partner_id = convo['user1_id'] if convo['user2_id'] == user_id else convo['user2_id']
        cursor.execute("SELECT name, profile_pic FROM Users_table WHERE user_id=%s", (partner_id,))
        user = cursor.fetchone()
        convo['name'] = user['name'] if user else 'Unknown'
        convo['profile_pic'] = user.get('profile_pic') if user else None
        convo['type'] = 'private'
        convo['lastMessage'] = ''
        convo['created_at'] = serialize_datetime(convo.get('created_at'))

    print(f"Private conversations: {convos}")
    emit('private_conversations', convos)

# --- Group Conversations ---
@socketio.on('get_group_conversations')
def handle_get_group_conversations(data):
    try:
        user_id = data.get('user_id')
        print(f"Fetching group conversations for user: {user_id}")

        db = get_db()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # Step 1: Get group_ids where the user is a member
        cursor.execute(
            "SELECT group_id FROM group_members WHERE user_id=%s",
            (user_id,)
        )
        member_group_ids = [row['group_id'] for row in cursor.fetchall()]
        print(f"User is member of groups: {member_group_ids}")

        # Step 2: Fetch groups where user is owner or a member
        # Using tuple for IN clause, if empty provide dummy value
        group_ids_tuple = tuple(member_group_ids) if member_group_ids else ('',)
        cursor.execute(f"""
            SELECT g.group_id AS id,
                   g.group_name AS name,
                   g.course,
                   g.user_id AS owner_id,
                   g.isFavorite,
                   (SELECT m.message FROM Messages m 
                    WHERE m.group_id=g.group_id 
                    ORDER BY m.created_at DESC LIMIT 1) AS lastMessage,
                   (SELECT COUNT(*) FROM Messages m 
                    WHERE m.group_id=g.group_id 
                      AND m.sender_id != %s AND m.is_read=0) AS unread_count,
                   (SELECT MAX(created_at) FROM Messages m WHERE m.group_id=g.group_id) AS lastMessageTime
            FROM `Groups` g
            WHERE g.user_id=%s OR g.group_id IN %s
            ORDER BY lastMessageTime DESC
        """, (user_id, user_id, group_ids_tuple))

        groups = cursor.fetchall()

        # Format groups
        for group in groups:
            group['type'] = 'group'
            group['lastMessageTime'] = serialize_datetime(group.get('lastMessageTime'))

        print(f"Group conversations: {groups}")
        emit('group_conversations', groups)

    except Exception as e:
        print("Error fetching group conversations:", e)
        emit('group_conversations', {"success": False, "error": str(e)})



@socketio.on("create_group")
def handle_create_group(data):
    try:
        group_name = data.get("group_name")
        course = data.get("course")
        user_id = data.get("user_id")  # VARCHAR from Users_table

        if not group_name or not user_id:
            emit("create_group_response", {
                "success": False,
                "error": "Missing group name or user_id"
            })
            return

        group_uuid = str(uuid.uuid4())  # external UUID for reference
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        cursor = db.cursor()

        # Insert into Groups (use UUID)
        cursor.execute("""
            INSERT INTO `Groups` (group_name, course, group_id, user_id, created_at, isFavorite)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (group_name, course, group_uuid, user_id, created_at, 0))
        db.commit()

        # Insert creator into group_members (use UUID, not INT PK)
        cursor.execute("""
            INSERT INTO group_members (group_id, user_id, role)
            VALUES (%s, %s, %s)
        """, (group_uuid, user_id, "admin"))
        db.commit()

        emit("create_group_response", {
            "success": True,
            "group_id": group_uuid,
            "group_name": group_name,
            "course": course,
            "created_at": created_at
        })

    except Exception as e:
        emit("create_group_response", {
            "success": False,
            "error": str(e)
        })






# --- Private Messages ---
@socketio.on('get_private_messages')
def handle_get_private_messages(data):
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    limit = data.get('limit', 20)       # default: 20 messages
    offset = data.get('offset', 0)      # default: start at 0 (latest)

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Fetch latest messages first, then reverse them in Python
    cursor.execute("""
        SELECT *
        FROM Messages
        WHERE group_id='UNI'
        AND ((sender_id=%s AND receivers_id=%s) OR (sender_id=%s AND receivers_id=%s))
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (sender_id, receiver_id, receiver_id, sender_id, limit, offset))

    messages = cursor.fetchall()

    # Reorder to ASC for display (oldest → newest)
    messages.reverse()

    for msg in messages:
        msg['created_at'] = serialize_datetime(msg.get('created_at'))

    emit('private_messages', messages)

# --- Group Messages ---
@socketio.on('get_group_messages')
def handle_get_group_messages(data):
    group_id = data.get('group_id')
    print(f"Fetching messages for group: {group_id}")
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT *
        FROM Messages
        WHERE group_id=%s
        ORDER BY created_at ASC
    """, (group_id,))

    messages = cursor.fetchall()
    for msg in messages:
        msg['created_at'] = serialize_datetime(msg.get('created_at'))

    emit('group_messages', messages)

# --- Join Room ---
@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    join_room(room)
    print(f"User joined room: {room}")

# --- Send Message ---
@socketio.on('send_message')
def handle_send_message(data):
    sender_id = data['sender_id']
    receiver_id = data.get('receiver_id')
    group_id = data.get('group_id', 'UNI')
    message = data['message']

    db = get_db()
    cursor = db.cursor()  # Ensure fetch returns dicts

    # ✅ Insert new message
    cursor.execute("""
        INSERT INTO Messages (sender_id, receivers_id, group_id, message, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, (sender_id, receiver_id, group_id, message))
    db.commit()

    # ✅ Determine which conversation to fetch
    if group_id and group_id != "UNI":  
        # Fetch all group messages
        cursor.execute("""
            SELECT m.id, m.sender_id, u.name AS sender_name, m.message, m.created_at
            FROM Messages m
            JOIN Users_table u ON m.sender_id = u.user_id
            WHERE m.group_id = %s
            ORDER BY m.created_at ASC
        """, (group_id,))
    else:
        # Fetch all private messages between two users
        cursor.execute("""
            SELECT m.id, m.sender_id, u.name AS sender_name, m.message, m.created_at
            FROM Messages m
            JOIN Users_table u ON m.sender_id = u.user_id
            WHERE (m.sender_id = %s AND m.receivers_id = %s)
               OR (m.sender_id = %s AND m.receivers_id = %s)
            ORDER BY m.created_at ASC
        """, (sender_id, receiver_id, receiver_id, sender_id))

    messages = cursor.fetchall()

    # ✅ Serialize timestamps
    for msg in messages:
        msg['created_at'] = serialize_datetime(msg['created_at'])

    # ✅ Choose the correct room
    room_to_emit = group_id if group_id != 'UNI' else receiver_id

    # ✅ Emit the entire chat history
    socketio.emit('chat_history', messages, room=room_to_emit)
    print(f"Chat history sent to room {room_to_emit} with {len(messages)} messages")

    # ✅ Emit only the new message to the sender as confirmation
    message_data = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "group_id": group_id,
        "message": message,
        "created_at": serialize_datetime(datetime.now())
    }
    socketio.emit("new_message", message_data, room=sender_id)
    socketio.emit("new message", message_data, room=receiver_id)





@socketio.on('start_private_conversation')
def handle_start_private_conversation(data):
    user1_id = data.get('user1_id')
    user2_id = data.get('user2_id')
    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Check if a private conversation already exists
    cursor.execute("""
        SELECT conversation_id 
        FROM Conversations
        WHERE (user1_id=%s AND user2_id=%s) OR (user1_id=%s AND user2_id=%s)
        LIMIT 1
    """, (user1_id, user2_id, user2_id, user1_id))
    convo = cursor.fetchone()

    if convo:
        # Conversation exists
        conversation_id = convo['conversation_id']
    else:
        # Create new conversation
        cursor.execute("""
            INSERT INTO Conversations (user1_id, user2_id, created_at)
            VALUES (%s, %s, NOW())
        """, (user1_id, user2_id))
        db.commit()
        conversation_id = cursor.lastrowid

    emit('start_private_conversation_response', {
        'success': True,
        'conversation_id': conversation_id
    })



# When user connects
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f"User connected: {sid}")
    # You may not know the user_id yet — wait for login/handshake event


# When user authenticates (after login, frontend should send user_id)
# Keep track of sid <-> user_id mapping
connected_users = {}

@socketio.on('user_online')
def handle_user_online(data):
    user_id = data.get('user_id')
    sid = request.sid
    if not user_id:
        return

    # Store mapping sid ↔ user_id
    connected_users[sid] = user_id
    print(f"User {user_id} is online with sid {sid}")

    db = get_db()
    cursor = db.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE Users_table
        SET is_online = 1, last_seen = %s
        WHERE user_id = %s
    """, (now, user_id))
    db.commit()

    # 🔔 Broadcast real-time status update to all clients
    socketio.emit('user_status', {
        "user_id": user_id,
        "is_online": 1,
        "last_seen": now
    }, broadcast=True)

    # 🔔 Send notification for the carousel
    socketio.emit("notification", {
        "type": "status",
        "message": f"{user_id} is now online"
    }, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    user_id = connected_users.pop(sid, None)  # Safe pop
    print(f"SID {sid} disconnected -> User: {user_id}")

    if not user_id:
        return

    db = get_db()
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE Users_table
        SET is_online = 0, last_seen = %s
        WHERE user_id = %s
    """, (now, user_id))
    db.commit()

    socketio.emit('user_status', {
        "user_id": user_id,
        "is_online": 0,
        "last_seen": now
    }, broadcast=True)



# ✅ Save resource to My Notes
@socketio.on("save_note")
def handle_save_note(data):
    user_id = data.get("user_id")
    resource_id = data.get("resource_id")

    if not user_id or not resource_id:
        emit("save_note_response", {"success": False, "message": "Missing data"})
        return

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Check if already saved
    cursor.execute("""
        SELECT id FROM Users_notes
        WHERE users_id = %s AND Resource_id = %s
    """, (user_id, resource_id))
    existing = cursor.fetchone()

    if existing:
        emit("save_note_response", {"success": False, "message": "Already saved"})
        return

    # Insert new note
    cursor.execute("""
        INSERT INTO Users_notes (users_id, Resource_id)
        VALUES (%s, %s)
    """, (user_id, resource_id))
    db.commit()

    emit("save_note_response", {
        "success": True,
        "message": "Saved to My Notes collection",
        "resource_id": resource_id
    })


# ✅ Fetch My Notes
@socketio.on("get_my_notes") 
def handle_get_my_notes(data):
    user_id = data.get("user_id")
    if not user_id:
        emit("get_my_notes_response", {"notes": []})
        return

    db = get_db()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    sql = """
        SELECT 
            r.resource_id,
            r.resource_name,
            r.course_name,
            r.resource_type,
            r.resource_url,
            r.created_at,
            u.name AS uploader_name
        FROM Users_notes un
        JOIN Resources r ON un.Resource_id = r.resource_id
        LEFT JOIN Users_table u ON r.sender_id = u.user_id
        WHERE un.users_id = %s
        ORDER BY un.created_at DESC
    """
    cursor.execute(sql, (user_id,))
    notes = cursor.fetchall()

    # 🔥 Convert datetime fields to string
    for note in notes:
        for key, value in note.items():
            if isinstance(value, datetime):
                note[key] = value.strftime("%Y-%m-%d %H:%M:%S")  # or .isoformat()

    emit("get_my_notes_response", {"notes": notes})




# -----------------------
# 🔎 SEARCH LOGIC
# -----------------------

def search_users(query):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT user_id, name, email, course_name, about, description, profile_pic, gender, year 
        FROM Users_table
        WHERE name LIKE %s OR course_name LIKE %s OR about LIKE %s OR description LIKE %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
    results = cursor.fetchall()
    return results

def search_resources(query):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT resource_id, resource_name, course_name, resource_type, resource_url, created_at 
        FROM Resources
        WHERE resource_name LIKE %s OR course_name LIKE %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (f"%{query}%", f"%{query}%"))
    results = cursor.fetchall()
    return results

def search_groups(query):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT group_id, group_name, course, created_at 
        FROM `Groups`
        WHERE group_name LIKE %s OR course LIKE %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (f"%{query}%", f"%{query}%"))
    results = cursor.fetchall()
    return results

def search_all(query):
    return {
        "users": search_users(query),
        "resources": search_resources(query),
        "groups": search_groups(query)
    }

# -----------------------
# 🔍 REST API ROUTES
# -----------------------

@app.route("/api/search", methods=["GET"])
def search_api():
    query = request.args.get("q", "")
    return jsonify(search_all(query))

@app.route("/api/search/users", methods=["GET"])
def search_users_api():
    query = request.args.get("q", "")
    return jsonify(search_users(query))

@app.route("/api/search/resources", methods=["GET"])
def search_resources_api():
    query = request.args.get("q", "")
    return jsonify(search_resources(query))

@app.route("/api/search/groups", methods=["GET"])
def search_groups_api():
    query = request.args.get("q", "")
    return jsonify(search_groups(query))

# -----------------------
# 🔌 SOCKET.IO EVENTS
# -----------------------

@socketio.on("search")
def handle_search(data):
    query = data.get("q", "")
    emit("search_response", search_all(query))

@socketio.on("search_users")
def handle_search_users(data):
    query = data.get("q", "")
    emit("search_users_response", search_users(query))

@socketio.on("search_resources")
def handle_search_resources(data):
    query = data.get("q", "")
    emit("search_resources_response", search_resources(query))

@socketio.on("search_groups")
def handle_search_groups(data):
    query = data.get("q", "")
    emit("search_groups_response", search_groups(query))


# ✅ Handle group join
@socketio.on("join_group")
def handle_join_group(data):
    print("join_group received:", data)
    group_id = data.get("group_id")
    user_id = data.get("user_id")

    if not group_id or not user_id:
        emit("join_group_response", {"success": False, "error": "Invalid data"})
        return

    try:
        db = get_db()
        cursor = db.cursor()
        print(f"DB cursor obtained. group_id={group_id}, user_id={user_id}")

        # Check if already a member
        cursor.execute(
            "SELECT id FROM group_members WHERE group_id=%s AND user_id=%s",
            (group_id, user_id),
        )
        existing = cursor.fetchone()
        print("Existing member check:", existing)
        if existing:
            emit("join_group_response", {"success": False, "error": "Already a member"})
            cursor.close()
            return

        # Count current members
        cursor.execute("SELECT COUNT(*) FROM group_members WHERE group_id=%s", (group_id,))
        count_result = cursor.fetchone()
        print("Member count result:", count_result)
        count = count_result['COUNT(*)'] if count_result else 0
        role = "admin" if count == 0 else "member"

        # Insert new member
        cursor.execute(
            "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, %s)",
            (group_id, user_id, role),
        )
        db.commit()
        print(f"Member inserted: {user_id} in group {group_id} with role {role}")

        emit("join_group_response", {
            "success": True,
            "group_id": group_id,
            "user_id": user_id,
            "role": role,
        })
        # cursor.close()

    except Exception as e:
        print("Join group error:", e)
        emit("join_group_response", {"success": False, "error": "Server error"})



# ✅ Check membership API
@app.route('/api/is-member', methods=['POST'])
def is_member():
    data = request.json
    print("DEBUG is-member data:", data)   # 👈 log incoming JSON
    group_id = data.get("group_id") if data else None
    user_id = data.get("user_id") if data else None

    if not group_id or not user_id:
        return jsonify({"error": "Invalid data"}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM group_members WHERE group_id=%s AND user_id=%s",
        (group_id, user_id)
    )
    member = cursor.fetchone()
    # cursor.close()

    return jsonify({
        "is_member": member is not None,
        "role": member["role"] if member else None
    })



# ✅ Root route
@app.route("/")
def home():
    return jsonify({"status": "StudyHub backend is running"})

# ✅ Ping route
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})

# ✅ Background self-pinger
def keep_alive():
    url = os.getenv("RENDER_URL", "https://studyhub-8req.onrender.com")
    while True:
        try:
            requests.get(url, timeout=10)
            print(f"[KeepAlive] Pinged {url}")
        except Exception as e:
            print(f"[KeepAlive Error] {e}")
        time.sleep(14 * 60)  # 14 minutes

# ✅ Start pinger in a background thread
def start_keep_alive():
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()


    
@app.route("/health")
def health():
    return "Backend is running!", 200




if __name__ == "__main__":
    start_keep_alive()
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
