# Importações necessárias
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os # ESSENCIAL: Importado para ler variáveis de ambiente
import csv
from datetime import datetime # ESTA IMPORTAÇÃO É NECESSÁRIA
from werkzeug.utils import secure_filename # NOVO: Para segurança de nomes de arquivo
import uuid # NOVO: Para nomes de arquivo únicos

# --- Configurações Iniciais ---
app = Flask(__name__)
# A secret_key é obrigatória para sessões, flash messages e segurança
app.secret_key = "ltip_secret_key" 

# >>> MUDANÇA PRINCIPAL: Configuração de Banco de Dados Persistente
# Usa a variável de ambiente DATABASE_URL (Render/Produção) ou fallback para SQLite (Desenvolvimento Local)
# A função .replace é um workaround comum para o formato de URL de alguns provedores de hospedagem (e.g., Render)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", 
    "sqlite:///ltip.db"
).replace("postgres://", "postgresql://")
# FIM DA MUDANÇA PRINCIPAL <<<

# Pasta para uploads de imagens (deve existir na raiz do projeto)
app.config["UPLOAD_FOLDER"] = "uploads"

# Inicialização das extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Define o nome completo do laboratório como uma constante
# NOME DO LABORATÓRIO MANTIDO
LAB_NAME_FULL = "LABORATÓRIO DE TECNOLOGIA DA INFORMAÇÃO DO PROFÁGUA" 

# --- NOVO: FUNÇÃO PARA TRATAMENTO DE UPLOAD DE IMAGEM ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ... (Mantenha o restante das suas classes de modelo - User, LabInfo, Maquina, Equipamento)

# --- MODELOS (CLASSES PARA O BANCO DE DADOS) ---

class User(UserMixin, db.Model):
# ... (Mantenha o conteúdo da classe User)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # Senha deve ser hash real em prod
    role = db.Column(db.String(50), nullable=False, default='visitante')

class LabInfo(db.Model):
# ... (Mantenha o conteúdo da classe LabInfo)
    id = db.Column(db.Integer, primary_key=True)
    coordenador_name = db.Column(db.String(100), nullable=False)
    coordenador_email = db.Column(db.String(100), nullable=False)
    bolsista_name = db.Column(db.String(100), nullable=False)
    bolsista_email = db.Column(db.String(100), nullable=False)

class Maquina(db.Model):
# ... (Mantenha o conteúdo da classe Maquina)
    id = db.Column(db.Integer, primary_key=True)
    tombo = db.Column(db.String(100), unique=False, nullable=False) # unique=False ajustado para permitir reuso
    nome = db.Column(db.String(100), nullable=False)
    localizacao = db.Column(db.String(100), nullable=True)
    processador = db.Column(db.String(100), nullable=True)
    memoria_ram = db.Column(db.String(100), nullable=True)
    sistema_operacional = db.Column(db.String(100), nullable=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    image_filename = db.Column(db.String(255), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

class Equipamento(db.Model):
# ... (Mantenha o conteúdo da classe Equipamento)
    id = db.Column(db.Integer, primary_key=True)
    tombo = db.Column(db.String(100), unique=False, nullable=False) # unique=False ajustado para permitir reuso
    nome = db.Column(db.String(100), nullable=False)
    localizacao = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='Disponível')
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    image_filename = db.Column(db.String(255), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTAS (VIEWS) ---

@app.route("/")
def index():
# ... (Mantenha o conteúdo da rota index)
    lab_info = LabInfo.query.first()
    return render_template("index.html", lab_name=LAB_NAME_FULL, info=lab_info)

@app.route("/inventario")
# ... (Mantenha o conteúdo da rota inventario)
def inventario():
    maquinas = Maquina.query.all()
    equipamentos = Equipamento.query.all()
    return render_template("inventario.html", maquinas=maquinas, equipamentos=equipamentos)

@app.route("/relatorios")
@login_required
def relatorios():
    return render_template("relatorios.html")

@app.route("/login", methods=["GET", "POST"])
# ... (Mantenha o conteúdo da rota login)
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password: # Atenção: Em produção, use hash de senha!
            login_user(user)
            flash(f"Login realizado com sucesso! Bem-vindo(a), {user.username}.", "success")
            return redirect(url_for("index"))
        else:
            flash("Nome de usuário ou senha inválidos.", "error")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você foi desconectado(a).", "info")
    return redirect(url_for("index"))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route("/gerenciamento", methods=["GET", "POST"])
@login_required
def gerenciamento():
    if current_user.role not in ['bolsista', 'coordenador']:
        flash("Permissão negada. Você não tem acesso à área de gerenciamento.", "error")
        return redirect(url_for("index"))

    # Pega o primeiro registro (LabInfo) ou cria um novo se não existir (o que foi feito na inicialização)
    lab_info = LabInfo.query.first()
    if not lab_info:
        # Se por acaso o primeiro não existir, tenta criar um dummy para evitar crash
        lab_info = LabInfo(coordenador_name="Não Encontrado", coordenador_email="...", bolsista_name="Não Encontrado", bolsista_email="...")
        
    active_tab = request.args.get('tab', 'info') # Obtém a aba ativa da URL ou usa 'info' como padrão

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        if active_tab == 'info':
            # --- Atualização de LabInfo ---
            lab_info.coordenador_name = request.form.get("coordenador_name")
            lab_info.coordenador_email = request.form.get("coordenador_email")
            lab_info.bolsista_name = request.form.get("bolsista_name")
            lab_info.bolsista_email = request.form.get("bolsista_email")
            
            try:
                db.session.commit()
                flash("Informações de contato atualizadas com sucesso!", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar: {e}", "error")
                
            return redirect(url_for('gerenciamento', tab='info'))

        elif active_tab == 'cadastro' and form_type in ['maquina', 'equipamento']:
            # --- Cadastro de Inventário ---
            tombo = request.form.get("tombo")
            nome = request.form.get("nome")
            localizacao = request.form.get("localizacao")
            observacoes = request.form.get("observacoes")
            
            # Tratar upload de imagem
            image_filename = None
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    original_filename = secure_filename(file.filename)
                    # Cria um nome de arquivo único para evitar colisões
                    unique_filename = str(uuid.uuid4()) + os.path.splitext(original_filename)[1]
                    # Garante que a pasta de upload exista
                    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
                        os.makedirs(app.config["UPLOAD_FOLDER"])
                    # Salva o arquivo
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
                    image_filename = unique_filename

            try:
                if form_type == 'maquina':
                    maquina = Maquina(
                        tombo=tombo,
                        nome=nome,
                        localizacao=localizacao,
                        processador=request.form.get("processador"),
                        memoria_ram=request.form.get("memoria_ram"),
                        sistema_operacional=request.form.get("sistema_operacional"),
                        observacoes=observacoes,
                        image_filename=image_filename
                    )
                    db.session.add(maquina)
                    flash(f"Máquina '{nome}' cadastrada com sucesso!", "success")
                
                elif form_type == 'equipamento':
                    equipamento = Equipamento(
                        tombo=tombo,
                        nome=nome,
                        localizacao=localizacao,
                        status=request.form.get("status", "Disponível"),
                        observacoes=observacoes,
                        image_filename=image_filename
                    )
                    db.session.add(equipamento)
                    flash(f"Equipamento '{nome}' cadastrado com sucesso!", "success")
                
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao cadastrar: Verifique se o Tombo/N° Patrimônio já existe (ou outra restrição do DB). Erro: {e}", "error")
                
            # Redireciona para a aba de cadastro, mantendo o formulário de máquina/equipamento ativo
            form_to_show = request.form.get('activeForm', 'maquina') # Obtém o form ativo do JS/Hidden field
            return redirect(url_for('gerenciamento', tab='cadastro', active_form=form_to_show))

    # GET request ou após o POST, para renderizar a página
    # ATENÇÃO: É importante garantir que o LabInfo seja passado, mesmo que vazio
    return render_template(
        "gerenciamento.html", 
        lab_info=lab_info, 
        active_tab=active_tab, # Passa a aba ativa para o JS/Jinja
        # NEW: Passa o form ativo (maquina/equipamento) para o JS inicializar corretamente após o POST
        active_form=request.args.get('active_form', 'maquina') 
    )

# --- CRIAÇÃO INICIAL E EXECUÇÃO ---
with app.app_context():
    # ATENÇÃO: Se o banco de dados já existe, db.create_all() não altera colunas.
    # É recomendável DELETAR o arquivo 'ltip.db' ANTES de rodar o app para que
    # as alterações nos modelos (remoção do unique=True no tombo) tenham efeito.
    # Se você for migrar para PostgreSQL, não é necessário deletar o arquivo SQLite,
    # mas o banco PostgreSQL deve ser populado uma vez.
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
            bolsista_email="arthur2006@uea.edu.br"
        )
        db.session.add(info)
        db.session.commit()
        print("Informações padrão do Lab criadas.")

if __name__ == "__main__":
    # Quando rodando localmente, cria a pasta de uploads se não existir
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])
    # Rodar o app
    app.run(debug=True)
