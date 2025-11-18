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

# ---------------- CONFIGURACIÓN PRINCIPAL ----------------

EXCEL_REGISTRO = "registro_montaje.xlsx"
EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"

# Fichero JSON que descargaste de Google Cloud (cuenta de servicio)
GOOGLE_CREDENTIALS_FILE = "credentials.json.json"  # cambia el nombre si tu archivo es distinto

# ID de la hoja de Google Sheets de auditoría
# Sacado de: https://docs.google.com/spreadsheets/d/ID_AQUI/edit...
AUDITORIA_SPREADSHEET_ID = "1r2KIJK5OrT8WMy4djtjUlMHBVF7qjlZ2hv_7zXpnnns"
AUDITORIA_SHEET_NAME = "Hoja 1"  # cambia si tu pestaña se llama distinto

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_mas_raro_y_largo"

# ---------------- GOOGLE SHEETS (AUDITORÍA) ----------------
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
    """
    Escribe una fila en la hoja de auditoría con la información de la modificación.
    """
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
        # No rompemos la app si la auditoría falla: solo mostramos por consola
        print("Error registrando auditoría:", e)


# ---------------- UTILIDADES EXCEL ----------------


def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve un diccionario:
    pin -> {"id": int, "nombre": str, "rol": str}
    """
    path = Path(EXCEL_TRABAJADORES)
    if not path.exists():
        print("⚠ No se encuentra el archivo de trabajadores:", EXCEL_TRABAJADORES)
        return {}

    df = pd.read_excel(path)

    trabajadores = {}
    for _, row in df.iterrows():
        try:
            # Columnas: B = nombre, C = id, D = pin, E = rol
            nombre = str(row.iloc[1]).strip()
            trabajador_id = str(row.iloc[2]).strip()
            pin = str(row.iloc[3]).strip()
            rol_raw = str(row.iloc[4]).strip().lower()

            if not pin or pin.lower() == "nan":
                continue

            if rol_raw not in {"admin", "jefe_obra", "trabajador"}:
                rol_raw = "trabajador"

            trabajadores[pin] = {
                "id": int(trabajador_id),
                "nombre": nombre,
                "rol": rol_raw,
            }
        except Exception:
            continue

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


# ---------------- PLANTILLAS HTML ----------------

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
    h2 { margin: 10px 0 20px; color: #c00000; }
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
    <img src="{{ url_for('static', filename='atm_logo.png') }}" class="logo" alt="ATM España">
    <h2>Introduce tu PIN</h2>

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
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .topbar-left { display: flex; align-items: center; gap: 10px; }
    .logo { height: 40px; }
    .nombre { font-weight: bold; font-size: 18px; }
    .rol { font-size: 13px; color: #777; }
    .link-resumen {
      font-size: 14px;
      text-decoration: none;
      color: #1976d2;
      margin-right: 15px;
    }
    .link-salir {
      font-size: 14px;
      text-decoration: none;
      color: #e30613;
    }
    .card {
      background: #fff;
      padding: 20px 20px 30px;
      border-radius: 16px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.15);
      max-width: 500px;
      margin: 0 auto;
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
  <div class="topbar">
    <div class="topbar-left">
      <img src="{{ url_for('static', filename='atm_logo.png') }}" class="logo" alt="ATM España">
      <div>
        <div class="nombre">{{ usuario_nombre }}</div>
        <div class="rol">{{ usuario_rol|capitalize }}</div>
      </div>
    </div>
    <div>
      {% if usuario_rol in ['admin', 'jefe_obra'] %}
        <a href="{{ url_for('resumen') }}" class="link-resumen">📋 Resumen</a>
      {% endif %}
      <a href="{{ url_for('logout') }}" class="link-salir">⏻ Salir</a>
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

RESUMEN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Resumen de registros</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; background:#f4f4f4; }
    h2 { margin-top: 0; }
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
    .top { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
    .btn-salir { color:#e30613; }
  </style>
</head>
<body>
  <div class="top">
    <h2>Resumen de registros</h2>
    <div>
      <a href="{{ url_for('formulario') }}">Volver al formulario</a> ·
      <a class="btn-salir" href="{{ url_for('logout') }}">Salir</a>
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
  </table>
</body>
</html>
"""

EDIT_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Editar registro</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f4f4f4; padding:20px; }
    .card {
      background:#fff;
      padding:20px;
      border-radius:12px;
      max-width:500px;
      margin:0 auto;
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
  </style>
</head>
<body>
  <div class="card">
    <h2>Editar registro #{{ indice }}</h2>
    <p><a href="{{ url_for('resumen') }}">← Volver al resumen</a></p>

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

# ---------------- RUTAS ----------------


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

        return redirect(url_for("formulario"))

    return render_template_string(LOGIN_HTML)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "msg")
    return redirect(url_for("login"))


def requiere_login():
    if "usuario_id" not in session:
        return False
    return True


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

    return render_template_string(RESUMEN_HTML, registros=registros)


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
    return render_template_string(EDIT_HTML, indice=indice, row=row)


# ---------------- MAIN ----------------

if __name__ == "__main__":
    app.run(debug=True)
