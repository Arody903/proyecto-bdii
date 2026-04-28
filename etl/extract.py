import pandas as pd

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


def run_extract():
    print("Iniciando Extracción de Datos...")

    df = pd.read_csv(RAW_FILE, usecols=COLUMNS_TO_KEEP, nrows=500000) # nrows para pruebas

    df = df.rename(columns=RENAME_MAP)

    print(f"Datos extraídos en memoria: {df.shape[0]} filas y {df.shape[1]} columnas.")

    # Guardar archivo
    df.to_csv(STAGING_FILE, index=False)
    print(f"Archivo de extracción guardado en: {STAGING_FILE}")


if __name__ == "__main__":
    run_extract()