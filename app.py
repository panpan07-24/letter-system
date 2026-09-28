import os
import sqlite3
import secrets
from datetime import datetime
from flask import Flask, request, render_template, url_for

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "letters.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS letters (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            opened_at TEXT,
            opened_ip TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, title, created_at, opened_at FROM letters ORDER BY created_at DESC").fetchall()
    conn.close()
    letters = [{"id": r[0], "title": r[1], "created": r[2], "opened": r[3]} for r in rows]
    return render_template("index.html", letters=letters)

@app.route("/send", methods=["POST"])
def send():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if not title or not content:
        return "标题和内容不能为空", 400

    letter_id = secrets.token_urlsafe(8)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO letters (id, title, content, created_at) VALUES (?, ?, ?, ?)",
                 (letter_id, title, content, now))
    conn.commit()
    conn.close()

    link = url_for("view_letter", letter_id=letter_id, _external=True)
    return f"函件已生成！链接：{link}\n请复制此链接发给对方。"

@app.route("/letter/<letter_id>")
def view_letter(letter_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT title, content, created_at, opened_at FROM letters WHERE id = ?",
                       (letter_id,)).fetchone()
    if not row:
        conn.close()
        return "函件不存在", 404

    title, content, created_at, opened_at = row

    if opened_at is None:
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE letters SET opened_at = ?, opened_ip = ? WHERE id = ?",
                     (now, client_ip, letter_id))
        conn.commit()
        opened_at = now

    conn.close()
    return render_template("letter.html", title=title, content=content,
                           created_at=created_at, opened_at=opened_at)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
