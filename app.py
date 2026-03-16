import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = "super-secret-key"

# Database path
instance_path = os.path.join(base_dir, 'instance')
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
    # NEW: Tracking for sorting and cleanup
    last_updated = db.Column(db.DateTime, default=datetime.now)
    delay_until = db.Column(db.DateTime, nullable=True) # Used if removal is denied

@app.template_filter('time_ago')
def time_ago(dt):
    if not dt: return ""
    diff = datetime.now() - dt
    if diff.days > 0: return f"({diff.days} dias atrás)"
    minutes = diff.seconds // 60
    if minutes < 1: return "(agora mesmo)"
    if minutes < 60: return f"({minutes} min atrás)"
    return f"({diff.seconds // 3600} horas atrás)"

# Logic to check if an item needs removal notification (90 days)
@app.context_processor
def utility_processor():
    def needs_cleanup(repair):
        if repair.status not in ['APPROVED', 'RETURNED']: return False
        if not repair.decision_date: return False
        
        # Check if 90 days passed since decision
        over_90_days = datetime.now() > (repair.decision_date + timedelta(days=90))
        # Check if the "Delay" period (30 days) is active
        not_delayed = repair.delay_until is None or datetime.now() > repair.delay_until
        
        return over_90_days and not_delayed
    return dict(needs_cleanup=needs_cleanup)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect(url_for('index'))
        flash('Login Inválido')
    return '''
        <form method="post" style="text-align:center; margin-top:100px; font-family:sans-serif;">
            <h2>Gestão de Reparos - Login Admin</h2>
            <input type="text" name="username" placeholder="Usuário" required><br><br>
            <input type="password" name="password" placeholder="Senha" required><br><br>
            <button type="submit">Entrar</button><br><br>
            <a href="/">Voltar para Visualização</a>
        </form>
    '''

@app.route('/')
def index():
    # Sort by last_updated descending (Newest/Recently updated on top)
    repairs = Repair.query.order_by(Repair.last_updated.desc()).all()
    return render_template('index.html', repairs=repairs)

@app.route('/add', methods=['POST'])
def add():
    if not session.get('logged_in'): return redirect(url_for('login'))
    desc = request.form.get('description')
    if desc:
        new_repair = Repair(description=desc.upper(), last_updated=datetime.now())
        db.session.add(new_repair)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/update/<int:id>/<action>')
def update(id, action):
    if not session.get('logged_in'): return redirect(url_for('login'))
    repair = Repair.query.get(id)
    repair.last_updated = datetime.now() # Move to top on any action
    
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
    elif action == 'deny_removal':
        # Restart count: set a delay for 30 days from now
        repair.delay_until = datetime.now() + timedelta(days=30)
        
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
