from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    render_template_string,
    session,
)
from datetime import date, datetime
from pathlib import Path
import pandas as pd

# -------- CONFIGURACIÓN --------
EXCEL_FILE = "registro_montaje.xlsx"
TRABAJADORES_FILE = "TRABAJADORES PIN.xlsx"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000


def cargar_trabajadores():
    """
    Lee el archivo TRABAJADORES PIN.xlsx y construye
    un diccionario PIN -> {id, nombre}.
    """
    path = Path(TRABAJADORES_FILE)
    if not path.exists():
        print(
            f"⚠ AVISO: No se encontró el archivo {TRABAJADORES_FILE}. "
            "Todos los PIN serán inválidos hasta que exista."
        )
        return {}

    df = pd.read_excel(path)

    mapping = {}
    for _, row in df.iterrows():
        pin_val = str(row["PIN"]).strip()
        nombre = str(row["NOMBRE"]).strip()
        try:
            trabajador_id = int(row["ID"])
        except Exception:
            trabajador_id = None

        mapping[pin_val] = {
            "id": trabajador_id,
            "nombre": nombre,
        }

    print(f"✔ Cargados {len(mapping)} trabajadores desde {TRABAJADORES_FILE}")
    return mapping


TRABAJADORES = cargar_trabajadores()

app = Flask(__name__)
app.secret_key = "cambia_estO_por_algo_mas_largo_y_raro"


# ------------ DATOS PRINCIPALES (ESTADO ACTUAL) ------------
def cargar_datos():
    path = Path(EXCEL_FILE)
    if not path.exists():
        columnas = [
            "ID trabajador",
            "Trabajador",
            "Fecha",
            "Hora inicio",
            "Hora fin",
            "CT",
            "Campo/Área",
            "Nº Mesa",
            "Par de apriete",
            "CHECK LIST",
            "Observaciones",
        ]
        return pd.DataFrame(columns=columnas)

    df = pd.read_excel(path)

    # Compatibilidad antigua: renombrar PPI a CHECK LIST si hace falta
    if "PPI" in df.columns and "CHECK LIST" not in df.columns:
        df = df.rename(columns={"PPI": "CHECK LIST"})

    columnas_objetivo = [
        "ID trabajador",
        "Trabajador",
        "Fecha",
        "Hora inicio",
        "Hora fin",
        "CT",
        "Campo/Área",
        "Nº Mesa",
        "Par de apriete",
        "CHECK LIST",
        "Observaciones",
    ]

    for col in columnas_objetivo:
        if col not in df.columns:
            df[col] = ""

    return df[columnas_objetivo]


def guardar_datos(df):
    df.to_excel(EXCEL_FILE, index=False)


def obtener_trabajador_desde_pin(pin_introducido: str):
    pin_introducido = pin_introducido.strip()
    return TRABAJADORES.get(pin_introducido)


# ----------- LOGIN ------------
HTML_LOGIN = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso trabajador - ATM España</title>
    <style>
      :root {
        --atm-red: #e30613;
        --atm-red-dark: #c40010;
        --atm-gray-bg: #f9fafb;
        --atm-border: #e5e7eb;
      }
      * { box-sizing: border-box; }
      body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 0;
        background: var(--atm-gray-bg);
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .container {
        width: 100%;
        max-width: 420px;
        padding: 16px;
      }
      .card {
        background: #ffffff;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15);
        padding: 22px 18px 26px 18px;
        border: 1px solid var(--atm-border);
      }
      .header {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        margin-bottom: 14px;
      }
      .logo {
        height: 60px;
        width: auto;
      }
      .title {
        font-size: 1.2rem;
        font-weight: bold;
        color: var(--atm-red);
        text-align: center;
      }
      .subtitle {
        font-size: 0.95rem;
        text-align: center;
        color: #4b5563;
      }
      form {
        margin-top: 18px;
      }
      label {
        display: block;
        font-size: 1.0rem;
        color: #111827;
        margin-bottom: 6px;
        text-align: center;
      }
      input[type="password"] {
        width: 100%;
        padding: 16px;
        font-size: 1.3rem;
        text-align: center;
        letter-spacing: 0.25em;
        border-radius: 14px;
        border: 1px solid var(--atm-border);
      }
      input[type="password"]:focus {
        outline: 2px solid var(--atm-red);
        border-color: var(--atm-red);
      }
      button {
        margin-top: 22px;
        width: 100%;
        padding: 16px;
        font-size: 1.2rem;
        background: var(--atm-red);
        color: white;
        border: none;
        border-radius: 999px;
        font-weight: bold;
      }
      button:active {
        transform: scale(0.98);
        background: var(--atm-red-dark);
      }
      .msg {
        margin-top: 12px;
        color: #16a34a;
        font-size: 0.95rem;
        text-align: center;
      }
      .error {
        margin-top: 12px;
        color: #dc2626;
        font-size: 0.95rem;
        text-align: center;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="card">
        <div class="header">
          <img src="{{ url_for('static', filename='logo_atm.png') }}" alt="ATM España" class="logo">
          <div class="title">ATM España</div>
          <div class="subtitle">Identifícate con tu PIN para registrar trabajos</div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="post">
          <label>PIN trabajador</label>
          <input type="password" name="pin" inputmode="numeric" pattern="[0-9]*" required>
          <button type="submit">Entrar</button>
        </form>
      </div>
    </div>
  </body>
</html>
"""


# ----------- FORMULARIO PRINCIPAL ------------
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

      * { box-sizing: border-box; }

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
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        font-size: 0.9rem;
      }

      .link-resumen, .link-logout {
        color: var(--atm-red);
        text-decoration: none;
        font-weight: bold;
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
        margin-bottom: 8px;
      }

      .logo {
        height: 40px;
        width: auto;
      }

      .worker-banner {
        font-size: 1.05rem;
        font-weight: bold;
        color: #111827;
      }

      label {
        display: block;
        margin-top: 14px;
        font-size: 1.02rem;
        color: #111827;
      }

      input, select, textarea {
        width: 100%;
        padding: 12px;
        margin-top: 6px;
        font-size: 1.0rem;
        border-radius: 10px;
        border: 1px solid var(--atm-border);
      }

      input:focus, select:focus, textarea:focus {
        outline: 2px solid var(--atm-red);
        border-color: var(--atm-red);
      }

      textarea {
        resize: vertical;
        min-height: 80px;
      }

      button {
        padding: 12px;
        font-size: 1.1rem;
        background: var(--atm-red);
        color: white;
        border: none;
        border-radius: 999px;
        font-weight: bold;
        width: 100%;
        margin-top: 20px;
      }

      .time-row {
        display: flex;
        gap: 8px;
      }

      .time-row button {
        width: auto;
        padding-inline: 10px;
        font-size: 0.9rem;
        border-radius: 999px;
      }

      .msg {
        margin-top: 10px;
        color: #16a34a;
        font-size: 0.9rem;
      }

      .error {
        margin-top: 10px;
        color: #dc2626;
        font-size: 0.9rem;
      }
    </style>

    <script>
      function horaActual() {
        const d = new Date();
        return String(d.getHours()).padStart(2, '0') + ":" + String(d.getMinutes()).padStart(2, '0');
      }
      function marcarInicio() {
        document.getElementById('hora_inicio').value = horaActual();
      }
      function marcarFin() {
        document.getElementById('hora_fin').value = horaActual();
      }
    </script>

  </head>
  <body>
    <div class="container">

      <div class="top-nav">
        <a href="{{ url_for('resumen') }}" class="link-resumen">📊 Resumen</a>
        <a href="{{ url_for('logout') }}" class="link-logout">⏻ Salir</a>
      </div>

      <div class="card">

        <div class="header">
          <img src="{{ url_for('static', filename='logo_atm.png') }}" class="logo">
          {% if trabajador_nombre %}
            <span class="worker-banner">👷 {{ trabajador_nombre }}</span>
          {% endif %}
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="post" id="form-registro">

          <label>Hora inicio:
            <div class="time-row">
              <input type="text" name="hora_inicio" id="hora_inicio" readonly>
              <button type="button" onclick="marcarInicio()">Marcar inicio</button>
            </div>
          </label>

          <label>Hora fin:
            <div class="time-row">
              <input type="text" name="hora_fin" id="hora_fin" readonly>
              <button type="button" onclick="marcarFin()">Marcar fin</button>
            </div>
          </label>

          <label>CT:
            <select name="ct">
              {% for i in cts %}<option value="{{ i }}">{{ i }}</option>{% endfor %}
            </select>
          </label>

          <label>Campo / Área:
            <select name="campo">
              {% for i in campos %}<option value="{{ i }}">{{ i }}</option>{% endfor %}
            </select>
          </label>

          <label>Nº Mesa:
            <select name="mesa">
              {% for i in mesas %}<option value="{{ i }}">{{ i }}</option>{% endfor %}
            </select>
          </label>

          <label>Par de apriete:
            <select name="par_apriete">
              <option value="OK">OK</option>
              <option value="NO OK">NO OK</option>
            </select>
          </label>

          <label>CHECK LIST:
            <select name="check_list">
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

    </div>
  </body>
</html>
"""


# ----------- RESUMEN ------------
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

      body {
        font-family: Arial;
        background: var(--atm-gray-bg);
        margin: 0;
        padding: 0;
      }

      .container {
        max-width: 1100px;
        margin: 0 auto;
        padding: 16px;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        margin-top: 15px;
      }

      th, td {
        border: 1px solid var(--atm-border);
        padding: 6px;
        text-align: center;
      }

      th {
        background: #f3f4f6;
      }

      .top-nav {
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
      }

      .link {
        color: var(--atm-red);
        text-decoration: none;
        font-weight: bold;
      }

      h2, h3 {
        margin-top: 10px;
      }
    </style>
  </head>

  <body>
    <div class="container">

      <div class="top-nav">
        <a href="{{ url_for('formulario') }}" class="link">⬅ Volver</a>
        <img src="{{ url_for('static', filename='logo_atm.png') }}" height="35">
      </div>

      <h2>Resumen total del proyecto</h2>
      <p>Total de registros: <strong>{{ total_registros }}</strong></p>

      <h3>Producción por día (todos los días)</h3>
      <table>
        <tr>
          <th>Fecha</th>
          <th>Registros</th>
        </tr>
        {% for fila in prod_dia %}
        <tr>
          <td>{{ fila["Fecha"] }}</td>
          <td>{{ fila["Registros"] }}</td>
        </tr>
        {% endfor %}
      </table>

      <h3>Todos los registros del proyecto</h3>
      <table>
        <tr>
          <th>Fecha</th>
          <th>Inicio</th>
          <th>Fin</th>
          <th>ID</th>
          <th>Trabajador</th>
          <th>CT</th>
          <th>Campo</th>
          <th>Mesa</th>
          <th>Par apriete</th>
          <th>CHECK LIST</th>
          <th>Observaciones</th>
        </tr>
        {% for r in registros %}
        <tr>
          <td>{{ r["Fecha"] }}</td


