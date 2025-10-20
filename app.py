from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os

# --------------------------------------------------------
# CONFIGURAÇÃO DO APP
# --------------------------------------------------------
app = Flask(__name__)
# Chave secreta unificada para maior segurança
app.secret_key = 'chave-segura-ltip' 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ltip.db"
app.config["UPLOAD_FOLDER"] = "uploads"

# Configuração para login
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# --------------------------------------------------------
# MODELOS (MODELS)
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
# LOGIN MANAGER
# --------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    # Forma moderna de buscar o usuário no Flask-SQLAlchemy 3.x
    return db.session.get(User, int(user_id))

# --------------------------------------------------------
# ROTAS (ROUTES)
# --------------------------------------------------------

# Rota para servir os arquivos de upload (imagens)
# ESSENCIAL: Permite que o navegador acesse arquivos dentro da pasta 'uploads'.
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/")
def index():
    # Esta é a única e correta rota 'index'
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
            # Adicionada lógica de redirecionamento mais inteligente após o login
            if user.role in ["admin", "bolsista"]:
                return redirect(url_for("gerenciamento"))
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
    # Verifica permissão para acesso à página
    if current_user.role not in ["admin", "bolsista"]:
        flash("Acesso negado. Apenas administradores e bolsistas.", "warning")
        return redirect(url_for("index"))
        
    equipamentos = Equipment.query.all()
    info = LabInfo.query.first()
    return render_template("gerenciamento.html", equipamentos=equipamentos, info=info)

@app.route("/adicionar_equipamento", methods=["POST"])
@login_required
def adicionar_equipamento():
    if current_user.role not in ["admin", "bolsista"]:
        flash("Permissão negada para adicionar equipamentos.", "warning")
        return redirect(url_for("gerenciamento"))
        
    nome = request.form["name"]
    func = request.form["functionality"]
    marca = request.form["brand"]
    modelo = request.form["model"]
    
    # Tratamento de erro para garantir que quantity seja um inteiro
    try:
        quantidade = int(request.form["quantity"])
    except ValueError:
        quantidade = 0
        
    tombo = request.form["tombo"]
    
    imagem_nome = None
    if "image" in request.files and request.files["image"].filename != "":
        imagem = request.files["image"]
        
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], imagem.filename)
        imagem.save(img_path)
        imagem_nome = imagem.filename

    novo = Equipment(
        name=nome, functionality=func, brand=marca,
        model=modelo, quantity=quantidade, tombo=tombo, image=imagem_nome
    )
    db.session.add(novo)
    db.session.commit()
    flash("Equipamento adicionado com sucesso!", "success")
    return redirect(url_for("gerenciamento"))


# --------------------------------------------------------
# CRIAÇÃO INICIAL DO BANCO E POPULAÇÃO
# --------------------------------------------------------
with app.app_context():
    # Garante que a pasta de uploads exista
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    # Cria as tabelas
    db.create_all()
    
    # Popula com dados iniciais se o banco estiver vazio
    if not LabInfo.query.first():
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
        
        # Equipamento de Exemplo para não iniciar vazio
        equipamento_exemplo = Equipment(
            name="Exemplo de Equipamento",
            functionality="Medição e análise",
            brand="ExemploCorp",
            model="M100",
            quantity=1,
            tombo="LTIP-EX01",
            image=None
        )
        db.session.add(equipamento_exemplo)
        
        db.session.commit()

# O bloco principal (para rodar localmente com 'python app.py')
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
