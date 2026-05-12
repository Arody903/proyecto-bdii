import pandas as pd
import numpy as np
import time


def run_transform():
    print("Iniciando Transformación de Datos...")

    start_time = time.time()

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
    print("Calculando métricas...")

    df['tiempo_resolucion_horas'] = (df['closed_date'] - df['created_date']).dt.total_seconds() / 3600
    df['tiempo_resolucion_horas'] = df['tiempo_resolucion_horas'].round(2)
    df['cerrado_mismo_dia'] = df['created_date'].dt.normalize() == df['closed_date'].dt.normalize()

    # Pregunta 3 - tipos de cierres
    res_unicas = df['resolution_description'].dropna().unique()
    res_series = pd.Series(res_unicas, index=res_unicas)

    condiciones = [
        res_series.str.contains('insufficient|not be processed|no contact', na=False, case=False),
        res_series.str.contains('duplicate', na=False, case=False),
        res_series.str.contains('corrected|responded|resolved', na=False, case=False)
    ]
    resultados_unicos = np.select(condiciones, ['Falta de Info', 'Duplicado', 'Resolución Real'], default='Otro')

    dict_resolucion = dict(zip(res_unicas, resultados_unicos))
    df['tipo_cierre'] = df['resolution_description'].map(dict_resolucion).fillna('Otro')

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

    # Reordenar las columnas para hacer match con el esquema de PostgreSQL
    orden_columnas_tiempo = [
        'id_fecha',
        'fecha_completa',
        'anio',
        'mes',
        'nombre_mes',
        'dia_semana',
        'es_fin_semana',
        'estacion'
    ]
    dim_tiempo = dim_tiempo[orden_columnas_tiempo]

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
    dict_agencia = dim_agencia.set_index(['siglas', 'nombre_completo'])['id_agencia'].to_dict()
    df = df.merge(dim_agencia,
                       left_on=['agency', 'agency_name'],
                       right_on=['siglas', 'nombre_completo'],
                       how='left')
    # Unir IDs de Tipo Queja
    dict_tipo_queja = dict(zip(dim_tipo_queja['descripcion_queja'], dim_tipo_queja['id_tipo_queja']))
    df['id_tipo_queja'] = df['complaint_type'].map(dict_tipo_queja)
    # Unir IDs de Resolución
    df = df.merge(dim_estado_resolucion, left_on=['status', 'tipo_cierre'],
                            right_on=['status_ticket', 'tipo_cierre'], how='left')
    # Unir IDs de Borough
    dict_distrito = dict(zip(dim_borough['nombre_distrito'], dim_borough[
        'id_distrito']))  # Asumiendo que tu df de dimensiones se llama dim_borough en python
    df['id_distrito'] = df['borough'].map(dict_distrito)

    # Crear IDs de fecha
    df['id_fecha_creacion'] = (df['created_date'].dt.year * 10000 + df['created_date'].dt.month * 100 + df[
        'created_date'].dt.day).fillna(0).astype(int)
    df['id_fecha_cierre'] = (
                df['closed_date'].dt.year * 10000 + df['closed_date'].dt.month * 100 + df['closed_date'].dt.day).fillna(
        0).astype(int)

    # Seleccionar solo las columnas finales para la BD
    columnas_fact = [
        'unique_key', 'id_fecha_creacion', 'id_fecha_cierre',
        'id_agencia', 'id_tipo_queja', 'id_estado_resolucion',
        'id_distrito',
        'tiempo_resolucion_horas', 'cerrado_mismo_dia'
    ]
    fact_quejas = df[columnas_fact]

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

    end_time = time.time()
    duration = end_time - start_time

    print("-" * 30)
    print("¡Transformación Completada! Los archivos están listos en la carpeta staging.")
    print(f"Tiempo total de transformación: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
    print("-" * 30)


if __name__ == "__main__":
    run_transform()