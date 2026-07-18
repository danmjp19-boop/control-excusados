import os
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "control_excusados_2026"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    cai = db.Column(db.String(50), nullable=False)


with app.app_context():
    db.drop_all()
    db.create_all()

    if Usuario.query.filter_by(usuario="admin").first() is None:
        admin = Usuario(
            usuario="admin",
            password="123456",
            rol="Administrador",
            cai="SUBA"
        )
        db.session.add(admin)
        db.session.commit()


@app.route("/", methods=["GET", "POST"])
def login():
    return render_template("login.html")


if __name__ == "__main__":
    app.run(debug=True)
