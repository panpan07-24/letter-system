import os
import sqlite3
import secrets
import uuid
from datetime import datetime
from flask import (Flask, request, render_template, redirect, url_for,
                   session, send_from_directory, abort)

app = Flask(__name__)
app.secret_key = "change-this-secret-2026-sanwei"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "letters.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ADMIN_PASSWORD = "123456"
ROLE_PASSWORD = "123456"

ROLES = {
    "mudiban":    "木地板",
    "cizhuan":    "瓷砖",
    "shica":      "石材",
    "jieju":      "洁具",
    "tuilamen":   "推拉门",
    "wujin":      "五金",
    "kaiguan":    "开关",
    "chugui":     "橱柜",
    "kouban":     "扣板",
    "mumen":      "木门",
    "dingzhi":    "定制柜",
    "fangshui":   "防水",
    "baohu":      "保护",
    "fengchuang": "封窗",
    "ruhumen":    "入户门",
    "jiaju":      "家具",
    "chuangdian": "床垫",
    "dianqi":     "电器",
    "chuanglian": "窗帘",
    "owner":      "业主",
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS letters (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            roles TEXT NOT NULL,
            files TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            letter_id TEXT NOT NULL,
            role TEXT NOT NULL,
            viewed_at TEXT NOT NULL,
            ip TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin_login.html", error="密码错误")

    if not session.get("is_admin"):
        return render_template("admin_login.html", error=None)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, title, roles, created_at FROM letters
        ORDER BY created_at DESC
    """).fetchall()
    letters = []
    for r in rows:
        letter_id, title, roles_str, created = r
        role_keys = roles_str.split(",") if roles_str else []
        view_rows = conn.execute("""
            SELECT role, MAX(viewed_at) FROM views
            WHERE letter_id = ? GROUP BY role
        """, (letter_id,)).fetchall()
        viewed_map = {v[0]: v[1] for v in view_rows}
        roles_info = []
        for rk in role_keys:
            roles_info.append({
                "key": rk,
                "name": ROLES.get(rk, rk),
                "viewed_at": viewed_map.get(rk)
            })
        letters.append({
            "id": letter_id,
            "title": title,
            "created": created,
            "roles": roles_info
        })
    conn.close()
    return render_template("admin.html", letters=letters, roles=ROLES)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin"))

@app.route("/send", methods=["POST"])
def send():
    if not session.get("is_admin"):
        return "无权限", 403

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    selected_roles = request.form.getlist("roles")

    if not title or not content or not selected_roles:
        return "标题、内容、接收角色都不能为空", 400

    letter_id = secrets.token_urlsafe(8)
    created = now_str()

    saved_files = []
    for f in request.files.getlist("files"):
        if f and f.filename:
            ext = os.path.splitext(f.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            f.save(os.path.join(UPLOAD_DIR, safe_name))
            saved_files.append(safe_name)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO letters (id, title, content, roles, files, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (letter_id, title, content, ",".join(selected_roles),
          ",".join(saved_files), created))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/r/<role_key>", methods=["GET", "POST"])
def role_view(role_key):
    if role_key not in ROLES:
        abort(404)
    role_name = ROLES[role_key]

    if not session.get(f"role_{role_key}"):
        if request.method == "POST":
            pwd = request.form.get("password", "")
            if pwd == ROLE_PASSWORD:
                session[f"role_{role_key}"] = True
                return redirect(url_for("role_view", role_key=role_key))
            return render_template("login.html", role_name=role_name,
                                   role_key=role_key, error="密码错误")
        return render_template("login.html", role_name=role_name,
                               role_key=role_key, error=None)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, title, content, files, created_at FROM letters
        WHERE ',' || roles || ',' LIKE ?
        ORDER BY created_at DESC
    """, (f"%,{role_key},%",)).fetchall()

    letters = []
    for r in rows:
        letter_id, title, content, files_str, created = r
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        conn.execute("""
            INSERT INTO views (letter_id, role, viewed_at, ip)
            VALUES (?, ?, ?, ?)
        """, (letter_id, role_key, now_str(), ip))

        files = []
        if files_str:
            for fn in files_str.split(","):
                if fn:
                    files.append({"name": fn, "url": url_for("download_file", filename=fn)})
        letters.append({"id": letter_id, "title": title, "content": content,
                        "created": created, "files": files})
    conn.commit()
    conn.close()
    return render_template("role_view.html", role_name=role_name,
                           role_key=role_key, letters=letters)

@app.route("/download/<filename>")
def download_file(filename):
    if "/" in filename or ".." in filename:
        abort(400)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

@app.route("/")
def index():
    return redirect(url_for("admin"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
