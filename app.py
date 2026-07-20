import os
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import pytesseract
import json
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
    db.drop_all()
    db.create_all()

    if Usuario.query.filter_by(cedula="1000000000").first() is None:
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
    return render_template("usuarios.html", usuarios=usuarios)

@app.route("/excusas", methods=["GET", "POST"])
def excusas():

    if request.method == "POST":
        archivo = request.files["excusa"]

        if archivo.filename != "":
            imagen = Image.open(archivo)

            texto = pytesseract.image_to_string(
                imagen,
                lang="spa"
            )

            return f"<pre>{texto}</pre>"

    return render_template("excusas.html")

if __name__ == "__main__":
    app.run(debug=True)
