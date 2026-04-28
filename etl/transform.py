import pandas as pd
import numpy as np


def run_transform():
    print("Iniciando Transformación de Datos...")
    df = pd.read_csv('../data/staging/extracted_311.csv')

    print("Limpiando fechas y calculando métricas...")

    formato_fecha = '%m/%d/%Y %I:%M:%S %p'
    df['created_date'] = pd.to_datetime(df['created_date'], format=formato_fecha, errors='coerce')
    df['closed_date'] = pd.to_datetime(df['closed_date'], format=formato_fecha, errors='coerce')

    # Filtrar solo tickets cerrados y con fechas válidas
    df = df.dropna(subset=['created_date', 'closed_date'])
    df = df[df['status'] == 'Closed']

    filas_antes = len(df)
    df = df[df['closed_date'] >= df['created_date']]
    filas_despues = len(df)

    if filas_antes > filas_despues:
        print(f"--- Aviso: Se eliminaron {filas_antes - filas_despues} registros con fechas inconsistentes (cierre < creación).")


    # Métricas (Preguntas 1, 3 y 4)
    df['tiempo_resolucion_horas'] = (df['closed_date'] - df['created_date']).dt.total_seconds() / 3600
    df['tiempo_resolucion_horas'] = df['tiempo_resolucion_horas'].round(2)
    df['cerrado_mismo_dia'] = df['created_date'].dt.date == df['closed_date'].dt.date

    # Pregunta 3 - tipos de cierres
    condiciones = [
        df['resolution_description'].str.contains('insufficient|not be processed|no contact', na=False, case=False),
        df['resolution_description'].str.contains('duplicate', na=False, case=False),
        df['resolution_description'].str.contains('corrected|responded|resolved', na=False, case=False)
    ]
    df['tipo_cierre'] = np.select(condiciones, ['Falta de Info', 'Duplicado', 'Resolución Real'], default='Otro')

    # ---------------------------------------------------------
    # CONSTRUCCIÓN DE TABLAS DE DIMENSIONES
    # ---------------------------------------------------------
    print("Generando Tablas de Dimensiones...")

    # -- Dim_Agencia --
    dim_agencia = df[['agency', 'agency_name']].drop_duplicates().reset_index(drop=True)
    dim_agencia.insert(0, 'id_agencia', dim_agencia.index + 1)  # Crear ID numérico
    dim_agencia.columns = ['id_agencia', 'siglas', 'nombre_completo']

    # -- Dim_Tipo_Queja --
    dim_tipo_queja = df[['complaint_type']].drop_duplicates().reset_index(drop=True)
    dim_tipo_queja.insert(0, 'id_tipo_queja', dim_tipo_queja.index + 1)
    dim_tipo_queja.columns = ['id_tipo_queja', 'descripcion_queja']

    # -- Dim_Estado_Resolucion --
    dim_estado_resolucion = df[['status', 'tipo_cierre']].drop_duplicates().reset_index(drop=True)
    dim_estado_resolucion.insert(0, 'id_estado_resolucion', dim_estado_resolucion.index + 1)
    dim_estado_resolucion.columns = ['id_estado_resolucion', 'status_ticket', 'tipo_cierre']

    # -- Dim_Tiempo (A partir de las fechas únicas de creación y cierre) --
    fechas = pd.concat([df['created_date'], df['closed_date']]).dropna().dt.date.unique()
    dim_tiempo = pd.DataFrame({'fecha_completa': fechas})
    dim_tiempo['fecha_completa'] = pd.to_datetime(dim_tiempo['fecha_completa'])

    dim_tiempo['id_fecha'] = dim_tiempo['fecha_completa'].dt.strftime('%Y%m%d').astype(int)
    dim_tiempo['anio'] = dim_tiempo['fecha_completa'].dt.year
    dim_tiempo['mes'] = dim_tiempo['fecha_completa'].dt.month
    dim_tiempo['nombre_mes'] = dim_tiempo['fecha_completa'].dt.month_name(locale='es_ES.utf8')  # Opcional español
    dim_tiempo['dia_semana'] = dim_tiempo['fecha_completa'].dt.day_name()
    dim_tiempo['es_fin_semana'] = dim_tiempo['dia_semana'].isin(['Saturday', 'Sunday', 'sábado', 'domingo'])

    # Lógica de estaciones
    cond_estacion = [
        dim_tiempo['mes'].isin([12, 1, 2]), dim_tiempo['mes'].isin([3, 4, 5]),
        dim_tiempo['mes'].isin([6, 7, 8]), dim_tiempo['mes'].isin([9, 10, 11])
    ]
    dim_tiempo['estacion'] = np.select(cond_estacion, ['Invierno', 'Primavera', 'Verano', 'Otoño'],
                                       default='Desconocido')

    # Limpieza borough
    df['borough'] = df['borough'].fillna('Sin Especificar')
    df['borough'] = df['borough'].str.strip()
    df['borough'] = df['borough'].replace(['Unspecified', ''], 'Sin Especificar')

    # -- Dim_Borough --
    dim_borough = df[['borough']].drop_duplicates().reset_index(drop=True)
    dim_borough.insert(0, 'id_distrito', dim_borough.index + 1)
    dim_borough.columns = ['id_distrito', 'nombre_distrito']

    # ---------------------------------------------------------
    # CONSTRUCCIÓN DE LA TABLA DE HECHOS (Mapeo de IDs)
    # ---------------------------------------------------------
    print("Mapeando Fact Table (Uniendo IDs)...")

    # Unir IDs de Agencia
    fact_df = df.merge(dim_agencia, left_on='agency', right_on='siglas', how='left')
    # Unir IDs de Tipo Queja
    fact_df = fact_df.merge(dim_tipo_queja, left_on='complaint_type', right_on='descripcion_queja', how='left')
    # Unir IDs de Resolución
    fact_df = fact_df.merge(dim_estado_resolucion, left_on=['status', 'tipo_cierre'],
                            right_on=['status_ticket', 'tipo_cierre'], how='left')
    # Unir IDs de Borough
    fact_df = fact_df.merge(dim_borough, left_on='borough', right_on='nombre_distrito', how='left')

    # Crear IDs de fecha
    fact_df['id_fecha_creacion'] = fact_df['created_date'].dt.strftime('%Y%m%d').astype(float).fillna(0).astype(int)
    fact_df['id_fecha_cierre'] = fact_df['closed_date'].dt.strftime('%Y%m%d').astype(float).fillna(0).astype(int)

    # Seleccionar solo las columnas finales para la BD
    columnas_fact = [
        'unique_key', 'id_fecha_creacion', 'id_fecha_cierre',
        'id_agencia', 'id_tipo_queja', 'id_estado_resolucion',
        'id_distrito',
        'tiempo_resolucion_horas', 'cerrado_mismo_dia'
    ]
    fact_quejas = fact_df[columnas_fact]

    # ---------------------------------------------------------
    # EXPORTAR A STAGING (Listos para PostgreSQL)
    # ---------------------------------------------------------
    print("Exportando CSVs finales a /staging...")
    dim_tiempo.to_csv('../data/staging/Dim_Tiempo.csv', index=False)
    dim_agencia.to_csv('../data/staging/Dim_Agencia.csv', index=False)
    dim_tipo_queja.to_csv('../data/staging/Dim_Tipo_Queja.csv', index=False)
    dim_estado_resolucion.to_csv('../data/staging/Dim_Estado_Resolucion.csv', index=False)
    dim_borough.to_csv('../data/staging/Dim_Distrito.csv', index=False)
    fact_quejas.to_csv('../data/staging/Fact_Quejas.csv', index=False)

    print("¡Transformación Completada! Los archivos están listos en la carpeta staging.")


if __name__ == "__main__":
    run_transform()