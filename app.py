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

    # Orden
    m = re.search(r"Orden[:\s]*([0-9]+)", texto, re.IGNORECASE)
    if m:
        datos["orden"] = m.group(1)

    # Cédula
    m = re.search(r"C[ée]dula[:\s]*([0-9]+)", texto, re.IGNORECASE)
    if m:
        datos["cedula"] = m.group(1)

    # Días
    m = re.search(r"(\d+)\s*d[ií]as", texto, re.IGNORECASE)
    if m:
        datos["dias"] = m.group(1)

    # Fechas
    fechas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)

    if len(fechas) >= 2:
        datos["fecha_inicio"] = fechas[0]
        datos["fecha_final"] = fechas[1]

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

            return f"""
            <h2>Datos encontrados</h2>
            <pre>{datos}</pre>

            <hr>

            <h2>Texto completo</h2>
            <pre>{texto}</pre>
            """

    return render_template("excusas.html")


if __name__ == "__main__":
    app.run(debug=True)
