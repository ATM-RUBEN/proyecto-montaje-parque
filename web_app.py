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

GOOGLE_CREDENTIALS_FILE = "credentials.json.json"

AUDITORIA_SPREADSHEET_ID = "1r2KIJK5OrT8WMy4djtjUlMHBVF7qjlZ2hv_7zXpnnns"
AUDITORIA_SHEET_NAME = "Hoja 1"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_mas_raro_y_largo"

# ---------------- GOOGLE SHEETS ----------------
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheets_service():
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
        print("Error registrando auditoría:", e)


# ---------------- UTILIDADES EXCEL ----------------


def cargar_trabajadores_desde_excel():
    path = Path(EXCEL_TRABAJADORES)
    if not path.exists():
        print("⚠ No se encuentra el archivo de trabajadores:", EXCEL_TRABAJADORES)
        return {}

    df = pd.read_excel(path)

    trabajadores = {}
    for _, row in df.iterrows():
        try:
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


# ---------------- HTML ----------------

LOGIN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
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
      width: 100%;
      max-width: 360px;
      box-sizing: border-box;
    }
    .logo {
      max-width: 140px;
      height: auto;
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
      box-sizing: border-box;
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
    .error { margin-top: 10px; color: #e30613; }
  </style>
</head>
<body>
  <div class="card">
    <img src="{{ url_for('static', filename='atm_logo.png') }}" class="logo">
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
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Registro de montaje</title>
  <style>
    body { font-family: Arial; background:#f4f4f4; margin:0; padding:10px; }

    .topbar { max-width:600px; margin:0 auto 10px; display:flex;
              align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; }

    .top-left { display:flex; align-items:center; gap:10px; }

    .logo { height:40px; width:auto; }

    .nombre { font-weight:bold; font-size:16px; max-width:200px;
              overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

    .rol { font-size:13px; color:#777; }

    .top-actions { display:flex; gap:10px; }

    .link-resumen { color:#1976d2; text-decoration:none; font-size:14px; }
    .link-salir { color:#e30613; text-decoration:none; font-size:14px; }

    .card {
      background:#fff;
      padding:20px;
      border-radius:16px;
      box-shadow:0 4px 15px rgba(0,0,0,0.1);
      max-width:600px;
      margin:0 auto;
    }

    label { margin-top:10px; display:block; font-size:14px; }

    input, select, textarea {
      width:100%; padding:12px; border-radius:10px; border:1px solid #ccc;
      margin-top:4px; font-size:16px; box-sizing:border-box;
    }

    textarea { resize:vertical; min-height:80px; }

    .fila-tiempo { display:flex; align-items:center; gap:10px; }

    .btn-tiempo {
      background:#e30613; color:#fff; border:none; padding:10px 12px;
      border-radius:999px; cursor:pointer; font-size:14px;
    }

    .btn-guardar {
      margin-top:20px; width:100%; padding:14px;
      background:#e30613; color:white; font-size:18px;
      border:none; border-radius:999px; cursor:pointer;
    }

    .msg { color:green; margin-top:10px; }
    .error { color:#e30613; margin-top:10px; }

  </style>

  <script>
    function marcarAhora(id){
      const d = new Date();
      const hh = String(d.getHours()).padStart(2,'0');
      const mm = String(d.getMinutes()).padStart(2,'0');
      document.getElementById(id).value = hh + ":" + mm;
    }
  </script>
</head>

<body>

<div class="topbar">
  <div class="top-left">
    <img src="{{ url_for('static', filename='atm_logo.png') }}" class="logo">
    <div>
      <div class="nombre">{{ usuario_nombre }}</div>
      <div class="rol">{{ usuario_rol|capitalize }}</div>
    </div>
  </div>

  <div class="top-actions">
    {% if usuario_rol in ['admin','jefe_obra'] %}
      <a class="link-resumen" href="{{ url_for('resumen') }}">📋 Resumen</a>
    {% endif %}
    <a class="link-salir" href="{{ url_for('logout') }}">⏻ Salir</a>
  </div>
</div>

<div class="card">

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for cat, msg in messages %}
        <div class="{{ cat }}">{{ msg }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <form method="post">

    <label>Hora inicio:</label>
    <div class="fila-tiempo">
      <input type="time" id="hora_inicio" name="hora_inicio">
      <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_inicio')">Marcar</button>
    </div>

    <label>Hora fin:</label>
    <div class="fila-tiempo">
      <input type="time" id="hora_fin" name="hora_fin">
      <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_fin')">Marcar</button>
    </div>

    <label>CT:</label>
    <select name="ct">
      {% for i in cts %}<option value="{{ i }}">{{ i }}</option>{% endfor %}
    </select>

    <label>Campo / Área:</label>
    <select name="campo">
      {% for i in campos %}<option value="{{ i }}">{{ i }}</option>{% endfor %}
    </select>

    <label>Nº Mesa:</label>
    <select name="mesa">
      {% for i in mesas %}<option value="{{ i }}">{{ i }}</option>{% endfor %}
    </select>

    <label>Par de apriete:</label>
    <select name="par_apriete">
      <option>OK</option><option>NO OK</option>
    </select>

    <label>CHECK LIST:</label>
    <select name="check_list">
      <option>OK</option><option>NO OK</option>
    </select>

    <label>Observaciones:</label>
    <textarea name="observaciones"></textarea>

    <button class="btn-guardar" type="submit">Guardar</button>

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
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resumen</title>

  <style>
    body { background:#f4f4f4; padding:10px; margin:0; font-family:Arial; }

    .top { max-width:1000px; margin:0 auto 15px; display:flex;
           justify-content:space-between; align-items:center;
           flex-wrap:wrap; gap:10px; }

    .logo { height:30px; width:auto; }

    table {
      border-collapse:collapse;
      width:100%;
      max-width:1000px;
      margin:0 auto;
      background:white;
    }

    th,td { border:1px solid #ccc; padding:6px; font-size:12px; }
    th { background:#eee; }

    a { text-decoration:none; }
    .salir { color:#e30613; }
  </style>
</head>

<body>

<div class="top">
  <div style="display:flex; align-items:center; gap:10px;">
    <img src="{{ url_for('static', filename='atm_logo.png') }}" class="logo">
    <h2 style="margin:0;">Resumen de registros</h2>
  </div>

  <div>
    <a href="{{ url_for('formulario') }}">Formulario</a> ·
    <a class="salir" href="{{ url_for('logout') }}">Salir</a>
  </div>
</div>

<table>
  <tr>
    <th>#</th><th>ID</th><th>Nombre</th>
    <th>Fecha</th><th>Inicio</th><th>Fin</th>
    <th>CT</th><th>Campo</th><th>Mesa</th>
    <th>Par</th><th>Checklist</th><th>Obs</th><th>Editar</th>
  </tr>

  {% for idx,row in registros %}
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

# ---------------- RUTAS ----------------


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        info = TRABAJADORES_PIN.get(pin)

        if not info:
            flash("PIN incorrecto", "error")
            return render_template_string(LOGIN_HTML)

        session["usuario_id"] = info["id"]
        session["usuario_nombre"] = info["nombre"]
        session["usuario_rol"] = info["rol"]

        return redirect(url_for("formulario"))

    return render_template_string(LOGIN_HTML)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada", "msg")
    return redirect(url_for("login"))


def requiere_login():
    return "usuario_id" in session


@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]

    if request.method == "POST":
        ct = int(request.form["ct"])
        campo = int(request.form["campo"])
        mesa = int(request.form["mesa"])

        df = cargar_registros()

        if not df[
            (df["CT"] == ct) &
            (df["Campo/Área"] == campo) &
            (df["Nº Mesa"] == mesa)
        ].empty:
            flash("⚠ Esta estructura ya fue registrada.", "error")
            return redirect(url_for("formulario"))

        nuevo = {
            "Trabajador": session["usuario_id"],
            "Nombre": usuario_nombre,
            "Fecha": date.today(),
            "Hora inicio": request.form["hora_inicio"],
            "Hora fin": request.form["hora_fin"],
            "CT": ct,
            "Campo/Área": campo,
            "Nº Mesa": mesa,
            "Par de apriete": request.form["par_apriete"],
            "CHECK LIST": request.form["check_list"],
            "Observaciones": request.form["observaciones"],
        }

        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_registros(df)

        flash("Registro guardado", "msg")
        return redirect(url_for("formulario"))

    cts = list(range(1, MAX_CT + 1))
    campos = list(range(1, MAX_CAMPO + 1))
    mesas = list(range(1, MAX_MESA + 1))

    return render_template_string(
        FORM_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        cts=cts,
        campos=campos,
        mesas=mesas,
    )


@app.route("/resumen")
def resumen():
    if not requiere_login():
        return redirect(url_for("login"))

    if session["usuario_rol"] not in ("admin", "jefe_obra"):
        flash("No tienes permiso", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()
    return render_template_string(RESUMEN_HTML, registros=list(df.iterrows()))


@app.route("/editar/<int:indice>", methods=["GET", "POST"])
def editar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    if session["usuario_rol"] not in ("admin", "jefe_obra"):
        flash("Sin permiso", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()

    if indice < 0 or indice >= len(df):
        flash("Registro no encontrado", "error")
        return redirect(url_for("resumen"))

    if request.method == "POST":
        row_antes = df.loc[indice].copy()

        df.at[indice, "Par de apriete"] = request.form["par_apriete"]
        df.at[indice, "CHECK LIST"] = request.form["check_list"]
        df.at[indice, "Observaciones"] = request.form["observaciones"]

        guardar_registros(df)

        flash("Cambios guardados", "msg")
        return redirect(url_for("resumen"))

    return render_template_string(EDIT_HTML, indice=indice, row=df.loc[indice])


# ---------------- MAIN ----------------

if __name__ == "__main__":
    app.run(debug=True)
