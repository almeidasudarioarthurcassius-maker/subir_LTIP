from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os

app = Flask(__name__)
app.secret_key = "ltip_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ltip.db"
app.config["UPLOAD_FOLDER"] = "uploads"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# --------------------------------------------------------
# MODELOS
# --------------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    functionality = db.Column(db.String(120))
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    quantity = db.Column(db.Integer)
    tombo = db.Column(db.String(50))
    image = db.Column(db.String(120))

class LabInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coordenador_name = db.Column(db.String(120))
    coordenador_email = db.Column(db.String(120))
    bolsista_name = db.Column(db.String(120))
    bolsista_email = db.Column(db.String(120))

# --------------------------------------------------------
# LOGIN
# --------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --------------------------------------------------------
# ROTAS
# --------------------------------------------------------
@app.route("/")
def index():
    info = LabInfo.query.first()
    equipamentos = Equipment.query.all()
    return render_template("index.html", info=info, equipamentos=equipamentos)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and user.password == request.form["password"]:
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))
        else:
            flash("Usuário ou senha incorretos.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("index"))

@app.route("/inventario")
def inventario():
    equipamentos = Equipment.query.all()
    return render_template("inventario.html", equipamentos=equipamentos)

@app.route("/gerenciamento")
@login_required
def gerenciamento():
    equipamentos = Equipment.query.all()
    return render_template("gerenciamento.html", equipamentos=equipamentos)

@app.route("/adicionar_equipamento", methods=["POST"])
@login_required
def adicionar_equipamento():
    nome = request.form["name"]
    func = request.form["functionality"]
    marca = request.form["brand"]
    modelo = request.form["model"]
    quantidade = request.form["quantity"]
    tombo = request.form["tombo"]
    imagem = request.files["image"]

    if imagem:
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], imagem.filename)
        imagem.save(img_path)
        imagem_nome = imagem.filename
    else:
        imagem_nome = None

    novo = Equipment(
        name=nome, functionality=func, brand=marca,
        model=modelo, quantity=quantidade, tombo=tombo, image=imagem_nome
    )
    db.session.add(novo)
    db.session.commit()
    flash("Equipamento adicionado com sucesso!", "success")
    return redirect(url_for("gerenciamento"))

# --------------------------------------------------------
# CRIAÇÃO INICIAL
# --------------------------------------------------------
@app.before_first_request
def create_tables():
    db.create_all()
    if not User.query.first():
        admin = User(username="admin", password="admin", role="admin")
        bolsista = User(username="bolsista", password="1234", role="bolsista")
        visitante = User(username="visitante", password="0000", role="visitante")
        db.session.add_all([admin, bolsista, visitante])
        info = LabInfo(
            coordenador_name="Coordenador LTIP",
            coordenador_email="coordenador@uea.edu.br",
            bolsista_name="Bolsista LTIP",
            bolsista_email="bolsista@uea.edu.br",
        )
        db.session.add(info)
        db.session.commit()

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
