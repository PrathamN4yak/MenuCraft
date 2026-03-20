# ============================================================
# MenuCraft — Flask Backend
# Production-ready for Vercel + Neon PostgreSQL
# ============================================================

import os, json, random, string
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# ── App setup ────────────────────────────────────────────────
# BASE_DIR = project root (parent of backend/)
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR   = os.path.join(BASE_DIR, 'static')

# Vercel sometimes runs from /var/task — fallback to cwd
if not os.path.isdir(TEMPLATE_DIR):
    TEMPLATE_DIR = os.path.join(os.getcwd(), 'templates')
if not os.path.isdir(STATIC_DIR):
    STATIC_DIR = os.path.join(os.getcwd(), 'static')

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)
CORS(app, supports_credentials=True)

# ── Config ───────────────────────────────────────────────────
IS_PROD = os.environ.get('FLASK_ENV') == 'production'

# Secret key — MUST be set in Vercel env vars in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key-change-in-production')

# Database — Neon PostgreSQL in production, SQLite locally
_db_url = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'menucraft.db')
)
# Vercel/Neon gives postgres://, SQLAlchemy needs postgresql://
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI']        = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS']      = {
    'pool_pre_ping': True,   # reconnect if connection drops
    'pool_recycle':  300,    # recycle connections every 5 mins
}

# Session cookie security
app.config['SESSION_COOKIE_SECURE']   = IS_PROD   # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True       # no JS access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Admin credentials — set these in Vercel environment variables
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-in-production')

db = SQLAlchemy(app)


# ============================================================
# MODELS
# ============================================================

class User(db.Model):
    id         = db.Column(db.Integer,     primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    phone      = db.Column(db.String(30),  default='')
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)
    orders     = db.relationship('Order',  backref='user', lazy=True)

    def to_dict(self):
        return { 'id': self.id, 'name': self.name, 'email': self.email, 'phone': self.phone or '' }


class Dish(db.Model):
    """Individual dishes shown in custom-menu.html Step 3"""
    id          = db.Column(db.Integer,     primary_key=True)
    name        = db.Column(db.String(150), nullable=False)
    category    = db.Column(db.String(50),  nullable=False)  # starter|main|bread|rice|dessert|drink|special
    price       = db.Column(db.Float,       nullable=False)
    emoji       = db.Column(db.String(10),  default='🍽️')
    description = db.Column(db.String(255), default='')
    image_url   = db.Column(db.Text,        default='')
    is_featured = db.Column(db.Boolean,     default=False)
    is_active   = db.Column(db.Boolean,     default=True)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'category': self.category,
            'price': self.price, 'emoji': self.emoji,
            'description': self.description, 'image_url': self.image_url,
            'is_featured': self.is_featured,
        }


class ComboPackage(db.Model):
    """Combo meal packages shown on menu.html"""
    id             = db.Column(db.Integer,     primary_key=True)
    name           = db.Column(db.String(150), nullable=False)
    tagline        = db.Column(db.String(255), default='')
    category       = db.Column(db.String(100), default='')
    price_per_head = db.Column(db.Float,       nullable=False)
    price_sub      = db.Column(db.String(30),  default='per head')
    dishes         = db.Column(db.Text,        default='[]')
    serves_note    = db.Column(db.String(100), default='')
    is_popular     = db.Column(db.Boolean,     default=False)
    popular_label  = db.Column(db.String(50),  default='')
    theme          = db.Column(db.String(30),  default='theme-south')
    emoji          = db.Column(db.String(10),  default='🍽️')
    is_active      = db.Column(db.Boolean,     default=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'tagline': self.tagline,
            'category': self.category, 'price': self.price_per_head,
            'price_sub': self.price_sub,
            'dishes': json.loads(self.dishes) if self.dishes else [],
            'serves_note': self.serves_note, 'is_popular': self.is_popular,
            'popular_label': self.popular_label, 'theme': self.theme, 'emoji': self.emoji,
        }


class Order(db.Model):
    id             = db.Column(db.Integer,     primary_key=True)
    customer_name  = db.Column(db.String(120), default='')
    customer_email = db.Column(db.String(120), default='')
    customer_phone = db.Column(db.String(30),  default='')
    event_type     = db.Column(db.String(60),  default='')
    event_date     = db.Column(db.String(20),  default='')
    event_time     = db.Column(db.String(10),  default='')
    venue          = db.Column(db.String(200), default='')
    guest_count    = db.Column(db.Integer,     default=0)
    serving_style  = db.Column(db.String(30),  default='')
    combo_id       = db.Column(db.Integer,     db.ForeignKey('combo_package.id'), nullable=True)
    custom_dishes  = db.Column(db.Text,        default='{}')
    special_notes  = db.Column(db.Text,        default='')
    total_price    = db.Column(db.Float,       default=0.0)
    status         = db.Column(db.String(30),  default='Pending')
    booking_ref    = db.Column(db.String(20),  unique=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)
    user_id        = db.Column(db.Integer,     db.ForeignKey('user.id'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'ref': self.booking_ref,
            'customer': self.customer_name, 'email': self.customer_email,
            'phone': self.customer_phone, 'event_type': self.event_type,
            'event_date': self.event_date, 'guests': self.guest_count,
            'serving': self.serving_style, 'venue': self.venue,
            'total': self.total_price, 'status': self.status,
            'created_at': str(self.created_at),
        }


class ContactMessage(db.Model):
    id         = db.Column(db.Integer,     primary_key=True)
    name       = db.Column(db.String(120), default='')
    email      = db.Column(db.String(120), default='')
    phone      = db.Column(db.String(30),  default='')
    enquiry    = db.Column(db.String(60),  default='General')
    message    = db.Column(db.Text,        default='')
    event_date = db.Column(db.String(20),  default='')
    guests     = db.Column(db.String(30),  default='')
    is_read    = db.Column(db.Boolean,     default=False)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)


# ============================================================
# DECORATORS
# ============================================================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'message': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated


# ============================================================
# HELPERS
# ============================================================

def make_ref():
    return 'MC-' + ''.join(random.choices(string.digits, k=6))


def sanitise(value, max_length=255):
    """Strip dangerous characters and enforce max length on user input"""
    if not value:
        return ''
    # Remove null bytes and control characters
    cleaned = str(value).replace('', '').strip()
    # Enforce max length
    return cleaned[:max_length]


# ============================================================
# PAGE ROUTES
# ============================================================

@app.route('/')
def home():          return render_template('index.html')

@app.route('/menu')
def menu():          return render_template('menu.html')

@app.route('/book')
def book_page():
    if not session.get('user_id'):
        return redirect('/auth?next=book')
    resp = make_response(render_template('book.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma']        = 'no-cache'
    resp.headers['Expires']       = '0'
    return resp

@app.route('/custom-menu')
def custom_menu():
    if not session.get('user_id'):
        return redirect('/auth?next=custom-menu')
    resp = make_response(render_template('custom-menu.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma']        = 'no-cache'
    resp.headers['Expires']       = '0'
    return resp

@app.route('/auth')
def auth():          return render_template('auth.html')

@app.route('/about')
def about():         return render_template('about.html')

@app.route('/contact')
def contact():       return render_template('contact.html')

@app.route('/dashboard')
def dashboard():
    resp = make_response(render_template('dashboard.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma']        = 'no-cache'
    resp.headers['Expires']       = '0'
    return resp

@app.route('/admin')
def admin_page():
    if not session.get('is_admin'):
        return render_template('admin-login.html')
    return render_template('admin.html')


# ============================================================
# PUBLIC API — DISHES
# ============================================================

@app.route('/api/dishes')
def get_dishes():
    category = request.args.get('category')
    q = Dish.query.filter_by(is_active=True)
    if category and category != 'all':
        q = q.filter_by(category=category)
    return jsonify([d.to_dict() for d in q.order_by(Dish.category, Dish.name).all()])


# ============================================================
# PUBLIC API — COMBOS
# ============================================================

@app.route('/api/combos')
def get_combos():
    category = request.args.get('category')
    q = ComboPackage.query.filter_by(is_active=True)
    if category and category != 'all':
        q = q.filter(ComboPackage.category.contains(category))
    return jsonify([c.to_dict() for c in q.order_by(ComboPackage.created_at).all()])


# ============================================================
# PUBLIC API — BOOKING
# ============================================================

@app.route('/api/book', methods=['POST'])
def api_book():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400

    # Prevent duplicate ref collisions
    ref = make_ref()
    while Order.query.filter_by(booking_ref=ref).first():
        ref = make_ref()

    order = Order(
        customer_name  = data.get('customer', {}).get('name', ''),
        customer_email = data.get('customer', {}).get('email', ''),
        customer_phone = data.get('customer', {}).get('phone', ''),
        event_type     = data.get('event', {}).get('type', ''),
        event_date     = data.get('event', {}).get('date', ''),
        event_time     = data.get('event', {}).get('time', ''),
        venue          = data.get('event', {}).get('venue', ''),
        guest_count    = int(data.get('event', {}).get('guests', 0) or 0),
        serving_style  = data.get('event', {}).get('serving', ''),
        special_notes  = data.get('event', {}).get('notes', ''),
        custom_dishes  = json.dumps(data.get('dishes', {})),
        total_price    = float(data.get('totalRaw', 0) or 0),
        booking_ref    = ref,
        status         = 'Pending',
        user_id        = session.get('user_id'),
    )
    db.session.add(order)
    db.session.commit()
    return jsonify({'success': True, 'booking_ref': ref})


# ============================================================
# PUBLIC API — CONTACT
# ============================================================

@app.route('/api/contact', methods=['POST'])
def api_contact():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    msg = ContactMessage(
        name       = sanitise(data.get('name', ''), 120),
        email      = sanitise(data.get('email', ''), 120),
        phone      = sanitise(data.get('phone', ''), 30),
        enquiry    = sanitise(data.get('enquiry', 'General'), 60),
        message    = sanitise(data.get('message', ''), 2000),
        event_date = sanitise(data.get('event_date', ''), 20),
        guests     = sanitise(data.get('guests', ''), 30),
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# AUTH API
# ============================================================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400

    name  = sanitise(data.get('name'), 120)
    email = sanitise(data.get('email'), 120).lower()
    phone = sanitise(data.get('phone'), 30)
    pwd   = data.get('password') or ''

    if not name or not email or not pwd:
        return jsonify({'success': False, 'message': 'Name, email and password are required'}), 400
    if len(pwd) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 400

    user = User(name=name, email=email, phone=phone, password=generate_password_hash(pwd))
    db.session.add(user)
    db.session.commit()
    session.permanent = True
    session['user_id']   = user.id
    session['user_name'] = user.name
    return jsonify({'success': True, 'name': user.name})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400

    email = (data.get('email') or '').strip().lower()
    pwd   = data.get('password') or ''
    user  = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, pwd):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    session.permanent = True
    session['user_id']   = user.id
    session['user_name'] = user.name
    return jsonify({'success': True, 'name': user.name})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/me')
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify({'success': True, 'name': user.name, 'email': user.email, 'phone': user.phone or ''})


@app.route('/api/my-orders')
@login_required
def my_orders():
    user    = User.query.get(session['user_id'])
    orders  = Order.query.filter_by(customer_email=user.email).order_by(Order.created_at.desc()).all()
    result  = []
    for o in orders:
        combo_name = None
        if o.combo_id:
            combo = ComboPackage.query.get(o.combo_id)
            if combo:
                combo_name = combo.name
        d = o.to_dict()
        d['combo_name'] = combo_name
        result.append(d)
    return jsonify(result)


# ============================================================
# ADMIN AUTH API
# ============================================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json(silent=True) or {}
    if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('is_admin', None)
    return jsonify({'success': True})


@app.route('/api/admin/check')
def admin_check():
    return jsonify({'is_admin': bool(session.get('is_admin'))})


# ============================================================
# ADMIN API — DISHES CRUD
# ============================================================

@app.route('/api/admin/dishes')
@admin_required
def admin_get_dishes():
    dishes = Dish.query.filter_by(is_active=True).order_by(Dish.category, Dish.name).all()
    return jsonify([d.to_dict() for d in dishes])


@app.route('/api/admin/dishes', methods=['POST'])
@admin_required
def admin_create_dish():
    data = request.get_json(silent=True) or {}
    dish = Dish(
        name        = data.get('name', ''),
        category    = data.get('category', 'main'),
        price       = float(data.get('price', 0) or 0),
        emoji       = data.get('emoji', '🍽️'),
        description = data.get('desc', ''),
        image_url   = data.get('img', ''),
        is_featured = bool(data.get('featured', False)),
    )
    db.session.add(dish)
    db.session.commit()
    return jsonify({'success': True, 'id': dish.id})


@app.route('/api/admin/dishes/<int:dish_id>', methods=['PUT'])
@admin_required
def admin_update_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    data = request.get_json(silent=True) or {}
    dish.name        = data.get('name',     dish.name)
    dish.category    = data.get('category', dish.category)
    dish.price       = float(data.get('price', dish.price) or dish.price)
    dish.emoji       = data.get('emoji',    dish.emoji)
    dish.description = data.get('desc',     dish.description)
    dish.image_url   = data.get('img',      dish.image_url)
    dish.is_featured = bool(data.get('featured', dish.is_featured))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/dishes/<int:dish_id>', methods=['DELETE'])
@admin_required
def admin_delete_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    dish.is_active = False
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# ADMIN API — COMBOS CRUD
# ============================================================

@app.route('/api/admin/combos')
@admin_required
def admin_get_combos():
    combos = ComboPackage.query.filter_by(is_active=True).order_by(ComboPackage.created_at).all()
    return jsonify([c.to_dict() for c in combos])


@app.route('/api/admin/combos', methods=['POST'])
@admin_required
def admin_create_combo():
    data  = request.get_json(silent=True) or {}
    combo = ComboPackage(
        name          = data.get('name', ''),
        tagline       = data.get('tagline', ''),
        category      = data.get('category', ''),
        price_per_head= float(data.get('price', 0) or 0),
        price_sub     = data.get('priceSub', 'per head'),
        dishes        = json.dumps(data.get('dishes', [])),
        serves_note   = data.get('serves', ''),
        is_popular    = bool(data.get('isPopular', False)),
        popular_label = data.get('popularLabel', ''),
        theme         = data.get('theme', 'theme-south'),
        emoji         = data.get('emoji', '🍽️'),
    )
    db.session.add(combo)
    db.session.commit()
    return jsonify({'success': True, 'id': combo.id})


@app.route('/api/admin/combos/<int:combo_id>', methods=['PUT'])
@admin_required
def admin_update_combo(combo_id):
    combo = ComboPackage.query.get_or_404(combo_id)
    data  = request.get_json(silent=True) or {}
    combo.name          = data.get('name',         combo.name)
    combo.tagline       = data.get('tagline',       combo.tagline)
    combo.category      = data.get('category',      combo.category)
    combo.price_per_head= float(data.get('price',   combo.price_per_head) or combo.price_per_head)
    combo.price_sub     = data.get('priceSub',      combo.price_sub)
    combo.dishes        = json.dumps(data['dishes']) if 'dishes' in data else combo.dishes
    combo.serves_note   = data.get('serves',        combo.serves_note)
    combo.is_popular    = bool(data.get('isPopular', combo.is_popular))
    combo.popular_label = data.get('popularLabel',  combo.popular_label)
    combo.theme         = data.get('theme',         combo.theme)
    combo.emoji         = data.get('emoji',         combo.emoji)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/combos/<int:combo_id>', methods=['DELETE'])
@admin_required
def admin_delete_combo(combo_id):
    combo = ComboPackage.query.get_or_404(combo_id)
    combo.is_active = False
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# ADMIN API — ORDERS
# ============================================================

@app.route('/api/admin/orders')
@admin_required
def admin_get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@app.route('/api/admin/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def admin_update_order_status(order_id):
    order  = Order.query.get_or_404(order_id)
    data   = request.get_json(silent=True) or {}
    status = data.get('status', '').strip()
    valid  = ['Pending', 'Confirmed', 'In Preparation', 'Delivered', 'Cancelled']
    if status not in valid:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    order.status = status
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# ADMIN API — CUSTOMERS
# ============================================================

@app.route('/api/admin/customers')
@admin_required
def admin_get_customers():
    users  = User.query.order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        orders      = Order.query.filter_by(customer_email=u.email).all()
        total_spent = sum(o.total_price or 0 for o in orders)
        result.append({
            'id':       u.id,
            'name':     u.name,
            'email':    u.email,
            'phone':    u.phone or '',
            'bookings': len(orders),
            'spent':    round(total_spent, 2),
            'joined':   u.created_at.strftime('%b %Y'),
        })
    return jsonify(result)


# ============================================================
# ADMIN API — CONTACT MESSAGES
# ============================================================

@app.route('/api/admin/messages')
@admin_required
def admin_get_messages():
    msgs = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return jsonify([{
        'id':         m.id,
        'name':       m.name,
        'email':      m.email,
        'phone':      m.phone,
        'enquiry':    m.enquiry,
        'message':    m.message,
        'event_date': m.event_date,
        'guests':     m.guests,
        'is_read':    m.is_read,
        'created_at': str(m.created_at),
    } for m in msgs])


@app.route('/api/admin/messages/<int:msg_id>/read', methods=['PUT'])
@admin_required
def admin_mark_message_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# SEED DATA — runs once on first startup
# ============================================================

def seed_data():
    if Dish.query.count() == 0:
        dishes = [
            Dish(name='Garden Fresh Salad',   category='starter', price=120, emoji='🥗', description='Fresh seasonal vegetables'),
            Dish(name='Crispy Veg Platter',   category='starter', price=180, emoji='🧆', description='Assorted fried starters'),
            Dish(name='Paneer Tikka Skewers', category='starter', price=200, emoji='🥙', description='Grilled paneer with spices',  is_featured=True),
            Dish(name='Sweet Corn Soup',      category='starter', price=90,  emoji='🍲', description='Creamy sweet corn soup'),
            Dish(name='Vadai',                category='starter', price=60,  emoji='🟤', description='Crispy South Indian fritter'),
            Dish(name='Paneer Butter Masala', category='main',    price=200, emoji='🍛', description='Rich paneer in tomato gravy', is_featured=True),
            Dish(name='Dal Makhani',          category='main',    price=160, emoji='🫕', description='Slow-cooked black lentils'),
            Dish(name='Mixed Veg Curry',      category='main',    price=150, emoji='🥘', description='Seasonal vegetables in curry'),
            Dish(name='Sambar',               category='main',    price=80,  emoji='🥣', description='South Indian lentil stew'),
            Dish(name='Rasam',                category='main',    price=60,  emoji='🥣', description='Tangy South Indian soup'),
            Dish(name='Avial',                category='main',    price=120, emoji='🥗', description='Vegetables in coconut gravy'),
            Dish(name='Kootu',                category='main',    price=100, emoji='🥘', description='Lentil and vegetable stew'),
            Dish(name='Parota',               category='bread',   price=40,  emoji='🫓', description='Flaky layered flatbread'),
            Dish(name='Roti / Chapati',       category='bread',   price=30,  emoji='🫓', description='Soft whole wheat flatbread'),
            Dish(name='Naan',                 category='bread',   price=50,  emoji='🫓', description='Soft leavened tandoor bread'),
            Dish(name='Puri',                 category='bread',   price=35,  emoji='🫓', description='Deep fried wheat puri'),
            Dish(name='Appalam / Papad',      category='bread',   price=25,  emoji='🥙', description='Crispy lentil wafer'),
            Dish(name='Steamed Rice',         category='rice',    price=60,  emoji='🍚', description='Plain steamed basmati rice'),
            Dish(name='Jeera Rice',           category='rice',    price=80,  emoji='🍚', description='Cumin flavoured rice'),
            Dish(name='Veg Dum Biryani',      category='rice',    price=180, emoji='🌾', description='Fragrant basmati with veg',  is_featured=True),
            Dish(name='Lemon Rice',           category='rice',    price=70,  emoji='🍋', description='Tangy South Indian rice'),
            Dish(name='Curd Rice',            category='rice',    price=65,  emoji='🍚', description='Cooling curd rice'),
            Dish(name='Gulab Jamun',          category='dessert', price=80,  emoji='🍮', description='Milk solids in sugar syrup'),
            Dish(name='Eggless Cake Slice',   category='dessert', price=180, emoji='🎂', description='Moist eggless cake',         is_featured=True),
            Dish(name='Kulfi Falooda',        category='dessert', price=110, emoji='🍨', description='Traditional Indian ice cream'),
            Dish(name='Payasam',              category='dessert', price=70,  emoji='🍯', description='South Indian sweet kheer'),
            Dish(name='Sweet Pongal',         category='dessert', price=80,  emoji='🍛', description='Sweet rice and lentil dish'),
            Dish(name='Welcome Mocktail',     category='drink',   price=90,  emoji='🥤', description='Refreshing fruit mocktail'),
            Dish(name='Masala Chai',          category='drink',   price=30,  emoji='☕', description='Spiced Indian tea'),
            Dish(name='Filter Coffee',        category='drink',   price=35,  emoji='☕', description='South Indian drip coffee'),
            Dish(name='Buttermilk',           category='drink',   price=40,  emoji='🥛', description='Chilled seasoned buttermilk'),
            Dish(name='Fresh Lime Soda',      category='drink',   price=50,  emoji='🍋', description='Refreshing lime drink'),
            Dish(name='South Indian Thali',   category='special', price=300, emoji='🍱', description='Complete traditional thali', is_featured=True),
            Dish(name='Live Pasta Station',   category='special', price=240, emoji='👨‍🍳', description='Freshly tossed pasta live'),
            Dish(name='Dal Baati Churma',     category='special', price=280, emoji='🫕', description='Rajasthani specialty'),
        ]
        db.session.add_all(dishes)
        print(f'  Seeded {len(dishes)} dishes')

    if ComboPackage.query.count() == 0:
        combos = [
            ComboPackage(
                name='Simple South Indian Dinner', tagline='Classic homestyle South Indian meal',
                category='south dinner', price_per_head=350, price_sub='per head',
                dishes=json.dumps([{'name':'Steamed Rice'},{'name':'Sambar'},{'name':'Rasam'},
                    {'name':'Kootu'},{'name':'Papad'},{'name':'Pickle'},
                    {'name':'Sweet Pongal'},{'name':'Buttermilk'}]),
                serves_note='Suitable for all event sizes', theme='theme-south', emoji='🍌'),
            ComboPackage(
                name='Grand South Indian Feast', tagline='Full traditional spread for weddings',
                category='south dinner wedding', price_per_head=650, price_sub='per head',
                dishes=json.dumps([{'name':'Welcome Drink'},{'name':'Vadai'},{'name':'Steamed Rice'},
                    {'name':'Sambar'},{'name':'Rasam'},{'name':'Avial'},{'name':'Kootu'},
                    {'name':'Poriyal'},{'name':'Appalam'},{'name':'Pickle'},
                    {'name':'Payasam'},{'name':'Buttermilk'}]),
                serves_note='Best for 100+ guests', is_popular=True,
                popular_label='⭐ Most Popular', theme='theme-wedding', emoji='🎊'),
            ComboPackage(
                name='North Indian Lunch Thali', tagline='Rich, flavourful North Indian spread',
                category='north lunch', price_per_head=480, price_sub='per head',
                dishes=json.dumps([{'name':'Dal Makhani'},{'name':'Paneer Butter Masala'},
                    {'name':'Jeera Rice'},{'name':'Naan / Roti'},{'name':'Raita'},
                    {'name':'Salad'},{'name':'Pickle'},{'name':'Gulab Jamun'}]),
                serves_note='Great for corporate & birthday', theme='theme-north', emoji='🫓'),
            ComboPackage(
                name='Evening Snack Package', tagline='Perfect for meetings & get-togethers',
                category='snack', price_per_head=180, price_sub='per head',
                dishes=json.dumps([{'name':'Masala Chai'},{'name':'Filter Coffee'},
                    {'name':'Samosa'},{'name':'Bread Pakora'},{'name':'Chutney'},
                    {'name':'Biscuits'},{'name':'Fruit Platter'}]),
                serves_note='Ideal for 20-200 guests', theme='theme-snack', emoji='☕'),
            ComboPackage(
                name='Premium Wedding Banquet', tagline='Extravagant multi-course feast',
                category='wedding dinner', price_per_head=950, price_sub='per head',
                dishes=json.dumps([{'name':'Welcome Mocktails'},{'name':'3 Starters'},
                    {'name':'Soup'},{'name':'Paneer Dish'},{'name':'Dal'},
                    {'name':'2 Sabzi'},{'name':'Biryani / Pulao'},{'name':'Naan & Rice'},
                    {'name':'Raita'},{'name':'Papad & Pickle'},
                    {'name':'2 Desserts'},{'name':'Eggless Cake'},{'name':'Buttermilk'}]),
                serves_note='Best for 200+ guests', is_popular=True,
                popular_label='👑 Premium', theme='theme-wedding', emoji='💍'),
            ComboPackage(
                name='Corporate Lunch Box', tagline='Neat and hygienic for office events',
                category='north south lunch', price_per_head=220, price_sub='per box',
                dishes=json.dumps([{'name':'Rice'},{'name':'Dal Tadka'},{'name':'1 Sabzi'},
                    {'name':'Chapati (3)'},{'name':'Salad'},{'name':'Pickle'},{'name':'Sweet'}]),
                serves_note='Minimum 30 boxes', theme='theme-dinner', emoji='🏢'),
        ]
        db.session.add_all(combos)
        print(f'  Seeded {len(combos)} combo packages')

    db.session.commit()


# ============================================================
# APP FACTORY — used by api/index.py (Vercel) and __main__
# ============================================================

def create_app():
    with app.app_context():
        db.create_all()
        seed_data()
    return app


if __name__ == '__main__':
    create_app()
    print('MenuCraft running at http://localhost:5000')
    app.run(debug=True, port=5000)