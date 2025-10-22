# Importações necessárias
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import csv
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid

# --- Configurações Iniciais ---
app = Flask(__name__)
app.secret_key = "ltip_secret_key" 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ltip.db"
app.config["UPLOAD_FOLDER"] = "uploads"

# Inicialização das extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

LAB_NAME_FULL = "LABORATÓRIO DE TECNOLOGIA DA INFORMAÇÃO DO PROFÁGUA - LTIP"

# --- FUNÇÃO PARA TRATAMENTO DE UPLOAD DE IMAGEM (MANTIDA) ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    """Salva o arquivo de imagem com um nome único."""
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = str(uuid.uuid4()) + "_" + filename 
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename
    return None

# --- CONTEXT PROCESSOR PARA DATETIME (MANTIDO) ---
@app.context_processor
def inject_now():
    return {'datetime': datetime}


# --- MODELOS ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, bolsista, visitante
    
    # NOVO: Propriedade para definir o nome de exibição
    @property
    def display_name(self):
        if self.username == "rendeiro2025" and self.role == "coordenador":
            return "mestre rendeiro" # Mensagem solicitada para o coordenador
        elif self.username == "arthur2006" and self.role == "bolsista":
            return "arthur" # Mensagem solicitada para o bolsista
        return self.username.capitalize() # Default

class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(50))
    brand_model = db.Column(db.String(120))
    serial_number = db.Column(db.String(120))
    format_status = db.Column(db.String(50))
    format_date = db.Column(db.Date)
    
    # NOVO CAMPO SOLICITADO
    physical_cleaning_date = db.Column(db.Date) # Data da última limpeza física
    
    software = db.Column(db.Text)
    license = db.Column(db.String(120))
    observations = db.Column(db.Text)
    tombo = db.Column(db.String(50)) 
    image_url = db.Column(db.String(255))

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    functionality = db.Column(db.String(120))
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    quantity = db.Column(db.Integer)
    tombo = db.Column(db.String(50)) 
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

# Rota para servir arquivos de upload (MANTIDA)
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Rota Inicial (MANTIDA)
@app.route("/")
def index():
    info = LabInfo.query.first()
    equipamentos = Equipment.query.order_by(Equipment.name).limit(5).all()
    maquinas = Machine.query.order_by(Machine.asset_id).limit(5).all()
    
    return render_template(
        "index.html",
        lab_name=LAB_NAME_FULL,
        info=info,
        equipamentos=equipamentos,
        maquinas=maquinas
    )

# Rota de Login (MANTIDA)
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("gerenciamento"))
        
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            # A mensagem de boas-vindas personalizada será exibida no base.html
            flash(f"Login de {user.role.capitalize()} realizado com sucesso!", "success")
            return redirect(url_for("gerenciamento"))
        else:
            flash("Usuário ou senha incorretos.", "error")
            return render_template("login.html")
    return render_template("login.html")

# Rota de Logout (MANTIDA)
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("index"))

# Rota de Inventário (CORRIGIDA)
@app.route("/inventario")
def inventario():
    # CORRIGIDO: Variável 'equipamentos' é usada no template
    equipamentos = Equipment.query.order_by(Equipment.name).all()
    maquinas = Machine.query.order_by(Machine.asset_id).all()

    return render_template(
        "inventario.html",
        maquinas=maquinas,
        equipamentos=equipamentos # Variável corrigida para o template
    )

# Rota de Gerenciamento (Adicionar/Editar/Excluir - Atualizada para o novo campo)
@app.route("/gerenciamento", methods=["GET", "POST"])
@login_required
def gerenciamento():
    info = LabInfo.query.first() or LabInfo()
    active_tab = request.args.get('tab', 'adicionar')
    
    maquinas = Machine.query.order_by(Machine.asset_id).all()
    equipamentos = Equipment.query.order_by(Equipment.name).all()

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        try:
            if form_type == "maquina":
                # Lógica de processamento de Máquina - Atualizada para novo campo
                asset_id = request.form.get("asset_id")
                
                if Machine.query.filter_by(asset_id=asset_id).first():
                    flash(f"Máquina com ID {asset_id} já existe.", "error")
                    return redirect(url_for("gerenciamento", tab="adicionar"))
                
                format_date_str = request.form.get("format_date")
                format_date = datetime.strptime(format_date_str, "%Y-%m-%d").date() if format_date_str else None

                # NOVO CAMPO: Limpeza Física
                cleaning_date_str = request.form.get("physical_cleaning_date")
                cleaning_date = datetime.strptime(cleaning_date_str, "%Y-%m-%d").date() if cleaning_date_str else None
                
                image_file = request.files.get('image_file')
                image_url = save_image(image_file) if image_file else None

                new_machine = Machine(
                    asset_id=asset_id,
                    type=request.form.get("type"),
                    brand_model=request.form.get("brand_model"),
                    serial_number=request.form.get("serial_number"),
                    format_status=request.form.get("format_status"),
                    format_date=format_date,
                    physical_cleaning_date=cleaning_date, # Salva novo campo
                    software=request.form.get("software"),
                    license=request.form.get("license"),
                    observations=request.form.get("observations"),
                    tombo=request.form.get("tombo"),
                    image_url=image_url
                )
                
                db.session.add(new_machine)
                db.session.commit()
                flash(f"Máquina {asset_id} adicionada com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="adicionar"))

            elif form_type == "equipamento":
                # Lógica de processamento de Equipamento (MANTIDA)
                name = request.form.get("name")
                
                image_file = request.files.get('image_file')
                image_url = save_image(image_file) if image_file else None

                new_equipment = Equipment(
                    name=name,
                    functionality=request.form.get("functionality"),
                    brand=request.form.get("brand"),
                    model=request.form.get("model"),
                    quantity=request.form.get("quantity", type=int),
                    tombo=request.form.get("tombo"),
                    image_url=image_url
                )
                
                db.session.add(new_equipment)
                db.session.commit()
                flash(f"Equipamento {name} adicionado com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="adicionar"))

            elif form_type == "update_info":
                # Lógica para atualizar LabInfo (MANTIDA)
                if not info.id:
                    db.session.add(info)
                
                info.coordenador_name = request.form.get("coordenador_name")
                info.coordenador_email = request.form.get("coordenador_email")
                info.bolsista_name = request.form.get("bolsista_name")
                info.bolsista_email = request.form.get("bolsista_email")
                
                db.session.commit()
                flash("Informações do laboratório atualizadas com sucesso!", "success")
                return redirect(url_for("gerenciamento", tab="info"))

            elif form_type == "update_machine":
                # Lógica para editar máquina existente - Atualizada para novo campo
                machine_id = request.form.get("machine_id", type=int)
                machine = Machine.query.get_or_404(machine_id)
                
                # Trata o campo de data de formatação
                format_date_str = request.form.get("format_date")
                machine.format_date = datetime.strptime(format_date_str, "%Y-%m-%d").date() if format_date_str else None
                
                # NOVO CAMPO: Trata o campo de data de limpeza
                cleaning_date_str = request.form.get("physical_cleaning_date")
                machine.physical_cleaning_date = datetime.strptime(cleaning_date_str, "%Y-%m-%d").date() if cleaning_date_str else None
                
                # Trata o upload de imagem (MANTIDO)
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
                return redirect(url_for("gerenciamento", tab="listar"))

            elif form_type == "update_equipment":
                # Lógica para editar equipamento existente (MANTIDA)
                equipment_id = request.form.get("equipment_id", type=int)
                equipment = Equipment.query.get_or_404(equipment_id)
                
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
                return redirect(url_for("gerenciamento", tab="listar"))
            
            elif form_type == "delete_machine":
                # Lógica para excluir máquina (MANTIDA)
                machine_id = request.form.get("machine_id", type=int)
                machine = Machine.query.get_or_404(machine_id)
                db.session.delete(machine)
                db.session.commit()
                flash(f"Máquina {machine.asset_id} excluída com sucesso.", "success")
                return redirect(url_for("gerenciamento", tab="listar"))

            elif form_type == "delete_equipment":
                # Lógica para excluir equipamento (MANTIDA)
                equipment_id = request.form.get("equipment_id", type=int)
                equipment = Equipment.query.get_or_404(equipment_id)
                db.session.delete(equipment)
                db.session.commit()
                flash(f"Equipamento {equipment.name} excluído com sucesso.", "success")
                return redirect(url_for("gerenciamento", tab="listar"))
            
            else:
                flash("Tipo de formulário desconhecido.", "error")

        except Exception as e:
            print(f"Erro ao processar formulário: {e}")
            flash(f"Erro ao adicionar/atualizar item: {e}", "error")
            return redirect(url_for("gerenciamento", tab=active_tab))

    # Lógica de GET (MANTIDA)
    return render_template(
        "gerenciamento.html",
        info=info, 
        equipamentos=equipamentos,
        maquinas=maquinas,
        active_tab=active_tab 
    )

# Rota de Relatórios (MANTIDA)
@app.route("/relatorios")
@login_required
def relatorios():
    return render_template("relatorios.html")


# --- CRIAÇÃO INICIAL E EXECUÇÃO ---
with app.app_context():
    # ATENÇÃO: É necessário DELETAR o arquivo 'ltip.db' ANTES de rodar o app para que
    # o novo campo 'physical_cleaning_date' seja criado no modelo Machine.
    db.create_all()
    
    # Cria usuários padrão (MANTIDO)
    if not User.query.first():
        # Estes são os usernames que disparam a mensagem de boas-vindas personalizada
        admin = User(username="rendeiro2025", password="admLTIP2025", role="coordenador")
        bolsista = User(username="arthur2006", password="LTIP2025", role="bolsista")
        visitante = User(username="visitante", password="0000", role="visitante")
        db.session.add_all([admin, bolsista, visitante])
        db.session.commit()
        print("Usuários padrão criados.")

    # Cria LabInfo padrão (MANTIDO)
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
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
        
    app.run(debug=True)
