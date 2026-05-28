import polars as pl
import time
import os
import rarfile
import requests

# CONSTANTES DE ENRUTAMIENTO Y RED
BASE_URL = 'https://tecnasaes-my.sharepoint.com/:u:/g/personal/mgarcia_tecnasa_com/IQDj6GVkeptmSJ5HXonJ2dJsAeHbaZ74_kGsY8c6w_m3xWg'
DATASET_URL = f"{BASE_URL}?download=1"

RAW_DIR = '../data/raw'
RAW_FILE = '../data/raw/311_Service_Requests.csv'
COMPRESSED_FILE = '../data/raw/311_Service_Requests.rar'
STAGING_FILE = '../data/staging/extracted_311.csv'

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

DTYPE_MAP = {
    'Agency': pl.Categorical,
    'Agency Name': pl.Categorical,
    'Problem (formerly Complaint Type)': pl.Categorical,
    'Status': pl.Categorical,
    'Borough': pl.Categorical,
}


def download_dataset(url, destination):
    print(f"Conectando con SharePoint e iniciando descarga...")
    start_time = time.time()

    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    chunk_size = 1024 * 1024
    bytes_written = 0

    with open(destination, 'wb') as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                bytes_written += len(chunk)
                if total_size > 0:
                    percent = (bytes_written / total_size) * 100
                    print(
                        f"   Descargando: {percent:.2f}% ({bytes_written / chunk_size:.1f} MB / {total_size / chunk_size:.1f} MB)",
                        end='\r')
                else:
                    print(f"   Descargando: {bytes_written / chunk_size:.1f} MB descargados...", end='\r')

    end_time = time.time()
    duration = end_time - start_time

    print("\n   Descarga de archivo .rar completada.")
    print(f"   Tiempo total de descarga: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
    print("-" * 30)


def decompress_dataset(source, target_dir):
    print(f"Descomprimiendo archivo RAR {source}...")
    start_time = time.time()

    with rarfile.RarFile(source) as rf:
        rf.extractall(target_dir)

    end_time = time.time()
    duration = end_time - start_time

    print("   Descompresión finalizada exitosamente.")
    print(f"  Tiempo total de descompresión: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
    print("-" * 30)


def ensure_raw_dataset():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(STAGING_FILE), exist_ok=True)

    if os.path.exists(RAW_FILE):
        print(f"Dataset localizado en ruta: {RAW_FILE}")
        return

    print(f"Alerta: El CSV crudo no se encuentra en la ruta.")

    if os.path.exists(COMPRESSED_FILE):
        print(f"Se localizó un respaldo .rar local.")
        decompress_dataset(COMPRESSED_FILE, RAW_DIR)
        return

    print(f"No se encontraron datos locales. Iniciando descarga desde la nube.")
    download_dataset(DATASET_URL, COMPRESSED_FILE)
    decompress_dataset(COMPRESSED_FILE, RAW_DIR)


def run_extract():
    ensure_raw_dataset()

    print("Iniciando Extracción de Datos con Polars (Lazy Evaluation)...")
    start_time = time.time()

    q = (
        pl.scan_csv(RAW_FILE, schema_overrides=DTYPE_MAP, ignore_errors=True)
        .select(COLUMNS_TO_KEEP)
        .rename(RENAME_MAP)
    )

    df = q.collect()

    print(f"Datos extraídos en memoria: {df.height} filas y {df.width} columnas.")

    df.write_csv(STAGING_FILE)
    print(f"Archivo de extracción guardado en: {STAGING_FILE}")

    end_time = time.time()
    duration = end_time - start_time

    print("-" * 30)
    print(f"Tiempo total de extracción: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
    print("-" * 30)


if __name__ == "__main__":
    run_extract()