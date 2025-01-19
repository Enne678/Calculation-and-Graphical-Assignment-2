from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pharmacy.db'
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')
    favorites = db.relationship('Favorites', backref='user', lazy=True)

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    generic_name = db.Column(db.String(100), nullable=False)
    prescription_only = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Favorites(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    medication_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validate_username(username):
    return re.match(r'^[a-zA-Z0-9_]+$', username) is not None

def validate_password(password):
    return re.match(r'^[a-zA-Z0-9_!@#$%^&*()]+$', password) is not None

@app.route('/')
def index():
    page = int(request.args.get('page', 0))
    query = Medicine.query
    if current_user.is_authenticated and current_user.role != 'admin':
        favorite_ids = [fav.medication_id for fav in current_user.favorites]
        query = query.order_by(Medicine.id.in_(favorite_ids).desc(), Medicine.name.asc())
    else:
        query = query.order_by(Medicine.name.asc())

    per_page = 10
    total = query.count()
    meds = query.offset(page * per_page).limit(per_page).all()
    has_more = (page + 1) * per_page < total

    fav_list = []
    if current_user.is_authenticated and current_user.role != 'admin':
        fav_list = [f.medication_id for f in current_user.favorites]

    return render_template('index.html', medications=meds, has_more=has_more, favorite_medications=fav_list)

@app.route('/search')
def search():
    search_term = request.args.get('term', '').strip()
    prescription_filter = request.args.get('prescription', '')
    max_price = request.args.get('max_price', '')
    page = int(request.args.get('page', 0))
    query = Medicine.query

    if search_term:
        query = query.filter(db.or_(
            Medicine.name.ilike(f'%{search_term}%'),
            Medicine.generic_name.ilike(f'%{search_term}%')
        ))
    if prescription_filter in ('true', 'false'):
        query = query.filter(Medicine.prescription_only == (prescription_filter == 'true'))
    if max_price:
        if float(max_price) < 0:
            flash('Цена не может быть отрицательной.', 'danger')
            return redirect(url_for('index'))
        query = query.filter(Medicine.price <= float(max_price))

    if current_user.is_authenticated and current_user.role != 'admin':
        favorite_ids = [fav.medication_id for fav in current_user.favorites]
        query = query.order_by(Medicine.id.in_(favorite_ids).desc(), Medicine.name.asc())
    else:
        query = query.order_by(Medicine.name.asc())

    per_page = 10
    total = query.count()
    meds = query.offset(page * per_page).limit(per_page).all()
    has_more = (page + 1) * per_page < total

    fav_list = []
    if current_user.is_authenticated and current_user.role != 'admin':
        fav_list = [f.medication_id for f in current_user.favorites]

    return render_template(
        'index.html',
        medications=meds,
        has_more=has_more,
        search_term=search_term,
        prescription_filter=prescription_filter,
        max_price=max_price,
        favorite_medications=fav_list
    )

@app.route('/load_more')
def load_more():
    page = int(request.args.get('page', 0))
    search_term = request.args.get('term', '').strip()
    prescription_filter = request.args.get('prescription', '')
    max_price = request.args.get('max_price', '')
    query = Medicine.query

    if search_term:
        query = query.filter(db.or_(
            Medicine.name.ilike(f'%{search_term}%'),
            Medicine.generic_name.ilike(f'%{search_term}%')
        ))
    if prescription_filter in ('true', 'false'):
        query = query.filter(Medicine.prescription_only == (prescription_filter == 'true'))
    if max_price:
        if float(max_price) < 0:
            return jsonify({'medications': [], 'has_more': False})
        query = query.filter(Medicine.price <= float(max_price))

    if current_user.is_authenticated and current_user.role != 'admin':
        fav_ids = [fav.medication_id for fav in current_user.favorites]
        query = query.order_by(Medicine.id.in_(fav_ids).desc(), Medicine.name.asc())
    else:
        query = query.order_by(Medicine.name.asc())

    per_page = 10
    total = query.count()
    meds = query.offset(page * per_page).limit(per_page).all()
    has_more = (page + 1) * per_page < total

    data = []
    for m in meds:
        data.append({
            'id': m.id,
            'name': m.name,
            'generic_name': m.generic_name,
            'prescription_only': m.prescription_only,
            'price': m.price,
            'quantity': m.quantity
        })

    return jsonify({'medications': data, 'has_more': has_more})

@app.route('/register', methods=['GET', 'POST'])
def register():
    fav_list = []
    if current_user.is_authenticated and current_user.role != 'admin':
        fav_list = [f.medication_id for f in current_user.favorites]

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not validate_username(username):
            flash('Логин может содержать только латинские буквы, цифры и символ подчеркивания.', 'danger')
            return redirect(url_for('register'))

        if not validate_password(password):
            flash('Пароль может содержать только латинские буквы, цифры и специальные символы.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Пароли не совпадают. Пожалуйста, повторите ввод.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', favorite_medications=fav_list)

@app.route('/login', methods=['GET', 'POST'])
def login():
    fav_list = []
    if current_user.is_authenticated and current_user.role != 'admin':
        fav_list = [f.medication_id for f in current_user.favorites]

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))

        flash('Неверный логин или пароль.', 'danger')

    return render_template('login.html', favorite_medications=fav_list)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    if current_user.role == 'admin':
        flash('Администратор не может удалить свой аккаунт.', 'danger')
        return redirect(url_for('index'))

    user = User.query.get_or_404(current_user.id)
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash('Ваш аккаунт успешно удален.', 'success')
    return redirect(url_for('index'))

@app.route('/add_medication', methods=['POST'])
@login_required
def add_medication():
    if current_user.role != 'admin':
        flash('У вас нет прав для выполнения этого действия.', 'danger')
        return redirect(url_for('index'))

    name = request.form.get('name')
    generic_name = request.form.get('generic_name')
    prescription_only = (request.form.get('prescription_only') == 'on')
    price = float(request.form.get('price', 0))
    quantity = int(request.form.get('quantity', 0))

    if price <= 0 or quantity < 0:
        flash('Цена и количество должны быть положительными.', 'danger')
        return redirect(url_for('index'))

    new_medicine = Medicine(
        name=name,
        generic_name=generic_name,
        prescription_only=prescription_only,
        price=price,
        quantity=quantity
    )
    db.session.add(new_medicine)
    db.session.commit()

    flash('Лекарство успешно добавлено!', 'success')
    return redirect(url_for('index'))

@app.route('/delete_medication/<int:id>', methods=['POST'])
@login_required
def delete_medication(id):
    if current_user.role != 'admin':
        flash('У вас нет прав для выполнения этого действия.', 'danger')
        return redirect(url_for('index'))

    med = Medicine.query.get_or_404(id)
    db.session.delete(med)
    db.session.commit()

    flash('Лекарство успешно удалено!', 'success')
    return redirect(url_for('index'))

@app.route('/edit_medication/<int:id>', methods=['POST'])
@login_required
def edit_medication(id):
    if current_user.role != 'admin':
        flash('У вас нет прав для выполнения этого действия.', 'danger')
        return redirect(url_for('index'))

    med = Medicine.query.get_or_404(id)
    med.name = request.form.get('name')
    med.generic_name = request.form.get('generic_name')
    med.prescription_only = (request.form.get('prescription_only') == 'on')
    med.price = float(request.form.get('price', 0))
    med.quantity = int(request.form.get('quantity', 0))

    db.session.commit()

    flash('Лекарство успешно обновлено!', 'success')
    return redirect(url_for('index'))

@app.route('/toggle_favorite/<int:medication_id>', methods=['POST'])
@login_required
def toggle_favorite(medication_id):
    if current_user.role == 'admin':
        return jsonify({'success': False})
    fav = Favorites.query.filter_by(user_id=current_user.id, medication_id=medication_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify({'success': True, 'is_favorite': False})
    else:
        new_fav = Favorites(user_id=current_user.id, medication_id=medication_id)
        db.session.add(new_fav)
        db.session.commit()
        return jsonify({'success': True, 'is_favorite': True})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)