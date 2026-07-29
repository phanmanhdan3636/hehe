
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import datetime
import random
import difflib

# =============================
# CONFIG
# =============================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = "/storage/emulated/0"
if not os.path.isdir(DATA_DIR):
    DATA_DIR = APP_DIR

FILE_USER = os.path.join(DATA_DIR, "user_data.txt")
FILE_PUBLIC = os.path.join(DATA_DIR, "public_data.txt")
FILE_PRIVATE = os.path.join(DATA_DIR, "private_data.txt")
FILE_TRUYEN = os.path.join(DATA_DIR, "truyen_cuoi.txt")
FILE_BAN = os.path.join(DATA_DIR, "banned_users.txt")
FILE_LOG = os.path.join(DATA_DIR, "activity_log.txt")
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.txt")
REPORT_FILE = os.path.join(DATA_DIR, "report.txt")
FILE_GROUP = os.path.join(DATA_DIR, "groups.txt")
FILE_GROUP_MEMBERS = os.path.join(DATA_DIR, "group_members.txt")
MUSIC_FOLDER = "static/music"
ADMIN = "phan mạnh đan"

app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, "templates"),
    static_folder=os.path.join(APP_DIR, "static"),
)
app.secret_key = "change-this-secret-key"

# =============================
# HELPERS
# =============================
def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def ensure_file(path):
    ensure_parent(path)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8"):
            pass

for _p in [
    FILE_USER, FILE_PUBLIC, FILE_PRIVATE, FILE_TRUYEN, FILE_BAN,
    FILE_LOG, MESSAGES_FILE, REPORT_FILE, FILE_GROUP, FILE_GROUP_MEMBERS
]:
    ensure_file(_p)

def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")

def now_human():
    return datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]

def write_lines(path, lines):
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

def append_line(path, line):
    ensure_parent(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def current_user():
    return session.get("user", "Khách")

def is_logged_in():
    return session.get("logged_in", False)

def is_admin():
    return current_user() == ADMIN

# =============================
# USERS / BAN / LOG
# =============================
def load_users():
    users = {}
    for line in read_lines(FILE_USER):
        if "|" in line:
            u, p = line.split("|", 1)
            users[u] = p
    return users

def save_users(users):
    lines = [f"{u}|{p}" for u, p in users.items()]
    write_lines(FILE_USER, lines)

def check_login(u, p):
    users = load_users()
    return u in users and users[u] == p

def load_banned():
    return [x for x in read_lines(FILE_BAN) if x.strip()]

def save_banned(ban_list):
    write_lines(FILE_BAN, ban_list)

def is_banned(user):
    return user in load_banned()

def ghi_nhat_ky(user):
    append_line(FILE_LOG, f"[{now_human()}] {user} đăng nhập")

def load_logs(loc_24h=True):
    now = datetime.datetime.now()
    out = []
    for line in read_lines(FILE_LOG):
        if not line.strip():
            continue
        try:
            time_str = line.split("]")[0][1:]
            t = datetime.datetime.strptime(time_str, "%d/%m/%Y %H:%M:%S")
        except Exception:
            continue
        if loc_24h and (now - t).total_seconds() > 86400:
            continue
        out.append(line)
    return out

# =============================
# KNOWLEDGE BASE
# =============================
def load_data(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "---" in content:
        return [b.strip() for b in content.split("---") if b.strip()]
    return [line.strip() for line in content.splitlines() if line.strip()]

def hoc_them(question, answer):
    append_line(FILE_PUBLIC, f"{question}: {answer}")
    append_line(FILE_PUBLIC, "---")

def tim_kiem_nang_cao(query, data):
    query = query.lower()
    keywords = query.split()

    results = []

    for line in data:
        line_low = line.lower()

        # bắt buộc có ít nhất 1 keyword
        if not any(kw in line_low for kw in keywords):
            continue

        score = difflib.SequenceMatcher(None, query, line_low).ratio()

        # tăng điểm keyword
        for kw in keywords:
            if kw in line_low:
                score += 0.2

        if score > 0.5:
            results.append((line, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:2]   # 👈 giảm xuống 1-2 kết quả thôi

def tra_loi_random():
    return random.choice([
        "Hmm câu này khó 🤔",
        "Tôi chưa học cái này 😅",
        "Bạn hỏi lại rõ hơn được không?",
        "Câu này hơi ngoài vùng hiểu biết 😵"
    ])

def chatbot_reply(user_input, logged_in):
    txt = user_input.strip()
    low = txt.lower()

    if low in ["help", "/help", "?"]:
        return (
            "Lệnh nhanh: menu, hộp thư, gửi tin, nhóm, tạo nhóm, vào nhóm, rời nhóm, "
            "truyện cười, tính điểm, báo cáo, đăng xuất"
        )

    if low in ["menu", "/menu"]:
        public_data = load_data(FILE_PUBLIC)
        preview = public_data[:3]
        if not preview:
            return "Chưa có dữ liệu công khai."
        return "Mục dữ liệu đang có:\n- " + "\n- ".join(x[:120] for x in preview)

    if low in ["truyện cười", "joke", "/joke"]:
        jokes = load_data(FILE_TRUYEN)
        return random.choice(jokes) if jokes else "Chưa có truyện cười."

    if low in ["hi", "hello", "chào", "xin chào"]:
        return "🤖 Hello 👋 bạn cần gì nào?"

    if "ngu" in low:
        return "🤖 😑 nói chuyện lịch sự chút đi bro"

    public_data = load_data(FILE_PUBLIC)
    private_data = load_data(FILE_PRIVATE)

    res_pri = tim_kiem_nang_cao(txt, private_data)
    res_pub = tim_kiem_nang_cao(txt, public_data)

    if is_logged_in:
        results = res_pri + res_pub
    else:
        results = res_pub
    if results:
        answers = [r.split(":", 1)[-1].strip() for r, _ in results]
        return "\n- " + "\n- ".join(answers)

    return None

# =============================
# DIRECT MESSAGES
# =============================
def send_dm(sender, receiver, msg):
    append_line(MESSAGES_FILE, f"{now_iso()}|{sender}|{receiver}|{msg}")

def parse_message_line(line):
    parts = line.split("|", 3)
    if len(parts) != 4:
        return None
    t, sender, receiver, msg = parts
    return {"time": t, "sender": sender, "receiver": receiver, "message": msg}

def inbox_messages(username):
    msgs = []
    for line in read_lines(MESSAGES_FILE):
        item = parse_message_line(line)
        if not item:
            continue
        if item["receiver"] == username or item["receiver"].lower() == "all":
            msgs.append(item)
    return msgs[-200:]

# =============================
# GROUPS
# =============================
def load_groups():
    data = {}
    for line in read_lines(FILE_GROUP):
        if "|" in line:
            name, pw = line.split("|", 1)
            data[name] = pw
    return data

def save_groups(groups):
    lines = [f"{name}|{pw}" for name, pw in groups.items()]
    write_lines(FILE_GROUP, lines)

def load_group_members():
    data = {}
    for line in read_lines(FILE_GROUP_MEMBERS):
        if "|" in line:
            user, groups = line.split("|", 1)
            data[user] = [g for g in groups.split(",") if g]
    return data

def save_group_members(data):
    lines = [f"{user}|{','.join(groups)}" for user, groups in data.items()]
    write_lines(FILE_GROUP_MEMBERS, lines)

def trong_nhom(user, group):
    return group in load_group_members().get(user, [])

def tao_nhom(group_name, pw=""):
    groups = load_groups()
    if group_name in groups:
        return False, "❌ Nhóm đã tồn tại!"
    groups[group_name] = pw
    save_groups(groups)
    return True, f"✅ Đã tạo nhóm '{group_name}'!"

def vao_nhom(user, group, user_pw=""):
    groups = load_groups()
    if group not in groups:
        return False, "❌ Nhóm không tồn tại!"
    pw = groups[group]
    if user != ADMIN and pw and user_pw != pw:
        return False, "❌ Sai mật khẩu!"
    members = load_group_members()
    user_groups = members.get(user, [])
    if group in user_groups:
        return False, "⚠️ Bạn đã ở trong nhóm!"
    user_groups.append(group)
    members[user] = user_groups
    save_group_members(members)
    append_line(MESSAGES_FILE, f"{now_iso()}|SYSTEM|GROUP:{group}|👤 {user} đã vào nhóm")
    return True, f"✅ Đã vào nhóm '{group}'!"

def roi_nhom(user, group):
    members = load_group_members()
    user_groups = members.get(user, [])
    if group not in user_groups:
        return False, "❌ Bạn chưa tham gia nhóm này!"
    user_groups.remove(group)
    members[user] = user_groups
    save_group_members(members)
    return True, f"👋 Đã rời nhóm '{group}'!"

def gui_tin_nhom(sender, group, msg):
    if not trong_nhom(sender, group) and sender != ADMIN:
        return False, "❌ Bạn chưa vào nhóm này!"
    append_line(MESSAGES_FILE, f"{now_iso()}|{sender}|GROUP:{group}|{msg}")
    return True, "✅ Đã gửi!"

def xem_chat_nhom(group):
    items = []
    for line in read_lines(MESSAGES_FILE):
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        t, sender, receiver, msg = parts
        if receiver == f"GROUP:{group}":
            items.append({"time": t, "sender": sender, "message": msg})
    return items[-300:]

def xem_tat_ca_nhom():
    groups = load_groups()
    members = load_group_members()
    out = []
    for g in groups:
        users = [user for user, gs in members.items() if g in gs]
        out.append({"name": g, "locked": bool(groups[g]), "members": users})
    return out

# =============================
# REPORTS
# =============================
def bao_cao(reporter, target, reason):
    append_line(REPORT_FILE, f"{now_iso()}|{reporter}|{target}|{reason}|0")
    count = dem_bao_cao_7ngay(target)
    if count >= 3:
        ban_list = load_banned()
        if target not in ban_list:
            ban_list.append(target)
            save_banned(ban_list)
            send_dm("ADMIN", target, "🚫 Bạn đã bị BAN!")

def thong_bao_bao_cao():
    for line in read_lines(REPORT_FILE):
        parts = line.split("|", 4)
        if len(parts) == 5 and parts[4] == "0":
            return True
    return False

def xem_bao_cao(loc_24h=True):
    now = datetime.datetime.now()
    found = False
    new_lines = []
    out = []
    for line in read_lines(REPORT_FILE):
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        t, reporter, target, reason, status = parts
        try:
            time_obj = datetime.datetime.fromisoformat(t)
        except Exception:
            continue
        if loc_24h and (now - time_obj).total_seconds() > 86400:
            new_lines.append(line)
            continue
        out.append({
            "time": time_obj.strftime("%d/%m/%Y %H:%M:%S"),
            "reporter": reporter,
            "target": target,
            "reason": reason,
            "status": status,
        })
        found = True
        new_lines.append(f"{t}|{reporter}|{target}|{reason}|0")

    if loc_24h:
        write_lines(REPORT_FILE, new_lines)
    return out, found

def dem_bao_cao_7ngay(target_user):
    now = datetime.datetime.now()
    count = 0
    for line in read_lines(REPORT_FILE):
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        t, reporter, target, reason, status = parts
        try:
            time_obj = datetime.datetime.fromisoformat(t)
        except Exception:
            continue
        if target == target_user and (now - time_obj).days <= 7:
            count += 1
    return count

# =============================
# SCORE CALCULATOR
# =============================
def calc_score(hk1, hk2):
    if hk1 is None or hk2 is None:
        return None
    return (hk1 + hk2 * 2) / 3

# =============================
# AUTH ROUTES
# =============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("user", "").strip()
        p = request.form.get("password", "").strip()
        users = load_users()

        if not u:
            return render_template("login.html", error="Nhập tên đăng nhập.")

        if is_banned(u):
            return render_template("login.html", error="🚫 Tài khoản đã bị khóa!")

        if u in users and users[u] == p:
            session["user"] = u
            session["logged_in"] = True
            ghi_nhat_ky(u)
            return redirect(url_for("home"))
        return render_template("login.html", error="Sai tài khoản hoặc mật khẩu.")

    return render_template("login.html", error=None)

@app.route("/register", methods=["POST"])
def register():
    u = request.form.get("user", "").strip()
    p = request.form.get("password", "").strip()
    users = load_users()
    if not u or not p:
        return render_template("login.html", error="Vui lòng nhập đủ thông tin.")
    if u in users:
        return render_template("login.html", error="Tài khoản đã tồn tại!")
    users[u] = p
    save_users(users)
    session["user"] = u
    session["logged_in"] = True
    ghi_nhat_ky(u)
    return redirect(url_for("home"))

@app.route("/guest", methods=["POST"])
def guest():
    session["user"] = "Khách"
    session["logged_in"] = False
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =============================
# PAGES
# =============================
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "index.html",
        user=current_user(),
        logged_in=is_logged_in(),
        admin=is_admin(),
        admin_name=ADMIN,
    )

@app.route("/admin")
def admin():
    if not is_admin():
        return "🔒 Không có quyền!", 403
    return render_template("admin.html", user=current_user())

# =============================
# API
# =============================
@app.route("/api/bootstrap")
def api_bootstrap():
    user = current_user()
    groups = load_groups()
    members = load_group_members()
    my_groups = members.get(user, [])
    inbox = inbox_messages(user) if user != "Khách" else []
    report_list, _ = xem_bao_cao(True) if is_admin() else ([], False)
    return jsonify({
        "user": user,
        "logged_in": is_logged_in(),
        "admin": is_admin(),
        "admin_name": ADMIN,
        "banned": is_banned(user),
        "groups": [
            {"name": name, "locked": bool(pw), "members": [u for u, gs in members.items() if name in gs]}
            for name, pw in groups.items()
        ],
        "my_groups": my_groups,
        "inbox": inbox,
        "inbox_count": len(inbox),
        "reports_count": len(report_list),
        "reports_unread": thong_bao_bao_cao() if is_admin() else False,
    })

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if "user" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    msg = (request.json or {}).get("msg", "").strip()
    if not msg:
        return jsonify({"error": "empty"}), 400

    user = current_user()
    low = msg.lower()

    if user != "Khách" and is_banned(user):
        return jsonify({"reply": "🚫 Bạn đã bị khóa!"}), 403

    if low in ["đăng xuất", "/logout"]:
        session.clear()
        return jsonify({"reply": "👋 Bạn đã đăng xuất. Tải lại trang để vào lại."})

    if low == "01032008":
        return jsonify({
            "reply": (
                "chào bạn,tôi là Đan,người viết ra chatbot này\n"
                "tôi nghĩ bạn đang khá bất ngờ,vì bạn vừa tìm ra những dòng chữ này đầu tiên\n"
                "đúng,bạn là người đầu tiên,tôi đã cài đặt khi ai xem thứ này đầu tiên,thì sẽ ko có người thứ 2\n"
                "và bạn sẽ có toàn quyền của admin khi sử dụng acc này\n"
                "tên:admin3\n"
                "mk:123456"
            )
        })

    reply = chatbot_reply(msg, is_logged_in())
    if reply:
        return jsonify({"reply": reply})

    return jsonify({"reply": tra_loi_random()})

@app.route("/api/learn", methods=["POST"])
def api_learn():
    if "user" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    question = (request.json or {}).get("question", "").strip()
    answer = (request.json or {}).get("answer", "").strip()
    if not question or not answer:
        return jsonify({"error": "empty"}), 400
    hoc_them(question, answer)
    return jsonify({"ok": True, "message": "✅ Đã học!"})

@app.route("/api/dm/send", methods=["POST"])
def api_dm_send():
    if "user" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    sender = current_user()
    receiver = (request.json or {}).get("receiver", "").strip()
    message = (request.json or {}).get("message", "").strip()
    if not receiver or not message:
        return jsonify({"error": "empty"}), 400
    if sender == receiver:
        return jsonify({"error": "self"}), 400
    send_dm(sender, receiver, message)
    return jsonify({"ok": True, "message": "✅ Đã gửi!"})

@app.route("/api/dm/inbox")
def api_dm_inbox():
    if "user" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    user = current_user()
    return jsonify({
        "messages": inbox_messages(user) if user != "Khách" else []
    })

@app.route("/api/groups", methods=["GET"])
def api_groups_list():
    groups = load_groups()
    members = load_group_members()
    return jsonify({
        "groups": [
            {"name": name, "locked": bool(pw), "members": [u for u, gs in members.items() if name in gs]}
            for name, pw in groups.items()
        ]
    })

@app.route("/api/groups/create", methods=["POST"])
def api_groups_create():
    if "user" not in session or current_user() == "Khách":
        return jsonify({"error": "login_required"}), 401
    group = (request.json or {}).get("group", "").strip()
    pw = (request.json or {}).get("password", "").strip()
    if not group:
        return jsonify({"error": "empty"}), 400
    ok, msg = tao_nhom(group, pw)
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/groups/join", methods=["POST"])
def api_groups_join():
    if "user" not in session or current_user() == "Khách":
        return jsonify({"error": "login_required"}), 401
    group = (request.json or {}).get("group", "").strip()
    pw = (request.json or {}).get("password", "").strip()
    ok, msg = vao_nhom(current_user(), group, pw)
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/groups/leave", methods=["POST"])
def api_groups_leave():
    if "user" not in session or current_user() == "Khách":
        return jsonify({"error": "login_required"}), 401
    group = (request.json or {}).get("group", "").strip()
    ok, msg = roi_nhom(current_user(), group)
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/groups/my")
def api_groups_my():
    user = current_user()
    members = load_group_members()
    return jsonify({"groups": members.get(user, []) if user != "Khách" else []})

@app.route("/api/groups/send", methods=["POST"])
def api_groups_send():
    if "user" not in session or current_user() == "Khách":
        return jsonify({"error": "login_required"}), 401
    group = (request.json or {}).get("group", "").strip()
    message = (request.json or {}).get("message", "").strip()
    if not group or not message:
        return jsonify({"error": "empty"}), 400
    ok, msg = gui_tin_nhom(current_user(), group, message)
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/groups/messages")
def api_groups_messages():
    group = request.args.get("group", "").strip()
    if not group:
        return jsonify({"error": "empty"}), 400
    user = current_user()
    if user != ADMIN and user != "Khách" and not trong_nhom(user, group):
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"messages": xem_chat_nhom(group)})

@app.route("/api/report", methods=["POST"])
def api_report():
    if "user" not in session or current_user() == "Khách":
        return jsonify({"error": "login_required"}), 401
    target = (request.json or {}).get("target", "").strip()
    reason = (request.json or {}).get("reason", "").strip()
    users = load_users()
    if not target or not reason:
        return jsonify({"error": "empty"}), 400
    if target not in users:
        return jsonify({"error": "no_user"}), 404
    if target == current_user():
        return jsonify({"error": "self"}), 400
    bao_cao(current_user(), target, reason)
    return jsonify({"ok": True, "message": "✅ Đã gửi báo cáo!"})

@app.route("/api/reports")
def api_reports():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    reports, _ = xem_bao_cao(True)
    return jsonify({"reports": reports})

@app.route("/api/logs")
def api_logs():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"logs": load_logs(True)})

@app.route("/api/users")
def api_users():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    users = load_users()
    banned = set(load_banned())
    return jsonify({
        "users": [{"username": u, "banned": u in banned} for u in users.keys()]
    })

@app.route("/api/admin/ban", methods=["POST"])
def api_admin_ban():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    user = (request.json or {}).get("user", "").strip()
    ban_list = load_banned()
    if user and user not in ban_list:
        ban_list.append(user)
        save_banned(ban_list)
        return jsonify({"ok": True, "message": "🚫 Đã ban!"})
    return jsonify({"ok": False, "message": "Không hợp lệ"})

@app.route("/api/admin/unban", methods=["POST"])
def api_admin_unban():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    user = (request.json or {}).get("user", "").strip()
    ban_list = load_banned()
    if user in ban_list:
        ban_list.remove(user)
        save_banned(ban_list)
        return jsonify({"ok": True, "message": "✅ Đã mở ban!"})
    return jsonify({"ok": False, "message": "Không bị ban"})

@app.route("/api/admin/delete_user", methods=["POST"])
def api_admin_delete_user():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    user = (request.json or {}).get("user", "").strip()
    users = load_users()
    if user in users:
        del users[user]
        save_users(users)
        return jsonify({"ok": True, "message": "✅ Đã xóa!"})
    return jsonify({"ok": False, "message": "Không tồn tại!"})

@app.route("/api/admin/reset_password", methods=["POST"])
def api_admin_reset_password():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    user = (request.json or {}).get("user", "").strip()
    newp = (request.json or {}).get("password", "").strip()
    users = load_users()
    if user in users and newp:
        users[user] = newp
        save_users(users)
        return jsonify({"ok": True, "message": "✅ Đã reset!"})
    return jsonify({"ok": False, "message": "Không hợp lệ!"})

@app.route("/api/admin/groups")
def api_admin_groups():
    if not is_admin():
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"groups": xem_tat_ca_nhom()})

@app.route("/api/calc", methods=["POST"])
def api_calc():
    data = request.json or {}
    try:
        hk1 = float(data.get("hk1")) if data.get("hk1") not in [None, ""] else None
        hk2 = float(data.get("hk2")) if data.get("hk2") not in [None, ""] else None
    except Exception:
        return jsonify({"error": "bad_number"}), 400
    if hk1 is None or hk2 is None:
        return jsonify({"error": "missing"})
    ca_nam = calc_score(hk1, hk2)
    return jsonify({"ca_nam": round(ca_nam, 2)})
@app.route("/music")
def music():
    playlists = {}

    if os.path.exists(MUSIC_FOLDER):
        for folder in os.listdir(MUSIC_FOLDER):
            folder_path = os.path.join(MUSIC_FOLDER, folder)

            if os.path.isdir(folder_path):
                playlists[folder] = []

                for file in os.listdir(folder_path):
                    if file.endswith(".mp3"):
                        playlists[folder].append({
                            "title": file.replace(".mp3", ""),
                            "file": f"/static/music/{folder}/{file}"
                        })

    return render_template("music.html", playlists=playlists)
# =============================
# MAIN
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
