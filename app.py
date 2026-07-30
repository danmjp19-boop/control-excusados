import os
import json
import re
import base64
import uuid
import tempfile
from sqlalchemy.orm import deferred
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from google.cloud import vision
from google.oauth2 import service_account
from io import BytesIO
from openpyxl import Workbook
from datetime import datetime


app = Flask(__name__)
app.secret_key = "control_excusados_2026"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "usuario_id" not in session:
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grado = db.Column(db.String(20), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(30), nullable=False)
    unidad = db.Column(db.String(100), nullable=False)
    cai = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(20), default="Activo")

class Excusa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    cedula = db.Column(db.String(20), nullable=False)
    cai = db.Column(db.String(100), nullable=True)
    orden = db.Column(db.String(30))
    fecha_inicio = db.Column(db.String(20))
    fecha_final = db.Column(db.String(20))
    dias = db.Column(db.String(10))
    fecha_registro = db.Column(db.DateTime, default=db.func.now())
    entregada = db.Column(db.Boolean, default=False, nullable=False)
    imagen = deferred(db.Column(db.LargeBinary, nullable=True))

class Novedad(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    excusa_id = db.Column(db.Integer, nullable=False)

    usuario = db.Column(db.String(100), nullable=False)

    rol = db.Column(db.String(30), nullable=False)

    comentario = db.Column(db.Text, nullable=False)

    estado = db.Column(db.String(20), default="Pendiente")

    fecha = db.Column(
        db.DateTime,
        default=db.func.now()
    )

@app.context_processor
def contador_novedades():

    if session.get("rol") == "Administrador":

        pendientes = Novedad.query.filter_by(
            estado="Pendiente"
        ).count()

        return {
            "novedades_pendientes": pendientes
        }

    return {
        "novedades_pendientes": 0
    }
    

with app.app_context():
    db.create_all()

    try:
        db.session.execute(
            db.text("ALTER TABLE excusa ADD COLUMN IF NOT EXISTS cai VARCHAR(100)")
        )
        db.session.commit()
        print("Columna CAI verificada correctamente")
    except Exception as e:
        db.session.rollback()
        print("Error verificando columna CAI:", e)

    try:
        db.session.execute(
            db.text("ALTER TABLE excusa ADD COLUMN IF NOT EXISTS imagen BYTEA")
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Error creando columna imagen:", e)

    admins = Usuario.query.filter_by(cedula="TAHUM-E11").all()

    if len(admins) == 0:

        admin = Usuario(
            grado="SI",
            nombres="Administrador",
            apellidos="Sistema",
            cedula="TAHUM-E11",
            password="Nueva321+",
            rol="Administrador",
            unidad="ESTACION DE POLICIA SUBA",
            cai="CAI ANDES",
            estado="Activo"
        )

        db.session.add(admin)
        db.session.commit()

    elif len(admins) > 1:

        for usuario in admins[1:]:
            db.session.delete(usuario)

        db.session.commit()


def extraer_datos(texto):

    datos = {
        "nombre": "",
        "cedula": "",
        "orden": "",
        "fecha_inicio": "",
        "fecha_final": "",
        "dias": ""
    }

    m = re.search(
        r"CC\s+(\d+)\s+([A-ZÁÉÍÓÚÑ ]+)",
        texto
    )

    if m:
        datos["cedula"] = m.group(1)
        datos["nombre"] = m.group(2).strip()

    # Orden
    m = re.search(r"No\.\s*Orden\s*\n?(\d+)", texto)
    if m:
        datos["orden"] = m.group(1)

    # Fecha inicial
    m = re.search(r"Fecha Inicial\s+(\d{4}/\d{2}/\d{2})", texto)
    if m:
        datos["fecha_inicio"] = m.group(1)

    # Fecha final
    m = re.search(r"Fecha Final\s+(\d{4}/\d{2}/\d{2})", texto)
    if m:
        datos["fecha_final"] = m.group(1)

    # Número de días
    m = re.search(r"Número de días incapacidad\s*\n?(\d+)", texto)
    if m:
        datos["dias"] = m.group(1)

    return datos


@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        password = request.form["password"]

        user = Usuario.query.filter_by(
            cedula=usuario,
            password=password
        ).first()

        if user:

            # Guardamos los datos del usuario que inició sesión
            session["usuario_id"] = user.id
            session["usuario"] = user.cedula
            session["nombre"] = user.nombres
            session["rol"] = user.rol
            session["cai"] = user.cai

            return redirect(url_for("admin"))

        return "Usuario o contraseña incorrectos"

    return render_template("login.html")

@app.route("/crear_columna_entregada")
def crear_columna_entregada():

    try:
        db.session.execute(
            db.text(
                "ALTER TABLE excusa ADD COLUMN IF NOT EXISTS entregada BOOLEAN DEFAULT FALSE"
            )
        )
        db.session.commit()
        return "Columna creada correctamente."
    except Exception as e:
        db.session.rollback()
        return str(e)

@app.route("/admin")
@login_required
def admin():

    from datetime import datetime

    hoy = datetime.now().strftime("%Y-%m-%d")

    total_usuarios = Usuario.query.count()
    total_excusas = Excusa.query.count()

    excusas_activas = Excusa.query.filter(
        Excusa.fecha_final >= hoy
    ).count()

    vencen_hoy = Excusa.query.filter(
        Excusa.fecha_final == hoy
    ).count()

    return render_template(
        "admin.html",
        total_usuarios=total_usuarios,
        excusas_activas=excusas_activas,
        vencen_hoy=vencen_hoy,
        total_excusas=total_excusas
    )


@app.route("/usuarios")
def usuarios():

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    usuarios = Usuario.query.all()

    return render_template(
        "usuarios.html",
        usuarios=usuarios
    )


@app.route("/crear_usuario", methods=["POST"])
def crear_usuario():

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    if Usuario.query.filter_by(cedula=request.form["cedula"]).first():
        return "Ya existe un usuario con ese usuario"

    nuevo = Usuario(
        grado=request.form["grado"],
        nombres=request.form["nombres"],
        apellidos=request.form["apellidos"],
        cedula=request.form["cedula"],
        password=request.form["password"],
        rol=request.form["rol"],
        unidad=request.form["unidad"],
        cai=request.form["cai"],
        estado="Activo"
    )

    db.session.add(nuevo)
    db.session.commit()

    return redirect(url_for("usuarios"))


@app.route("/editar_usuario/<int:id>", methods=["GET", "POST"])
def editar_usuario(id):

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    usuario = Usuario.query.get_or_404(id)

    if request.method == "POST":

        usuario.grado = request.form["grado"]
        usuario.nombres = request.form["nombres"]
        usuario.apellidos = request.form["apellidos"]
        usuario.cedula = request.form["cedula"]
        usuario.password = request.form["password"]
        usuario.rol = request.form["rol"]
        usuario.unidad = request.form["unidad"]
        usuario.cai = request.form["cai"]

        db.session.commit()

        return redirect(url_for("usuarios"))

    return render_template(
        "editar_usuario.html",
        usuario=usuario
    )


@app.route("/eliminar_usuario/<int:id>")
def eliminar_usuario(id):

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    usuario = Usuario.query.get_or_404(id)

    db.session.delete(usuario)
    db.session.commit()

    return redirect(url_for("usuarios"))

@app.route("/excusas", methods=["GET", "POST"])
def excusas():

    if request.method == "POST":

        archivo = request.files["excusa"]

        if archivo.filename != "":

            contenido = archivo.read()

            imagen_id = str(uuid.uuid4())

            ruta_temporal = os.path.join(
                tempfile.gettempdir(),
                imagen_id + ".jpg"
            )

            with open(ruta_temporal, "wb") as f:
                f.write(contenido)

            info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
            credentials = service_account.Credentials.from_service_account_info(info)

            cliente = vision.ImageAnnotatorClient(credentials=credentials)

            imagen = vision.Image(content=contenido)

            respuesta = cliente.text_detection(image=imagen)

            texto = respuesta.full_text_annotation.text

            datos = extraer_datos(texto)

            # Verificar si la orden ya existe
            if datos["orden"]:

                existe = Excusa.query.filter_by(
                    orden=datos["orden"]
                ).first()

                if existe:

                    return render_template(
                        "resultado.html",
                        datos=datos,
                        imagen_id=imagen_id,
                        mensaje=True
                    )

            return render_template(
                "resultado.html",
                datos=datos,
                imagen_id=imagen_id
            )

    return render_template("excusas.html")

@app.route("/guardar_excusa", methods=["POST"])
def guardar_excusa():

    imagen_id = request.form.get("imagen_id")

    imagen_bytes = None

    if imagen_id:

        ruta_temporal = os.path.join(
            tempfile.gettempdir(),
            imagen_id + ".jpg"
        )

        if os.path.exists(ruta_temporal):

            with open(ruta_temporal, "rb") as f:
                imagen_bytes = f.read()

            os.remove(ruta_temporal)

    orden = request.form["orden"].strip()

    # Verificar si la orden ya existe
    if Excusa.query.filter_by(orden=orden).first():
        return f"La orden No. {orden} ya se encuentra registrada."

    excusa = Excusa(
        nombre=request.form["nombre"],
        cedula=request.form["cedula"],
        cai=request.form["cai"],
        orden=orden,
        fecha_inicio=request.form["fecha_inicio"],
        fecha_final=request.form["fecha_final"],
        dias=request.form["dias"],
        imagen=imagen_bytes
    )

    db.session.add(excusa)
    db.session.commit()

    return redirect(url_for("excusas"))

@app.route("/ver_excusa/<int:id>")
def ver_excusa(id):

    excusa = Excusa.query.get_or_404(id)

    if not excusa.imagen:
        return "Esta excusa no tiene imagen guardada", 404

    return Response(
        excusa.imagen,
        mimetype="image/jpeg"
    )

@app.route("/descargar_excel")
def descargar_excel():

    fecha_desde = request.args.get("desde")
    fecha_hasta = request.args.get("hasta")

    consulta = Excusa.query

    if fecha_desde:
        consulta = consulta.filter(Excusa.fecha_inicio >= fecha_desde)

    if fecha_hasta:
        consulta = consulta.filter(Excusa.fecha_inicio <= fecha_hasta)

    excusas = consulta.order_by(Excusa.fecha_inicio.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de Excusas"

    ws.append([
        "ID",
        "Nombre",
        "Cédula",
        "Número de Orden",
        "Fecha Inicial",
        "Fecha Final",
        "Número de Días"
    ])

    for e in excusas:
        ws.append([
            e.id,
            e.nombre,
            e.cedula,
            e.orden,
            e.fecha_inicio,
            e.fecha_final,
            e.dias
        ])

    archivo = BytesIO()
    wb.save(archivo)
    archivo.seek(0)

    return send_file(
        archivo,
        as_attachment=True,
        download_name="reporte_excusas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/lista_excusas")
def lista_excusas():

    from datetime import datetime

    pagina = request.args.get("pagina", 1, type=int)

    estado = request.args.get("estado", "")
    mostrar = request.args.get("mostrar", "")

    paginacion = (
        Excusa.query
        .order_by(Excusa.id.desc())
        .paginate(page=pagina, per_page=50, error_out=False)
    )

    excusas = paginacion.items

    hoy = datetime.now().date()

    for e in excusas:
        try:
            fecha_final = datetime.strptime(e.fecha_final, "%Y-%m-%d").date()
            restantes = (fecha_final - hoy).days

            if restantes < 0:
                e.dias_restantes = "Finalizada"
            elif restantes == 0:
                e.dias_restantes = "Finaliza hoy"
            else:
                e.dias_restantes = restantes

        except:
            e.dias_restantes = "-"

    return render_template(
    "lista_excusas.html",
    excusas=excusas,
    paginacion=paginacion,
    estado=estado,
    mostrar=mostrar
)

@app.route("/editar_excusa/<int:id>", methods=["GET", "POST"])
def editar_excusa(id):
    if session.get("rol") != "Administrador":
        return redirect(url_for("lista_excusas"))

    excusa = Excusa.query.get_or_404(id)

    if request.method == "POST":
        excusa.nombre = request.form["nombre"]
        excusa.cedula = request.form["cedula"]
        excusa.cai = request.form["cai"]
        excusa.orden = request.form["orden"]
        excusa.fecha_inicio = request.form["fecha_inicio"]
        excusa.fecha_final = request.form["fecha_final"]
        excusa.dias = request.form["dias"]

        db.session.commit()

        return redirect(url_for("lista_excusas"))

    return render_template("editar_excusa.html", excusa=excusa)

@app.route("/eliminar_excusa/<int:id>")
def eliminar_excusa(id):
    if session.get("rol") != "Administrador":
        return redirect(url_for("lista_excusas"))

    excusa = Excusa.query.get_or_404(id)

    db.session.delete(excusa)
    db.session.commit()

    return redirect(url_for("lista_excusas"))

@app.route("/crear_novedad/<int:id>", methods=["GET", "POST"])
def crear_novedad(id):

    # Solo Supervisor y Secretario pueden enviar novedades
    if session.get("rol") not in ["Supervisor", "Secretario"]:
        return redirect(url_for("lista_excusas"))

    excusa = Excusa.query.get_or_404(id)

    if request.method == "POST":

        comentario = request.form["comentario"].strip()

        if comentario:

            nueva = Novedad(
                excusa_id=excusa.id,
                usuario=session.get("usuario", "Sin identificar"),
                rol=session.get("rol", ""),
                comentario=comentario,
                estado="Pendiente"
            )

            db.session.add(nueva)
            db.session.commit()

        return redirect(url_for("lista_excusas"))

    return render_template(
        "crear_novedad.html",
        excusa=excusa
    )

@app.route("/revisar_novedad/<int:id>")
def revisar_novedad(id):

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    novedad = Novedad.query.get_or_404(id)

    novedad.estado = "Revisado"

    db.session.commit()

    return redirect(url_for("novedades"))

@app.route("/novedades")
def novedades():

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    lista_novedades = Novedad.query.order_by(
        Novedad.fecha.desc()
    ).all()

    pendientes = Novedad.query.filter_by(
        estado="Pendiente"
    ).count()

    return render_template(
        "novedades.html",
        novedades=lista_novedades,
        pendientes=pendientes
    )

@app.route("/editar_novedad/<int:id>", methods=["GET", "POST"])
def editar_novedad(id):

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    novedad = Novedad.query.get_or_404(id)

    if request.method == "POST":

        novedad.comentario = request.form["comentario"].strip()

        db.session.commit()

        return redirect(url_for("novedades"))

    return render_template(
        "editar_novedad.html",
        novedad=novedad
    )


@app.route("/eliminar_novedad/<int:id>")
def eliminar_novedad(id):

    if session.get("rol") != "Administrador":
        return redirect(url_for("admin"))

    novedad = Novedad.query.get_or_404(id)

    db.session.delete(novedad)
    db.session.commit()

    return redirect(url_for("novedades"))


if __name__ == "__main__":
    app.run(debug=True)
