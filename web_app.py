from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    render_template_string,
    session,
    send_file,
)
from datetime import date, datetime
from pathlib import Path
import pandas as pd

# -------------------------------------------------
# CONFIGURACIÓN PRINCIPAL
# -------------------------------------------------

EXCEL_REGISTRO = "registro_montaje.xlsx"
EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"

# Fichero JSON de la cuenta de servicio de Google
GOOGLE_CREDENTIALS_FILE = "credentials.json.json"  # cambia si tu archivo tiene otro nombre

# ID de la hoja de Google Sheets de auditoría
AUDITORIA_SPREADSHEET_ID = "1r2KIJK5OrT8WMy4djtjUlMHBVF7qjlZ2hv_7zXpnnns"
AUDITORIA_SHEET_NAME = "Hoja 1"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_mas_raro_y_largo"

# -------------------------------------------------
# GOOGLE SHEETS (AUDITORÍA)
# -------------------------------------------------
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def get_sheets_service():
        """Devuelve un cliente de Google Sheets usando la cuenta de servicio."""
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        return build("sheets", "v4", credentials=creds)

    def registrar_auditoria(
        usuario_id,
        usuario_nombre,
        rol,
        ct,
        campo,
        mesa,
        campo_modificado,
        valor_antes,
        valor_despues,
    ):
        """Escribe una fila en la hoja de auditoría. Si falla, solo imprime en consola."""
        try:
            service = get_sheets_service()
            sheet = service.spreadsheets()

            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            values = [
                [
                    ahora,
                    str(usuario_id),
                    usuario_nombre,
                    rol,
                    int(ct),
                    int(campo),
                    int(mesa),
                    campo_modificado,
                    str(valor_antes),
                    str(valor_despues),
                ]
            ]

            body = {"values": values}

            sheet.values().append(
                spreadsheetId=AUDITORIA_SPREADSHEET_ID,
                range=f"{AUDITORIA_SHEET_NAME}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()
        except Exception as e:
            print("Error registrando auditoría en Google Sheets:", e)

except Exception as e:
    # Si las librerías de Google no están, la auditoría se desactiva pero la app sigue.
    print("Aviso: librerías de Google no disponibles. Auditoría desactivada:", e)

    def registrar_auditoria(*args, **kwargs):
        pass


# -------------------------------------------------
# UTILIDADES EXCEL
# -------------------------------------------------


def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve un diccionario:
    pin -> {"id": int, "nombre": str, "rol": str}
    """
    path = Path(EXCEL_TRABAJADORES)
    if not path.exists():
        print("⚠ No se encuentra el archivo de trabajadores:", EXCEL_TRABAJADORES)
        return {}

    try:
        df = pd.read_excel(path)
    except Exception as e:
        print("⚠ Error leyendo TRABAJADORES PIN.xlsx:", e)
        return {}

    trabajadores = {}
    for _, row in df.iterrows():
        try:
            # Columnas: NOMBRE | ID | PIN | ROL
            nombre = str(row["NOMBRE"]).strip()
            trabajador_id = int(row["ID"])
            pin = str(row["PIN"]).strip()
            rol_raw = str(row["ROL"]).strip().lower()

            if not pin or pin.lower() == "nan":
                continue

            if rol_raw not in {"admin", "jefe_obra", "trabajador"}:
                rol_raw = "trabajador"

            trabajadores[pin] = {
                "id": trabajador_id,
                "nombre": nombre,
                "rol": rol_raw,
            }
        except Exception as e_row:
            print("Error leyendo fila de trabajadores:", e_row)
            continue

    print(f"Trabajadores cargados: {len(trabajadores)}")
    return trabajadores


TRABAJADORES_PIN = cargar_trabajadores_desde_excel()


def cargar_registros():
    path = Path(EXCEL_REGISTRO)
    if path.exists():
        return pd.read_excel(path)
    columnas = [
        "Trabajador",
        "Nombre",
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


def guardar_registros(df):
    df.to_excel(EXCEL_REGISTRO, index=False)


# -------------------------------------------------
# PLANTILLAS HTML
# -------------------------------------------------

LOGIN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>ATM España · Acceso</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f4f4f4;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #fff;
      padding: 30px 40px;
      border-radius: 16px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.15);
      text-align: center;
      width: 360px;
    }
    .logo {
      width: 140px;
      margin-bottom: 10px;
    }
    h2 { margin: 10px 0 10px; color: #c00000; }
    p.sub {
      margin: 0 0 20px;
      font-size: 14px;
      color: #555;
    }
    input[type=password] {
      width: 100%;
      padding: 12px;
      font-size: 20px;
      text-align: center;
      border-radius: 8px;
      border: 1px solid #ccc;
      background: #eef4ff;
      letter-spacing: 0.4em;
    }
    button {
      margin-top: 20px;
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 8px;
      background: #e30613;
      color: white;
      font-size: 18px;
      cursor: pointer;
    }
    .msg { margin-top: 15px; color: green; }
    .error { margin-top: 15px; color: #e30613; }
  </style>
</head>
<body>
  <div class="card">
    <img src="{{ url_for('static', filename='logo_atm.png') }}" class="logo" alt="ATM España">
    <h2>Introduce tu PIN</h2>
    <p class="sub">Acceso al registro de montaje del parque solar</p>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <input type="password" name="pin" maxlength="4" autofocus required>
      <button type="submit">Entrar</button>
    </form>
  </div>
</body>
</html>
"""

# FORMULARIO: estilo tipo app, logo + nombre + rol + icono
FORM_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Registro de montaje</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f4f4f4;
      margin: 0;
      padding: 20px;
    }
    .header-wrapper {
      display: flex;
      justify-content: center;
      margin-bottom: 10px;
    }
    .header-card {
      background: #ffffff;
      border-radius: 999px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.15);
      padding: 10px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
      max-width: 520px;
      width: 100%;
    }
    .logo-small {
      height: 36px;
      width: auto;
    }
    .user-block {
      display: flex;
      flex-direction: column;
      flex: 1;
    }
    .user-top {
      display: flex;
      align-items: center;
      gap: 8px;
      justify-content: flex-start;
      flex-wrap: wrap;
    }
    .nombre {
      font-weight: bold;
      font-size: 16px;
    }
    .rol {
      font-size: 13px;
      color: #777;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .rol-icon {
      font-size: 14px;
    }
    .links {
      display: flex;
      gap: 12px;
      justify-content: flex-end;
      font-size: 13px;
      margin-top: 4px;
    }
    .links a {
      text-decoration: none;
    }
    .link-resumen { color: #1976d2; }
    .link-salir { color: #e30613; }

    .card {
      background: #fff;
      padding: 20px 20px 30px;
      border-radius: 16px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.15);
      max-width: 520px;
      margin: 10px auto 0 auto;
    }
    label { display: block; margin-top: 10px; font-size: 14px; }
    input, select, textarea {
      width: 100%;
      padding: 12px;
      margin-top: 4px;
      border-radius: 10px;
      border: 1px solid #ccc;
      font-size: 16px;
      box-sizing: border-box;
    }
    textarea { resize: vertical; min-height: 80px; }
    .fila-tiempo {
      display: flex;
      gap: 10px;
      align-items: center;
      margin-top: 5px;
    }
    .fila-tiempo input {
      flex: 1;
    }
    .btn-tiempo {
      padding: 10px 14px;
      border: none;
      border-radius: 999px;
      background: #e30613;
      color: white;
      cursor: pointer;
      font-size: 13px;
      min-width: 110px;
    }
    .btn-guardar {
      margin-top: 20px;
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: 999px;
      background: #e30613;
      color: white;
      font-size: 18px;
      cursor: pointer;
    }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: #e30613; }
  </style>
  <script>
    function marcarAhora(idCampo) {
      const ahora = new Date();
      const hh = String(ahora.getHours()).padStart(2, '0');
      const mm = String(ahora.getMinutes()).padStart(2, '0');
      document.getElementById(idCampo).value = hh + ":" + mm;
    }
  </script>
</head>
<body>
  <div class="header-wrapper">
    <div class="header-card">
      <img src="{{ url_for('static', filename='logo_atm.png') }}" class="logo-small" alt="ATM España">
      <div class="user-block">
        <div class="user-top">
          <div class="nombre">{{ usuario_nombre }}</div>
          <div class="rol">
            <span class="rol-icon">👷</span>
            <span>{{ usuario_rol|replace('_', ' ')|title }}</span>
          </div>
        </div>
        <div class="links">
          {% if usuario_rol in ['admin', 'jefe_obra'] %}
            <a href="{{ url_for('resumen') }}" class="link-resumen">📋 Resumen</a>
          {% endif %}
          <a href="{{ url_for('logout') }}" class="link-salir">⏻ Salir</a>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <label>Hora inicio:</label>
      <div class="fila-tiempo">
        <input type="time" id="hora_inicio" name="hora_inicio" value="">
        <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_inicio')">Marcar inicio</button>
      </div>

      <label>Hora fin:</label>
      <div class="fila-tiempo">
        <input type="time" id="hora_fin" name="hora_fin" value="">
        <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_fin')">Marcar fin</button>
      </div>

      <label>CT:</label>
      <select name="ct">
        {% for i in cts %}
          <option value="{{ i }}">{{ i }}</option>
        {% endfor %}
      </select>

      <label>Campo / Área:</label>
      <select name="campo">
        {% for i in campos %}
          <option value="{{ i }}">{{ i }}</option>
        {% endfor %}
      </select>

      <label>Nº Mesa:</label>
      <select name="mesa">
        {% for i in mesas %}
          <option value="{{ i }}">{{ i }}</option>
        {% endfor %}
      </select>

      <label>Par de apriete:</label>
      <select name="par_apriete">
        <option value="OK">OK</option>
        <option value="NO OK">NO OK</option>
      </select>

      <label>CHECK LIST:</label>
      <select name="check_list">
        <option value="OK">OK</option>
        <option value="NO OK">NO OK</option>
      </select>

      <label>Observaciones:</label>
      <textarea name="observaciones"></textarea>

      <button type="submit" class="btn-guardar">Guardar registro</button>
    </form>
  </div>
</body>
</html>
"""

# RESUMEN: logo, cabecera tipo app + dos tablas con botón de descarga arriba dcha
RESUMEN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Resumen de registros</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; background:#f4f4f4; margin:0; }

    .header-wrapper {
      display:flex;
      justify-content:center;
      margin-bottom:10px;
    }
    .header-card {
      background:#fff;
      border-radius:999px;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
      padding:10px 18px;
      display:flex;
      align-items:center;
      gap:12px;
      max-width:900px;
      width:100%;
    }
    .logo-small {
      height:36px;
      width:auto;
    }
    .user-block {
      display:flex;
      flex-direction:column;
      flex:1;
    }
    .user-top {
      display:flex;
      align-items:center;
      gap:8px;
      flex-wrap:wrap;
    }
    .usuario {
      font-weight:bold;
      font-size:16px;
    }
    .rol {
      font-size:13px;
      color:#777;
      display:flex;
      align-items:center;
      gap:4px;
    }
    .rol-icon { font-size:14px; }
    .nav-links-top {
      display:flex;
      gap:12px;
      justify-content:flex-end;
      font-size:13px;
      margin-top:4px;
    }
    .nav-links-top a {
      text-decoration:none;
    }
    .link-form { color:#1976d2; }
    .link-salir { color:#e30613; }

    .section-card {
      background:#fff;
      border-radius:12px;
      padding:12px 12px 16px;
      margin-top:12px;
      box-shadow:0 2px 8px rgba(0,0,0,0.08);
    }
    .section-header {
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:6px;
    }
    .section-header h2 {
      margin:0;
      font-size:16px;
    }
    .section-sub {
      font-size:12px;
      color:#555;
      margin:0 0 6px 0;
    }

    table {
      border-collapse: collapse;
      width: 100%;
      background:#fff;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 6px 8px;
      font-size: 12px;
    }
    th { background:#eee; }
    a { text-decoration:none; color:#1976d2; }

    .btn-descargar {
      display:inline-block;
      padding:6px 12px;
      border-radius:999px;
      background:#e30613;
      color:#fff;
      font-size:12px;
    }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: #e30613; }
  </style>
</head>
<body>
  <div class="header-wrapper">
    <div class="header-card">
      <img src="{{ url_for('static', filename='logo_atm.png') }}" class="logo-small" alt="ATM España">
      <div class="user-block">
        <div class="user-top">
          <div class="usuario">{{ usuario_nombre }}</div>
          <div class="rol">
            <span class="rol-icon">👷</span>
            <span>{{ usuario_rol|replace('_',' ')|title }}</span>
          </div>
        </div>
        <div class="nav-links-top">
          <a href="{{ url_for('formulario') }}" class="link-form">← Formulario</a>
          <a href="{{ url_for('logout') }}" class="link-salir">Salir</a>
        </div>
      </div>
    </div>
  </div>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class="{{ category }}">{{ message }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <div class="section-card">
    <div class="section-header">
      <h2>Resumen diario</h2>
      <a class="btn-descargar" href="{{ url_for('descargar_resumen_diario') }}">⬇ Excel diario</a>
    </div>
    <p class="section-sub">Número de estructuras registradas por día.</p>
    <table>
      <tr>
        <th>Fecha</th>
        <th>Nº registros</th>
      </tr>
      {% for fecha, n in resumen_diario %}
        <tr>
          <td>{{ fecha }}</td>
          <td>{{ n }}</td>
        </tr>
      {% endfor %}
      {% if resumen_diario|length == 0 %}
        <tr><td colspan="2">Aún no hay registros.</td></tr>
      {% endif %}
    </table>
  </div>

  <div class="section-card">
    <div class="section-header">
      <h2>Listado completo</h2>
      <a class="btn-descargar" href="{{ url_for('descargar_registros') }}">⬇ Excel completo</a>
    </div>
    <p class="section-sub">Detalle de todos los registros del proyecto.</p>
    <table>
      <tr>
        <th>#</th>
        <th>Trabajador</th>
        <th>Nombre</th>
        <th>Fecha</th>
        <th>Hora inicio</th>
        <th>Hora fin</th>
        <th>CT</th>
        <th>Campo</th>
        <th>Mesa</th>
        <th>Par</th>
        <th>CHECK LIST</th>
        <th>Obs.</th>
        <th>Editar</th>
      </tr>
      {% for idx, row in registros %}
        <tr>
          <td>{{ idx }}</td>
          <td>{{ row["Trabajador"] }}</td>
          <td>{{ row["Nombre"] }}</td>
          <td>{{ row["Fecha"] }}</td>
          <td>{{ row["Hora inicio"] }}</td>
          <td>{{ row["Hora fin"] }}</td>
          <td>{{ row["CT"] }}</td>
          <td>{{ row["Campo/Área"] }}</td>
          <td>{{ row["Nº Mesa"] }}</td>
          <td>{{ row["Par de apriete"] }}</td>
          <td>{{ row["CHECK LIST"] }}</td>
          <td>{{ row["Observaciones"] }}</td>
          <td><a href="{{ url_for('editar_registro', indice=idx) }}">Editar</a></td>
        </tr>
      {% endfor %}
      {% if registros|length == 0 %}
        <tr><td colspan="13">Aún no hay registros.</td></tr>
      {% endif %}
    </table>
  </div>
</body>
</html>
"""

# EDIT: también con logo en la parte superior, estilo app
EDIT_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Editar registro</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f4f4f4; padding:20px; margin:0; }

    .header-wrapper {
      display:flex;
      justify-content:center;
      margin-bottom:10px;
    }
    .header-card {
      background:#fff;
      border-radius:999px;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
      padding:10px 18px;
      display:flex;
      align-items:center;
      gap:12px;
      max-width:520px;
      width:100%;
    }
    .logo-small {
      height:36px;
      width:auto;
    }
    .user-block {
      display:flex;
      flex-direction:column;
      flex:1;
    }
    .user-top {
      display:flex;
      align-items:center;
      gap:8px;
      flex-wrap:wrap;
    }
    .usuario {
      font-weight:bold;
      font-size:16px;
    }
    .rol {
      font-size:13px;
      color:#777;
      display:flex;
      align-items:center;
      gap:4px;
    }
    .rol-icon { font-size:14px; }
    .nav-links-top {
      display:flex;
      gap:12px;
      justify-content:flex-end;
      font-size:13px;
      margin-top:4px;
    }
    .nav-links-top a {
      text-decoration:none;
    }
    .link-resumen { color:#1976d2; }
    .link-salir { color:#e30613; }

    .card {
      background:#fff;
      padding:20px;
      border-radius:12px;
      max-width:520px;
      margin:10px auto 0 auto;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
    }
    label { display:block; margin-top:10px; }
    input, select, textarea {
      width:100%;
      padding:8px;
      margin-top:4px;
      border-radius:8px;
      border:1px solid #ccc;
      box-sizing:border-box;
    }
    textarea { resize:vertical; min-height:70px; }
    button {
      margin-top:20px;
      width:100%;
      padding:12px;
      border:none;
      border-radius:999px;
      background:#e30613;
      color:#fff;
      font-size:16px;
      cursor:pointer;
    }
    a { text-decoration:none; color:#1976d2; }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: #e30613; }
  </style>
</head>
<body>
  <div class="header-wrapper">
    <div class="header-card">
      <img src="{{ url_for('static', filename='logo_atm.png') }}" class="logo-small" alt="ATM España">
      <div class="user-block">
        <div class="user-top">
          <div class="usuario">{{ usuario_nombre }}</div>
          <div class="rol">
            <span class="rol-icon">👷</span>
            <span>{{ usuario_rol|replace('_',' ')|title }}</span>
          </div>
        </div>
        <div class="nav-links-top">
          <a href="{{ url_for('resumen') }}" class="link-resumen">← Resumen</a>
          <a href="{{ url_for('logout') }}" class="link-salir">Salir</a>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Editar registro #{{ indice }}</h2>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <p><strong>Estructura:</strong> CT {{ row["CT"] }} · Campo {{ row["Campo/Área"] }} · Mesa {{ row["Nº Mesa"] }}</p>

      <label>Par de apriete:</label>
      <select name="par_apriete">
        <option value="OK" {% if row["Par de apriete"] == "OK" %}selected{% endif %}>OK</option>
        <option value="NO OK" {% if row["Par de apriete"] == "NO OK" %}selected{% endif %}>NO OK</option>
      </select>

      <label>CHECK LIST:</label>
      <select name="check_list">
        <option value="OK" {% if row["CHECK LIST"] == "OK" %}selected{% endif %}>OK</option>
        <option value="NO OK" {% if row["CHECK LIST"] == "NO OK" %}selected{% endif %}>NO OK</option>
      </select>

      <label>Observaciones:</label>
      <textarea name="observaciones">{{ row["Observaciones"] }}</textarea>

      <button type="submit">Guardar cambios</button>
    </form>
  </div>
</body>
</html>
"""

# -------------------------------------------------
# RUTAS
# -------------------------------------------------


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        trabajador_info = TRABAJADORES_PIN.get(pin)

        if not trabajador_info:
            flash("PIN incorrecto. Inténtalo de nuevo.", "error")
            return render_template_string(LOGIN_HTML)

        session["usuario_id"] = trabajador_info["id"]
        session["usuario_nombre"] = trabajador_info["nombre"]
        session["usuario_rol"] = trabajador_info["rol"]

        flash(f"Bienvenido, {trabajador_info['nombre']}.", "msg")
        return redirect(url_for("formulario"))

    return render_template_string(LOGIN_HTML)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "msg")
    return redirect(url_for("login"))


def requiere_login():
    return "usuario_id" in session


@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]

    if request.method == "POST":
        hora_inicio = request.form.get("hora_inicio", "")
        hora_fin = request.form.get("hora_fin", "")
        ct = request.form.get("ct", "")
        campo = request.form.get("campo", "")
        mesa = request.form.get("mesa", "")
        par_apriete = request.form.get("par_apriete", "")
        check_list = request.form.get("check_list", "")
        observaciones = request.form.get("observaciones", "")

        try:
            ct_int = int(ct)
            campo_int = int(campo)
            mesa_int = int(mesa)
        except ValueError:
            flash("CT, Campo y Mesa deben ser números válidos.", "error")
            return redirect(url_for("formulario"))

        df = cargar_registros()

        # Comprobar duplicado de estructura
        duplicado = df[
            (df["CT"] == ct_int)
            & (df["Campo/Área"] == campo_int)
            & (df["Nº Mesa"] == mesa_int)
        ]

        if not duplicado.empty:
            flash(
                "Esta estructura ya ha sido registrada anteriormente. "
                "Por favor, contacta con tu supervisor para aclarar esta situación.",
                "error",
            )
            return redirect(url_for("formulario"))

        hoy = date.today()

        nuevo = {
            "Trabajador": usuario_id,
            "Nombre": usuario_nombre,
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

        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_registros(df)

        flash("✅ Registro guardado correctamente.", "msg")
        return redirect(url_for("formulario"))

    cts = list(range(1, MAX_CT + 1))
    campos = list(range(1, MAX_CAMPO + 1))
    mesas = list(range(1, MAX_MESA + 1))

    return render_template_string(
        FORM_HTML,
        cts=cts,
        campos=campos,
        mesas=mesas,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
    )


@app.route("/resumen")
def resumen():
    if not requiere_login():
        return redirect(url_for("login"))

    rol = session.get("usuario_rol", "trabajador")
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para ver el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()
    registros = list(df.iterrows())  # [(index, row), ...]

    # Resumen diario: número de registros por fecha
    resumen_diario = []
    if not df.empty and "Fecha" in df.columns:
        try:
            grp = df.groupby("Fecha").size().reset_index(name="num_registros")
            resumen_diario = [
                (row["Fecha"], int(row["num_registros"]))
                for _, row in grp.iterrows()
            ]
        except Exception as e:
            print("Error generando resumen diario:", e)
            resumen_diario = []

    return render_template_string(
        RESUMEN_HTML,
        registros=registros,
        resumen_diario=resumen_diario,
        usuario_nombre=session.get("usuario_nombre", ""),
        usuario_rol=rol,
    )


@app.route("/editar/<int:indice>", methods=["GET", "POST"])
def editar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    rol = session.get("usuario_rol", "trabajador")
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para editar registros.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()

    if indice < 0 or indice >= len(df):
        flash("Registro no encontrado.", "error")
        return redirect(url_for("resumen"))

    if request.method == "POST":
        row_antes = df.loc[indice].copy()

        par_apriete_nuevo = request.form.get("par_apriete", "")
        check_list_nuevo = request.form.get("check_list", "")
        obs_nueva = request.form.get("observaciones", "")

        df.at[indice, "Par de apriete"] = par_apriete_nuevo
        df.at[indice, "CHECK LIST"] = check_list_nuevo
        df.at[indice, "Observaciones"] = obs_nueva

        guardar_registros(df)

        usuario_id = session["usuario_id"]
        usuario_nombre = session["usuario_nombre"]
        usuario_rol = session["usuario_rol"]

        ct = row_antes["CT"]
        campo = row_antes["Campo/Área"]
        mesa = row_antes["Nº Mesa"]

        # Registrar auditoría solo si cambian estos campos
        if row_antes["Par de apriete"] != par_apriete_nuevo:
            registrar_auditoria(
                usuario_id,
                usuario_nombre,
                usuario_rol,
                ct,
                campo,
                mesa,
                "Par de apriete",
                row_antes["Par de apriete"],
                par_apriete_nuevo,
            )

        if row_antes["CHECK LIST"] != check_list_nuevo:
            registrar_auditoria(
                usuario_id,
                usuario_nombre,
                usuario_rol,
                ct,
                campo,
                mesa,
                "CHECK LIST",
                row_antes["CHECK LIST"],
                check_list_nuevo,
            )

        flash("Cambios guardados correctamente.", "msg")
        return redirect(url_for("resumen"))

    row = df.loc[indice]
    return render_template_string(
        EDIT_HTML,
        indice=indice,
        row=row,
        usuario_nombre=session.get("usuario_nombre", ""),
        usuario_rol=session.get("usuario_rol", ""),
    )


# -------------------------------------------------
# DESCARGAS EXCEL
# -------------------------------------------------


@app.route("/descargar_resumen_diario")
def descargar_resumen_diario():
    if not requiere_login():
        return redirect(url_for("login"))

    rol = session.get("usuario_rol", "trabajador")
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para descargar el informe diario.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()
    if df.empty:
        flash("Aún no hay registros para generar el resumen diario.", "error")
        return redirect(url_for("resumen"))

    try:
        grp = df.groupby("Fecha").size().reset_index(name="num_registros")
    except Exception as e:
        print("Error generando resumen diario para Excel:", e)
        flash("Error generando el resumen diario.", "error")
        return redirect(url_for("resumen"))

    path = Path("resumen_diario.xlsx")
    grp.to_excel(path, index=False)

    return send_file(
        path,
        as_attachment=True,
        download_name="resumen_diario.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/descargar_registros")
def descargar_registros():
    """Devuelve el fichero registro_montaje.xlsx tal cual."""
    if not requiere_login():
        return redirect(url_for("login"))

    rol = session.get("usuario_rol", "trabajador")
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para descargar el informe completo.", "error")
        return redirect(url_for("formulario"))

    path = Path(EXCEL_REGISTRO)
    if not path.exists():
        flash("Aún no hay registros para descargar.", "error")
        return redirect(url_for("resumen"))

    return send_file(
        path,
        as_attachment=True,
        download_name="registro_montaje.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# -------------------------------------------------
# MAIN
# -------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)

