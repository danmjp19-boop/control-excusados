import os
import json
import re

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from google.cloud import vision
from google.oauth2 import service_account

app = Flask(__name__)
app.secret_key = "control_excusados_2026"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


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
    orden = db.Column(db.String(30))
    fecha_inicio = db.Column(db.String(20))
    fecha_final = db.Column(db.String(20))
    dias = db.Column(db.String(10))
    fecha_registro = db.Column(db.DateTime, default=db.func.now())


with app.app_context():
    db.create_all()

    if Usuario.query.filter_by(cedula="CAI ANDES").first() is None:
        admin = Usuario(
            grado="SI",
            nombres="Administrador",
            apellidos="Sistema",
            cedula="CAI ANDES",
            password="123",
            rol="Administrador",
            unidad="ESTACION SUBA",
            cai="CAI ANDES",
            estado="Activo"
        )

        db.session.add(admin)
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
            return render_template(
                "admin.html",
                usuario=user.nombres
            )

        return "Usuario o contraseña incorrectos"

    return render_template("login.html")


@app.route("/usuarios")
def usuarios():

    usuarios = Usuario.query.all()

    return render_template(
        "usuarios.html",
        usuarios=usuarios
    )


@app.route("/excusas", methods=["GET", "POST"])
def excusas():

    if request.method == "POST":

        archivo = request.files["excusa"]

        if archivo.filename != "":

            contenido = archivo.read()

            info = json.loads(os.environ["GOOGLE_CREDENTIALS"])

            credentials = service_account.Credentials.from_service_account_info(info)

            cliente = vision.ImageAnnotatorClient(
                credentials=credentials
            )

            imagen = vision.Image(content=contenido)

            respuesta = cliente.text_detection(image=imagen)

            texto = respuesta.full_text_annotation.text

            datos = extraer_datos(texto)

            return render_template(
    "resultado.html",
    datos=datos
)

    return render_template("excusas.html")


if __name__ == "__main__":
    app.run(debug=True)
