
DROP TABLE IF EXISTS Fact_Quejas CASCADE;
DROP TABLE IF EXISTS Dim_Tiempo CASCADE;
DROP TABLE IF EXISTS Dim_Agencia CASCADE;
DROP TABLE IF EXISTS Dim_Tipo_Queja CASCADE;
DROP TABLE IF EXISTS Dim_Estado_Resolucion CASCADE;
DROP TABLE IF EXISTS Dim_Distrito CASCADE;


CREATE TABLE Dim_Tiempo (
    id_fecha INT PRIMARY KEY,
    fecha_completa DATE NOT NULL,
    anio INT NOT NULL,
    mes INT NOT NULL,
    nombre_mes VARCHAR(20) NOT NULL,
    dia_semana VARCHAR(20) NOT NULL,
    es_fin_semana BOOLEAN NOT NULL,
    estacion VARCHAR(20)
);

CREATE TABLE Dim_Agencia (
    id_agencia INT PRIMARY KEY,
    siglas VARCHAR(50) NOT NULL,
    nombre_completo VARCHAR(255)
);

CREATE TABLE Dim_Tipo_Queja (
    id_tipo_queja INT PRIMARY KEY,
    descripcion_queja VARCHAR(255) NOT NULL
);

CREATE TABLE Dim_Estado_Resolucion (
    id_estado_resolucion INT PRIMARY KEY,
    status_ticket VARCHAR(50) NOT NULL,
    tipo_cierre VARCHAR(100) NOT NULL
);

CREATE TABLE Dim_Distrito (
    id_distrito INT PRIMARY KEY,
    nombre_distrito VARCHAR(100) NOT NULL
);

CREATE TABLE Fact_Quejas (
    unique_key BIGINT NOT NULL,
    id_fecha_creacion INT NOT NULL,
    id_fecha_cierre INT NOT NULL,
    id_agencia INT NOT NULL,
    id_tipo_queja INT NOT NULL,
    id_estado_resolucion INT NOT NULL,
    id_distrito INT NOT NULL,
    tiempo_resolucion_horas NUMERIC(10, 2),
    cerrado_mismo_dia BOOLEAN NOT NULL,
    
    PRIMARY KEY (unique_key, id_fecha_creacion)
) PARTITION BY RANGE (id_fecha_creacion);

-- LLAVES FORÁNEAS (EJECUCIÓN EN LOAD PARA ACELERAR CARGA) ------------
-- ALTER TABLE Fact_Quejas
--                     ADD CONSTRAINT fk_tiempo_creacion FOREIGN KEY (id_fecha_creacion) REFERENCES Dim_Tiempo(id_fecha),
--                     ADD CONSTRAINT fk_tiempo_cierre FOREIGN KEY (id_fecha_cierre) REFERENCES Dim_Tiempo(id_fecha),
--                     ADD CONSTRAINT fk_agencia FOREIGN KEY (id_agencia) REFERENCES Dim_Agencia(id_agencia),
--                     ADD CONSTRAINT fk_tipo_queja FOREIGN KEY (id_tipo_queja) REFERENCES Dim_Tipo_Queja(id_tipo_queja),
--                     ADD CONSTRAINT fk_estado_resolucion FOREIGN KEY (id_estado_resolucion) REFERENCES Dim_Estado_Resolucion(id_estado_resolucion),
--                     ADD CONSTRAINT fk_distrito FOREIGN KEY (id_distrito) REFERENCES Dim_Distrito(id_distrito);

DO $$
DECLARE
    fecha_inicio DATE := DATE '2010-01-01';
    fecha_fin    DATE := DATE '2020-01-01'; -- exclusivo
    actual DATE;
    siguiente DATE;
BEGIN
    actual := fecha_inicio;

    WHILE actual < fecha_fin LOOP
        siguiente := (actual + INTERVAL '1 month')::DATE;

        EXECUTE format(
            'CREATE TABLE fact_quejas_%s PARTITION OF Fact_Quejas
             FOR VALUES FROM (%s) TO (%s);',
            to_char(actual, 'YYYY_MM'),
            to_char(actual, 'YYYYMMDD'),
            to_char(siguiente, 'YYYYMMDD')
        );

        actual := siguiente;
    END LOOP;
END $$;

CREATE TABLE fact_quejas_default PARTITION OF Fact_Quejas DEFAULT;


--CREACION DE INDICES

--indices para la optimizacion de consultas olap
--indice para filtros temporales y partition pruning
CREATE INDEX idx_fact_fecha_creacion
ON Fact_Quejas(id_fecha_creacion);

-- Índice para consultas por tipo de queja
CREATE INDEX idx_fact_tipo_queja
ON Fact_Quejas(id_tipo_queja);

--indice compuesto para filtros por distro y fecha
--es importante porque es compuesto y se usa mucho en dashboards
CREATE INDEX idx_fact_distrito_fecha
ON Fact_Quejas(id_distrito, id_fecha_creacion);

-- Índice para análisis por agencia
CREATE INDEX idx_fact_agencia
ON Fact_Quejas(id_agencia);
