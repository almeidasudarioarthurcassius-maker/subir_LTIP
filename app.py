# Importações necessárias
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import csv
from datetime import datetime # ESTA IMPORTAÇÃO É NECESSÁRIA

# --- Configurações Iniciais ---
app = Flask(__name__)
# A secret_key é obrigatória para sessões, flash messages e segurança
app.secret_key = "ltip_secret_key" 
# Configura o banco de dados SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ltip.db"
# Pasta para uploads de imagens (deve existir na raiz do projeto)
app.config["UPLOAD_FOLDER"] = "uploads"

# Inicialização das extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Define o nome completo do laboratório como uma constante
LAB_NAME_FULL = "LABORATÓRIO DE TECNOLOGIA DA INFORMAÇÃO DO PROFÁGUA - LTIP"

# --- NOVO: CONTEXT PROCESSOR PARA DATETIME ---
# Isso garante que a função datetime esteja disponível em TODOS os templates Jinja
@app.context_processor
def inject_now():
    return {'datetime': datetime}


# --- MODELOS ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, bolsista, visitante

# Novo modelo Machine para controle detalhado (Planilha1.csv)
class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), unique=True, nullable=False) # LTIP-COMP-001
    type = db.Column(db.String(50)) # desktop, laptop
    brand_model = db.Column(db.String(120))
    serial_number = db.Column(db.String(120))
    format_status = db.Column(db.String(50)) # Formatado, Em andamento, Não formatado
    format_date = db.Column(db.Date)
    software = db.Column(db.Text)
    license = db.Column(db.String(120))
    observations = db.Column(db.Text)
    tombo = db.Column(db.String(50), unique=True)
    image_url = db.Column(db.String(255)) # Novo campo para imagem

# Modelo Equipment para itens gerais (Sheet1.csv)
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False) # Tipo de Equipamento
    functionality = db.Column(db.String(120)) # Finalidade
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    quantity = db.Column(db.Integer)
    tombo = db.Column(db.String(50), unique=True)
    image_url = db.Column(db.String(255)) # Novo campo para imagem

# Modelo LabInfo para informações de contato
class LabInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coordenador_name = db.Column(db.String(120))
    coordenador_email = db.Column(db.String(120))
    bolsista_name = db.Column(db.String(120))
    bolsista_email = db.Column(db.String(120))


# --- LOGIN MANAGER ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- ROTAS ---

# Rota para servir arquivos de upload (essencial para exibir imagens)
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Rota Inicial
@app.route("/")
def index():
    # Busca as informações de contato do laboratório para exibir
    info = LabInfo.query.first()
    
    # Busca equipamentos para exibição na página inicial (opcional, mas bom ter)
    equipamentos = Equipment.query.order_by(Equipment.name).limit(5).all()
    maquinas = Machine.query.order_by(Machine.asset_id).limit(5).all()
    
    return render_template(
        "index.html",
        lab_name=LAB_NAME_FULL,
        info=info,
        equipamentos=equipamentos,
        maquinas=maquinas
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("gerenciamento"))
        
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        
        # NOTE: Em um sistema real, a senha deve ser hasheada (ex: usando werkzeug.security.check_password_hash)
        if user and user.password == password:
            login_user(user)
            flash(f"Login de {user.role.capitalize()} realizado com sucesso!", "success")
            return redirect(url_for("gerenciamento"))
        else:
            flash("Usuário ou senha incorretos.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("index"))

@app.route("/inventario")
def inventario():
    # Carrega todos os dados para o inventário público
    maquinas = Machine.query.order_by(Machine.asset_id).all()
    equipamentos_gerais = Equipment.query.order_by(Equipment.name).all()
    
    return render_template(
        "inventario.html",
        lab_name=LAB_NAME_FULL,
        maquinas=maquinas,
        equipamentos_gerais=equipamentos_gerais
    )

@app.route("/gerenciamento", methods=["GET", "POST"])
@login_required
def gerenciamento():
    info = LabInfo.query.first() # Busca informações para o GET e para o POST, caso falhe

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        # --- Lógica de Edição de Informações de Contato (COMPLETADA) ---
        if form_type == "lab_info":
            if not info:
                info = LabInfo() # Cria se não existir
            
            info.coordenador_name = request.form["coordenador_name"]
            info.coordenador_email = request.form["coordenador_email"]
            info.bolsista_name = request.form["bolsista_name"]
            info.bolsista_email = request.form["bolsista_email"] # CAMPO COMPLETADO
            
            db.session.add(info)
            db.session.commit()
            flash("Informações de contato atualizadas com sucesso!", "success")
            # Redireciona para a aba de edição após o sucesso
            return redirect(url_for("gerenciamento", _anchor="lab-info")) 
        
        # --- Lógica de Adição de Máquina ---
        elif form_type == "maquina":
            try:
                asset_id = request.form["asset_id"]
                tombo = request.form.get("tombo")
                
                # Checa por Asset ID duplicado
                if Machine.query.filter_by(asset_id=asset_id).first():
                    flash(f"Erro: Máquina com ID de Ativo '{asset_id}' já existe.", "error")
                    return redirect(url_for("gerenciamento", _anchor="add-machine"))
                
                # Upload de Imagem (opcional)
                # NOTE: Lógica de upload deve estar completa aqui (o snippet original não mostra o bloco completo, assumindo que foi ajustado).
                imagem = request.files.get("image")
                imagem_nome = None 
                if imagem and imagem.filename:
                    # NOTE: Certificar-se que a lógica de salvamento e nomeação está robusta
                    img_path = os.path.join(app.config["UPLOAD_FOLDER"], imagem.filename)
                    imagem.save(img_path)
                    imagem_nome = imagem.filename

                # Converte data de string para objeto Date
                format_date_str = request.form.get("format_date")
                format_date = datetime.strptime(format_date_str, '%Y-%m-%d').date() if format_date_str else None
                
                nova_maquina = Machine(
                    asset_id=asset_id,
                    type=request.form["type"],
                    brand_model=request.form["brand_model"],
                    serial_number=request.form.get("serial_number"),
                    format_status=request.form["format_status"],
                    format_date=format_date,
                    software=request.form.get("software"),
                    license=request.form.get("license"),
                    observations=request.form.get("observations"),
                    tombo=tombo,
                    image_url=imagem_nome
                )
                db.session.add(nova_maquina)
                db.session.commit()
                flash("Máquina cadastrada com sucesso!", "success")
                return redirect(url_for("gerenciamento", _anchor="add-machine"))

            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao cadastrar máquina: {e}", "error")
                return redirect(url_for("gerenciamento", _anchor="add-machine"))

        # --- Lógica de Adição de Equipamento Geral ---
        elif form_type == "equipamento":
            try:
                # Upload de Imagem (opcional)
                imagem = request.files.get("image")
                imagem_nome = None 
                if imagem and imagem.filename:
                    # NOTE: Certificar-se que a lógica de salvamento e nomeação está robusta
                    img_path = os.path.join(app.config["UPLOAD_FOLDER"], imagem.filename)
                    imagem.save(img_path)
                    imagem_nome = imagem.filename
                    
                novo_equipamento = Equipment(
                    name=request.form["name"],
                    functionality=request.form.get("functionality"),
                    brand=request.form.get("brand"),
                    model=request.form.get("model"),
                    quantity=request.form.get("quantity"),
                    tombo=request.form.get("tombo"),
                    image_url=imagem_nome
                )
                db.session.add(novo_equipamento)
                db.session.commit()
                flash("Equipamento cadastrado com sucesso!", "success")
                return redirect(url_for("gerenciamento", _anchor="add-machine"))
            
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao cadastrar equipamento: {e}", "error")
                return redirect(url_for("gerenciamento", _anchor="add-machine"))
                
    # Lógica para GET (renderizar o template)
    maquinas = Machine.query.order_by(Machine.asset_id).all()
    equipamentos_gerais = Equipment.query.order_by(Equipment.name).all()
    
    return render_template(
        "gerenciamento.html",
        lab_name=LAB_NAME_FULL,
        info=info,
        maquinas=maquinas,
        equipamentos_gerais=equipamentos_gerais
    )

# --- CRIAÇÃO INICIAL E EXECUÇÃO ---
with app.app_context():
    db.create_all()
    
    # Cria usuários padrão (se não existirem)
    if not User.query.first():
        admin = User(username="rendeiro2025", password="admLTIP2025", role="coordenador")
        bolsista = User(username="arthur2006", password="LTIP2025", role="bolsista")
        visitante = User(username="visitante", password="0000", role="visitante")
        db.session.add_all([admin, bolsista, visitante])
        db.session.commit()
        print("Usuários padrão criados.")

    # Cria LabInfo padrão (se não existir)
    if not LabInfo.query.first():
        info = LabInfo(
            coordenador_name="[NOME DO COORDENADOR]",
            coordenador_email="coordenador@uea.edu.br",
            bolsista_name="Arthur [SOBRENOME]",
            bolsista_email="arthur2006@uea.edu.br",
        )
        db.session.add(info)
        db.session.commit()
        print("Informações do Laboratório padrão criadas.")

if __name__ == "__main__":
    # Garante que a pasta de uploads exista
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    app.run(debug=True)
