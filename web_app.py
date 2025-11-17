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
AUDIT_FILE = "auditoria_cambios.xlsx"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000


def cargar_trabajadores():
    """
    Lee el archivo TRABAJADORES PIN.xlsx y construye
    un diccionario PIN -> {id, nombre, rol}.
    El rol se lee de la columna 'ROL' (admin, jefe_obra, trabajador...).
    Si no hay rol, se asume 'trabajador'.
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
    tiene_col_rol = "ROL" in df.columns

    for _, row in df.iterrows():
        pin_val = str(row["PIN"]).strip()
        nombre = str(row["NOMBRE"]).strip()
        try:
            trabajador_id = int(row["ID"])
        except Exception:
            trabajador_id = None

        rol = "trabajador"
        if tiene_col_rol:
            valor_rol = row.get("ROL", None)
            if pd.notna(valor_rol):
                rol = str(valor_rol).strip().lower()

        mapping[pin_val] = {
            "id": trabajador_id,
            "nombre": nombre,
            "rol": rol,
        }

    print(f"✔ Cargados {len(mapping)} trabajadores desde {TRABAJADORES_FILE}")
    return mapping


TRABAJADORES = cargar_trabajadores()

app = Flask(__name__)
app.secret_key = "cambia_estO_por_algo_mas_largo_y_raro"


# ------------ DATOS PRINCIPALES ------------
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


def guardar_auditoria(lista_cambios):
    """
    Guarda en AUDIT_FILE la lista de cambios realizados.
    Cada elemento de lista_cambios es un diccionario con:
    - Fecha cambio
    - Hora cambio
    - ID editor
    - Editor
    - Rol editor
    - Row ID
    - CT
    - Campo/Área
    - Nº Mesa
    - Campo modificado
    - Valor anterior
    - Valor nuevo
    """
    path = Path(AUDIT_FILE)
    if path.exists():
        df_a = pd.read_excel(path)
    else:
        df_a = pd.DataFrame(
            columns=[
                "Fecha cambio",
                "Hora cambio",
                "ID editor",
                "Editor",
                "Rol editor",
                "Row ID",
                "CT",
                "Campo/Área",
                "Nº Mesa",
                "Campo modificado",
                "Valor anterior",
                "Valor nuevo",
            ]
        )

    df_nuevos = pd.DataFrame(lista_cambios)
    df_final = pd.concat([df_a, df_nuevos], ignore_index=True)
    df_final.to_excel(AUDIT_FILE, index=False)


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
          <div>
            {% if trabajador_nombre %}
              <div class="worker-banner">👷 {{ trabajador_nombre }}</div>
            {% endif %}
            {% if rol %}
              <div style="font-size:0.8rem; color:#6b7280;">
                {% if rol == 'admin' %}
                  👑 Administrador
                {% elif rol == 'jefe_obra' %}
                  📋 Jefe de obra
                {% else %}
                  🔧 Trabajador
                {% endif %}
              </div>
            {% endif %}
          </div>
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

      .btn-editar {
        color: var(--atm-red);
        text-decoration: none;
        font-weight: bold;
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
      <p>Total de registros visibles: <strong>{{ total_registros }}</strong></p>

      <h3>Producción por día (todos los días visibles)</h3>
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

      <h3>Registros detallados</h3>
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
          {% if puede_editar %}
            <th>Acciones</th>
          {% endif %}
        </tr>
        {% for r in registros %}
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
          {% if puede_editar %}
            <td>
              <a href="{{ url_for('editar_registro', row_id=r['row_id']) }}" class="btn-editar">
                ✏️ Editar
              </a>
            </td>
          {% endif %}
        </tr>
        {% endfor %}
      </table>

    </div>
  </body>
</html>
"""


# ----------- PANTALLA EDICIÓN ------------
HTML_EDITAR = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editar registro - ATM España</title>
    <style>
      :root {
        --atm-red: #e30613;
        --atm-gray-bg: #f9fafb;
        --atm-border: #e5e7eb;
      }
      body {
        font-family: Arial, sans-serif;
        background: var(--atm-gray-bg);
        margin: 0;
        padding: 0;
      }
      .container {
        max-width: 480px;
        margin: 0 auto;
        padding: 16px;
      }
      .card {
        background: #ffffff;
        border-radius: 16px;
        padding: 18px 16px 22px 16px;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
        border: 1px solid var(--atm-border);
      }
      h2 {
        margin-top: 0;
        margin-bottom: 10px;
      }
      label {
        display: block;
        margin-top: 12px;
        font-size: 0.95rem;
        color: #111827;
      }
      input, select, textarea {
        width: 100%;
        padding: 10px;
        margin-top: 4px;
        font-size: 0.95rem;
        border-radius: 8px;
        border: 1px solid var(--atm-border);
      }
      input[readonly] {
        background: #f3f4f6;
      }
      textarea {
        resize: vertical;
        min-height: 70px;
      }
      button {
        margin-top: 18px;
        width: 100%;
        padding: 12px;
        font-size: 1rem;
        background: var(--atm-red);
        color: white;
        border: none;
        border-radius: 999px;
        font-weight: bold;
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
      .info {
        font-size: 0.85rem;
        color: #6b7280;
        margin-top: 6px;
      }
      .error {
        margin-top: 10px;
        color: #dc2626;
        font-size: 0.9rem;
      }
      .msg {
        margin-top: 10px;
        color: #16a34a;
        font-size: 0.9rem;
      }
    </style>
  </head>
  <body>
    <div class="container">

      <div class="top-nav">
        <a href="{{ url_for('resumen') }}" class="link">⬅ Volver al resumen</a>
        <img src="{{ url_for('static', filename='logo_atm.png') }}" height="30">
      </div>

      <div class="card">
        <h2>Editar registro</h2>

        <div class="info">
          CT {{ reg["CT"] }} · Campo {{ reg["Campo/Área"] }} · Mesa {{ reg["Nº Mesa"] }}<br>
          Fecha: {{ reg["Fecha"] }} · Trabajador: {{ reg["Trabajador"] }}
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="post">
          <label>Par de apriete:
            <select name="par_apriete">
              <option value="OK" {% if reg["Par de apriete"] == "OK" %}selected{% endif %}>OK</option>
              <option value="NO OK" {% if reg["Par de apriete"] == "NO OK" %}selected{% endif %}>NO OK</option>
            </select>
          </label>

          <label>CHECK LIST:
            <select name="check_list">
              <option value="OK" {% if reg["CHECK LIST"] == "OK" %}selected{% endif %}>OK</option>
              <option value="NO OK" {% if reg["CHECK LIST"] == "NO OK" %}selected{% endif %}>NO OK</option>
            </select>
          </label>

          <label>Observaciones:
            <textarea name="observaciones">{{ reg["Observaciones"] }}</textarea>
          </label>

          <button type="submit">Guardar cambios</button>
        </form>
      </div>
    </div>
  </body>
</html>
"""


# -------------------------- RUTAS FLASK -------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "")
        trabajador_info = obtener_trabajador_desde_pin(pin)

        if trabajador_info is None:
            flash("PIN incorrecto.", "error")
            return redirect(url_for("login"))

        session["trabajador_id"] = trabajador_info["id"]
        session["trabajador_nombre"] = trabajador_info["nombre"]
        session["rol"] = trabajador_info.get("rol", "trabajador")

        return redirect(url_for("formulario"))

    return render_template_string(HTML_LOGIN)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
def formulario():
    if "trabajador_id" not in session:
        return redirect(url_for("login"))

    trabajador_id = session["trabajador_id"]
    trabajador_nombre = session["trabajador_nombre"]
    rol = session.get("rol", "trabajador")

    if request.method == "POST":
        hora_inicio = request.form.get("hora_inicio", "")
        hora_fin = request.form.get("hora_fin", "")
        ct = int(request.form.get("ct"))
        campo = int(request.form.get("campo"))
        mesa = int(request.form.get("mesa"))
        par_apriete = request.form.get("par_apriete")
        check_list = request.form.get("check_list")
        observaciones = request.form.get("observaciones")

        # Completar horas si vienen vacías
        if not hora_fin:
            hora_fin = datetime.now().strftime("%H:%M")
        if not hora_inicio:
            hora_inicio = hora_fin

        # Cargar datos existentes
        df = cargar_datos()

        # Asegurarnos de comparar numéricamente para duplicados
        df_ct = pd.to_numeric(df["CT"], errors="coerce")
        df_campo = pd.to_numeric(df["Campo/Área"], errors="coerce")
        df_mesa = pd.to_numeric(df["Nº Mesa"], errors="coerce")

        mismos = df[
            (df_ct == ct) &
            (df_campo == campo) &
            (df_mesa == mesa)
        ]

        if not mismos.empty:
            flash(
                "Esta estructura ya ha sido registrada anteriormente. "
                "Por favor, contacta con tu supervisor para aclarar esta situación.",
                "error",
            )
            return redirect(url_for("formulario"))

        # Si no existe, creamos un registro nuevo
        nuevo = {
            "ID trabajador": trabajador_id,
            "Trabajador": trabajador_nombre,
            "Fecha": date.today(),
            "Hora inicio": hora_inicio,
            "Hora fin": hora_fin,
            "CT": ct,
            "Campo/Área": campo,
            "Nº Mesa": mesa,
            "Par de apriete": par_apriete,
            "CHECK LIST": check_list,
            "Observaciones": observaciones,
        }

        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_datos(df)

        flash("Registro guardado.", "msg")
        return redirect(url_for("formulario"))

    # GET: mostrar formulario
    return render_template_string(
        HTML_FORM,
        trabajador_nombre=trabajador_nombre,
        rol=rol,
        cts=list(range(1, MAX_CT + 1)),
        campos=list(range(1, MAX_CAMPO + 1)),
        mesas=list(range(1, MAX_MESA + 1)),
    )


@app.route("/resumen")
def resumen():
    if "trabajador_id" not in session:
        return redirect(url_for("login"))

    rol = session.get("rol", "trabajador")
    trabajador_id = session.get("trabajador_id")

    # Solo admin y jefe_obra pueden ver el resumen
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permisos para ver el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_datos()

    # Filtro por rol:
    # - admin: ve todo
    # - jefe_obra: de momento, ve solo sus propios registros
    if rol == "jefe_obra":
        df = df[df["ID trabajador"] == trabajador_id]

    total_registros = len(df)

    if total_registros == 0:
        prod_dia = []
        registros = []
    else:
        df["Fecha"] = df["Fecha"].astype(str)
        prod_dia_df = (
            df.groupby("Fecha")
            .size()
            .reset_index(name="Registros")
            .sort_values("Fecha", ascending=True)
        )
        prod_dia = prod_dia_df.to_dict(orient="records")

        # Para permitir edición, añadimos la columna row_id (índice real en el Excel)
        df_sorted = df.sort_values(
            ["Fecha", "Hora inicio"], ascending=[True, True]
        )
        df_sorted = df_sorted.reset_index().rename(columns={"index": "row_id"})
        registros = df_sorted.to_dict(orient="records")

    puede_editar = rol in ("admin", "jefe_obra")

    return render_template_string(
        HTML_RESUMEN,
        total_registros=total_registros,
        prod_dia=prod_dia,
        registros=registros,
        puede_editar=puede_editar,
    )


@app.route("/editar/<int:row_id>", methods=["GET", "POST"])
def editar_registro(row_id):
    if "trabajador_id" not in session:
        return redirect(url_for("login"))

    rol = session.get("rol", "trabajador")
    editor_id = session.get("trabajador_id")
    editor_nombre = session.get("trabajador_nombre")

    # Solo admin y jefe_obra pueden editar
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permisos para editar registros.", "error")
        return redirect(url_for("resumen"))

    df = cargar_datos()

    if row_id not in df.index:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("resumen"))

    registro = df.loc[row_id]

    # Si es jefe_obra, solo puede editar sus propios registros (por ahora)
    if rol == "jefe_obra" and registro["ID trabajador"] != editor_id:
        flash("No tienes permisos para editar este registro.", "error")
        return redirect(url_for("resumen"))

    if request.method == "POST":
        nuevo_par = request.form.get("par_apriete")
        nuevo_check = request.form.get("check_list")
        nuevas_obs = request.form.get("observaciones", "")

        cambios = []
        ahora = datetime.now()
        fecha_cambio = ahora.date()
        hora_cambio = ahora.strftime("%H:%M")

        # Comparar y registrar cambios en Par de apriete
        valor_ant_par = registro["Par de apriete"]
        if str(valor_ant_par) != str(nuevo_par):
            cambios.append(
                {
                    "Fecha cambio": fecha_cambio,
                    "Hora cambio": hora_cambio,
                    "ID editor": editor_id,
                    "Editor": editor_nombre,
                    "Rol editor": rol,
                    "Row ID": row_id,
                    "CT": registro["CT"],
                    "Campo/Área": registro["Campo/Área"],
                    "Nº Mesa": registro["Nº Mesa"],
                    "Campo modificado": "Par de apriete",
                    "Valor anterior": valor_ant_par,
                    "Valor nuevo": nuevo_par,
                }
            )
            df.loc[row_id, "Par de apriete"] = nuevo_par

        # Comparar y registrar cambios en CHECK LIST
        valor_ant_check = registro["CHECK LIST"]
        if str(valor_ant_check) != str(nuevo_check):
            cambios.append(
                {
                    "Fecha cambio": fecha_cambio,
                    "Hora cambio": hora_cambio,
                    "ID editor": editor_id,
                    "Editor": editor_nombre,
                    "Rol editor": rol,
                    "Row ID": row_id,
                    "CT": registro["CT"],
                    "Campo/Área": registro["Campo/Área"],
                    "Nº Mesa": registro["Nº Mesa"],
                    "Campo modificado": "CHECK LIST",
                    "Valor anterior": valor_ant_check,
                    "Valor nuevo": nuevo_check,
                }
            )
            df.loc[row_id, "CHECK LIST"] = nuevo_check

        # Observaciones: no lo metemos en auditoría de detalle,
        # pero sí actualizamos el Excel
        df.loc[row_id, "Observaciones"] = nuevas_obs

        guardar_datos(df)

        # Guardar auditoría si hay cambios en Par de apriete / CHECK LIST
        if cambios:
            guardar_auditoria(cambios)
            flash("Cambios guardados y auditados correctamente.", "msg")
        else:
            flash("No se ha modificado Par de apriete ni CHECK LIST.", "msg")

        return redirect(url_for("resumen"))

    # GET: mostrar formulario de edición
    reg_dict = registro.to_dict()
    return render_template_string(HTML_EDITAR, reg=reg_dict)


if __name__ == "__main__":
    app.run(debug=True)

