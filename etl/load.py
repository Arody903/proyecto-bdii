import psycopg2
import time
import os

DB_CONFIG = {
    "host": "localhost",
    "database": "prueba_proyecto_final",
    "user": "postgres",
    "password": "root"
}

STAGING_PATH = "../data/staging/"
SQL_PATH = "../sql/ddl_schema.sql"


def execute_sql_file(cursor, file_path):
    """Lee y ejecuta un archivo .sql completo."""
    print(f"Ejecutando esquema desde {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        cursor.execute(f.read())


def bulk_load_csv(cursor, table_name, file_name):
    """Usa el comando COPY de PostgreSQL para carga ultra rápida."""
    file_path = os.path.abspath(os.path.join(STAGING_PATH, file_name))

    copy_sql = f"""
        COPY {table_name}
        FROM STDIN
        WITH (FORMAT CSV, HEADER, DELIMITER ',', ENCODING 'UTF8');
    """

    with open(file_path, 'r', encoding='utf-8') as f:
        cursor.copy_expert(sql=copy_sql, file=f)
    print(f"   ✓ Tabla {table_name} cargada exitosamente.")


def main():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True 
        cur = conn.cursor()

      
        execute_sql_file(cur, SQL_PATH)

        cur.execute("SET maintenance_work_mem = '2097151kB';")
        cur.execute("SET work_mem = '512MB';")

        print("\nIniciando carga masiva de datos...")
        start_time = time.time()

        bulk_load_csv(cur, "dim_tiempo", "dim_tiempo.csv")
        bulk_load_csv(cur, "dim_agencia", "dim_agencia.csv")
        bulk_load_csv(cur, "dim_tipo_queja", "dim_tipo_queja.csv")
        bulk_load_csv(cur, "dim_estado_resolucion", "dim_estado_resolucion.csv")
        bulk_load_csv(cur, "dim_distrito", "dim_distrito.csv")

        print("Cargando Tabla de Hechos (esto puede tardar unos minutos)...")
        bulk_load_csv(cur, "fact_quejas", "fact_quejas.csv")

        print("Creando Llaves Foráneas...")
        constraints_sql = """
                    ALTER TABLE Fact_Quejas
                    ADD CONSTRAINT fk_tiempo_creacion FOREIGN KEY (id_fecha_creacion) REFERENCES Dim_Tiempo(id_fecha),
                    ADD CONSTRAINT fk_tiempo_cierre FOREIGN KEY (id_fecha_cierre) REFERENCES Dim_Tiempo(id_fecha),
                    ADD CONSTRAINT fk_agencia FOREIGN KEY (id_agencia) REFERENCES Dim_Agencia(id_agencia),
                    ADD CONSTRAINT fk_tipo_queja FOREIGN KEY (id_tipo_queja) REFERENCES Dim_Tipo_Queja(id_tipo_queja),
                    ADD CONSTRAINT fk_estado_resolucion FOREIGN KEY (id_estado_resolucion) REFERENCES Dim_Estado_Resolucion(id_estado_resolucion),
                    ADD CONSTRAINT fk_distrito FOREIGN KEY (id_distrito) REFERENCES Dim_Distrito(id_distrito);
                """
        cur.execute(constraints_sql)
        print("   ✓ Llaves foráneas creadas y validadas correctamente.")

        # Descomentar para ejecución de índices
        # print("Creando índices...")
        # indexes_sql = """
        #                     SCRIPT SQL PARA CREACIÓN DE ÍNDICES
        #                 """
        # cur.execute(indexes_sql)
        # print("   ✓ Índices creados correctamente.")

        end_time = time.time()

        duration = end_time - start_time
        print("-" * 30)
        print(f"CARGA FINALIZADA")
        print(f"Tiempo total: {duration:.2f} segundos ({duration / 60:.2f} minutos)")
        print("-" * 30)

    except Exception as e:
        print(f"ERROR DURANTE LA CARGA: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    main()