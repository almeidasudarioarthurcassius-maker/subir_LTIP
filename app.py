# Importações necessárias
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import csv
from datetime import datetime # ESTA IMPORTAÇÃO É NECESSÁRIA
from werkzeug.utils import secure_filename # NOVO: Para segurança de nomes de arquivo
import uuid # NOVO: Para nomes de arquivo únicos

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

# --- NOVO: FUNÇÃO PARA TRATAMENTO DE UPLOAD DE IMAGEM ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    """Salva o arquivo de imagem com um nome único."""
    if file and file.filename and allowed_file(file.filename):
        # 1. Cria um nome único usando UUID
        filename = secure_filename(file.filename)
        # Prefere usar o nome original (seguro) após o UUID para rastreabilidade
        unique_filename = str(uuid.uuid4()) + "_" + filename 
        # 2. Salva o arquivo na pasta de uploads
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename
    return None

# --- CONTEXT PROCESSOR PARA DATETIME ---
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
    # CORRIGIDO: Removido unique=True para permitir tombo vazio
    tombo = db.Column(db.String(50)) 
    image_url = db.Column(db.String(255)) # Novo campo para imagem

# Modelo Equipment para itens gerais (Sheet1.csv)
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False) # Tipo de Equipamento
    functionality = db.Column(db.String(120)) # Finalidade
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    quantity = db.Column(db.Integer)
    # CORRIGIDO: Removido unique=True para permitir tombo vazio
    tombo = db.Column(db.String(50)) 
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
            flash("Usuário ou senha inválidos.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for("index"))

@app.route("/inventario")
def inventario():
    equipamentos = Equipment.query.order_by(Equipment.name).all()
    maquinas = Machine.query.order_by(Machine.asset_id).all()

    return render_template(
        "inventario.html",
        equipamentos=equipamentos,
        maquinas=maquinas
    )

# Rota de Gerenciamento (Adicionar/Editar/Excluir)
@app.route("/gerenciamento", methods=["GET", "POST"])
@login_required
def gerenciamento():
    # Inicializa ou busca as informações de contato
    info = LabInfo.query.first() or LabInfo() # Garante que info não é None
    
    # Obter o valor do parâmetro 'tab' da URL para saber qual aba manter ativa
    active_tab = request.args.get('tab', 'adicionar') # Padrão para 'adicionar'
    
    # Listar itens para a aba de listagem
    maquinas = Machine.query.order_by(Machine.asset_id).all()
    equipamentos = Equipment.query.order_by(Equipment.name).all()

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        try:
            if form_type == "maquina":
                # Lógica de processamento de Máquina
                asset_id = request.form.get("asset_id")
                
                # Previne duplicação
                if Machine.query.filter_by(asset_id=asset_id).first():
                    flash(f"Máquina com ID {asset_id} já existe.", "error")
                    return redirect(url_for("gerenciamento", tab="adicionar")) # CORREÇÃO: Passar tab
                
                # Trata o campo de data, que pode vir vazio
                format_date_str = request.form.get("format_date")
                format_date = datetime.strptime(format_date_str, "%Y-%m-%d").date() if format_date_str else None
                
                # Trata o upload de imagem
                image_file = request.files.get('image_file')
                image_url = save_image(image_file) if image_file else None

                new_machine = Machine(
                    asset_id=asset_id,
                    type=request.form.get("type"),
                    brand_model=request.form.get("brand_model"),
                    serial_number=request.form.get("serial_number"),
                    format_status=request.form.get("format_status"),
                    format_date=format_date,
                    software=request.form.get("software"),
                    license=request.form.get("license"),
                    observations=request.form.get("observations"),
                    tombo=request.form.get("tombo"),
                    image_url=image_url # Salva o nome único do arquivo
                )
                
                db.session.add(new_machine)
                db.session.commit()
                flash(f"Máquina {asset_id} adicionada com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="adicionar")) # CORREÇÃO: Passar tab

            elif form_type == "equipamento":
                # Lógica de processamento de Equipamento
                name = request.form.get("name")
                
                # Trata o upload de imagem
                image_file = request.files.get('image_file')
                image_url = save_image(image_file) if image_file else None

                new_equipment = Equipment(
                    name=name,
                    functionality=request.form.get("functionality"),
                    brand=request.form.get("brand"),
                    model=request.form.get("model"),
                    quantity=request.form.get("quantity", type=int),
                    tombo=request.form.get("tombo"),
                    image_url=image_url # Salva o nome único do arquivo
                )
                
                db.session.add(new_equipment)
                db.session.commit()
                flash(f"Equipamento {name} adicionado com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="adicionar")) # CORREÇÃO: Passar tab

            elif form_type == "update_info":
                # Lógica para atualizar LabInfo
                
                # Se não existir, cria uma nova instância
                if not info.id:
                    db.session.add(info)
                
                info.coordenador_name = request.form.get("coordenador_name")
                info.coordenador_email = request.form.get("coordenador_email")
                info.bolsista_name = request.form.get("bolsista_name")
                info.bolsista_email = request.form.get("bolsista_email")
                
                db.session.commit()
                flash("Informações do laboratório atualizadas com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="info")) # CORREÇÃO: Passar tab

            elif form_type == "update_machine":
                # Lógica para editar máquina existente
                machine_id = request.form.get("machine_id", type=int)
                machine = Machine.query.get_or_404(machine_id)
                
                # Trata o campo de data
                format_date_str = request.form.get("format_date")
                machine.format_date = datetime.strptime(format_date_str, "%Y-%m-%d").date() if format_date_str else None
                
                # Trata o upload de imagem
                image_file = request.files.get('image_file')
                if image_file and image_file.filename:
                    image_url = save_image(image_file)
                    if image_url:
                        machine.image_url = image_url

                machine.type = request.form.get("type")
                machine.brand_model = request.form.get("brand_model")
                machine.serial_number = request.form.get("serial_number")
                machine.format_status = request.form.get("format_status")
                machine.software = request.form.get("software")
                machine.license = request.form.get("license")
                machine.observations = request.form.get("observations")
                machine.tombo = request.form.get("tombo")

                db.session.commit()
                flash(f"Máquina {machine.asset_id} atualizada com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="listar")) # CORREÇÃO: Passar tab

            elif form_type == "update_equipment":
                # Lógica para editar equipamento existente
                equipment_id = request.form.get("equipment_id", type=int)
                equipment = Equipment.query.get_or_404(equipment_id)
                
                # Trata o upload de imagem
                image_file = request.files.get('image_file')
                if image_file and image_file.filename:
                    image_url = save_image(image_file)
                    if image_url:
                        equipment.image_url = image_url

                equipment.name = request.form.get("name")
                equipment.functionality = request.form.get("functionality")
                equipment.brand = request.form.get("brand")
                equipment.model = request.form.get("model")
                equipment.quantity = request.form.get("quantity", type=int)
                equipment.tombo = request.form.get("tombo")

                db.session.commit()
                flash(f"Equipamento {equipment.name} atualizado com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="listar")) # CORREÇÃO: Passar tab
            
            elif form_type == "delete_machine":
                # Lógica para excluir máquina
                machine_id = request.form.get("machine_id", type=int)
                machine = Machine.query.get_or_404(machine_id)
                db.session.delete(machine)
                db.session.commit()
                flash(f"Máquina {machine.asset_id} excluída com sucesso.", "success")
                return redirect(url_for("gerenciamento", tab="listar")) # CORREÇÃO: Passar tab

            elif form_type == "delete_equipment":
                # Lógica para excluir equipamento
                equipment_id = request.form.get("equipment_id", type=int)
                equipment = Equipment.query.get_or_404(equipment_id)
                db.session.delete(equipment)
                db.session.commit()
                flash(f"Equipamento {equipment.name} excluído com sucesso.", "success")
                return redirect(url_for("gerenciamento", tab="listar")) # CORREÇÃO: Passar tab
            
            else:
                flash("Tipo de formulário desconhecido.", "error")

        except Exception as e:
            # Em caso de qualquer erro no POST, exibe a mensagem de erro e redireciona.
            print(f"Erro ao processar formulário: {e}")
            flash(f"Erro ao adicionar item: {e}", "error")
            return redirect(url_for("gerenciamento", tab=active_tab)) # CORREÇÃO: Passar tab

    # Lógica de GET (ou após o redirect do POST)
    return render_template(
        "gerenciamento.html",
        info=info, 
        equipamentos=equipamentos,
        maquinas=maquinas,
        # O active_tab é crucial para o template saber qual aba manter ativa
        active_tab=active_tab 
    )

@app.route("/relatorios")
@login_required
def relatorios():
    return render_template("relatorios.html")


# --- CRIAÇÃO INICIAL E EXECUÇÃO ---
with app.app_context():
    # ATENÇÃO: Se o banco de dados já existe, db.create_all() não altera colunas.
    # É recomendável DELETAR o arquivo 'ltip.db' ANTES de rodar o app para que
    # as alterações nos modelos (remoção do unique=True no tombo) tenham efeito.
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
        print("Informações de Laboratório padrão criadas.")


if __name__ == "__main__":
    # Garante que a pasta 'uploads' existe antes de iniciar o app
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
        
    app.run(debug=True)
