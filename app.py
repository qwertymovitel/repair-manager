import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = "super-secret-key"

instance_path = os.path.join(base_dir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'repairs.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class Technician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='NEW')
    technician_id = db.Column(db.Integer, db.ForeignKey('technician.id'), nullable=True)
    technician = db.relationship('Technician', backref='repairs')
    quote_date = db.Column(db.DateTime, nullable=True)
    decision_date = db.Column(db.DateTime, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.now)
    delay_until = db.Column(db.DateTime, nullable=True)

# --- FILTERS ---
@app.template_filter('time_ago')
def time_ago(dt):
    if not dt: return ""
    diff = datetime.now() - dt
    if diff.days > 0: return f"({diff.days} dias atrás)"
    minutes = diff.seconds // 60
    if minutes < 1: return "(agora mesmo)"
    if minutes < 60: return f"({minutes} min atrás)"
    return f"({diff.seconds // 3600} horas atrás)"

@app.context_processor
def utility_processor():
    def needs_cleanup(repair):
        if repair.status not in ['APPROVED', 'RETURNED'] or not repair.decision_date: return False
        over_90 = datetime.now() > (repair.decision_date + timedelta(days=90))
        not_delayed = repair.delay_until is None or datetime.now() > repair.delay_until
        return over_90 and not_delayed
    return dict(needs_cleanup=needs_cleanup)

# --- ROUTES ---
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
    repairs = Repair.query.order_by(Repair.last_updated.desc()).all()
    techs = Technician.query.order_by(Technician.name).all()
    return render_template('index.html', repairs=repairs, techs=techs)

@app.route('/add', methods=['POST'])
def add():
    if not session.get('logged_in'): return redirect(url_for('login'))
    desc = request.form.get('description')
    tech_id = request.form.get('tech_id')
    if desc:
        new_repair = Repair(
            description=desc.upper(), 
            technician_id=tech_id if tech_id != "" else None,
            last_updated=datetime.now()
        )
        db.session.add(new_repair)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/reassign/<int:id>', methods=['POST'])
def reassign(id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    repair = Repair.query.get(id)
    tech_id = request.form.get('tech_id')
    repair.technician_id = tech_id if tech_id != "" else None
    repair.last_updated = datetime.now() # Item moves to top
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/tech/manage', methods=['POST'])
def add_tech():
    if not session.get('logged_in'): return redirect(url_for('login'))
    name = request.form.get('tech_name')
    if name and not Technician.query.filter_by(name=name).first():
        db.session.add(Technician(name=name))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/tech/delete/<int:id>')
def delete_tech(id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    tech = Technician.query.get(id)
    if tech:
        db.session.delete(tech)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/update/<int:id>/<action>')
def update(id, action):
    if not session.get('logged_in'): return redirect(url_for('login'))
    repair = Repair.query.get(id)
    repair.last_updated = datetime.now()
    if action == 'quote':
        repair.status = 'PENDING'; repair.quote_date = datetime.now()
    elif action == 'approve':
        repair.status = 'APPROVED'; repair.decision_date = datetime.now()
    elif action == 'return':
        repair.status = 'RETURNED'; repair.decision_date = datetime.now()
    elif action == 'delete':
        db.session.delete(repair)
    elif action == 'deny_removal':
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
        # Seed initial techs if empty
        if Technician.query.count() == 0:
            for n in ["Homo", "Willard", "Madeline", "Reginaldo", "Dinis"]:
                db.session.add(Technician(name=n))
            db.session.commit()
    app.run(host='0.0.0.0', port=5000)
