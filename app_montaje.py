import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from pathlib import Path

import pandas as pd

EXCEL_FILE = "registro_montaje.xlsx"

# -------- CONFIGURACIÓN --------
MAX_CT = 100         # CT 1..100 (ajustado)
MAX_CAMPO = 10000    # Campo/Área 1..10000
MAX_MESA = 10000     # Mesa 1..10000

# PIN de trabajadores
TRABAJADORES_PIN = {
    "1": "1111",
    "2": "2222",
    "3": "3333",
    "4": "4444",
}


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


def habilitar_formulario(habilitar: bool):
    estado_combo = "readonly" if habilitar else "disabled"
    estado_texto = tk.NORMAL if habilitar else tk.DISABLED
    estado_boton = tk.NORMAL if habilitar else tk.DISABLED

    combo_ct.config(state=estado_combo)
    combo_campo.config(state=estado_combo)
    combo_mesa.config(state=estado_combo)
    combo_par.config(state=estado_combo)
    combo_ppi.config(state=estado_combo)
    txt_obs.config(state=estado_texto)
    btn_guardar.config(state=estado_boton)


def validar_pin():
    pin = entry_pin.get().strip()
    trabajador = obtener_trabajador_desde_pin(pin)

    if trabajador is None:
        lbl_trabajador_valor.config(text="-")
        habilitar_formulario(False)
        messagebox.showerror("Error", "PIN incorrecto. Revisa tu código de trabajador.")
    else:
        lbl_trabajador_valor.config(text=str(trabajador))
        habilitar_formulario(True)
        messagebox.showinfo("PIN correcto", f"Bienvenido, Trabajador {trabajador}")


def guardar_registro():
    pin = entry_pin.get().strip()
    trabajador = obtener_trabajador_desde_pin(pin)
    if trabajador is None:
        messagebox.showerror("Error", "No se puede guardar: PIN incorrecto o vacío.")
        return

    try:
        ct = int(combo_ct.get())
        campo = int(combo_campo.get())
        mesa = int(combo_mesa.get())
    except ValueError:
        messagebox.showerror("Error", "CT, Campo y Mesa deben ser números válidos.")
        return

    par_apriete = combo_par.get()
    ppi = combo_ppi.get()
    observaciones = txt_obs.get("1.0", tk.END).strip()
    hoy = date.today()

    if not par_apriete or not ppi:
        messagebox.showerror("Error", "Debes seleccionar Par de apriete y PPI.")
        return

    df = cargar_datos()

    nuevo_registro = {
        "Trabajador": trabajador,
        "Fecha": hoy,
        "CT": ct,
        "Campo/Área": campo,
        "Nº Mesa": mesa,
        "Par de apriete": par_apriete,
        "PPI": ppi,
        "Observaciones": observaciones,
    }

    df = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
    guardar_datos(df)

    messagebox.showinfo("Registro guardado", "✅ Registro guardado correctamente.")

    # Limpiar observaciones
    txt_obs.delete("1.0", tk.END)

    # Auto-incrementar nº de mesa (hasta MAX_MESA)
    try:
        mesa_actual = int(combo_mesa.get())
        if mesa_actual < MAX_MESA:
            combo_mesa.set(str(mesa_actual + 1))
    except ValueError:
        pass


# ------- INTERFAZ GRÁFICA (TKINTER) -------

root = tk.Tk()
root.title("Registro de montaje - Parque solar")
root.geometry("600x450")  # ventana un poco más grande

frame = ttk.Frame(root, padding=20)
frame.grid(row=0, column=0, sticky="nsew")

root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# PIN trabajador
ttk.Label(frame, text="PIN trabajador:").grid(row=0, column=0, sticky="w", pady=5)
entry_pin = ttk.Entry(frame, width=10, show="*")
entry_pin.grid(row=0, column=1, sticky="w", pady=5)

btn_validar = ttk.Button(frame, text="Validar PIN", command=validar_pin)
btn_validar.grid(row=0, column=2, sticky="w", padx=5, pady=5)

# Trabajador detectado
ttk.Label(frame, text="Trabajador (nº):").grid(row=1, column=0, sticky="w", pady=5)
lbl_trabajador_valor = ttk.Label(frame, text="-")
lbl_trabajador_valor.grid(row=1, column=1, sticky="w", pady=5)

# Fecha
ttk.Label(frame, text="Fecha:").grid(row=2, column=0, sticky="w", pady=5)
lbl_fecha = ttk.Label(frame, text=str(date.today()))
lbl_fecha.grid(row=2, column=1, sticky="w", pady=5)

# CT
ttk.Label(frame, text="CT (Centro de Transformación):").grid(row=3, column=0, sticky="w", pady=5)
cts = [str(i) for i in range(1, MAX_CT + 1)]
combo_ct = ttk.Combobox(frame, values=cts, state="readonly", width=10)
combo_ct.grid(row=3, column=1, sticky="w", pady=5)
combo_ct.current(0)

# Campo / Área
ttk.Label(frame, text="Campo / Área:").grid(row=4, column=0, sticky="w", pady=5)
campos = [str(i) for i in range(1, MAX_CAMPO + 1)]
combo_campo = ttk.Combobox(frame, values=campos, state="readonly", width=10)
combo_campo.grid(row=4, column=1, sticky="w", pady=5)
combo_campo.current(0)

# Nº Mesa
ttk.Label(frame, text="Nº Mesa:").grid(row=5, column=0, sticky="w", pady=5)
mesas = [str(i) for i in range(1, MAX_MESA + 1)]
combo_mesa = ttk.Combobox(frame, values=mesas, state="readonly", width=10)
combo_mesa.grid(row=5, column=1, sticky="w", pady=5)
combo_mesa.current(0)

# Par de apriete
ttk.Label(frame, text="Par de apriete:").grid(row=6, column=0, sticky="w", pady=5)
combo_par = ttk.Combobox(frame, values=["OK", "NO OK"], state="readonly", width=10)
combo_par.grid(row=6, column=1, sticky="w", pady=5)
combo_par.current(0)

# PPI
ttk.Label(frame, text="PPI:").grid(row=7, column=0, sticky="w", pady=5)
combo_ppi = ttk.Combobox(frame, values=["OK", "NO OK"], state="readonly", width=10)
combo_ppi.grid(row=7, column=1, sticky="w", pady=5)
combo_ppi.current(0)

# Observaciones
ttk.Label(frame, text="Observaciones:").grid(row=8, column=0, sticky="nw", pady=5)
txt_obs = tk.Text(frame, width=40, height=5)
txt_obs.grid(row=8, column=1, sticky="w", pady=5)

# Botón
btn_guardar = ttk.Button(frame, text="Guardar registro", command=guardar_registro)
btn_guardar.grid(row=9, column=0, columnspan=3, pady=15)

# Al inicio, el formulario está deshabilitado hasta que el PIN sea válido
habilitar_formulario(False)

root.mainloop()
