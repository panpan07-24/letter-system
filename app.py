import os
import sqlite3
import secrets
import json
from datetime import datetime
from flask import (Flask, request, render_template, redirect, url_for,
                   session, abort)

app = Flask(__name__)
app.secret_key = "sanwei-purchase-2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "orders.db")

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
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            contract_no TEXT,
            customer TEXT,
            address TEXT,
            manager TEXT,
            supervisor TEXT,
            start_date TEXT,
            accept_date TEXT,
            designer TEXT,
            designer_phone TEXT,
            estimator TEXT,
            estimator_phone TEXT,
            remark TEXT,
            items TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def now_str():
    return datetime.now().strftime("%Y-%m-%d")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and "password" in request.form:
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin_login.html", error="密码错误")

    if not session.get("is_admin"):
        return render_template("admin_login.html", error=None)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, role, customer, address, created_at FROM orders
        ORDER BY created_at DESC
    """).fetchall()
    orders = [{"id": r[0], "role": r[1], "role_name": ROLES.get(r[1], r[1]),
               "customer": r[2], "address": r[3], "created": r[4]} for r in rows]
    conn.close()
    return render_template("admin.html", orders=orders, roles=ROLES)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin"))

@app.route("/create", methods=["POST"])
def create_order():
    if not session.get("is_admin"):
        return "无权限", 403

    role = request.form.get("role", "").strip()
    if role not in ROLES:
        return "请选择材料品类", 400

    rooms = request.form.getlist("room[]")
    products = request.form.getlist("product[]")
    brands = request.form.getlist("brand[]")
    models = request.form.getlist("model[]")
    specs = request.form.getlist("spec[]")
    quantities = request.form.getlist("quantity[]")
    units = request.form.getlist("unit[]")

    items = []
    for i in range(len(products)):
        if products[i].strip():
            items.append({
                "room": rooms[i] if i < len(rooms) else "",
                "product": products[i],
                "brand": brands[i] if i < len(brands) else "",
                "model": models[i] if i < len(models) else "",
                "spec": specs[i] if i < len(specs) else "",
                "quantity": quantities[i] if i < len(quantities) else "",
                "unit": units[i] if i < len(units) else "",
            })

    if not items:
        return "请至少填写一行材料", 400

    order_id = secrets.token_urlsafe(8)
    created = now_str()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO orders (id, role, contract_no, customer, address, manager,
            supervisor, start_date, accept_date, designer, designer_phone,
            estimator, estimator_phone, remark, items, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, role,
        request.form.get("contract_no", ""),
        request.form.get("customer", ""),
        request.form.get("address", ""),
        request.form.get("manager", ""),
        request.form.get("supervisor", ""),
        request.form.get("start_date", ""),
        request.form.get("accept_date", ""),
        request.form.get("designer", ""),
        request.form.get("designer_phone", ""),
        request.form.get("estimator", ""),
        request.form.get("estimator_phone", ""),
        request.form.get("remark", ""),
        json.dumps(items, ensure_ascii=False),
        created
    ))
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
        SELECT id, contract_no, customer, address, manager, supervisor,
               start_date, accept_date, designer, designer_phone,
               estimator, estimator_phone, remark, items, created_at
        FROM orders WHERE role = ? ORDER BY created_at DESC
    """, (role_key,)).fetchall()
    conn.close()

    orders = []
    for r in rows:
        orders.append({
            "id": r[0], "contract_no": r[1], "customer": r[2], "address": r[3],
            "manager": r[4], "supervisor": r[5], "start_date": r[6],
            "accept_date": r[7], "designer": r[8], "designer_phone": r[9],
            "estimator": r[10], "estimator_phone": r[11], "remark": r[12],
            "items": json.loads(r[13]), "created": r[14]
        })

    return render_template("order_view.html", role_name=role_name,
                           role_key=role_key, orders=orders)

@app.route("/print/<order_id>")
def print_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT id, role, contract_no, customer, address, manager, supervisor,
               start_date, accept_date, designer, designer_phone,
               estimator, estimator_phone, remark, items, created_at
        FROM orders WHERE id = ?
    """, (order_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)

    order = {
        "id": row[0], "role": row[1], "role_name": ROLES.get(row[1], row[1]),
        "contract_no": row[2], "customer": row[3], "address": row[4],
        "manager": row[5], "supervisor": row[6], "start_date": row[7],
        "accept_date": row[8], "designer": row[9], "designer_phone": row[10],
        "estimator": row[11], "estimator_phone": row[12], "remark": row[13],
        "items": json.loads(row[14]), "created": row[15]
    }
    return render_template("order_print.html", order=order)

@app.route("/")
def index():
    return redirect(url_for("admin"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
