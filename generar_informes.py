from pathlib import Path
import pandas as pd

ARCHIVO_DATOS = "registro_montaje.xlsx"
ARCHIVO_RESUMEN = "resumen_montaje.xlsx"


def cargar_datos():
    path = Path(ARCHIVO_DATOS)
    if not path.exists():
        raise FileNotFoundError(
            f"No se ha encontrado el archivo {ARCHIVO_DATOS}. "
            "Primero debes registrar datos con la aplicación de montaje."
        )
    df = pd.read_excel(path)

    # Nos aseguramos de que la columna Fecha sea realmente de tipo fecha
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date

    return df


def generar_resumen_diario_global(df: pd.DataFrame) -> pd.DataFrame:
    # Contamos registros por fecha
    resumen = df.groupby("Fecha").agg(
        Mesas_registradas=("Nº Mesa", "count"),
        Par_OK=("Par de apriete", lambda x: (x == "OK").sum()),
        Par_NO_OK=("Par de apriete", lambda x: (x == "NO OK").sum()),
        PPI_OK=("PPI", lambda x: (x == "OK").sum()),
        PPI_NO_OK=("PPI", lambda x: (x == "NO OK").sum()),
    ).reset_index()

    return resumen.sort_values("Fecha")


def generar_resumen_por_trabajador(df: pd.DataFrame) -> pd.DataFrame:
    resumen = (
        df.groupby(["Trabajador", "Fecha"])
        .agg(Mesas_registradas=("Nº Mesa", "count"))
        .reset_index()
        .sort_values(["Trabajador", "Fecha"])
    )
    return resumen


def generar_resumen_por_ct(df: pd.DataFrame) -> pd.DataFrame:
    resumen = (
        df.groupby(["CT", "Fecha"])
        .agg(Mesas_registradas=("Nº Mesa", "count"))
        .reset_index()
        .sort_values(["CT", "Fecha"])
    )
    return resumen


def main():
    print("Leyendo datos de montaje...")
    df = cargar_datos()

    print("Generando resumen diario global...")
    resumen_diario = generar_resumen_diario_global(df)

    print("Generando resumen por trabajador...")
    resumen_trabajador = generar_resumen_por_trabajador(df)

    print("Generando resumen por CT...")
    resumen_ct = generar_resumen_por_ct(df)

    print(f"Guardando todo en {ARCHIVO_RESUMEN} ...")
    with pd.ExcelWriter(ARCHIVO_RESUMEN, engine="openpyxl") as writer:
        resumen_diario.to_excel(writer, sheet_name="Resumen_diario_global", index=False)
        resumen_trabajador.to_excel(writer, sheet_name="Resumen_por_trabajador", index=False)
        resumen_ct.to_excel(writer, sheet_name="Resumen_por_CT", index=False)

    print("✅ Resumen generado correctamente.")


if __name__ == "__main__":
    main()
