# Importações necessárias
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import csv
from datetime import datetime, date # ESTA IMPORTAÇÃO É NECESSÁRIA
from werkzeug.utils import secure_filename # NOVO: Para segurança no upload de arquivos
import uuid # NOVO: Para gerar nomes de arquivo únicos

# --- Configurações Iniciais ---
app = Flask(__name__)
# A secret_key é obrigatória para sessões, flash messages e segurança
app.secret_key = "ltip_secret_key" 
# Configura o banco de dados SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ltip.db"
# Pasta para uploads de imagens (deve existir na raiz do projeto)
app.config["UPLOAD_FOLDER"] = "uploads"
# Extensões permitidas para upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} 

# Inicialização das extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Define o nome completo do laboratório como uma constante (Corrigido conforme pedido)
LAB_NAME_FULL = "LABORATÓRIO DE TECNOLOGIA DA INFORMAÇÃO DO PROFÁGUA"

# --- NOVO: CONTEXT PROCESSOR PARA DATETIME ---
@app.context_processor
def inject_now():
    return {'datetime': datetime}

# --- FUNÇÕES AUXILIARES DE UPLOAD ---
def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file):
    """Salva o arquivo com um nome único e retorna o nome do arquivo seguro."""
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Gera um nome de arquivo único para evitar colisões
        unique_filename = str(uuid.uuid4()) + '_' + filename 
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename
    return None

# --- MODELOS --- (Mantidos como estavam, apenas garantindo o campo image_url)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, bolsista, coordenador

class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), unique=True, nullable=False) # LTIP-COMP-001
    type = db.Column(db.String(50)) # desktop, laptop
    brand_model = db.Column(db.String(120)) # Marca/Modelo
    serial_number = db.Column(db.String(120))
    format_status = db.Column(db.String(50)) # Formatado, Em andamento, Não formatado
    format_date = db.Column(db.Date)
    software = db.Column(db.Text)
    license = db.Column(db.String(120))
    tombo = db.Column(db.String(50), unique=True)
    image_url = db.Column(db.String(255)) 

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False) # Tipo de Equipamento
    functionality = db.Column(db.String(120)) # Finalidade
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    quantity = db.Column(db.Integer)
    tombo = db.Column(db.String(50), unique=True)
    image_url = db.Column(db.String(255)) 

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
    info = LabInfo.query.first()
    return render_template("index.html", lab_name=LAB_NAME_FULL, info=info)

# Rota de Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("gerenciamento"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and user.password == password: # Atenção: Senhas devem ser hasheadas em produção real
            login_user(user)
            flash(f"Login de {user.role.capitalize()} realizado com sucesso!", "success")
            return redirect(url_for("gerenciamento"))
        else:
            flash("Credenciais inválidas. Tente novamente.", "error")
    return render_template("login.html")

# Rota de Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("index"))

# Rota do Inventário (Visualização Pública)
@app.route("/inventario")
def inventario():
    equipamentos = Equipment.query.all()
    maquinas = Machine.query.all()
    return render_template("inventario.html", equipamentos=equipamentos, maquinas=maquinas)


# Rota do Gerenciamento (Acesso Restrito: Cadastro/Edição de Itens e Infos de Contato)
@app.route("/gerenciamento", methods=["GET", "POST"])
@login_required 
def gerenciamento():
    """Painel de gerenciamento para Bolsistas e Coordenadores."""
    
    # 1. Obter a aba ativa da query string
    active_tab = request.args.get('tab', 'adicionar')
    
    # Redirecionar visitantes não-gerenciais
    if current_user.role not in ['admin', 'bolsista', 'coordenador']:
        flash("Acesso negado. Você não tem permissão para gerenciar o inventário.", "error")
        return redirect(url_for('index'))

    # 2. Processamento do Formulário POST
    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        # --- Lógica de Cadastro de MÁQUINA ---
        if form_type == "maquina":
            try:
                image_file = request.files.get('image_file')
                image_url = save_upload(image_file)
                
                asset_id = request.form["asset_id"].strip()
                type_m = request.form["type"]
                brand_model = request.form["brand_model"]
                serial_number = request.form.get("serial_number")
                format_status = request.form["format_status"]
                format_date_str = request.form.get("format_date")
                software = request.form.get("software")
                license = request.form.get("license")
                tombo = request.form.get("tombo")

                format_date_obj = datetime.strptime(format_date_str, '%Y-%m-%d').date() if format_date_str else None

                new_machine = Machine(
                    asset_id=asset_id, type=type_m, brand_model=brand_model, serial_number=serial_number, 
                    format_status=format_status, format_date=format_date_obj, software=software, 
                    license=license, tombo=tombo, image_url=image_url
                )
                db.session.add(new_machine)
                db.session.commit()
                flash(f"Máquina '{asset_id}' cadastrada com sucesso!", "success")
                active_tab = 'listar' 
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao cadastrar máquina. Verifique se o ID ou Tombo já existe. Detalhe: {str(e)}", "error")
                active_tab = 'adicionar'

        # --- Lógica de Cadastro de EQUIPAMENTO GERAL ---
        elif form_type == "equipamento":
            try:
                image_file = request.files.get('image_file')
                image_url = save_upload(image_file)
                
                name = request.form["name"]
                functionality = request.form["functionality"]
                brand = request.form.get("brand")
                model = request.form.get("model")
                quantity = int(request.form.get("quantity", 1))
                tombo = request.form.get("tombo")

                new_equipment = Equipment(
                    name=name, functionality=functionality, brand=brand, model=model, 
                    quantity=quantity, tombo=tombo, image_url=image_url
                )
                db.session.add(new_equipment)
                db.session.commit()
                flash(f"Equipamento '{name}' cadastrado com sucesso!", "success")
                active_tab = 'listar'
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao cadastrar equipamento. Verifique se o Tombo já existe. Detalhe: {str(e)}", "error")
                active_tab = 'adicionar'
                
        # --- Lógica de Edição de INFORMAÇÕES DE CONTATO ---
        elif form_type == "lab_info":
            if current_user.role not in ['admin', 'bolsista', 'coordenador']:
                flash("Ação negada. Permissão insuficiente.", "error")
                return redirect(url_for('gerenciamento', tab='info'))

            try:
                info = LabInfo.query.first()
                if not info:
                    info = LabInfo() # Cria se não existir
                    db.session.add(info)

                info.coordenador_name = request.form.get("coordenador_name")
                info.coordenador_email = request.form.get("coordenador_email")
                info.bolsista_name = request.form.get("bolsista_name")
                info.bolsista_email = request.form.get("bolsista_email")
                
                db.session.commit()
                flash("Informações de contato atualizadas com sucesso!", "success")
                active_tab = 'info'
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao atualizar informações: {str(e)}", "error")
                active_tab = 'info'

    # 3. Renderizar a Página
    maquinas = Machine.query.all()
    equipamentos = Equipment.query.all()
    info = LabInfo.query.first()
    
    # Garante que a pasta de uploads exista
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])
    
    return render_template(
        "gerenciamento.html",
        maquinas=maquinas,
        equipamentos=equipamentos,
        info=info or LabInfo(), # Garante que LabInfo seja passado, mesmo que vazio
        active_tab=active_tab 
    )

# Rota de Relatórios (em construção)
@app.route("/relatorios")
@login_required
def relatorios():
    return render_template("relatorios.html")


# --- CRIAÇÃO INICIAL E EXECUÇÃO ---
with app.app_context():
    db.create_all()
    
    # Cria usuários padrão (se não existirem)
    if not User.query.first():
        admin = User(username="rendeiro2025", password="admLTIP2025", role="coordenador")
        bolsista = User(username="arthur2006", password="LTIP2025", role="bolsista")
        # Visitante permanece, mas não tem acesso ao gerenciamento
        visitante = User(username="visitante", password="0000", role="visitante") 
        db.session.add_all([admin, bolsista, visitante])
        db.session.commit()
        print("Usuários padrão criados.")

    # Cria LabInfo padrão (se não existir)
    if not LabInfo.query.first():
        info = LabInfo(
            coordenador_name="[NOME DO COORDENADOR]",
            coordenador_email="coordenador@uea.edu.br",
            bolsista_name="Arthur (Bolsista)",
            bolsista_email="arthur@bolsista.uea.edu.br" 
        )
        db.session.add(info)
        db.session.commit()
        print("Informações de Laboratório padrão criadas.")
    
if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
