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


def cargar_datos():
    """
    Carga el Excel de registros. Si no existe, crea uno nuevo.
    Si encuentra una columna antigua 'PPI', la renombra a 'CHECK LIST'.
    """
    path = Path(EXCEL_FILE)
    if path.exists():
        df = pd.read_excel(path)

        # Migración: si el Excel antiguo tiene PPI y no CHECK LIST, renombrar
        if "PPI" in df.columns and "CHECK LIST" not in df.columns:
            df = df.rename(columns={"PPI": "CHECK LIST"})
            guardar_datos(df)

        return df
    else:
        columnas = [
            "ID trabajador",
            "Trabajador",  # nombre
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


def guardar_datos(df):
    df.to_excel(EXCEL_FILE, index=False)


def obtener_trabajador_desde_pin(pin_introducido: str):
    pin_introducido = pin_introducido.strip()
    return TRABAJADORES.get(pin_introducido)


# ----------- PANTALLA LOGIN (PIN, ESTILO GRANDE PARA MÓVIL) ------------
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


# ----------- FORMULARIO PRINCIPAL (SOLO SI YA HAY TRABAJADOR EN SESIÓN) ------------
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

      .link-resumen:hover, .link-logout:hover {
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

      .worker-banner {
        margin-top: 4px;
        font-size: 0.95rem;
        color: #111827;
        font-weight: bold;
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
        <a href="{{ url_for('resumen') }}" class="link-resumen">📊 Resumen</a>
        <a href="{{ url_for('logout') }}" class="link-logout">⏻ Salir</a>
      </div>

      <div class="card">

        <div class="header">
          <img src="{{ url_for('static', filename='logo_atm.png') }}" alt="ATM España" class="logo">
          <div class="title-block">
            <span class="app-title">ATM España</span>
            <span class="app-subtitle">Registro de montaje · Parque solar</span>
            {% if trabajador_nombre %}
              <span class="worker-banner">👷 Trabajador: {{ trabajador_nombre }}</span>
            {% endif %}
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

          <label>CHECK LIST:
            <select name="check_list">
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
        <h3>Todos los registros</h3>
        {% if ultimos %}
          <table>
            <tr>
              <th>Fecha</th>
              <th>Hora inicio</th>
              <th>Hora fin</th>
              <th>ID</th>
              <th>Trabajador</th>
              <th>CT</th>
              <th>Campo/Área</th>
              <th>Nº Mesa</th>
              <th>Par apriete</th>
              <th>CHECK LIST</th>
              <th>Observaciones</th>
            </tr>
            {% for r in ultimos %}
              <tr>
                <td>{{ r["Fecha"] }}</td>
                <td>{{ r["Hora inicio"] }}</td>
                <td>{{ r["Hora fin"] }}</td>
                <td>{{ r["ID trabajador"] }}</td>
                <td>{{ r["Trabajador"] }}</td>
                <td>{{ r["CT"] }}</td>
                <td>{{ r["Campo/Área"] }}</td>
                <td>{{ r["Nº Mesa"] }}</td>
                <td>{{ r["Par de apriete"] }}</td>
                <td>{{ r["CHECK LIST"] }}</td>
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

@app.route("/login", methods=["GET", "POST"])
def login():
    # Siempre pedimos PIN al entrar (aunque ya hubiera sesión previa)
    if request.method == "POST":
        pin = request.form.get("pin", "")
        trabajador_info = obtener_trabajador_desde_pin(pin)
        if trabajador_info is None:
            flash("PIN incorrecto. Inténtalo de nuevo.", "error")
            return redirect(url_for("login"))

        # Guardar en sesión
        session["trabajador_id"] = trabajador_info["id"]
        session["trabajador_nombre"] = trabajador_info["nombre"]

        flash(f"Bienvenido, {trabajador_info['nombre']}.", "msg")
        return redirect(url_for("formulario"))

    # Si hubiera sesión previa, la borramos para obligar a nuevo PIN
    session.clear()
    return render_template_string(HTML_LOGIN)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada. Introduce tu PIN para continuar.", "msg")
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
def formulario():
    # Si no hay trabajador en sesión, enviar siempre a login
    if "trabajador_id" not in session or "trabajador_nombre" not in session:
        return redirect(url_for("login"))

    trabajador_id = session["trabajador_id"]
    trabajador_nombre = session["trabajador_nombre"]

    if request.method == "POST":
        hora_inicio = request.form.get("hora_inicio", "")
        hora_fin = request.form.get("hora_fin", "")
        ct = request.form.get("ct", "")
        campo = request.form.get("campo", "")
        mesa = request.form.get("mesa", "")
        par_apriete = request.form.get("par_apriete", "")
        check_list = request.form.get("check_list", "")
        observaciones = request.form.get("observaciones", "")

        # Si no viene hora_fin (por si fallara el JS), la ponemos aquí
        if not hora_fin:
            hora_fin = datetime.now().strftime("%H:%M")
        # Si no viene hora_inicio, igualarla a hora_fin
        if not hora_inicio:
            hora_inicio = hora_fin

        # Validación numérica de CT / Campo / Mesa
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
            "ID trabajador": trabajador_id,
            "Trabajador": trabajador_nombre,
            "Fecha": hoy,
            "Hora inicio": hora_inicio,
            "Hora fin": hora_fin,
            "CT": ct_int,
            "Campo/Área": campo_int,
            "Nº Mesa": mesa_int,
            "Par de apriete": par_apriete,
            "CHECK LIST": check_list,
            "Observaciones": observaciones,
        }

        df = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
        guardar_datos(df)

        flash(
            f"✅ Registro guardado correctamente para {trabajador_nombre}.",
            "msg",
        )
        return redirect(url_for("formulario"))

    # GET — mostrar formulario
    cts = list(range(1, MAX_CT + 1))
    campos = list(range(1, MAX_CAMPO + 1))
    mesas = list(range(1, MAX_MESA + 1))

    return render_template_string(
        HTML_FORM,
        cts=cts,
        campos=campos,
        mesas=mesas,
        trabajador_nombre=trabajador_nombre,
    )


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

    # Producción por día (últimos 10 días con registros)
    prod_dia_df = (
        df.groupby("Fecha")
        .size()
        .reset_index(name="Registros")
        .sort_values("Fecha", ascending=False)
        .head(10)
        .sort_values("Fecha", ascending=True)
    )
    prod_dia = prod_dia_df.to_dict(orient="records")

    # TODOS los registros, ordenados del más antiguo al más reciente
    try:
        ultimos_df = df.sort_values(["Fecha", "Hora inicio"], ascending=[True, True])
    except Exception:
        ultimos_df = df.sort_values("Fecha", ascending=True)

    ultimos = ultimos_df.to_dict(orient="records")

    return render_template_string(
        HTML_RESUMEN,
        total_registros=total_registros,
        prod_dia=prod_dia,
        ultimos=ultimos,
    )


if __name__ == "__main__":
    app.run(debug=True)




