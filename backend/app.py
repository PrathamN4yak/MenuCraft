# ============================================
# MenuCraft — Flask Backend (app.py)
# ============================================

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# ── Config ──
app.config['SECRET_KEY'] = 'menucraft-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///menucraft.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ══════════════════════════════════════
# DATABASE MODELS
# ══════════════════════════════════════

class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    phone      = db.Column(db.String(20))
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders     = db.relationship('Order', backref='user', lazy=True)

class ComboPackage(db.Model):
    """
    Combo meal package — e.g. 'Simple South Indian Dinner'
    Managed via the Admin Panel (add / edit / delete)
    Displayed on menu.html
    """
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(150), nullable=False)
    tagline       = db.Column(db.String(255))
    category      = db.Column(db.String(100))   # e.g. 'south dinner', 'north lunch', 'wedding'
    price_per_head= db.Column(db.Float, nullable=False)
    price_sub     = db.Column(db.String(30), default='per head')  # 'per head' or 'per box'
    dishes        = db.Column(db.Text)           # JSON array: ["Rice","Sambar","Rasam",...]
    serves_note   = db.Column(db.String(100))    # e.g. 'Best for 100+ guests'
    is_popular    = db.Column(db.Boolean, default=False)
    popular_label = db.Column(db.String(50))     # e.g. '⭐ Most Popular', '👑 Premium'
    theme         = db.Column(db.String(30), default='theme-south')  # CSS theme class
    emoji         = db.Column(db.String(10), default='🍽️')
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    # Customer info (for guest bookings without login)
    customer_name = db.Column(db.String(120))
    customer_email= db.Column(db.String(120))
    customer_phone= db.Column(db.String(20))
    # Event info
    event_type    = db.Column(db.String(60))
    event_date    = db.Column(db.String(20))
    event_time    = db.Column(db.String(10))
    venue         = db.Column(db.String(200))
    guest_count   = db.Column(db.Integer)
    serving_style = db.Column(db.String(30))    # 'Buffet' or 'Banana Leaf'
    # Combo or custom
    combo_id      = db.Column(db.Integer, db.ForeignKey('combo_package.id'), nullable=True)
    custom_dishes = db.Column(db.Text)          # JSON for custom menu selections
    special_notes = db.Column(db.Text)
    total_price   = db.Column(db.Float)
    status        = db.Column(db.String(30), default='Pending')
    booking_ref   = db.Column(db.String(20), unique=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    # Optional user link
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    phone      = db.Column(db.String(20))
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders     = db.relationship('Order', backref='user', lazy=True)

# ══════════════════════════════════════
# ROUTES
# ══════════════════════════════════════

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/menu')
def menu():
    combos = ComboPackage.query.filter_by(is_active=True).all()
    return render_template('menu.html', combos=combos)

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        data = request.get_json()
        import random, string
        ref = 'MC-' + ''.join(random.choices(string.digits, k=6))
        order = Order(
            customer_name  = data['customer']['name'],
            customer_email = data['customer']['email'],
            customer_phone = data['customer']['phone'],
            event_type     = data['event']['type'],
            event_date     = data['event']['date'],
            event_time     = data['event']['time'],
            venue          = data['event']['venue'],
            guest_count    = data['event']['guests'],
            serving_style  = data['event']['serving'],
            special_notes  = data['event'].get('notes',''),
            custom_dishes  = str(data.get('dishes', {})),
            total_price    = data.get('totalRaw', 0),
            booking_ref    = ref,
            status         = 'Pending'
        )
        db.session.add(order)
        db.session.commit()
        return jsonify({'success': True, 'booking_ref': ref})
    return render_template('book.html')

# ── Combos API (used by menu.html & admin panel) ──
@app.route('/api/combos', methods=['GET'])
def get_combos():
    import json
    category = request.args.get('category')
    query = ComboPackage.query.filter_by(is_active=True)
    if category and category != 'all':
        query = query.filter(ComboPackage.category.contains(category))
    combos = query.all()
    return jsonify([{
        'id':           c.id,
        'name':         c.name,
        'tagline':      c.tagline,
        'category':     c.category,
        'price':        c.price_per_head,
        'price_sub':    c.price_sub,
        'dishes':       json.loads(c.dishes) if c.dishes else [],
        'serves_note':  c.serves_note,
        'is_popular':   c.is_popular,
        'popular_label':c.popular_label,
        'theme':        c.theme,
        'emoji':        c.emoji,
    } for c in combos])

# ── Admin: Add new combo ──
@app.route('/api/admin/combos', methods=['POST'])
def create_combo():
    import json
    data = request.get_json()
    combo = ComboPackage(
        name           = data['name'],
        tagline        = data.get('tagline',''),
        category       = data['category'],
        price_per_head = float(data['price']),
        price_sub      = data.get('price_sub', 'per head'),
        dishes         = json.dumps(data['dishes']),   # ["Rice","Sambar",...]
        serves_note    = data.get('serves_note',''),
        is_popular     = data.get('is_popular', False),
        popular_label  = data.get('popular_label',''),
        theme          = data.get('theme','theme-south'),
        emoji          = data.get('emoji','🍽️'),
        is_active      = True
    )
    db.session.add(combo)
    db.session.commit()
    return jsonify({'success': True, 'id': combo.id})

# ── Admin: Edit combo ──
@app.route('/api/admin/combos/<int:combo_id>', methods=['PUT'])
def update_combo(combo_id):
    import json
    combo = ComboPackage.query.get_or_404(combo_id)
    data  = request.get_json()
    combo.name           = data.get('name', combo.name)
    combo.tagline        = data.get('tagline', combo.tagline)
    combo.category       = data.get('category', combo.category)
    combo.price_per_head = float(data.get('price', combo.price_per_head))
    combo.price_sub      = data.get('price_sub', combo.price_sub)
    combo.dishes         = json.dumps(data['dishes']) if 'dishes' in data else combo.dishes
    combo.serves_note    = data.get('serves_note', combo.serves_note)
    combo.is_popular     = data.get('is_popular', combo.is_popular)
    combo.popular_label  = data.get('popular_label', combo.popular_label)
    combo.theme          = data.get('theme', combo.theme)
    combo.emoji          = data.get('emoji', combo.emoji)
    db.session.commit()
    return jsonify({'success': True})

# ── Admin: Delete combo ──
@app.route('/api/admin/combos/<int:combo_id>', methods=['DELETE'])
def delete_combo(combo_id):
    combo = ComboPackage.query.get_or_404(combo_id)
    combo.is_active = False   # soft delete
    db.session.commit()
    return jsonify({'success': True})

# ── Admin: All orders ──
@app.route('/api/admin/orders', methods=['GET'])
def get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([{
        'id':           o.id,
        'ref':          o.booking_ref,
        'customer':     o.customer_name,
        'email':        o.customer_email,
        'phone':        o.customer_phone,
        'event_type':   o.event_type,
        'event_date':   o.event_date,
        'guests':       o.guest_count,
        'serving':      o.serving_style,
        'venue':        o.venue,
        'total':        o.total_price,
        'status':       o.status,
        'created_at':   str(o.created_at),
    } for o in orders])

# ── Admin: Update order status ──
@app.route('/api/admin/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    data  = request.get_json()
    order.status = data['status']   # Pending → Confirmed → In Preparation → Delivered
    db.session.commit()
    return jsonify({'success': True})
    return render_template('book.html')

@app.route('/api/menu-items')
def api_menu_items():
    category = request.args.get('category', None)
    if category:
        items = MenuItem.query.filter_by(category=category).all()
    else:
        items = MenuItem.query.all()
    return jsonify([{
        'id': i.id, 'name': i.name, 'category': i.category,
        'description': i.description, 'price': i.price,
        'is_veg': i.is_veg, 'image_url': i.image_url
    } for i in items])

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 400
    hashed_pw = generate_password_hash(data['password'])
    user = User(name=data['name'], email=data['email'], phone=data.get('phone',''), password=hashed_pw)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Registration successful!'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        session['user_id'] = user.id
        session['user_name'] = user.name
        return jsonify({'success': True, 'name': user.name})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ══════════════════════════════════════
# INIT DB & RUN
# ══════════════════════════════════════

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ MenuCraft database initialized!")
    app.run(debug=True, port=5000)