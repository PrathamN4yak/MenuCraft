# ============================================
# MenuCraft — Flask Backend (app.py)
# ============================================

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json, random, string

app = Flask(__name__, template_folder='..', static_folder='../static')
CORS(app)   # allow fetch() from HTML files during local dev

# ── Config ──
app.config['SECRET_KEY']                     = 'menucraft-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI']        = 'sqlite:///menucraft.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ══════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════

class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    phone      = db.Column(db.String(20))
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders     = db.relationship('Order', backref='user', lazy=True)


class Dish(db.Model):
    """
    Individual dishes — e.g. Parota, Roti, Paneer Butter Masala
    Managed via Admin Panel → Dishes section
    Shown in custom-menu.html Step 3
    """
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False)
    category    = db.Column(db.String(50),  nullable=False)  # starter|main|bread|rice|dessert|drink|special
    price       = db.Column(db.Float,       nullable=False)
    emoji       = db.Column(db.String(10),  default='🍽️')
    description = db.Column(db.String(255), default='')
    image_url   = db.Column(db.Text,        default='')       # base64 or URL
    is_featured = db.Column(db.Boolean,     default=False)
    is_active   = db.Column(db.Boolean,     default=True)     # False = soft deleted
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'category':    self.category,
            'price':       self.price,
            'emoji':       self.emoji,
            'description': self.description,
            'image_url':   self.image_url,
            'is_featured': self.is_featured,
        }


class ComboPackage(db.Model):
    """
    Combo meal packages — e.g. 'Simple South Indian Dinner'
    Managed via Admin Panel → Combo Packages section
    Shown on menu.html
    """
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(150), nullable=False)
    tagline        = db.Column(db.String(255), default='')
    category       = db.Column(db.String(100), default='')
    price_per_head = db.Column(db.Float,       nullable=False)
    price_sub      = db.Column(db.String(30),  default='per head')
    dishes         = db.Column(db.Text,        default='[]')  # JSON array
    serves_note    = db.Column(db.String(100), default='')
    is_popular     = db.Column(db.Boolean,     default=False)
    popular_label  = db.Column(db.String(50),  default='')
    theme          = db.Column(db.String(30),  default='theme-south')
    emoji          = db.Column(db.String(10),  default='🍽️')
    is_active      = db.Column(db.Boolean,     default=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':            self.id,
            'name':          self.name,
            'tagline':       self.tagline,
            'category':      self.category,
            'price':         self.price_per_head,
            'price_sub':     self.price_sub,
            'dishes':        json.loads(self.dishes) if self.dishes else [],
            'serves_note':   self.serves_note,
            'is_popular':    self.is_popular,
            'popular_label': self.popular_label,
            'theme':         self.theme,
            'emoji':         self.emoji,
        }


class Order(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    customer_name  = db.Column(db.String(120))
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    event_type     = db.Column(db.String(60))
    event_date     = db.Column(db.String(20))
    event_time     = db.Column(db.String(10))
    venue          = db.Column(db.String(200))
    guest_count    = db.Column(db.Integer)
    serving_style  = db.Column(db.String(30))
    combo_id       = db.Column(db.Integer, db.ForeignKey('combo_package.id'), nullable=True)
    custom_dishes  = db.Column(db.Text)
    special_notes  = db.Column(db.Text)
    total_price    = db.Column(db.Float)
    status         = db.Column(db.String(30), default='Pending')
    booking_ref    = db.Column(db.String(20), unique=True)
    created_at     = db.Column(db.DateTime,   default=datetime.utcnow)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def to_dict(self):
        return {
            'id':         self.id,
            'ref':        self.booking_ref,
            'customer':   self.customer_name,
            'email':      self.customer_email,
            'phone':      self.customer_phone,
            'event_type': self.event_type,
            'event_date': self.event_date,
            'guests':     self.guest_count,
            'serving':    self.serving_style,
            'venue':      self.venue,
            'total':      self.total_price,
            'status':     self.status,
            'created_at': str(self.created_at),
        }


# ══════════════════════════════════════════════════════
# PUBLIC — DISHES
# ══════════════════════════════════════════════════════

@app.route('/api/dishes')
def get_dishes():
    """ GET /api/dishes  or  /api/dishes?category=main
        Used by custom-menu.html Step 3 """
    category = request.args.get('category')
    q = Dish.query.filter_by(is_active=True)
    if category and category != 'all':
        q = q.filter_by(category=category)
    return jsonify([d.to_dict() for d in q.order_by(Dish.category, Dish.name).all()])


# ══════════════════════════════════════════════════════
# PUBLIC — COMBOS
# ══════════════════════════════════════════════════════

@app.route('/api/combos')
def get_combos():
    """ GET /api/combos  or  /api/combos?category=south
        Used by menu.html """
    category = request.args.get('category')
    q = ComboPackage.query.filter_by(is_active=True)
    if category and category != 'all':
        q = q.filter(ComboPackage.category.contains(category))
    return jsonify([c.to_dict() for c in q.order_by(ComboPackage.created_at).all()])


# ══════════════════════════════════════════════════════
# PUBLIC — BOOKING
# ══════════════════════════════════════════════════════

@app.route('/api/book', methods=['POST'])
def api_book():
    data = request.get_json()
    ref  = 'MC-' + ''.join(random.choices(string.digits, k=6))
    order = Order(
        customer_name  = data['customer']['name'],
        customer_email = data['customer']['email'],
        customer_phone = data['customer']['phone'],
        event_type     = data['event']['type'],
        event_date     = data['event']['date'],
        event_time     = data['event'].get('time', ''),
        venue          = data['event']['venue'],
        guest_count    = data['event']['guests'],
        serving_style  = data['event'].get('serving', ''),
        special_notes  = data['event'].get('notes', ''),
        custom_dishes  = json.dumps(data.get('dishes', {})),
        total_price    = data.get('totalRaw', 0),
        booking_ref    = ref,
        status         = 'Pending'
    )
    db.session.add(order)
    db.session.commit()
    return jsonify({'success': True, 'booking_ref': ref})


# ══════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 400
    user = User(
        name     = data['name'],
        email    = data['email'],
        phone    = data.get('phone', ''),
        password = generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()
    session['user_id']   = user.id
    session['user_name'] = user.name
    return jsonify({'success': True, 'name': user.name})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        session['user_id']   = user.id
        session['user_name'] = user.name
        return jsonify({'success': True, 'name': user.name})
    return jsonify({'success': False, 'message': 'Invalid email or password'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════
# ADMIN — DISHES CRUD
# ══════════════════════════════════════════════════════

@app.route('/api/admin/dishes', methods=['GET'])
def admin_get_dishes():
    dishes = Dish.query.filter_by(is_active=True).order_by(Dish.category, Dish.name).all()
    return jsonify([d.to_dict() for d in dishes])


@app.route('/api/admin/dishes', methods=['POST'])
def admin_create_dish():
    data = request.get_json()
    dish = Dish(
        name        = data['name'],
        category    = data['category'],
        price       = float(data['price']),
        emoji       = data.get('emoji', '🍽️'),
        description = data.get('desc', ''),
        image_url   = data.get('img', ''),
        is_featured = data.get('featured', False),
    )
    db.session.add(dish)
    db.session.commit()
    return jsonify({'success': True, 'id': dish.id})


@app.route('/api/admin/dishes/<int:dish_id>', methods=['PUT'])
def admin_update_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    data = request.get_json()
    dish.name        = data.get('name',     dish.name)
    dish.category    = data.get('category', dish.category)
    dish.price       = float(data.get('price', dish.price))
    dish.emoji       = data.get('emoji',    dish.emoji)
    dish.description = data.get('desc',     dish.description)
    dish.image_url   = data.get('img',      dish.image_url)
    dish.is_featured = data.get('featured', dish.is_featured)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/dishes/<int:dish_id>', methods=['DELETE'])
def admin_delete_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    dish.is_active = False  # soft delete — instantly hides from custom-menu.html
    db.session.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════
# ADMIN — COMBOS CRUD
# ══════════════════════════════════════════════════════

@app.route('/api/admin/combos', methods=['GET'])
def admin_get_combos():
    combos = ComboPackage.query.filter_by(is_active=True).order_by(ComboPackage.created_at).all()
    return jsonify([c.to_dict() for c in combos])


@app.route('/api/admin/combos', methods=['POST'])
def admin_create_combo():
    data  = request.get_json()
    combo = ComboPackage(
        name          = data['name'],
        tagline       = data.get('tagline', ''),
        category      = data['category'],
        price_per_head= float(data['price']),
        price_sub     = data.get('priceSub', 'per head'),
        dishes        = json.dumps(data.get('dishes', [])),
        serves_note   = data.get('serves', ''),
        is_popular    = data.get('isPopular', False),
        popular_label = data.get('popularLabel', ''),
        theme         = data.get('theme', 'theme-south'),
        emoji         = data.get('emoji', '🍽️'),
    )
    db.session.add(combo)
    db.session.commit()
    return jsonify({'success': True, 'id': combo.id})


@app.route('/api/admin/combos/<int:combo_id>', methods=['PUT'])
def admin_update_combo(combo_id):
    combo = ComboPackage.query.get_or_404(combo_id)
    data  = request.get_json()
    combo.name          = data.get('name',         combo.name)
    combo.tagline       = data.get('tagline',       combo.tagline)
    combo.category      = data.get('category',      combo.category)
    combo.price_per_head= float(data.get('price',   combo.price_per_head))
    combo.price_sub     = data.get('priceSub',      combo.price_sub)
    combo.dishes        = json.dumps(data['dishes']) if 'dishes' in data else combo.dishes
    combo.serves_note   = data.get('serves',        combo.serves_note)
    combo.is_popular    = data.get('isPopular',     combo.is_popular)
    combo.popular_label = data.get('popularLabel',  combo.popular_label)
    combo.theme         = data.get('theme',         combo.theme)
    combo.emoji         = data.get('emoji',         combo.emoji)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/combos/<int:combo_id>', methods=['DELETE'])
def admin_delete_combo(combo_id):
    combo = ComboPackage.query.get_or_404(combo_id)
    combo.is_active = False
    db.session.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════
# ADMIN — ORDERS
# ══════════════════════════════════════════════════════

@app.route('/api/admin/orders')
def admin_get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@app.route('/api/admin/orders/<int:order_id>/status', methods=['PUT'])
def admin_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = request.get_json()['status']
    db.session.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════
# ADMIN — CUSTOMERS
# ══════════════════════════════════════════════════════

@app.route('/api/admin/customers')
def admin_get_customers():
    users = User.query.order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        orders      = Order.query.filter_by(customer_email=u.email).all()
        total_spent = sum(o.total_price or 0 for o in orders)
        result.append({
            'id':       u.id,
            'name':     u.name,
            'email':    u.email,
            'phone':    u.phone,
            'bookings': len(orders),
            'spent':    round(total_spent, 2),
            'joined':   u.created_at.strftime('%b %Y'),
        })
    return jsonify(result)


# ══════════════════════════════════════════════════════
# PAGE ROUTES
# ══════════════════════════════════════════════════════

@app.route('/')
def home():        return render_template('index.html')

@app.route('/menu')
def menu():        return render_template('menu.html')

@app.route('/book')
def book_page():   return render_template('book.html')

@app.route('/custom-menu')
def custom_menu(): return render_template('custom-menu.html')

@app.route('/auth')
def auth():        return render_template('auth.html')

@app.route('/about')
def about():       return render_template('about.html')

@app.route('/contact')
def contact():     return render_template('contact.html')

@app.route('/admin')
def admin_page():  return render_template('admin.html')

@app.route('/dashboard')
def dashboard():   return render_template('dashboard.html')


# ══════════════════════════════════════════════════════
# SEED — fills DB on first run
# ══════════════════════════════════════════════════════

def seed_data():
    if Dish.query.count() == 0:
        dishes = [
            Dish(name='Garden Fresh Salad',   category='starter', price=120, emoji='🥗', description='Fresh seasonal vegetables'),
            Dish(name='Crispy Veg Platter',   category='starter', price=180, emoji='🧆', description='Assorted fried starters'),
            Dish(name='Paneer Tikka Skewers', category='starter', price=200, emoji='🥙', description='Grilled paneer with spices',    is_featured=True),
            Dish(name='Sweet Corn Soup',      category='starter', price=90,  emoji='🍲', description='Creamy sweet corn soup'),
            Dish(name='Vadai',                category='starter', price=60,  emoji='🟤', description='Crispy South Indian fritter'),
            Dish(name='Paneer Butter Masala', category='main',    price=200, emoji='🍛', description='Rich paneer in tomato gravy',   is_featured=True),
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
            Dish(name='Veg Dum Biryani',      category='rice',    price=180, emoji='🌾', description='Fragrant basmati with veg',     is_featured=True),
            Dish(name='Lemon Rice',           category='rice',    price=70,  emoji='🍋', description='Tangy South Indian rice'),
            Dish(name='Curd Rice',            category='rice',    price=65,  emoji='🍚', description='Cooling curd rice'),
            Dish(name='Gulab Jamun',          category='dessert', price=80,  emoji='🍮', description='Milk solids in sugar syrup'),
            Dish(name='Eggless Cake Slice',   category='dessert', price=180, emoji='🎂', description='Moist eggless cake',            is_featured=True),
            Dish(name='Kulfi Falooda',        category='dessert', price=110, emoji='🍨', description='Traditional Indian ice cream'),
            Dish(name='Payasam',              category='dessert', price=70,  emoji='🍯', description='South Indian sweet kheer'),
            Dish(name='Sweet Pongal',         category='dessert', price=80,  emoji='🍛', description='Sweet rice and lentil dish'),
            Dish(name='Welcome Mocktail',     category='drink',   price=90,  emoji='🥤', description='Refreshing fruit mocktail'),
            Dish(name='Masala Chai',          category='drink',   price=30,  emoji='☕', description='Spiced Indian tea'),
            Dish(name='Filter Coffee',        category='drink',   price=35,  emoji='☕', description='South Indian drip coffee'),
            Dish(name='Buttermilk',           category='drink',   price=40,  emoji='🥛', description='Chilled seasoned buttermilk'),
            Dish(name='Fresh Lime Soda',      category='drink',   price=50,  emoji='🍋', description='Refreshing lime drink'),
            Dish(name='South Indian Thali',   category='special', price=300, emoji='🍱', description='Complete traditional thali',    is_featured=True),
            Dish(name='Live Pasta Station',   category='special', price=240, emoji='👨‍🍳', description='Freshly tossed pasta live'),
            Dish(name='Dal Baati Churma',     category='special', price=280, emoji='🫕', description='Rajasthani specialty'),
        ]
        db.session.add_all(dishes)
        print(f'  ✅ Seeded {len(dishes)} dishes')

    if ComboPackage.query.count() == 0:
        combos = [
            ComboPackage(name='Simple South Indian Dinner', tagline='Classic homestyle South Indian meal',
                category='south dinner', price_per_head=350, price_sub='per head',
                dishes=json.dumps([{'name':'Steamed Rice'},{'name':'Sambar'},{'name':'Rasam'},
                    {'name':'Kootu'},{'name':'Papad'},{'name':'Pickle'},
                    {'name':'Sweet Pongal'},{'name':'Buttermilk'}]),
                serves_note='Suitable for all event sizes', theme='theme-south', emoji='🍌'),
            ComboPackage(name='Grand South Indian Feast', tagline='Full traditional spread for weddings',
                category='south dinner wedding', price_per_head=650, price_sub='per head',
                dishes=json.dumps([{'name':'Welcome Drink'},{'name':'Vadai'},{'name':'Steamed Rice'},
                    {'name':'Sambar'},{'name':'Rasam'},{'name':'Avial'},{'name':'Kootu'},
                    {'name':'Poriyal'},{'name':'Appalam'},{'name':'Pickle'},
                    {'name':'Payasam'},{'name':'Buttermilk'}]),
                serves_note='Best for 100+ guests', is_popular=True,
                popular_label='⭐ Most Popular', theme='theme-wedding', emoji='🎊'),
            ComboPackage(name='North Indian Lunch Thali', tagline='Rich, flavourful North Indian spread',
                category='north lunch', price_per_head=480, price_sub='per head',
                dishes=json.dumps([{'name':'Dal Makhani'},{'name':'Paneer Butter Masala'},
                    {'name':'Jeera Rice'},{'name':'Naan / Roti'},{'name':'Raita'},
                    {'name':'Salad'},{'name':'Pickle'},{'name':'Gulab Jamun'}]),
                serves_note='Great for corporate & birthday', theme='theme-north', emoji='🫓'),
            ComboPackage(name='Evening Snack Package', tagline='Perfect for meetings & get-togethers',
                category='snack', price_per_head=180, price_sub='per head',
                dishes=json.dumps([{'name':'Masala Chai'},{'name':'Filter Coffee'},
                    {'name':'Samosa'},{'name':'Bread Pakora'},{'name':'Chutney'},
                    {'name':'Biscuits'},{'name':'Fruit Platter'}]),
                serves_note='Ideal for 20-200 guests', theme='theme-snack', emoji='☕'),
            ComboPackage(name='Premium Wedding Banquet', tagline='Extravagant multi-course feast',
                category='wedding dinner', price_per_head=950, price_sub='per head',
                dishes=json.dumps([{'name':'Welcome Mocktails'},{'name':'3 Starters'},
                    {'name':'Soup'},{'name':'Paneer Dish'},{'name':'Dal'},
                    {'name':'2 Sabzi'},{'name':'Biryani / Pulao'},{'name':'Naan & Rice'},
                    {'name':'Raita'},{'name':'Papad & Pickle'},
                    {'name':'2 Desserts'},{'name':'Eggless Cake'},{'name':'Buttermilk'}]),
                serves_note='Best for 200+ guests', is_popular=True,
                popular_label='👑 Premium', theme='theme-wedding', emoji='💍'),
            ComboPackage(name='Corporate Lunch Box', tagline='Neat and hygienic for office events',
                category='north south lunch', price_per_head=220, price_sub='per box',
                dishes=json.dumps([{'name':'Rice'},{'name':'Dal Tadka'},{'name':'1 Sabzi'},
                    {'name':'Chapati (3)'},{'name':'Salad'},{'name':'Pickle'},{'name':'Sweet'}]),
                serves_note='Minimum 30 boxes', theme='theme-dinner', emoji='🏢'),
        ]
        db.session.add_all(combos)
        print(f'  ✅ Seeded {len(combos)} combo packages')

    db.session.commit()


# ══════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
        print('✅ MenuCraft is ready at http://localhost:5000')
    app.run(debug=True, port=5000)