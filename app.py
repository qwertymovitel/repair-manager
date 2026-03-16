from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "super-secret-key"

# FIX: Explicitly handle the database path for Docker
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')

if not os.path.exists(instance_path):
    os.makedirs(instance_path)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'repairs.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='NEW')
    quote_date = db.Column(db.DateTime, nullable=True)
    decision_date = db.Column(db.DateTime, nullable=True)

# Helper for timestamps
@app.template_filter('time_ago')
def time_ago(dt):
    if not dt: return ""
    diff = datetime.now() - dt
    if diff.days > 0:
        return f"({diff.days} dias atrás)"
    minutes = diff.seconds // 60
    if minutes < 1: return "(agora mesmo)"
    if minutes < 60:
        return f"({minutes} min atrás)"
    return f"({diff.seconds // 3600} horas atrás)"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect(url_for('index'))
        flash('Login Inválido')
    return '''
        <form method="post" style="text-align:center; margin-top:100px; font-family:sans-serif;">
            <h2>Gestão de Reparos - Login</h2>
            <input type="text" name="username" placeholder="Usuário" required><br><br>
            <input type="password" name="password" placeholder="Senha" required><br><br>
            <button type="submit">Entrar</button>
        </form>
    '''

@app.route('/')
def index():
    if not session.get('logged_in'): return redirect(url_for('login'))
    repairs = Repair.query.all()
    return render_template('index.html', repairs=repairs)

@app.route('/add', methods=['POST'])
def add():
    desc = request.form.get('description')
    if desc:
        new_repair = Repair(description=desc.upper())
        db.session.add(new_repair)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/update/<int:id>/<action>')
def update(id, action):
    repair = Repair.query.get(id)
    if action == 'quote':
        repair.status = 'PENDING'
        repair.quote_date = datetime.now()
    elif action == 'approve':
        repair.status = 'APPROVED'
        repair.decision_date = datetime.now()
    elif action == 'return':
        repair.status = 'RETURNED'
        repair.decision_date = datetime.now()
    elif action == 'delete':
        db.session.delete(repair)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
