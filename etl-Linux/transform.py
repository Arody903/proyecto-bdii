import polars as pl
import time
import datetime

def run_transform():
    print("Iniciando Transformación de Datos con Polars...")
    start_time = time.time()

    # Cargar datos desde staging
    df = pl.read_csv('../data/staging/extracted_311.csv')

    print("Limpiando fechas y calculando métricas...")
    formato_fecha = "%m/%d/%Y %I:%M:%S %p"

    # Conversión de fechas y filtrado inicial
    df = (
        df
        .with_columns([
            pl.col("created_date").str.strptime(pl.Datetime, format=formato_fecha, strict=False),
            pl.col("closed_date").str.strptime(pl.Datetime, format=formato_fecha, strict=False)
        ])
        .filter(
            pl.col("created_date").is_not_null() & 
            pl.col("closed_date").is_not_null() & 
            (pl.col("status") == "Closed")
        )
    )

    # FILTRO DE SEGURIDAD PARA ANOMALÍAS DE NYC 311 (Filtramos años irreales)
    df = df.filter(
        (pl.col("created_date").dt.year() >= 2000) & 
        (pl.col("closed_date").dt.year() <= 2030)
    )

    filas_antes = df.height
    df = df.filter(pl.col("closed_date") >= pl.col("created_date"))
    filas_despues = df.height

    if filas_antes > filas_despues:
        print(f"--- Aviso: Se eliminaron {filas_antes - filas_despues} registros con fechas inconsistentes.")

    print("Calculando métricas y tipos de cierre...")
    df = df.with_columns([
        ((pl.col("closed_date") - pl.col("created_date")).dt.total_seconds() / 3600).round(2).alias("tiempo_resolucion_horas"),
        (pl.col("created_date").dt.date() == pl.col("closed_date").dt.date()).alias("cerrado_mismo_dia"),
        
        pl.when(pl.col("resolution_description").str.contains("(?i)insufficient|not be processed|no contact"))
          .then(pl.lit("Falta de Info"))
          .when(pl.col("resolution_description").str.contains("(?i)duplicate"))
          .then(pl.lit("Duplicado"))
          .when(pl.col("resolution_description").str.contains("(?i)corrected|responded|resolved"))
          .then(pl.lit("Resolución Real"))
          .otherwise(pl.lit("Otro"))
          .alias("tipo_cierre"),
          
        pl.col("borough").fill_null("Sin Especificar").str.strip_chars().replace(["Unspecified", ""], "Sin Especificar")
    ])

    # ---------------------------------------------------------
    # CONSTRUCCIÓN DE TABLAS DE DIMENSIONES
    # ---------------------------------------------------------
    print("Generando Tablas de Dimensiones...")

    dim_agencia = (
        df.select(["agency", "agency_name"]).unique()
        .with_row_index("id_agencia", offset=1)
        .rename({"agency": "siglas", "agency_name": "nombre_completo"})
    )

    dim_tipo_queja = (
        df.select(["complaint_type"]).unique()
        .with_row_index("id_tipo_queja", offset=1)
        .rename({"complaint_type": "descripcion_queja"})
    )

    dim_estado_resolucion = (
        df.select(["status", "tipo_cierre"]).unique()
        .with_row_index("id_estado_resolucion", offset=1)
        .rename({"status": "status_ticket"})
    )

    dim_distrito = (
        df.select(["borough"]).unique()
        .with_row_index("id_distrito", offset=1)
        .rename({"borough": "nombre_distrito"})
    )

    # -- Dimensión Tiempo (METODOLOGÍA KIMBALL: Rango Continuo Estático) --
    print("Generando Dimensión Tiempo Continua...")
    
    start_date = datetime.date(2000, 1, 1)
    end_date = datetime.date(2030, 12, 31)
    fechas_list = [start_date + datetime.timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    fechas_df = pl.DataFrame({"fecha": fechas_list})

    meses_espanol = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 
                     7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    dias_espanol = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes', 6: 'Sábado', 7: 'Domingo'}

    dim_tiempo = (
        fechas_df
        .with_columns([
            pl.col("fecha").dt.strftime("%Y%m%d").cast(pl.Int32).alias("id_fecha"),
            pl.col("fecha").dt.year().alias("anio"),
            pl.col("fecha").dt.month().alias("mes"),
            pl.col("fecha").dt.weekday().alias("num_dia_semana") 
        ])
    )
    
    dim_tiempo = dim_tiempo.with_columns([
        pl.col("mes").cast(pl.String).replace({str(k): v for k, v in meses_espanol.items()}).alias("nombre_mes"),
        pl.col("num_dia_semana").cast(pl.String).replace({str(k): v for k, v in dias_espanol.items()}).alias("dia_semana"),
        pl.col("num_dia_semana").is_in([6, 7]).alias("es_fin_semana"),
        pl.when(pl.col("mes").is_in([12, 1, 2])).then(pl.lit("Invierno"))
          .when(pl.col("mes").is_in([3, 4, 5])).then(pl.lit("Primavera"))
          .when(pl.col("mes").is_in([6, 7, 8])).then(pl.lit("Verano"))
          .otherwise(pl.lit("Otoño")).alias("estacion"),
        pl.col("fecha").alias("fecha_completa")
    ]).select(["id_fecha", "fecha_completa", "anio", "mes", "nombre_mes", "dia_semana", "es_fin_semana", "estacion"])

    # ---------------------------------------------------------
    # CONSTRUCCIÓN DE LA TABLA DE HECHOS
    # ---------------------------------------------------------
    print("Mapeando Fact Table (Uniendo IDs)...")

    fact_quejas = (
        df
        .join(dim_agencia, left_on=["agency", "agency_name"], right_on=["siglas", "nombre_completo"], how="left")
        .join(dim_tipo_queja, left_on=["complaint_type"], right_on=["descripcion_queja"], how="left")
        .join(dim_estado_resolucion, left_on=["status", "tipo_cierre"], right_on=["status_ticket", "tipo_cierre"], how="left")
        .join(dim_distrito, left_on=["borough"], right_on=["nombre_distrito"], how="left")
        .with_columns([
            pl.col("created_date").dt.strftime("%Y%m%d").cast(pl.Int32).alias("id_fecha_creacion"),
            pl.col("closed_date").dt.strftime("%Y%m%d").cast(pl.Int32).alias("id_fecha_cierre")
        ])
        .select([
            'unique_key', 'id_fecha_creacion', 'id_fecha_cierre',
            'id_agencia', 'id_tipo_queja', 'id_estado_resolucion', 'id_distrito',
            'tiempo_resolucion_horas', 'cerrado_mismo_dia'
        ])
    )

    # ---------------------------------------------------------
    # EXPORTAR A STAGING
    # ---------------------------------------------------------
    print("Exportando CSVs finales a /staging...")
    dim_tiempo.write_csv('../data/staging/dim_tiempo.csv')
    dim_agencia.write_csv('../data/staging/dim_agencia.csv')
    dim_tipo_queja.write_csv('../data/staging/dim_tipo_queja.csv')
    dim_estado_resolucion.write_csv('../data/staging/dim_estado_resolucion.csv')
    dim_distrito.write_csv('../data/staging/dim_distrito.csv')
    fact_quejas.write_csv('../data/staging/fact_quejas.csv')

    end_time = time.time()
    duration = end_time - start_time

    print("-" * 30)
    print("¡Transformación Completada! Los archivos están listos.")
    print(f"Tiempo total de transformación: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
    print("-" * 30)

if __name__ == "__main__":
    run_transform()