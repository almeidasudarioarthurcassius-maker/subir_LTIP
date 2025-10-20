from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import csv
from io import StringIO
from datetime import datetime

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

# Modelo para Usuários (Admin, Bolsista, Visitante)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False) # Em um sistema real, use hash para senhas!
    role = db.Column(db.String(20), nullable=False)

# Modelo para o Inventário Geral (Infraestrutura, Ferramentas, etc.) - Base Sheet1.csv
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120)) # Tipo de Equipamento
    functionality = db.Column(db.String(120)) # Finalidade
    brand = db.Column(db.String(120)) # Marca
    model = db.Column(db.String(120)) # Modelo
    quantity = db.Column(db.Integer) # quantidade
    tombo = db.Column(db.String(50), unique=True, nullable=True) # Tombo do Equipamento Geral
    image = db.Column(db.String(120), nullable=True) 

# Modelo para o Controle Detalhado de Máquinas (Computadores/Notebooks) - Base Planilha1.csv
class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), unique=True, nullable=False) # ID (LTIP-COMP-001)
    type = db.Column(db.String(50)) # TIPO (desktop/laptop)
    brand_model = db.Column(db.String(120)) # MARCA/MODELO
    serial_number = db.Column(db.String(120), nullable=True) # N° DE SÉRIE
    format_status = db.Column(db.String(50)) # STATUS DA FORMATAÇÃO (Formatado, Em andamento, etc.)
    format_date = db.Column(db.Date, nullable=True) # DATA DA FORMATAÇÃO
    software = db.Column(db.Text, nullable=True) # SOFTWARES INSTALADOS
    license = db.Column(db.String(120), nullable=True) # LICENÇA(SE HOUVER)
    notes = db.Column(db.Text, nullable=True) # OBSERVAÇÕES
    tombo = db.Column(db.String(50), unique=True, nullable=True) # Tombo (Identificação)

# Modelo para Informações de Contato do Laboratório
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
    return db.session.get(User, int(user_id))

# --------------------------------------------------------
# FUNÇÕES AUXILIARES DE IMPORTAÇÃO DE CSV
# --------------------------------------------------------
def _import_equipment_data(filename):
    """Importa dados do inventário geral (Sheet1.csv)."""
    try:
        # Pega o conteúdo do arquivo
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # O cabeçalho real começa após 5 linhas de cabeçalho irrelevante
        reader = csv.reader(StringIO(content), delimiter=',')
        
        # Pula as linhas de cabeçalho
        for _ in range(5):
            next(reader) 

        # A próxima linha é o cabeçalho real (Tipo de Equipamento,Finalidade,Marca,Modelo,quantidade,Tombo,Imagem)
        header = next(reader) 
        
        # Mapeamento de colunas (em português)
        col_map = {
            'Tipo de Equipamento': 0, 'Finalidade': 1, 'Marca': 2, 'Modelo': 3, 
            'quantidade': 4, 'Tombo': 5, 'Imagem': 6
        }

        imported_count = 0
        for row in reader:
            if not row or len(row) < 7 or not row[col_map['Tipo de Equipamento']].strip():
                continue
            
            # Tenta evitar duplicatas pelo Tombo
            tombo_val = row[col_map['Tombo']].strip() or None
            if tombo_val and Equipment.query.filter_by(tombo=tombo_val).first():
                continue
                
            qty = row[col_map['quantidade']].strip()
            
            new_equipment = Equipment(
                name=row[col_map['Tipo de Equipamento']].strip(),
                functionality=row[col_map['Finalidade']].strip(),
                brand=row[col_map['Marca']].strip() or None,
                model=row[col_map['Modelo']].strip() or None,
                quantity=int(qty) if qty and qty.isdigit() else 1,
                tombo=tombo_val,
                image=row[col_map['Imagem']].strip() if len(row) > col_map['Imagem'] and row[col_map['Imagem']].strip() else None
            )
            db.session.add(new_equipment)
            imported_count += 1
        db.session.commit()
        print(f"Importação de Equipamentos concluída. Total de {imported_count} itens importados.")

    except Exception as e:
        print(f"Erro ao importar dados de equipamentos: {e}")

def _import_machine_data(filename):
    """Importa dados de controle de máquinas (Planilha1.csv)."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        reader = csv.reader(StringIO(content), delimiter=',')
        
        # Pula as 5 linhas de cabeçalho irrelevante
        for _ in range(5):
            next(reader) 
            
        # A próxima linha é o cabeçalho real 
        # ID,TIPO,MARCA/MODELO,N° DE SÉRIE,STATUS DA FORMATAÇÃO,DATA DA FORMATAÇÃO,SOFTWARES INSTALADOS,LICENÇA(SE HOUVER),OBSERVAÇÕES,TOMBO...
        header = next(reader)
        
        # Mapeamento de colunas (baseado na estrutura da Planilha1.csv)
        col_map = {
            'ID': 0, 'TIPO': 1, 'MARCA/MODELO': 2, 'N° DE SÉRIE': 3, 
            'STATUS DA FORMATAÇÃO': 4, 'DATA DA FORMATAÇÃO': 5, 
            'SOFTWARES INSTALADOS': 6, 'LICENÇA(SE HOUVER)': 7, 
            'OBSERVAÇÕES': 8, 'TOMBO': 9
        }

        imported_count = 0
        for row in reader:
            if not row or len(row) < 10 or not row[col_map['ID']].strip():
                continue
            
            asset_id = row[col_map['ID']].strip()
            # Pula se já existir uma máquina com este ID
            if Machine.query.filter_by(asset_id=asset_id).first():
                continue
                
            date_str = row[col_map['DATA DA FORMATAÇÃO']].strip()
            format_date = None
            try:
                if date_str:
                    # Tenta formatar a data, se não conseguir, deixa como None
                    format_date = datetime.strptime(date_str, '%Y-%m-%d').date() 
            except ValueError:
                pass # Data inválida ou vazia
            
            new_machine = Machine(
                asset_id=asset_id,
                type=row[col_map['TIPO']].strip() or 'Não Classificado',
                brand_model=row[col_map['MARCA/MODELO']].strip() or 'N/A',
                serial_number=row[col_map['N° DE SÉRIE']].strip() or None,
                format_status=row[col_map['STATUS DA FORMATAÇÃO']].strip() or 'Não formatado',
                format_date=format_date,
                software=row[col_map['SOFTWARES INSTALADOS']].strip() or None,
                license=row[col_map['LICENÇA(SE HOUVER)']].strip() or None,
                notes=row[col_map['OBSERVAÇÕES']].strip() or None,
                tombo=row[col_map['TOMBO']].strip() or None
            )
            db.session.add(new_machine)
            imported_count += 1
        db.session.commit()
        print(f"Importação de Máquinas concluída. Total de {imported_count} itens importados.")

    except Exception as e:
        print(f"Erro ao importar dados de máquinas: {e}")


# --------------------------------------------------------
# ROTAS (ROUTES)
# --------------------------------------------------------

# Rota para servir os arquivos de upload (imagens)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/")
def index():
    info = LabInfo.query.first()
    # Pega equipamentos gerais para destaque na Home
    equipamentos = Equipment.query.limit(3).all() 
    return render_template("index.html", info=info, equipamentos=equipamentos)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and user.password == request.form["password"]:
            login_user(user)
            flash("Login realizado com sucesso!", "success")
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
    # Envia dados dos dois modelos para o inventário público
    equipamentos_gerais = Equipment.query.all()
    maquinas = Machine.query.all()
    return render_template("inventario.html", equipamentos_gerais=equipamentos_gerais, maquinas=maquinas)

@app.route("/gerenciamento")
@login_required
def gerenciamento():
    if current_user.role not in ["admin", "bolsista"]:
        flash("Acesso negado. Apenas administradores e bolsistas.", "warning")
        return redirect(url_for("index"))
        
    # Envia dados dos dois modelos para o gerenciamento
    equipamentos_gerais = Equipment.query.all()
    maquinas = Machine.query.all()
    info = LabInfo.query.first()
    return render_template("gerenciamento.html", 
                           equipamentos_gerais=equipamentos_gerais, 
                           maquinas=maquinas, 
                           info=info)

# ROTA: Edição das Informações de Contato
@app.route("/editar_info_laboratorio", methods=["POST"])
@login_required
def editar_info_laboratorio():
    if current_user.role not in ["admin", "bolsista"]:
        flash("Permissão negada para editar as informações do laboratório.", "warning")
        return redirect(url_for("gerenciamento"))
    
    info = LabInfo.query.first()
    if not info:
        info = LabInfo()
        db.session.add(info)
        
    info.coordenador_name = request.form["coordenador_name"]
    info.coordenador_email = request.form["coordenador_email"]
    info.bolsista_name = request.form["bolsista_name"]
    info.bolsista_email = request.form["bolsista_email"]

    db.session.commit()
    flash("Informações do laboratório atualizadas com sucesso!", "success")
    return redirect(url_for("gerenciamento"))

# ROTA: Adicionar Equipamento Geral (Infraestrutura)
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
    flash(f"Equipamento '{nome}' adicionado com sucesso!", "success")
    # Redireciona para a aba correta no gerenciamento
    return redirect(url_for("gerenciamento", _anchor="content-equipamentos")) 

# ROTA: Adicionar Máquina (Computador/Notebook)
@app.route("/adicionar_maquina", methods=["POST"])
@login_required
def adicionar_maquina():
    if current_user.role not in ["admin", "bolsista"]:
        flash("Permissão negada para adicionar máquinas.", "warning")
        return redirect(url_for("gerenciamento"))
        
    try:
        format_date = None
        date_str = request.form["format_date"]
        if date_str:
             format_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        format_date = None # Data inválida
        
    nova_maquina = Machine(
        asset_id=request.form["asset_id"],
        type=request.form["type"],
        brand_model=request.form["brand_model"],
        serial_number=request.form["serial_number"] or None,
        format_status=request.form["format_status"],
        format_date=format_date,
        software=request.form["software"] or None,
        license=request.form["license"] or None,
        notes=request.form["notes"] or None,
        tombo=request.form["tombo"] or None
    )
    db.session.add(nova_maquina)
    db.session.commit()
    flash(f"Máquina '{nova_maquina.asset_id}' adicionada com sucesso!", "success")
    # Redireciona para a aba correta no gerenciamento
    return redirect(url_for("gerenciamento", _anchor="content-maquinas")) 

# --------------------------------------------------------
# CRIAÇÃO INICIAL DO BANCO E POPULAÇÃO
# --------------------------------------------------------
with app.app_context():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()
    
    if not User.query.first():
        # Logins solicitados pelo usuário
        admin = User(username="rendeiro2025", password="admLTIP2025", role="admin")
        bolsista = User(username="arthur2006", password="LTIP2025", role="bolsista")
        visitante = User(username="visitante", password="0000", role="visitante")
        db.session.add_all([admin, bolsista, visitante])
        db.session.commit()
        
    if not LabInfo.query.first():
        info = LabInfo(
            coordenador_name="Coordenador LTIP",
            coordenador_email="coordenador@uea.edu.br",
            bolsista_name="Bolsista LTIP",
            bolsista_email="bolsista@uea.edu.br",
        )
        db.session.add(info)
        db.session.commit()
        
    # Importação dos dados das planilhas, se o banco estiver vazio
    if not Equipment.query.first() or not Machine.query.first():
        print("Iniciando importação de dados da planilha...")
        _import_equipment_data("Inventario_Laboratorio_Informática.xlsx - Sheet1.csv")
        _import_machine_data("Inventario_Laboratorio_Informática.xlsx - Planilha1.csv")
        print("Importação concluída.")


# O bloco principal (para rodar localmente com 'python app.py')
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
