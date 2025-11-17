from flask import Flask, request, redirect, url_for, flash, render_template_string
from datetime import date, datetime
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
            "Hora inicio",
            "Hora fin",
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


# ----------- FORMULARIO HTML CON LOGO ATM Y COLORES CORPORATIVOS ------------
HTML_FORM = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Registro de montaje - ATM España</title>
    <style>
      :root {
        --atm-red: #e30613;
        --atm-red-dark: #c40010;
        --atm-gray-bg: #f9fafb;
        --atm-border: #e5e7eb;
      }

      * {
        box-sizing: border-box;
      }

      body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 0;
        background: var(--atm-gray-bg);
      }

      .container {
        max-width: 480px;
        margin: 0 auto;
        padding: 16px;
      }

      .top-nav {
        text-align: right;
        margin-bottom: 8px;
        font-size: 0.9rem;
      }

      .link-resumen {
        color: var(--atm-red);
        text-decoration: none;
        font-weight: bold;
      }

      .link-resumen:hover {
        text-decoration: underline;
      }

      .card {
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
        padding: 18px 16px 22px 16px;
        border: 1px solid var(--atm-border);
      }

      .header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
      }

      .logo {
        height: 40px;
        width: auto;
      }

      .title-block {
        display: flex;
        flex-direction: column;
      }

      .app-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: var(--atm-red);
        line-height: 1.1;
      }

      .app-subtitle {
        font-size: 0.90rem;
        color: #4b5563;
      }

      .section-title {
        margin-top: 6px;
        font-size: 0.95rem;
        color: #6b7280;
      }

      label {
        display: block;
        margin-top: 16px;
        font-size: 1.02rem;
        color: #111827;
      }

      input, select, textarea {
        width: 100%;
        padding: 14px;
        margin-top: 6px;
        font-size: 1.05rem;
        border-radius: 10px;
        border: 1px solid var(--atm-border);
      }

      input:focus, select:focus, textarea:focus {
        outline: 2px solid var(--atm-red);
        border-color: var(--atm-red);
      }

      textarea {
        resize: vertical;
        min-height: 90px;
      }

      button {
        padding: 12px 16px;
        font-size: 1.0rem;
        background: var(--atm-red);
        color: white;
        border: none;
        border-radius: 999px;
        font-weight: bold;
        cursor: pointer;
      }

      button:active {
        transform: scale(0.98);
        background: var(--atm-red-dark);
      }

      .btn-guardar {
        margin-top: 22px;
        width: 100%;
        font-size: 1.1rem;
      }

      .time-row {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .time-row input {
        flex: 1;
      }

      .btn-time {
        white-space: nowrap;
        padding-inline: 12px;
        font-size: 0.9rem;
      }

      .msg {
        margin-top: 12px;
        color: #16a34a;
        font-size: 0.95rem;
      }

      .error {
        margin-top: 12px;
        color: #dc2626;
        font-size: 0.95rem;
      }
    </style>
    <script>
      function horaActual() {
        const d = new Date();
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        return hh + ":" + mm;
      }

      function marcarInicio() {
        document.getElementById('hora_inicio').value = horaActual();
      }

      function marcarFin() {
        document.getElementById('hora_fin').value = horaActual();
      }

      window.addEventListener('DOMContentLoaded', function() {
        const form = document.getElementById('form-registro');
        form.addEventListener('submit', function() {
          const fin = document.getElementById('hora_fin');
          const inicio = document.getElementById('hora_inicio');
          if (!fin.value) {
            fin.value = horaActual();   // si no han marcado fin, se pone al guardar
          }
          if (!inicio.value) {
            inicio.value = fin.value;   // si tampoco hay inicio, se iguala a la hora de fin
          }
        });
      });
    </script>
  </head>
  <body>
    <div class="container">

      <div class="top-nav">
        <a href="{{ url_for('resumen') }}" class="link-resumen">📊 Ver resumen e informes</a>
      </div>

      <div class="card">

        <div class="header">
          <img src="{{ url_for('static', filename='logo_atm.png') }}" alt="ATM España" class="logo">
          <div class="title-block">
            <span class="app-title">ATM España</span>
            <span class="app-subtitle">Registro de montaje · Parque solar</span>
          </div>
        </div>

        <p class="section-title">Introduce los datos del montaje en campo.</p>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="post" id="form-registro">

          <label>PIN trabajador:
            <input type="password" name="pin" required>
          </label>

          <label>Hora inicio:
            <div class="time-row">
              <input type="text" name="hora_inicio" id="hora_inicio" readonly>
              <button type="button" class="btn-time" onclick="marcarInicio()">Marcar inicio</button>
            </div>
          </label>

          <label>Hora fin:
            <div class="time-row">
              <input type="text" name="hora_fin" id="hora_fin" readonly>
              <button type="button" class="btn-time" onclick="marcarFin()">Marcar fin</button>
            </div>
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

          <button type="submit" class="btn-guardar">Guardar registro</button>

        </form>
      </div>
    </div>
  </body>
</html>
"""


# ----------- PÁGINA DE RESUMEN / INFORMES ----------------
HTML_RESUMEN = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resumen de montaje - ATM España</title>
    <style>
      :root {
        --atm-red: #e30613;
        --atm-gray-bg: #f9fafb;
        --atm-border: #e5e7eb;
      }
      * { box-sizing: border-box; }
      body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 0;
        background: var(--atm-gray-bg);
      }
      .container {
        max-width: 900px;
        margin: 0 auto;
        padding: 16px;
      }
      .top-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        font-size: 0.9rem;
      }
      .link-resumen {
        color: var(--atm-red);
        text-decoration: none;
        font-weight: bold;
      }
      .link-resumen:hover {
        text-decoration: underline;
      }
      .logo {
        height: 34px;
        width: auto;
      }
      .card {
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
        padding: 18px 16px 22px 16px;
        border: 1px solid var(--atm-border);
        margin-bottom: 16px;
      }
      h2 {
        font-size: 1.3rem;
        margin: 0 0 6px 0;
      }
      h3 {
        font-size: 1.05rem;
        margin-top: 0;
      }
      .kpi {
        font-size: 1.2rem;
        font-weight: bold;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
      }
      th, td {
        border: 1px solid var(--atm-border);
        padding: 6px 4px;
        text-align: center;
      }
      th {
        background: #f3f4f6;
      }
      @media (max-width: 600px) {
        table {
          font-size: 0.75rem;
        }
      }
    </style>
  </head>
  <body>
    <div class="container">

      <div class="top-nav">
        <a href="{{ url_for('formulario') }}" class="link-resumen">⬅ Volver al registro</a>
        <img src="{{ url_for('static', filename='logo_atm.png') }}" alt="ATM España" class="logo">
      </div>

      <div class="card">
        <h2>Resumen de montaje</h2>
        <p>Total de registros: <span class="kpi">{{ total_registros }}</span></p>
        {% if prod_dia %}
          <h3>Producción por día (últimos días con registros)</h3>
          <table>
            <tr>
              <th>Fecha</th>
              <th>Nº de registros</th>
            </tr>
            {% for fila in prod_dia %}
              <tr>
                <td>{{ fila["Fecha"] }}</td>
                <td>{{ fila["Registros"] }}</td>
              </tr>
            {% endfor %}
          </table>
        {% else %}
          <p>Aún no hay datos para resumir.</p>
        {% endif %}
      </div>

      <div class="card">
        <h3>Últimos 50 registros</h3>
        {% if ultimos %}
          <table>
            <tr>
              <th>Fecha</th>
              <th>Hora inicio</th>
              <th>Hora fin</th>
              <th>Trabajador</th>
              <th>CT</th>
              <th>Campo/Área</th>
              <th>Nº Mesa</th>
              <th>Par apriete</th>
              <th>PPI</th>
              <th>Observaciones</th>
            </tr>
            {% for r in ultimos %}
              <tr>
                <td>{{ r["Fecha"] }}</td>
                <td>{{ r["Hora inicio"] }}</td>
                <td>{{ r["Hora fin"] }}</td>
                <td>{{ r["Trabajador"] }}</td>
                <td>{{ r["CT"] }}</td>
                <td>{{ r["Campo/Área"] }}</td>
                <td>{{ r["Nº Mesa"] }}</td>
                <td>{{ r["Par de apriete"] }}</td>
                <td>{{ r["PPI"] }}</td>
                <td>{{ r["Observaciones"] }}</td>
              </tr>
            {% endfor %}
          </table>
        {% else %}
          <p>No hay registros todavía.</p>
        {% endif %}
      </div>

    </div>
  </body>
</html>
"""


# -------------------------- RUTAS FLASK -------------------------------
@app.route("/", methods=["GET", "POST"])
def formulario():
    if request.method == "POST":
        pin = request.form.get("pin", "")
        hora_inicio = request.form.get("hora_inicio", "")
        hora_fin = request.form.get("hora_fin", "")
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

        # Si no viene hora_fin (por si fallara el JS), la ponemos aquí
        if not hora_fin:
            hora_fin = datetime.now().strftime("%H:%M")
        # Si no viene hora_inicio, igualarla a hora_fin
        if not hora_inicio:
            hora_inicio = hora_fin

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
            "Hora inicio": hora_inicio,
            "Hora fin": hora_fin,
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


@app.route("/resumen")
def resumen():
    df = cargar_datos()
    total_registros = len(df)

    if total_registros == 0:
        return render_template_string(
            HTML_RESUMEN,
            total_registros=0,
            prod_dia=[],
            ultimos=[],
        )

    df = df.copy()
    df["Fecha"] = df["Fecha"].astype(str)

    prod_dia_df = (
        df.groupby("Fecha")
        .size()
        .reset_index(name="Registros")
        .sort_values("Fecha", ascending=False)
        .head(10)
    )
    prod_dia = prod_dia_df.to_dict(orient="records")

    ultimos_df = df.sort_index(ascending=False).head(50)
    ultimos_df = ultimos_df.iloc[::-1]
    ultimos = ultimos_df.to_dict(orient="records")

    return render_template_string(
        HTML_RESUMEN,
        total_registros=total_registros,
        prod_dia=prod_dia,
        ultimos=ultimos,
    )


if __name__ == "__main__":
    app.run(debug=True)

