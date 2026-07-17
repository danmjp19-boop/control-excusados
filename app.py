from flask import Flask

app = Flask(__name__)

@app.route("/")
def inicio():
    return "<h1>Sistema de Control de Personal Excusado</h1><p>Aplicación funcionando correctamente.</p>"

if __name__ == "__main__":
    app.run(debug=True)
