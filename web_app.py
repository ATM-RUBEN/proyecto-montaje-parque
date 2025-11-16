from flask import Flask, request, redirect, url_for, flash, render_template_string
from datetime import date
from pathlib import Path
import pandas as pd

# -------- CONFIGURACIÓN --------
EXCEL_FILE = "registro_montaje.xlsx"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

# PIN asociados a cada trabajador
TRABAJADORES_PIN = {
    "1": "1111",
    "2": "2222",
    "3": "3333",
    "4": "4444",
}

app = Flask(__name__)
app.secret_key = "cambia_estO_por_algo_mas_largo_y_raro"


def cargar_datos():
    path = Path(EXCEL_FILE)
    if path.exists():
        return pd.read_excel(path)
    else:
        columnas = [
            "Trabajador",
            "Fecha",
            "CT",
            "Campo/Área",
            "Nº Mesa",
            "Par de apriete",
            "PPI",
            "Observaciones",
        ]
        return pd.DataFrame(columns=columnas)


def guardar_datos(df):
    df.to_excel(EXCEL_FILE, index=False)


def obtener_trabajador_desde_pin(pin_introducido: str):
    pin_introducido = pin_introducido.strip()
    for num_trabajador, pin_correcto in TRABAJADORES_PIN.items():
        if pin_introducido == pin_correcto:
            return int(num_trabajador)
    return None


# ----------- FORMULARIO HTML ADAPTADO A MÓVIL (CUADROS GRANDES) ------------
HTML_FORM = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Registro de montaje</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 0;
        background: #f3f4f6;
      }
      .container {
        max-width: 480px;
        margin: 0 auto;
        padding: 18px;
      }
      h2 {
        font-size: 1.5rem;
        text-align: center;
        margin-bottom: 18px;
      }
      label {
        display: block;
        margin-top: 18px;
        font-size: 1.1rem;
      }
      input, select, textarea {
        width: 100%;
        padding: 16px;
        margin-top: 6px;
        font-size: 1.15rem;
        border-radius: 10px;
        border: 1px solid #cbd5e1;
      }
      textarea {
        resize: vertical;
        min-height: 100px;
      }
      button {
        margin-top: 24px;
        padding: 16px;
        width: 100%;
        font-size: 1.2rem;
        background: #2563eb;
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: bold;
      }
      button:active {
        transform: scale(0.98);
      }
      .msg {
        margin-top: 10px;
        color: #16a34a;
        font-size: 1rem;
      }
      .error {
        margin-top: 10px;
        color: #dc2626;
        font-size: 1rem;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <h2>Registro de montaje - Parque solar</h2>

      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class="{{ category }}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <form method="post">

        <label>PIN trabajador:
          <input type="password" name="pin" required>
        </label>

        <label>CT (Centro de Transformación):
          <select name="ct">
            {% for i in cts %}
              <option value="{{ i }}">{{ i }}</option>
            {% endfor %}
          </select>
        </label>

        <label>Campo / Área:
          <select name="campo">
            {% for i in campos %}
              <option value="{{ i }}">{{ i }}</option>
            {% endfor %}
          </select>
        </label>

        <label>Nº Mesa:
          <select name="mesa">
            {% for i in mesas %}
              <option value="{{ i }}">{{ i }}</option>
            {% endfor %}
          </select>
        </label>

        <label>Par de apriete:
          <select name="par_apriete">
            <option value="OK">OK</option>
            <option value="NO OK">NO OK</option>
          </select>
        </label>

        <label>PPI:
          <select name="ppi">
            <option value="OK">OK</option>
            <option value="NO OK">NO OK</option>
          </select>
        </label>

        <label>Observaciones:
          <textarea name="observaciones"></textarea>
        </label>

        <button type="submit">Guardar registro</button>
      </form>
    </div>
  </body>
</html>
"""


# -------------------------- LÓGICA FLASK -------------------------------
@app.route("/", methods=["GET", "POST"])
def formulario():

    if request.method == "POST":
        pin = request.form.get("pin", "")
        ct = request.form.get("ct", "")
        campo = request.form.get("campo", "")
        mesa = request.form.get("mesa", "")
        par_apriete = request.form.get("par_apriete", "")
        ppi = request.form.get("ppi", "")
        observaciones = request.form.get("observaciones", "")

        # Validación del PIN
        trabajador = obtener_trabajador_desde_pin(pin)
        if trabajador is None:
            flash("PIN incorrecto. No se ha guardado el registro.", "error")
            return redirect(url_for("formulario"))

        # Validación numérica
        try:
            ct_int = int(ct)
            campo_int = int(campo)
            mesa_int = int(mesa)
        except ValueError:
            flash("CT, Campo y Mesa deben ser números válidos.", "error")
            return redirect(url_for("formulario"))

        hoy = date.today()
        df = cargar_datos()

        nuevo_registro = {
            "Trabajador": trabajador,
            "Fecha": hoy,
            "CT": ct_int,
            "Campo/Área": campo_int,
            "Nº Mesa": mesa_int,
            "Par de apriete": par_apriete,
            "PPI": ppi,
            "Observaciones": observaciones,
        }

        df = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
        guardar_datos(df)

        flash(f"✅ Registro guardado correctamente para el trabajador {trabajador}.", "msg")
        return redirect(url_for("formulario"))

    # GET — mostrar formulario
    cts = list(range(1, MAX_CT + 1))
    campos = list(range(1, MAX_CAMPO + 1))
    mesas = list(range(1, MAX_MESA + 1))

    return render_template_string(HTML_FORM, cts=cts, campos=campos, mesas=mesas)


if __name__ == "__main__":
    app.run(debug=True)
