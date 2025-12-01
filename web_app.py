from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import pandas as pd
from pathlib import Path
from datetime import date

app = Flask(__name__)
app.secret_key = "clave_segura_para_montaje"

ARCHIVO = "registro_montaje_v2.xlsx"

EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"

def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve un diccionario:
    pin -> {"id": str, "nombre": str}
    """
    path = Path(EXCEL_TRABAJADORES)
    if not path.exists():
        print("⚠ No se encuentra el archivo de trabajadores:", EXCEL_TRABAJADORES)
        return {}

    df = pd.read_excel(path)

    trabajadores = {}
    for _, row in df.iterrows():
        try:
            # Ajustamos a la estructura que ya tenías:
            # col 1: nombre, col 2: id, col 3: pin
            nombre = str(row.iloc[1]).strip()
            trabajador_id = str(row.iloc[2]).strip()
            pin = str(row.iloc[3]).strip()

            if not pin or pin.lower() == "nan":
                continue

            trabajadores[pin] = {
                "id": trabajador_id,
                "nombre": nombre,
            }
        except Exception as e:
            print("Error leyendo fila de TRABAJADORES PIN:", e)
            continue

    print("TRABAJADORES_PIN cargado:", trabajadores)
    return trabajadores

TRABAJADORES_PIN = cargar_trabajadores_desde_excel()

# ------------------ UTILIDADES ------------------

def cargar_registros():
    """
    Carga el Excel de registros de montaje.
    Si no existe, crea uno vacío con todas las columnas necesarias.
    """
    path = Path(ARCHIVO)
    if path.exists():
        df = pd.read_excel(path)
    else:
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
        df = pd.DataFrame(columns=columnas)
    return df


def guardar_registro(registro):
    """
    Añade un registro al Excel.
    """
    df = cargar_registros()
    df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
    df.to_excel(ARCHIVO, index=False)


# ------------------ RUTAS ------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()

        if not TRABAJADORES_PIN:
            flash("No se han podido cargar los trabajadores. Revisa el archivo TRABAJADORES PIN.xlsx.", "error")
        else:
            trabajador = TRABAJADORES_PIN.get(pin)
            if trabajador:
                session["usuario"] = {
                    "id": trabajador["id"],
                    "nombre": trabajador["nombre"],
                }
                return redirect(url_for("formulario"))
            else:
                flash("PIN incorrecto", "error")

    return render_template_string("""
        <!doctype html>
        <html lang="es">
        <head><meta charset="utf-8"><title>Acceso</title></head>
        <body>
            <h2>Acceso</h2>
            <form method="post">
                PIN: <input type="password" name="pin" maxlength="4">
                <button type="submit">Entrar</button>
            </form>
            {% for c, m in get_flashed_messages(with_categories=True) %}
                <p style="color:red">{{ m }}</p>
            {% endfor %}
        </body>
        </html>
    """)



@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("login"))


@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    if "usuario" not in session:
        return redirect(url_for("login"))

    usuario = session["usuario"]

    if request.method == "POST":
        fecha = request.form.get("fecha") or str(date.today())
        hora_inicio = request.form.get("hora_inicio") or ""
        hora_fin = request.form.get("hora_fin") or ""
        ct = request.form.get("ct") or ""
        campo_area = request.form.get("campo_area") or ""
        mesa = request.form.get("mesa") or ""
        par = request.form.get("par") or ""
        checklist = 1 if request.form.get("checklist") else 0
        observaciones = request.form.get("observaciones") or ""

        registro = {
            "Trabajador": usuario["id"],
            "Nombre": usuario["nombre"],
            "Fecha": fecha,
            "Hora inicio": hora_inicio,
            "Hora fin": hora_fin,
            "CT": ct,
            "Campo/Área": campo_area,
            "Nº Mesa": mesa,
            "Par de apriete": par,
            "CHECK LIST": checklist,
            "Observaciones": observaciones,
        }

        guardar_registro(registro)
        flash("Registro guardado", "ok")
        return redirect(url_for("formulario"))

    hoy = str(date.today())

    return render_template_string("""
        <!doctype html>
        <html lang="es">
        <head><meta charset="utf-8"><title>Formulario montaje</title></head>
        <body>
            <h2>Registro de montaje</h2>
            <p>Usuario: {{ usuario['nombre'] }}</p>
            <p><a href="{{ url_for('logout') }}">Cerrar sesión</a> |
               <a href="{{ url_for('resumen') }}">Ver resumen</a></p>

            {% for c, m in get_flashed_messages(with_categories=True) %}
                <p style="color:green">{{ m }}</p>
            {% endfor %}

            <form method="post">
                Fecha: <input type="date" name="fecha" value="{{ hoy }}"><br><br>
                Hora inicio: <input type="time" name="hora_inicio"><br><br>
                Hora fin: <input type="time" name="hora_fin"><br><br>
                CT: <input type="number" name="ct"><br><br>
                Campo/Área: <input type="text" name="campo_area"><br><br>
                Nº Mesa: <input type="text" name="mesa"><br><br>
                Par de apriete: <input type="text" name="par"><br><br>
                Checklist realizado: <input type="checkbox" name="checklist" value="1"><br><br>
                Observaciones:<br>
                <textarea name="observaciones" rows="4" cols="40"></textarea><br><br>

                <button type="submit">Guardar</button>
            </form>
        </body>
        </html>
    """, usuario=usuario, hoy=hoy)


@app.route("/resumen")
def resumen():
    if "usuario" not in session:
        return redirect(url_for("login"))

    df = cargar_registros()

    if df.empty:
        tabla_html = "<p>No hay registros.</p>"
    else:
        tabla_html = df.to_html(index=False)

    usuario = session["usuario"]

    return render_template_string("""
        <!doctype html>
        <html lang="es">
        <head><meta charset="utf-8"><title>Resumen</title></head>
        <body>
            <h2>Resumen de registros</h2>
            <p>Usuario: {{ usuario['nombre'] }}</p>
            <p><a href="{{ url_for('formulario') }}">Volver al formulario</a> |
               <a href="{{ url_for('logout') }}">Cerrar sesión</a></p>

            {{ tabla_html|safe }}
        </body>
        </html>
    """, usuario=usuario, tabla_html=tabla_html)


# ------------------ EJECUCIÓN ------------------

if __name__ == "__main__":
    app.run(debug=True)
