
from __future__ import annotations
import json, os, secrets, sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'ffhub.db'
AVATAR_DIR = BASE_DIR / 'uploads' / 'avatars'
POST_DIR = BASE_DIR / 'uploads' / 'posts'
ALLOWED = {'png','jpg','jpeg','gif','webp'}
CATEGORIES = ['Esports','Tin tức','Cẩm nang','Cộng đồng','Tuyển team','Giftcode','Review','Highlight','Meme','Rank']
ROLE_ORDER = {'guest':0,'member':1,'mod':2,'admin':3}
DEFAULT_SCHEDULE = [
    {'time':'19:00','title':'VFL: Team A vs Team B','detail':'Bermuda · trực tiếp'},
    {'time':'20:30','title':'FFWS: Vòng bảng','detail':'Theo dõi top 1, top 2 và tổng điểm'},
    {'time':'22:00','title':'Giao hữu cộng đồng','detail':'Đăng ký squad, luyện team, tìm đồng đội'},
]
DEFAULT_POINTS = [
    {'team':'Team Alpha','points':92},
    {'team':'Team Nova','points':88},
    {'team':'Team Titan','points':81},
    {'team':'Team Blaze','points':76},
]

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 12*1024*1024


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def prettydate(value):
    try:
        return datetime.fromisoformat(value).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return value or ''


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return query_one('SELECT * FROM users WHERE id=?', (uid,))


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def get_db():
    if 'db' not in g:
        g.db = connect_db()
    return g.db


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def exec_db(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur


def ensure_dirs():
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    POST_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR/'instance').mkdir(exist_ok=True)


def seed_db(db):
    if not db.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        seed_users = [
            ('admin','Admin FF','admin123','admin','Tài khoản quản trị mẫu','admin.png'),
            ('mod','Mod FF','mod123','mod','Người kiểm duyệt mẫu','mod.png'),
            ('member','Member FF','member123','member','Tài khoản thành viên mẫu','member.png'),
        ]
        for u,d,p,r,b,a in seed_users:
            db.execute('INSERT INTO users (username, display_name, password_hash, role, bio, avatar, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (u,d,generate_password_hash(p),r,b,a,now_str(),now_str()))
    if not db.execute('SELECT 1 FROM tournament_settings WHERE id=1').fetchone():
        db.execute('''INSERT INTO tournament_settings
            (id,title,season,region,current_stage,status,approved_only,rule_text,prize_text,schedule_json,points_json,updated_at)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?)''',
            ('FF Hub Championship','Season 1','SEA / Việt Nam','Vòng bảng','Đang diễn ra',1,
             'Member đăng bài sẽ vào chờ duyệt. Admin và Mod có thể duyệt, xóa và chỉnh sửa.',
             'Top 1, top 2, top 3, MVP và quà cộng đồng.',
             json.dumps(DEFAULT_SCHEDULE, ensure_ascii=False), json.dumps(DEFAULT_POINTS, ensure_ascii=False), now_str()))
    if not db.execute('SELECT 1 FROM posts LIMIT 1').fetchone():
        admin_id = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
        mod_id = db.execute("SELECT id FROM users WHERE username='mod'").fetchone()['id']
        posts = [
            ('Highlight kéo tâm cực căng','Highlight','Mẫu bài test cho like, bình luận, ảnh và video.','', '', admin_id, 'approved'),
            ('Review skin mới','Review','Bài review mẫu cho skin/súng/vòng quay.','', '', mod_id, 'approved'),
            ('Bài chờ duyệt','Meme','Bài demo cho quy trình kiểm duyệt.','', '', admin_id, 'pending'),
        ]
        for t,c,content,img,vid,aid,status in posts:
            db.execute('''INSERT INTO posts (title, category, content, image, video_url, author_id, status, created_at, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (t,c,content,img,vid,aid,status,now_str(),now_str()))
    if not db.execute('SELECT 1 FROM giftcodes LIMIT 1').fetchone():
        admin_id = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
        codes = [
            ('FFHUB-NEW','Vàng + vé spin',(datetime.now()+timedelta(days=7)).date().isoformat(),'active'),
            ('RANK-UP25','Gói hỗ trợ leo rank',(datetime.now()+timedelta(days=5)).date().isoformat(),'active'),
            ('LOOT-888','Vật phẩm ngẫu nhiên',(datetime.now()-timedelta(days=1)).date().isoformat(),'expired'),
        ]
        for code,reward,exp,status in codes:
            db.execute('INSERT INTO giftcodes (code,reward,expires_at,status,created_by,created_at) VALUES (?, ?, ?, ?, ?, ?)',
                       (code,reward,exp,status,admin_id,now_str()))
    db.commit()


def init_db():
    ensure_dirs()
    with connect_db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            bio TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            image TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            author_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(post_id, user_id),
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tournament_settings (
            id INTEGER PRIMARY KEY CHECK (id=1),
            title TEXT NOT NULL,
            season TEXT NOT NULL,
            region TEXT NOT NULL,
            current_stage TEXT NOT NULL,
            status TEXT NOT NULL,
            approved_only INTEGER NOT NULL DEFAULT 1,
            rule_text TEXT NOT NULL,
            prize_text TEXT NOT NULL,
            schedule_json TEXT NOT NULL,
            points_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS giftcodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            reward TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
        );
        ''')
        seed_db(db)


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.template_filter('prettydate')
def _prettydate(v):
    return prettydate(v)


@app.template_filter('fromjson')
def _fromjson(v):
    try:
        return json.loads(v or '[]')
    except Exception:
        return []


@app.context_processor
def inject():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return {
        'csrf_token': session['csrf_token'],
        'current_user': current_user(),
        'tournament': query_one('SELECT * FROM tournament_settings WHERE id=1'),
        'categories': CATEGORIES,
        'media_url': media_url,
    }


def media_url(folder, filename):
    return url_for('media_file', folder=folder, filename=filename)


def login_required(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if not current_user():
            flash('Cần đăng nhập trước.', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrap


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrap(*args, **kwargs):
            u = current_user()
            if not u:
                flash('Cần đăng nhập trước.', 'warning')
                return redirect(url_for('login'))
            if u['role'] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrap
    return deco


def can_view_post(post, user):
    if post['status'] == 'approved':
        return True
    if not user:
        return False
    return user['role'] in ('admin','mod') or user['id'] == post['author_id']


def base_post_sql():
    return '''SELECT p.*, u.username AS author_username, u.display_name AS author_display_name, u.avatar AS author_avatar, u.role AS author_role
              FROM posts p JOIN users u ON u.id = p.author_id'''


def save_upload(file_storage, folder, prefix):
    if not file_storage or not file_storage.filename:
        return ''
    if not allowed_image(file_storage.filename):
        raise ValueError('invalid')
    filename = f"{prefix}_{secrets.token_hex(8)}_{secure_filename(file_storage.filename)}"
    file_storage.save(folder / filename)
    return filename


@app.route('/')
def home():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', 'approved').strip()
    sql = base_post_sql() + ' WHERE 1=1'
    params = []
    if q:
        like = f'%{q}%'
        sql += ' AND (p.title LIKE ? OR p.content LIKE ? OR u.display_name LIKE ? OR u.username LIKE ?)'
        params += [like, like, like, like]
    if category:
        sql += ' AND p.category=?'
        params.append(category)
    if status in ('approved','pending','all') and status != 'all':
        sql += ' AND p.status=?'
        params.append(status)
    else:
        sql += " AND p.status='approved'"
    sql += ' ORDER BY p.created_at DESC'
    rows = query_all(sql, tuple(params))
    user = current_user()
    posts = []
    for r in rows:
        if can_view_post(r, user):
            d = dict(r)
            d['likes_count'] = query_one('SELECT COUNT(*) AS c FROM likes WHERE post_id=?', (r['id'],))['c']
            d['comments_count'] = query_one('SELECT COUNT(*) AS c FROM comments WHERE post_id=?', (r['id'],))['c']
            d['liked'] = False if not user else query_one('SELECT 1 FROM likes WHERE post_id=? AND user_id=?', (r['id'], user['id'])) is not None
            posts.append(d)
    return render_template('home.html', title='FF Hub', active='home', posts=posts, q=q, category=category, status=status)


@app.route('/section/<section_name>')
def section(section_name):
    mapping = {'esports':'Esports','news':'Tin tức','guides':'Cẩm nang','community':'Cộng đồng','recruit':'Tuyển team','giftcode':'Giftcode'}
    if section_name not in mapping:
        abort(404)
    cat = mapping[section_name]
    rows = query_all(base_post_sql() + " WHERE p.category=? AND p.status='approved' ORDER BY p.created_at DESC", (cat,))
    return render_template('section.html', title=f'{cat} · FF Hub', active=section_name, section_title=cat, posts=[dict(x) for x in rows])


@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = query_one(base_post_sql() + ' WHERE p.id=?', (post_id,))
    if not post:
        abort(404)
    user = current_user()
    if not can_view_post(post, user):
        abort(403)
    comments = query_all('''SELECT c.*, u.username, u.display_name, u.avatar FROM comments c JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.created_at ASC''', (post_id,))
    likes_count = query_one('SELECT COUNT(*) AS c FROM likes WHERE post_id=?', (post_id,))['c']
    liked = False if not user else query_one('SELECT 1 FROM likes WHERE post_id=? AND user_id=?', (post_id, user['id'])) is not None
    return render_template('post_detail.html', title=post['title'], active='home', post=post, comments=comments, likes_count=likes_count, liked=liked)


@app.route('/media/<folder>/<path:filename>')
def media_file(folder, filename):
    if folder not in ('avatars', 'posts'):
        abort(404)
    directory = AVATAR_DIR if folder == 'avatars' else POST_DIR
    return send_from_directory(directory, filename)


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        username = request.form.get('username', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '').strip()
        if len(username) < 3 or len(display_name) < 2 or len(password) < 6:
            flash('Thông tin chưa hợp lệ.', 'warning')
            return redirect(url_for('register'))
        if query_one('SELECT 1 FROM users WHERE username=?', (username,)):
            flash('Tên đăng nhập đã tồn tại.', 'warning')
            return redirect(url_for('register'))
        exec_db('INSERT INTO users (username, display_name, password_hash, role, bio, avatar, created_at, updated_at) VALUES (?, ?, ?, "member", "", "", ?, ?)',
                (username, display_name, generate_password_hash(password), now_str(), now_str()))
        session['user_id'] = query_one('SELECT id FROM users WHERE username=?', (username,))['id']
        flash('Đăng ký thành công.', 'success')
        return redirect(url_for('home'))
    return render_template('auth_register.html', title='Đăng ký', active='auth')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = query_one('SELECT * FROM users WHERE username=?', (username,))
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Sai tài khoản hoặc mật khẩu.', 'danger')
            return redirect(url_for('login'))
        session['user_id'] = user['id']
        flash(f"Xin chào {user['display_name']}!", 'success')
        return redirect(url_for('home'))
    return render_template('auth_login.html', title='Đăng nhập', active='auth')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Đã đăng xuất.', 'info')
    return redirect(url_for('home'))


@app.route('/post/create', methods=['GET','POST'])
@login_required
def create_post():
    u = current_user()
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'Cộng đồng').strip()
        content = request.form.get('content', '').strip()
        video_url = request.form.get('video_url', '').strip()
        if not title or not content:
            flash('Cần tiêu đề và nội dung.', 'warning')
            return redirect(url_for('create_post'))
        try:
            image_name = save_upload(request.files.get('image'), POST_DIR, 'post')
        except ValueError:
            flash('Ảnh không hợp lệ.', 'warning')
            return redirect(url_for('create_post'))
        need_approval = query_one('SELECT approved_only FROM tournament_settings WHERE id=1')['approved_only'] == 1
        status = 'pending' if (need_approval and u['role'] == 'member') else 'approved'
        exec_db('''INSERT INTO posts (title, category, content, image, video_url, author_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (title, category, content, image_name, video_url, u['id'], status, now_str(), now_str()))
        flash('Đã đăng bài.' if status == 'approved' else 'Bài đã vào chờ duyệt.', 'success')
        return redirect(url_for('home'))
    return render_template('post_form.html', title='Đăng bài mới', active='home', post=None)


@app.route('/post/<int:post_id>/edit', methods=['GET','POST'])
@login_required
def edit_post(post_id):
    post = query_one('SELECT * FROM posts WHERE id=?', (post_id,))
    if not post:
        abort(404)
    u = current_user()
    if u['role'] not in ('admin','mod') and u['id'] != post['author_id']:
        abort(403)
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        content = request.form.get('content', '').strip()
        video_url = request.form.get('video_url', '').strip()
        status = request.form.get('status', post['status'])
        if u['role'] == 'member':
            status = post['status']
        image_name = post['image'] or ''
        try:
            image = request.files.get('image')
            if image and image.filename:
                image_name = save_upload(image, POST_DIR, 'post')
        except ValueError:
            flash('Ảnh không hợp lệ.', 'warning')
            return redirect(url_for('edit_post', post_id=post_id))
        exec_db('''UPDATE posts SET title=?, category=?, content=?, image=?, video_url=?, status=?, updated_at=? WHERE id=?''',
                (title, category, content, image_name, video_url, status, now_str(), post_id))
        flash('Đã lưu thay đổi.', 'success')
        return redirect(url_for('post_detail', post_id=post_id))
    return render_template('post_form.html', title='Chỉnh sửa bài viết', active='home', post=post)


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)
    post = query_one('SELECT * FROM posts WHERE id=?', (post_id,))
    if not post:
        abort(404)
    u = current_user()
    if u['role'] not in ('admin','mod') and u['id'] != post['author_id']:
        abort(403)
    exec_db('DELETE FROM posts WHERE id=?', (post_id,))
    flash('Đã xóa bài.', 'success')
    return redirect(url_for('home'))


@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)
    u = current_user()
    exists = query_one('SELECT id FROM likes WHERE post_id=? AND user_id=?', (post_id, u['id']))
    if exists:
        exec_db('DELETE FROM likes WHERE id=?', (exists['id'],))
    else:
        try:
            exec_db('INSERT INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)', (post_id, u['id'], now_str()))
        except sqlite3.IntegrityError:
            pass
    return redirect(request.referrer or url_for('home'))


@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)
    content = request.form.get('content', '').strip()
    if not content:
        flash('Bình luận không được trống.', 'warning')
        return redirect(url_for('post_detail', post_id=post_id))
    exec_db('INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, ?)', (post_id, current_user()['id'], content, now_str()))
    flash('Đã gửi bình luận.', 'success')
    return redirect(url_for('post_detail', post_id=post_id))


@app.route('/profile/<username>')
def profile(username):
    user = query_one('SELECT * FROM users WHERE username=?', (username.lower(),))
    if not user:
        abort(404)
    posts = query_all(base_post_sql() + " WHERE p.author_id=? AND p.status='approved' ORDER BY p.created_at DESC", (user['id'],))
    return render_template('profile.html', title=user['display_name'], active=None, profile=user, posts=[dict(r) for r in posts])


@app.route('/account/edit', methods=['GET','POST'])
@login_required
def edit_my_account():
    u = current_user()
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        if len(display_name) < 2:
            flash('Tên hiển thị quá ngắn.', 'warning')
            return redirect(url_for('edit_my_account'))
        avatar_name = u['avatar'] or ''
        try:
            avatar = request.files.get('avatar')
            if avatar and avatar.filename:
                avatar_name = save_upload(avatar, AVATAR_DIR, 'avatar')
        except ValueError:
            flash('Avatar không hợp lệ.', 'warning')
            return redirect(url_for('edit_my_account'))
        exec_db('UPDATE users SET display_name=?, bio=?, avatar=?, updated_at=? WHERE id=?', (display_name, bio, avatar_name, now_str(), u['id']))
        flash('Đã cập nhật hồ sơ.', 'success')
        return redirect(url_for('profile', username=u['username']))
    return render_template('account_edit.html', title='Chỉnh hồ sơ', active=None, profile=u)


@app.route('/admin')
@role_required('mod','admin')
def admin_dashboard():
    users = query_all('SELECT * FROM users ORDER BY created_at DESC')
    pending_posts = query_all(base_post_sql() + " WHERE p.status='pending' ORDER BY p.created_at ASC")
    giftcodes = query_all('''SELECT g.*, u.username AS creator_username, u.display_name AS creator_display_name FROM giftcodes g JOIN users u ON u.id=g.created_by ORDER BY g.created_at DESC''')
    return render_template('admin_dashboard.html', title='Admin Dashboard', active='admin', users=users, pending_posts=[dict(r) for r in pending_posts], giftcodes=giftcodes)


@app.route('/admin/users', methods=['GET','POST'])
@role_required('admin')
def admin_users():
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        username = request.form.get('username', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'member')
        bio = request.form.get('bio', '').strip()
        if role not in ('member','mod'):
            flash('Chỉ tạo member hoặc mod.', 'warning')
            return redirect(url_for('admin_users'))
        if len(username) < 3 or len(display_name) < 2 or len(password) < 6:
            flash('Thông tin chưa hợp lệ.', 'warning')
            return redirect(url_for('admin_users'))
        if query_one('SELECT 1 FROM users WHERE username=?', (username,)):
            flash('Tài khoản đã tồn tại.', 'warning')
            return redirect(url_for('admin_users'))
        avatar_name = ''
        try:
            avatar = request.files.get('avatar')
            if avatar and avatar.filename:
                avatar_name = save_upload(avatar, AVATAR_DIR, 'avatar')
        except ValueError:
            flash('Avatar không hợp lệ.', 'warning')
            return redirect(url_for('admin_users'))
        exec_db('INSERT INTO users (username, display_name, password_hash, role, bio, avatar, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (username, display_name, generate_password_hash(password), role, bio, avatar_name, now_str(), now_str()))
        flash('Đã tạo tài khoản mới.', 'success')
        return redirect(url_for('admin_users'))
    users = query_all('SELECT * FROM users ORDER BY created_at DESC')
    return render_template('admin_users.html', title='Quản lý tài khoản', active='admin', users=users)


@app.route('/admin/users/<int:user_id>/edit', methods=['GET','POST'])
@role_required('admin')
def admin_edit_user(user_id):
    user = query_one('SELECT * FROM users WHERE id=?', (user_id,))
    if not user:
        abort(404)
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        username = request.form.get('username', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        role = request.form.get('role', user['role'])
        bio = request.form.get('bio', '').strip()
        if role not in ('member','mod','admin'):
            flash('Vai trò không hợp lệ.', 'warning')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        if user['username'] == 'admin' and role != 'admin':
            flash('Không thể hạ vai trò admin gốc.', 'warning')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        if len(username) < 3 or len(display_name) < 2:
            flash('Tên không hợp lệ.', 'warning')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        other = query_one('SELECT id FROM users WHERE username=? AND id<>?', (username, user_id))
        if other:
            flash('Username đã tồn tại.', 'warning')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        avatar_name = user['avatar'] or ''
        try:
            avatar = request.files.get('avatar')
            if avatar and avatar.filename:
                avatar_name = save_upload(avatar, AVATAR_DIR, 'avatar')
        except ValueError:
            flash('Avatar không hợp lệ.', 'warning')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        exec_db('UPDATE users SET username=?, display_name=?, role=?, bio=?, avatar=?, updated_at=? WHERE id=?',
                (username, display_name, role, bio, avatar_name, now_str(), user_id))
        flash('Đã cập nhật tài khoản.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin_user_edit.html', title='Sửa tài khoản', active='admin', edit_user=user)


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@role_required('admin')
def admin_change_role(user_id):
    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)
    role = request.form.get('role', 'member')
    if role not in ('member','mod','admin'):
        abort(400)
    user = query_one('SELECT * FROM users WHERE id=?', (user_id,))
    if not user:
        abort(404)
    if user['username'] == 'admin' and role != 'admin':
        flash('Không thể đổi vai trò admin gốc.', 'warning')
        return redirect(url_for('admin_users'))
    exec_db('UPDATE users SET role=?, updated_at=? WHERE id=?', (role, now_str(), user_id))
    flash('Đã đổi vai trò.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/password', methods=['POST'])
@role_required('admin')
def admin_reset_password(user_id):
    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('Mật khẩu mới quá ngắn.', 'warning')
        return redirect(url_for('admin_users'))
    exec_db('UPDATE users SET password_hash=?, updated_at=? WHERE id=?', (generate_password_hash(new_password), now_str(), user_id))
    flash('Đã reset mật khẩu.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/tournament', methods=['GET','POST'])
@role_required('admin','mod')
def admin_tournament():
    tournament = query_one('SELECT * FROM tournament_settings WHERE id=1')
    if request.method == 'POST':
        if request.form.get('csrf_token') != session.get('csrf_token'):
            abort(400)
        title = request.form.get('title', '').strip()
        season = request.form.get('season', '').strip()
        region = request.form.get('region', '').strip()
        current_stage = request.form.get('current_stage', '').strip()
        status = request.form.get('status', '').strip()
        approved_only = 1 if request.form.get('approved_only') == 'on' else 0
        rule_text = request.form.get('rule_text', '').strip()
        prize_text = request.form.get('prize_text', '').strip()
        schedule_json = request.form.get('schedule_json', '').strip()
        points_json = request.form.get('points_json', '').strip()
        if not title:
            flash('Tên giải không được trống.', 'warning')
            return redirect(url_for('admin_tournament'))
        try:
            json.loads(schedule_json)
            json.loads(points_json)
        except Exception:
            flash('JSON lịch thi đấu hoặc bảng điểm không hợp lệ.', 'warning')
            return redirect(url_for('admin_tournament'))
        exec_db('''UPDATE tournament_settings SET title=?, season=?, region=?, current_stage=?, status=?, approved_only=?, rule_text=?, prize_text=?, schedule_json=?, points_json=?, updated_at=? WHERE id=1''',
                (title, season, region, current_stage, status, approved_only, rule_text, prize_text, schedule_json, points_json, now_str()))
        flash('Đã lưu thông số giải đấu.', 'success')
        return redirect(url_for('admin_tournament'))
    return render_template('admin_tournament.html', title='Chỉnh thông số giải đấu', active='admin', tournament=tournament)


@app.route('/admin/giftcodes', methods=['POST'])
@role_required('admin','mod')
def create_giftcode():
    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)
    code = request.form.get('code', '').strip().upper()
    reward = request.form.get('reward', '').strip()
    expires_at = request.form.get('expires_at', '').strip()
    if not code or not reward or not expires_at:
        flash('Điền đủ mã, quà và ngày hết hạn.', 'warning')
        return redirect(url_for('admin_dashboard'))
    try:
        datetime.fromisoformat(expires_at)
    except Exception:
        flash('Ngày hết hạn không hợp lệ.', 'warning')
        return redirect(url_for('admin_dashboard'))
    if query_one('SELECT 1 FROM giftcodes WHERE code=?', (code,)):
        flash('Giftcode đã tồn tại.', 'warning')
        return redirect(url_for('admin_dashboard'))
    exec_db('INSERT INTO giftcodes (code,reward,expires_at,status,created_by,created_at) VALUES (?, ?, ?, "active", ?, ?)',
            (code,reward,expires_at,current_user()['id'],now_str()))
    flash('Đã tạo giftcode.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/giftcodes')
def giftcodes_page():
    items = query_all('''SELECT g.*, u.username AS creator_username, u.display_name AS creator_display_name FROM giftcodes g JOIN users u ON u.id=g.created_by ORDER BY g.created_at DESC''')
    return render_template('giftcodes.html', title='Kho giftcode', active='giftcode', giftcodes=items)


@app.route('/api/tournament')
def api_tournament():
    t = query_one('SELECT * FROM tournament_settings WHERE id=1')
    return jsonify({
        'title': t['title'],
        'season': t['season'],
        'region': t['region'],
        'current_stage': t['current_stage'],
        'status': t['status'],
        'approved_only': bool(t['approved_only']),
        'rule_text': t['rule_text'],
        'prize_text': t['prize_text'],
        'schedule': json.loads(t['schedule_json']),
        'points': json.loads(t['points_json']),
        'updated_at': t['updated_at'],
    })


@app.errorhandler(403)
def e403(_):
    return render_template('error.html', title='403', code=403, message='Bạn không có quyền truy cập trang này.'), 403


@app.errorhandler(404)
def e404(_):
    return render_template('error.html', title='404', code=404, message='Không tìm thấy trang.'), 404


@app.errorhandler(413)
def e413(_):
    return render_template('error.html', title='413', code=413, message='File quá lớn.'), 413


@app.before_request
def boot():
    if not DB_PATH.exists():
        init_db()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
