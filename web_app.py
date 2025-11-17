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

# --- GOOGLE SHEETS ---
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------

EXCEL_REGISTROS = "registro_montaje.xlsx"
EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"
EXCEL_AUDITORIA_LOCAL = "auditoria_cambios.xlsx"

# Google Sheets (auditoría)
GOOGLE_SHEETS_ID = "1r2KIJK5OrT8WMy4djtjUlMHBVF7qjlZ2hv_7zXpnnns"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_largo_y_raro_123"


# ---------------------------------------------------------
# UTILIDADES DE TRABAJADORES Y ROLES
# ---------------------------------------------------------


def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve un diccionario:
    { PIN(str): {"id": int, "nombre": str, "rol": str} }
    Asumimos:
      Col B -> nombre
      Col C -> id
      Col D -> PIN
      Col E -> rol (admin / jefe_obra / trabajador)
    """
    path = Path(EXCEL_TRABAJADORES)
    if not path.exists():
        print(f"⚠ No se encuentra {EXCEL_TRABAJADORES}")
        return {}

    df = pd.read_excel(path)
    trabajadores = {}

    for _, row in df.iterrows():
        try:
            nombre = str(row.iloc[1]).strip()
            id_trab = row.iloc[2]
            pin_raw = row.iloc[3]
            rol = str(row.iloc[4]).strip().lower()

            if pd.isna(pin_raw):
                continue

            pin = str(pin_raw).strip()
            # Por si viene como 1029.0
            if "." in pin:
                pin = pin.split(".")[0]

            trabajadores[pin] = {
                "id": int(id_trab),
                "nombre": nombre,
                "rol": rol,
            }
        except Exception as e:
            print("Error leyendo fila de trabajadores:", e)
            continue

    return trabajadores


def obtener_usuario_por_pin(pin_introducido: str):
    pin_introducido = pin_introducido.strip()
    trabajadores = cargar_trabajadores_desde_excel()
    return trabajadores.get(pin_introducido)


def rol_legible(rol_interno: str) -> str:
    rol_interno = (rol_interno or "").lower()
    if rol_interno == "admin":
        return "Administrador"
    if rol_interno == "jefe_obra":
        return "Jefe de obra"
    return "Trabajador"


# ---------------------------------------------------------
# UTILIDADES DE GOOGLE SHEETS (AUDITORÍA)
# ---------------------------------------------------------


def obtener_servicio_sheets():
    """
    Devuelve el cliente de Google Sheets usando credentials.json
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=GOOGLE_SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        print("⚠ Error creando servicio de Google Sheets:", e)
        return None


def registrar_auditoria_google_sheets(
    fecha,
    hora,
    usuario,
    rol,
    accion,
    ct,
    campo,
    mesa,
    campo_modificado,
    valor_anterior,
    valor_nuevo,
):
    """
    Añade una fila a la hoja de Google Sheets con la auditoría.
    Asumimos que se escribe en la Hoja1, desde A1 hacia abajo.
    """
    service = obtener_servicio_sheets()
    if service is None:
        return

    valores = [
        [
            fecha,
            hora,
            usuario,
            rol,
            accion,
            ct,
            campo,
            mesa,
            campo_modificado,
            valor_anterior,
            valor_nuevo,
        ]
    ]

    body = {"values": valores}

    try:
        service.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range="Hoja1!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
    except Exception as e:
        print("⚠ Error escribiendo en Google Sheets:", e)


# ---------------------------------------------------------
# UTILIDADES DE EXCEL LOCAL
# ---------------------------------------------------------


def cargar_registros():
    path = Path(EXCEL_REGISTROS)
    if path.exists():
        return pd.read_excel(path)
    else:
        columnas = [
            "Trabajador_ID",
            "Trabajador_Nombre",
            "Trabajador_Rol",
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


def guardar_registros(df: pd.DataFrame):
    df.to_excel(EXCEL_REGISTROS, index=False)


def registrar_auditoria_local(
    fecha,
    hora,
    usuario,
    rol,
    accion,
    ct,
    campo,
    mesa,
    campo_modificado,
    valor_anterior,
    valor_nuevo,
):
    path = Path(EXCEL_AUDITORIA_LOCAL)
    nuevo = {
        "Fecha": fecha,
        "Hora": hora,
        "Usuario": usuario,
        "Rol": rol,
        "Acción": accion,
        "CT": ct,
        "Campo/Área": campo,
        "Nº Mesa": mesa,
        "Campo modificado": campo_modificado,
        "Valor anterior": valor_anterior,
        "Valor nuevo": valor_nuevo,
    }

    if path.exists():
        df = pd.read_excel(path)
        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
    else:
        df = pd.DataFrame([nuevo])

    df.to_excel(path, index=False)


def registrar_auditoria(
    usuario,
    rol,
    accion,
    ct,
    campo,
    mesa,
    campo_modificado,
    valor_anterior,
    valor_nuevo,
):
    """
    Registra la auditoría tanto en Excel local como en Google Sheets.
    """
    ahora = datetime.now()
    fecha = ahora.date().isoformat()
    hora = ahora.strftime("%H:%M:%S")

    # Excel local
    registrar_auditoria_local(
        fecha,
        hora,
        usuario,
        rol,
        accion,
        ct,
        campo,
        mesa,
        campo_modificado,
        valor_anterior,
        valor_nuevo,
    )

    # Google Sheets
    registrar_auditoria_google_sheets(
        fecha,
        hora,
        usuario,
        rol,
        accion,
        ct,
        campo,
        mesa,
        campo_modificado,
        valor_anterior,
        valor_nuevo,
    )


# ---------------------------------------------------------
# PLANTILLAS HTML
# ---------------------------------------------------------

LOGIN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Acceso · Registro de montaje</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f5f5f5;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: white;
      padding: 25px;
      border-radius: 12px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
      width: 360px;
      text-align: center;
    }
    .logo {
      height: 60px;
      margin-bottom: 15px;
    }
    input {
      width: 100%;
      padding: 10px;
      font-size: 18px;
      margin-top: 10px;
      border-radius: 6px;
      border: 1px solid #ccc;
      box-sizing: border-box;
      text-align: center;
      letter-spacing: 4px;
    }
    button {
      margin-top: 15px;
      width: 100%;
      padding: 10px;
      font-size: 18px;
      border-radius: 6px;
      border: none;
      background: #e30613;
      color: white;
      cursor: pointer;
    }
    button:hover {
      background: #c10510;
    }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: red; }
  </style>
</head>
<body>
  <div class="card">
    <img src="{{ url_for('static', filename='ATM_v_pos_rgb_definitivo.jpg') }}" class="logo" alt="ATM España">
    <h3>Introduce tu PIN</h3>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <input type="password" name="pin" autocomplete="off" required>
      <button type="submit">Entrar</button>
    </form>
  </div>
</body>
</html>
"""


FORM_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Registro de montaje · Parque solar</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f5f5f5;
      margin: 0;
      padding: 15px;
    }
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .top-links a {
      text-decoration: none;
      margin-right: 15px;
      color: #444;
      font-size: 14px;
    }
    .top-links a:hover {
      text-decoration: underline;
    }
    .card {
      max-width: 520px;
      margin: 0 auto;
      background: white;
      padding: 20px;
      border-radius: 14px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }
    .header {
      display: flex;
      align-items: center;
      margin-bottom: 10px;
    }
    .logo {
      height: 45px;
      margin-right: 10px;
    }
    .user-info {
      display: flex;
      flex-direction: column;
    }
    .user-name {
      font-weight: bold;
      font-size: 16px;
    }
    .user-role {
      font-size: 13px;
      color: #777;
    }
    label {
      display: block;
      margin-top: 10px;
      font-size: 14px;
    }
    input, select, textarea {
      width: 100%;
      padding: 10px;
      font-size: 16px;
      margin-top: 4px;
      border-radius: 8px;
      border: 1px solid #ccc;
      box-sizing: border-box;
    }
    textarea {
      resize: vertical;
      min-height: 80px;
    }
    .time-row {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .time-row input {
      flex: 1;
    }
    .small-btn {
      background: #e30613;
      color: white;
      border: none;
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 13px;
      cursor: pointer;
      min-width: 90px;
    }
    .small-btn:hover {
      background: #c10510;
    }
    .btn-main {
      width: 100%;
      margin-top: 20px;
      padding: 14px;
      font-size: 18px;
      background: #007bff;
      color: white;
      border: none;
      border-radius: 999px;
      cursor: pointer;
    }
    .btn-main:hover {
      background: #0069d9;
    }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: red; }
  </style>
  <script>
    function marcarHora(campoId) {
      const ahora = new Date();
      const h = String(ahora.getHours()).padStart(2, '0');
      const m = String(ahora.getMinutes()).padStart(2, '0');
      const s = String(ahora.getSeconds()).padStart(2, '0');
      document.getElementById(campoId).value = h + ":" + m + ":" + s;
    }
  </script>
</head>
<body>
  <div class="top-bar">
    <div class="top-links">
      {% if rol in ['admin', 'jefe_obra'] %}
        <a href="{{ url_for('resumen') }}">📊 Resumen</a>
      {% endif %}
    </div>
    <div class="top-links">
      <a href="{{ url_for('logout') }}">🔴 Salir</a>
    </div>
  </div>

  <div class="card">
    <div class="header">
      <img src="{{ url_for('static', filename='ATM_v_pos_rgb_definitivo.jpg') }}" class="logo" alt="ATM España">
      <div class="user-info">
        <div class="user-name">{{ nombre }}</div>
        <div class="user-role">{{ rol_mostrar }}</div>
      </div>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <label>Hora inicio:</label>
      <div class="time-row">
        <input type="text" id="hora_inicio" name="hora_inicio" value="">
        <button type="button" class="small-btn" onclick="marcarHora('hora_inicio')">Marcar<br>inicio</button>
      </div>

      <label>Hora fin:</label>
      <div class="time-row">
        <input type="text" id="hora_fin" name="hora_fin" value="">
        <button type="button" class="small-btn" onclick="marcarHora('hora_fin')">Marcar<br>fin</button>
      </div>

      <label>CT:</label>
      <select name="ct">
        {% for i in range(1, 101) %}
          <option value="{{ i }}">{{ i }}</option>
        {% endfor %}
      </select>

      <label>Campo / Área:</label>
      <select name="campo">
        {% for i in range(1, 10001) %}
          <option value="{{ i }}">{{ i }}</option>
        {% endfor %}
      </select>

      <label>Nº Mesa:</label>
      <select name="mesa">
        {% for i in range(1, 10001) %}
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

      <button type="submit" class="btn-main">Guardar registro</button>
    </form>
  </div>
</body>
</html>
"""


RESUMEN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Resumen · Registro de montaje</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f5f5f5;
      margin: 0;
      padding: 15px;
    }
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .top-links a {
      text-decoration: none;
      margin-right: 15px;
      color: #444;
      font-size: 14px;
    }
    .top-links a:hover {
      text-decoration: underline;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      background: white;
      border-radius: 8px;
      overflow: hidden;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 6px 8px;
      font-size: 12px;
      text-align: center;
    }
    th {
      background: #eee;
    }
    .btn-edit {
      background: #007bff;
      color: white;
      border: none;
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 11px;
      cursor: pointer;
      text-decoration: none;
    }
    .btn-edit:hover {
      background: #0069d9;
    }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: red; }
  </style>
</head>
<body>
  <div class="top-bar">
    <div class="top-links">
      <a href="{{ url_for('formulario') }}">⬅ Volver al formulario</a>
    </div>
    <div class="top-links">
      <a href="{{ url_for('logout') }}">🔴 Salir</a>
    </div>
  </div>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class="{{ category }}">{{ message }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Trabajador</th>
        <th>Rol</th>
        <th>Fecha</th>
        <th>Hora inicio</th>
        <th>Hora fin</th>
        <th>CT</th>
        <th>Campo</th>
        <th>Mesa</th>
        <th>Par apriete</th>
        <th>CHECK LIST</th>
        <th>Obs.</th>
        <th>Acciones</th>
      </tr>
    </thead>
    <tbody>
      {% for i, fila in registros %}
        <tr>
          <td>{{ i }}</td>
          <td>{{ fila["Trabajador_Nombre"] }}</td>
          <td>{{ fila["Trabajador_Rol"] }}</td>
          <td>{{ fila["Fecha"] }}</td>
          <td>{{ fila["Hora inicio"] }}</td>
          <td>{{ fila["Hora fin"] }}</td>
          <td>{{ fila["CT"] }}</td>
          <td>{{ fila["Campo/Área"] }}</td>
          <td>{{ fila["Nº Mesa"] }}</td>
          <td>{{ fila["Par de apriete"] }}</td>
          <td>{{ fila["CHECK LIST"] }}</td>
          <td>{{ fila["Observaciones"] }}</td>
          <td>
            <a class="btn-edit" href="{{ url_for('editar_registro', indice=i) }}">Editar</a>
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""


EDITAR_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Editar registro</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f5f5f5;
      margin: 0;
      padding: 15px;
    }
    .card {
      max-width: 500px;
      margin: 0 auto;
      background: white;
      padding: 20px;
      border-radius: 14px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }
    label {
      display: block;
      margin-top: 10px;
      font-size: 14px;
    }
    input, select, textarea {
      width: 100%;
      padding: 10px;
      font-size: 16px;
      margin-top: 4px;
      border-radius: 8px;
      border: 1px solid #ccc;
      box-sizing: border-box;
    }
    input[readonly] {
      background: #eee;
    }
    button {
      margin-top: 20px;
      width: 100%;
      padding: 12px;
      font-size: 16px;
      border-radius: 999px;
      border: none;
      background: #007bff;
      color: white;
      cursor: pointer;
    }
    button:hover {
      background: #0069d9;
    }
    .top-links {
      margin-bottom: 10px;
    }
    .top-links a {
      text-decoration: none;
      color: #444;
      font-size: 14px;
    }
    .top-links a:hover { text-decoration: underline; }
    .msg { margin-top: 10px; color: green; }
    .error { margin-top: 10px; color: red; }
  </style>
</head>
<body>
  <div class="top-links">
    <a href="{{ url_for('resumen') }}">⬅ Volver al resumen</a>
  </div>

  <div class="card">
    <h3>Editar registro #{{ indice }}</h3>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <label>Trabajador:</label>
      <input type="text" value="{{ fila['Trabajador_Nombre'] }}" readonly>

      <label>Fecha:</label>
      <input type="text" value="{{ fila['Fecha'] }}" readonly>

      <label>CT:</label>
      <input type="text" value="{{ fila['CT'] }}" readonly>

      <label>Campo / Área:</label>
      <input type="text" value="{{ fila['Campo/Área'] }}" readonly>

      <label>Nº Mesa:</label>
      <input type="text" value="{{ fila['Nº Mesa'] }}" readonly>

      <label>Par de apriete:</label>
      <select name="par_apriete">
        <option value="OK" {% if fila['Par de apriete'] == 'OK' %}selected{% endif %}>OK</option>
        <option value="NO OK" {% if fila['Par de apriete'] == 'NO OK' %}selected{% endif %}>NO OK</option>
      </select>

      <label>CHECK LIST:</label>
      <select name="check_list">
        <option value="OK" {% if fila['CHECK LIST'] == 'OK' %}selected{% endif %}>OK</option>
        <option value="NO OK" {% if fila['CHECK LIST'] == 'NO OK' %}selected{% endif %}>NO OK</option>
      </select>

      <label>Observaciones:</label>
      <textarea name="observaciones">{{ fila['Observaciones'] }}</textarea>

      <button type="submit">Guardar cambios</button>
    </form>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------
# MIDDLEWARE SENCILLO DE LOGIN
# ---------------------------------------------------------


def requiere_login():
    if "user_id" not in session:
        flash("Debes iniciar sesión con tu PIN.", "error")
        return False
    return True


def rol_actual():
    return session.get("rol", "trabajador")


# ---------------------------------------------------------
# RUTAS
# ---------------------------------------------------------


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "")
        usuario = obtener_usuario_por_pin(pin)

        if not usuario:
            flash("PIN incorrecto. Inténtalo de nuevo.", "error")
            return redirect(url_for("login"))

        # Guardar en sesión
        session["user_id"] = usuario["id"]
        session["nombre"] = usuario["nombre"]
        session["rol"] = usuario["rol"]

        flash(f"Bienvenido, {usuario['nombre']}.", "msg")
        return redirect(url_for("formulario"))

    return render_template_string(LOGIN_HTML)


@app.route("/salir")
def logout():
    session.clear()
    flash("Has cerrado sesión.", "msg")
    return redirect(url_for("login"))


@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    if not requiere_login():
        return redirect(url_for("login"))

    nombre = session.get("nombre", "")
    rol = rol_actual()
    rol_mostrar = rol_legible(rol)

    if request.method == "POST":
        # Datos del formulario
        hora_inicio = request.form.get("hora_inicio", "").strip()
        hora_fin = request.form.get("hora_fin", "").strip()
        ct = request.form.get("ct", "0")
        campo = request.form.get("campo", "0")
        mesa = request.form.get("mesa", "0")
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

        # Cargar registros
        df = cargar_registros()

        # Comprobar duplicado (misma estructura CT+Campo+Mesa)
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

        hoy = date.today().isoformat()
        nuevo_registro = {
            "Trabajador_ID": session["user_id"],
            "Trabajador_Nombre": nombre,
            "Trabajador_Rol": rol_mostrar,
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
        guardar_registros(df)

        flash("✅ Registro guardado correctamente.", "msg")
        return redirect(url_for("formulario"))

    return render_template_string(
        FORM_HTML, nombre=nombre, rol=rol, rol_mostrar=rol_mostrar
    )


@app.route("/resumen")
def resumen():
    if not requiere_login():
        return redirect(url_for("login"))

    rol = rol_actual()
    if rol not in ["admin", "jefe_obra"]:
        flash("No tienes permisos para ver el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()

    # Convertir DataFrame a lista de filas (índice, dict)
    registros = []
    for i, fila in df.iterrows():
        registros.append((i, fila))

    return render_template_string(RESUMEN_HTML, registros=registros)


@app.route("/editar/<int:indice>", methods=["GET", "POST"])
def editar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    rol = rol_actual()
    if rol not in ["admin", "jefe_obra"]:
        flash("No tienes permisos para editar registros.", "error")
        return redirect(url_for("resumen"))

    df = cargar_registros()

    if indice < 0 or indice >= len(df):
        flash("Registro no encontrado.", "error")
        return redirect(url_for("resumen"))

    fila = df.iloc[indice].copy()

    if request.method == "POST":
        nuevo_par = request.form.get("par_apriete", "")
        nuevo_check = request.form.get("check_list", "")
        nuevas_obs = request.form.get("observaciones", "")

        cambios = []

        if str(fila["Par de apriete"]) != nuevo_par:
            cambios.append(
                ("Par de apriete", str(fila["Par de apriete"]), nuevo_par)
            )

        if str(fila["CHECK LIST"]) != nuevo_check:
            cambios.append(("CHECK LIST", str(fila["CHECK LIST"]), nuevo_check))

        if str(fila["Observaciones"]) != nuevas_obs:
            cambios.append(
                ("Observaciones", str(fila["Observaciones"]), nuevas_obs)
            )

        # Actualizar DataFrame
        df.at[indice, "Par de apriete"] = nuevo_par
        df.at[indice, "CHECK LIST"] = nuevo_check
        df.at[indice, "Observaciones"] = nuevas_obs

        guardar_registros(df)

        usuario_nombre = session.get("nombre", "")
        rol_mostrar = rol_legible(rol)

        ct = fila["CT"]
        campo = fila["Campo/Área"]
        mesa = fila["Nº Mesa"]

        # Registrar cada cambio en auditoría
        for campo_mod, val_ant, val_nuevo in cambios:
            registrar_auditoria(
                usuario=usuario_nombre,
                rol=rol_mostrar,
                accion="MODIFICACIÓN",
                ct=ct,
                campo=campo,
                mesa=mesa,
                campo_modificado=campo_mod,
                valor_anterior=val_ant,
                valor_nuevo=val_nuevo,
            )

        if cambios:
            flash("✅ Cambios guardados y auditados.", "msg")
        else:
            flash("No se ha modificado ningún valor.", "msg")

        return redirect(url_for("resumen"))

    # GET
    return render_template_string(EDITAR_HTML, indice=indice, fila=fila)


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == "__main__":
    # En local, debug=True; en Render no se usa esta línea.
    app.run(debug=True, host="0.0.0.0", port=5000)

