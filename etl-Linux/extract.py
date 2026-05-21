import polars as pl
import time

# Rutas de archivos
RAW_FILE = '../data/raw/311_Service_Requests.csv'
STAGING_FILE = '../data/staging/extracted_311.csv'

# Se cargan solo las columnas que se usarán
COLUMNS_TO_KEEP = [
    'Unique Key', 'Created Date', 'Closed Date',
    'Agency', 'Agency Name', 'Problem (formerly Complaint Type)',
    'Status', 'Resolution Description', 'Borough'
]

RENAME_MAP = {
    'Unique Key': 'unique_key',
    'Created Date': 'created_date',
    'Closed Date': 'closed_date',
    'Agency': 'agency',
    'Agency Name': 'agency_name',
    'Problem (formerly Complaint Type)': 'complaint_type',
    'Status': 'status',
    'Resolution Description': 'resolution_description',
    'Borough': 'borough'
}

# Tipos de datos optimizados para Polars (Categorical ahorra muchísima RAM)
DTYPE_MAP = {
    'Agency': pl.Categorical,
    'Agency Name': pl.Categorical,
    'Problem (formerly Complaint Type)': pl.Categorical,
    'Status': pl.Categorical,
    'Borough': pl.Categorical,
}

def run_extract():
    print("Iniciando Extracción de Datos con Polars (Lazy Evaluation)...")
    start_time = time.time()

    # scan_csv prepara el plan de ejecución sin cargar todo a la RAM
    # Modificado a schema_overrides para soportar versiones recientes de Polars
    q = (
        pl.scan_csv(RAW_FILE, schema_overrides=DTYPE_MAP, ignore_errors=True)
        .select(COLUMNS_TO_KEEP)
        .rename(RENAME_MAP)
    )

    # .collect() ejecuta usando los 8 vCPUs de tu servidor
    df = q.collect() 

    print(f"Datos extraídos en memoria: {df.height} filas y {df.width} columnas.")

    # Guardar archivo
    df.write_csv(STAGING_FILE)
    print(f"Archivo de extracción guardado en: {STAGING_FILE}")

    end_time = time.time()
    duration = end_time - start_time

    print("-" * 30)
    print(f"Tiempo total de extracción: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
    print("-" * 30)

if __name__ == "__main__":
    run_extract()