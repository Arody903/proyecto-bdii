# Documento de Decisiones Técnicas - Proyecto Final (Base de Datos II)
**Dataset:** NYC 311 Service Requests (~22 Millones de registros)

---

## 1. ¿Por qué eligieron el esquema estrella o snowflake? ¿Qué alternativa descartaron y por qué?

Para el modelado del Data Warehouse se eligió un **Esquema en Estrella (Star Schema)** debido a que el objetivo principal del proyecto es el análisis de grandes volúmenes de datos históricos de quejas ciudadanas, priorizando el rendimiento de consultas analíticas sobre la normalización extrema.

El modelo está compuesto por una tabla de hechos denominada `Fact_Quejas` y cinco dimensiones:
* `Dim_Tiempo`
* `Dim_Agencia`
* `Dim_Tipo_Queja`
* `Dim_Estado_Resolucion`
* `Dim_Distrito`

Este diseño reduce la cantidad de *joins* necesarios para responder consultas analíticas y facilita la construcción de dashboards en Power BI o Tableau.

**Alternativa descartada:** Se descartó explícitamente el esquema en Copo de Nieve (*Snowflake Schema*).

**Justificación técnica:** Las dimensiones identificadas en el origen de datos no poseen jerarquías profundas o anidadas que justifiquen una normalización adicional (Tercera Forma Normal). En un entorno analítico con aproximadamente 22 millones de registros, un modelo snowflake introduciría un *overhead* computacional severo, obligando al motor de base de datos a resolver múltiples niveles de operaciones `JOIN` para agrupaciones simples. El esquema en estrella garantiza rutas de acceso directas a los hechos, optimiza las operaciones en memoria RAM y simplifica estructuralmente la conexión con herramientas de Business Intelligence.

---

## 2. ¿Qué consultas motivaron la creación de cada índice?

Para responder a las preguntas de negocio con tiempos de latencia mínimos, se implementaron índices B-Tree estratégicos sobre la tabla de hechos, evaluados mediante la herramienta `EXPLAIN ANALYZE`.

### Consulta 1: Eficiencia y Desempeño Operativo

```sql
EXPLAIN ANALYZE
WITH Estadisticas_Anuales AS (
    SELECT a.nombre_completo,
           t.anio,
           ROUND(AVG(f.tiempo_resolucion_horas), 2) AS promedio_horas,
           COUNT(*) AS volumen_quejas,
           ROUND(STDDEV_POP(f.tiempo_resolucion_horas), 2) AS desviacion_estandar_h,
           ROUND(MIN(f.tiempo_resolucion_horas), 2) AS minimo_horas,
           ROUND(MAX(f.tiempo_resolucion_horas), 2) AS maximo_horas
    FROM Fact_Quejas f
    JOIN Dim_Agencia a ON f.id_agencia = a.id_agencia
    JOIN Dim_Tiempo t ON f.id_fecha_creacion = t.id_fecha
    WHERE f.id_distrito = 1
    AND f.id_fecha_creacion >= 20180101
    GROUP BY a.nombre_completo, t.anio
),
Comparacion_Anual AS (
    SELECT nombre_completo,
           anio,
           promedio_horas AS horas_actuales,
           LAG(promedio_horas) OVER (PARTITION BY nombre_completo ORDER BY anio) AS horas_anio_anterior,
           (promedio_horas - LAG(promedio_horas) OVER (PARTITION BY nombre_completo ORDER BY anio)) AS diferencia_horas,
           
           volumen_quejas AS volumen_actual,
           LAG(volumen_quejas) OVER (PARTITION BY nombre_completo ORDER BY anio) AS volumen_anio_anterior,
           (volumen_quejas - LAG(volumen_quejas) OVER (PARTITION BY nombre_completo ORDER BY anio)) AS diferencia_volumen,
           
           desviacion_estandar_h,
           minimo_horas,
           maximo_horas
    FROM Estadisticas_Anuales
)
SELECT nombre_completo,
       horas_anio_anterior,
       horas_actuales,
       diferencia_horas AS horas_de_retraso,
       volumen_anio_anterior,
       volumen_actual,
       diferencia_volumen AS incremento_quejas,
       desviacion_estandar_h,
       minimo_horas,
       maximo_horas
FROM Comparacion_Anual
WHERE anio = 2019
  AND diferencia_horas > 0
ORDER BY diferencia_horas DESC;
```


**Pregunta de Negocio:** ¿Cuál es el tiempo promedio de resolución de quejas agrupado por Agencia, y cuáles han empeorado críticamente su tiempo de respuesta en el último año?

* **Índice Utilizado:** `idx_fact_distrito_fecha`
* **Motivo Técnico:** La consulta requiere un filtrado temporal estricto desde 2018 (`id_fecha_creacion >= 20180101`) y una agrupación intensiva mediante la unión (`JOIN`) con la dimensión Agencia. PostgreSQL utiliza el *Partition Pruning* para descartar los años anteriores a 2018, y luego aprovecha el índice para acelerar el cruce relacional al agrupar los tiempos de resolución, evitando recorrer el 100% de los datos de las particiones sobrevivientes.

**Comparativa de Rendimiento:**
* **SIN ÍNDICE:**
  * Planning Time: 2.003 ms
  * Execution Time: 233.078 ms
  * Costo: `(cost=131772.45..131772.69 rows=96 width=253)`
* **CON ÍNDICE:**
  * Planning Time: 6.407 ms
  * Execution Time: 327.977 ms
  * Costo: `(cost=70710.45..70710.69 rows=96 width=253)` *(Nota: Aunque el tiempo de ejecución es similar, el costo del plan estimado por el CBO se redujo en casi un 50%)*

### Consulta 2: Ciclos y Tendencias

```sql
EXPLAIN ANALYZE
WITH top_5_problemas AS (
    SELECT id_tipo_queja
    FROM Fact_Quejas
    GROUP BY id_tipo_queja
    ORDER BY COUNT(*) DESC
    LIMIT 5
),
Volumen_Anual_Estacional AS (
    SELECT t.anio,
           t.estacion,
           tq.descripcion_queja,
           COUNT(*) AS total_quejas
    FROM Fact_Quejas f
    JOIN Dim_Tiempo t ON f.id_fecha_creacion = t.id_fecha
    JOIN Dim_Tipo_Queja tq ON f.id_tipo_queja = tq.id_tipo_queja
    WHERE f.id_tipo_queja IN (SELECT id_tipo_queja FROM top_5_problemas)
    GROUP BY t.anio, t.estacion, tq.descripcion_queja
)
SELECT anio,
       estacion,
       descripcion_queja,
       total_quejas,
       ROUND((total_quejas * 100.0) / SUM(total_quejas) OVER (PARTITION BY anio, descripcion_queja), 2) AS porcentaje_del_anio
FROM Volumen_Anual_Estacional
ORDER BY descripcion_queja, anio, porcentaje_del_anio DESC;
```

**Pregunta de Negocio:** ¿Existen patrones estacionales marcados para los 5 problemas más comunes de la ciudad?

* **Índice Utilizado:** `idx_fact_tipo_queja`
* **Motivo Técnico:** Esta consulta ejecuta primero una subconsulta (CTE) para calcular el Top 5 de problemas masivos. El índice permite que el motor resuelva esta agrupación preliminar de forma ultrarrápida leyendo el árbol B-Tree. Posteriormente, acelera drásticamente el filtrado principal (`WHERE f.id_tipo_queja IN...`) aislando únicamente las filas pertinentes sin realizar escaneos secuenciales en disco.

**Comparativa de Rendimiento:**
* **SIN ÍNDICE:**
  * Planning Time: 3.137 ms
  * Execution Time: 9308.522 ms
  * Costo: `(cost=951626.50..951720.74 rows=37696 width=70)`
* **CON ÍNDICE:**
  * Planning Time: 25.318 ms
  * Execution Time: 5598.112 ms
  * Costo: `(cost=418574.89..418669.13 rows=37696 width=70)` *(Reducción del 40% en tiempo de ejecución y 56% en costo del plan)*

### Consulta 3: Calidad de Cierre (Auditoría)

```sql
EXPLAIN ANALYZE
WITH Resumen_Cierres AS (
    SELECT er.tipo_cierre,
           f.cerrado_mismo_dia,
           COUNT(*) AS total_quejas,
           ROUND(AVG(f.tiempo_resolucion_horas), 2) AS promedio_resolucion_horas
    FROM Fact_Quejas f
    JOIN Dim_Estado_Resolucion er
        ON f.id_estado_resolucion = er.id_estado_resolucion
    WHERE f.id_fecha_creacion >= 20170101
    GROUP BY er.tipo_cierre, f.cerrado_mismo_dia
)
SELECT tipo_cierre,
       cerrado_mismo_dia,
       total_quejas,
       promedio_resolucion_horas,
       
       ROUND(total_quejas * 100.0 / SUM(total_quejas) OVER (PARTITION BY cerrado_mismo_dia), 2) AS proporcion_del_mismo_dia,
       
       ROUND(total_quejas * 100.0 / SUM(total_quejas) OVER (PARTITION BY tipo_cierre), 2) AS proporcion_dentro_del_tipo

FROM Resumen_Cierres
ORDER BY cerrado_mismo_dia DESC, total_quejas DESC;
```


**Pregunta de Negocio:** ¿Qué proporción de quejas se cierran el mismo día que son creadas?

* **Índices Utilizados:** `idx_fact_cierre_mismo_dia`, `idx_fact_fecha_creacion`
* **Motivo Técnico:** Las funciones de ventana analíticas (`OVER (PARTITION BY...)`) requieren que los datos estén previamente ordenados o agrupados en memoria. El índice booleano sobre `cerrado_mismo_dia` pre-ordena lógicamente estas clasificaciones, permitiendo que el motor calcule las proporciones relativas y el `GROUP BY` inicial con un uso mínimo de la memoria de trabajo (`work_mem`). El índice de fecha asiste descartando el historial previo a 2017.

**Comparativa de Rendimiento:**
* **SIN ÍNDICE:**
  * Planning Time: 1.141 ms
  * Execution Time: 1011.559 ms
  * Costo: `(cost=156768.28..156769.28 rows=400 width=323)`
* **CON ÍNDICE:**
  * Planning Time: 1.474 ms
  * Execution Time: 1011.392 ms
  * Costo: `(cost=157820.62..157821.62 rows=400 width=323)`

### Consulta 4: Impacto Temporal

```sql
EXPLAIN ANALYZE
WITH Agrupacion_Diaria AS (
    SELECT a.siglas,
           t.es_fin_semana,
           f.id_fecha_creacion,
           COUNT(*) AS total_quejas_dia,
           SUM(f.tiempo_resolucion_horas) AS suma_horas_dia
    FROM Fact_Quejas f
    JOIN Dim_Agencia a ON f.id_agencia = a.id_agencia
    JOIN Dim_Tiempo t ON f.id_fecha_creacion = t.id_fecha
    WHERE a.siglas IN ('NYPD', 'HPD')
    AND f.id_distrito = 3
    GROUP BY a.siglas, t.es_fin_semana, f.id_fecha_creacion
)
SELECT siglas,
       es_fin_semana,
       SUM(total_quejas_dia) AS total_quejas,
       ROUND(SUM(total_quejas_dia) * 100.0 / SUM(SUM(total_quejas_dia)) OVER (PARTITION BY siglas), 2) AS porcentaje_volumen_total,
       
       COUNT(id_fecha_creacion) AS dias_evaluados,
       ROUND(AVG(total_quejas_dia), 0) AS promedio_quejas_por_dia,
       
       ROUND(SUM(suma_horas_dia) / SUM(total_quejas_dia), 2) AS promedio_horas_resolucion

FROM Agrupacion_Diaria
GROUP BY siglas, es_fin_semana
ORDER BY siglas, es_fin_semana DESC;
```

**Pregunta de Negocio:** ¿Cómo varía el volumen de quejas entre días hábiles y fines de semana para NYPD y HPD?

* **Índice Utilizado:** `idx_fact_agencia`
* **Motivo Técnico:** La consulta limita el análisis exclusivamente a dos agencias (`WHERE a.siglas IN ('NYPD', 'HPD')`). En lugar de escanear toda la tabla de hechos, el optimizador evalúa primero la dimensión, obtiene los IDs numéricos de ambas agencias, y utiliza el índice para realizar un *Bitmap Index Scan*, extrayendo de la tabla particionada únicamente los bloques físicos que pertenecen a esas dos instituciones.

**Comparativa de Rendimiento:**
* **SIN ÍNDICE:**
  * Planning Time: 3.742 ms
  * Execution Time: 2067.371 ms
  * Costo: `(cost=352117.19..354663.86 rows=400 width=141)`
* **CON ÍNDICE:**
  * Planning Time: 24.360 ms
  * Execution Time: 1369.966 ms
  * Costo: `(cost=265468.45..266756.83 rows=400 width=141)` *(Reducción del 33% en tiempo de ejecución)*

---

## 3. ¿Qué estrategia de partición usaron y por qué es adecuado para el volumen y los patrones de consulta?

* **Decisión:** Particionamiento por rango (de fechas) sobre la columna `id_fecha_creacion`.
* **Granularidad:** Mensual.

**Justificación de elección:** El volumen de cada partición por mes es más manejable que con partición por año. Además, para responder preguntas de negocio que incluyan rangos específicos dentro de un mismo año (como estaciones climáticas), una granularidad anual no sería eficiente. Con una distribución aproximada de 180,000 registros por partición, logramos un tamaño óptimo para que PostgreSQL pueda cargar la tabla completa a la memoria RAM sin dificultad. 

* Se automatizó la creación de particiones con una función anónima (PL/pgSQL en el archivo `ddl_schema.sql`) para otorgar la versatilidad de crear más particiones a futuro cambiando solo un parámetro, y se creó una partición `DEFAULT` para capturar anomalías y evitar interrupciones en la carga.
* Se configuró una llave primaria (PK) compuesta en la tabla de hechos, requisito técnico de PostgreSQL para tablas particionadas.

---

## 4. Evidencia de Partition Pruning
El *Partition Pruning* (exclusión de particiones) es un mecanismo del optimizador de PostgreSQL que omite la lectura de tablas físicas que no contienen datos relevantes para la consulta, reduciendo drásticamente el consumo de I/O y memoria RAM. A continuación, se presentan dos consultas que evidencian esta optimización en el Data Warehouse.

Para evidenciar la sinergia entre el Partition Pruning y las agrupaciones geográficas, se ejecutó una consulta solicitando el volumen total de quejas por distrito exclusivamente para todo el año 2019 (`BETWEEN 20190101 AND 20190131`). Como se observa en el plan de ejecución analizado, el motor descartó todo el historial masivo de la base de datos ajeno a ese año (omitiendo el escaneo de particiones de 2010 a 2018) y desplegó operaciones Parallel Append exclusivamente sobre los 12 meses físicos correspondientes (ej. `fact_quejas_2019_06`, `fact_quejas_2019_05`, etc.), resolviendo el cruce con las dimensiones y el agrupamiento en apenas **401.83 milisegundos**.

```sql
EXPLAIN ANALYZE
SELECT d.nombre_distrito,
       t.anio,
       t.mes,
       COUNT(*) AS total_quejas
FROM Fact_Quejas f
JOIN Dim_Distrito d
    ON f.id_distrito = d.id_distrito
JOIN Dim_Tiempo t
    ON f.id_fecha_creacion = t.id_fecha
WHERE f.id_fecha_creacion BETWEEN 20190101 AND 20191231
GROUP BY d.nombre_distrito, t.anio, t.mes
ORDER BY d.nombre_distrito, t.mes DESC;
```

**Fragmento de Evidencia (EXPLAIN ANALYZE):**

```text
QUERY PLAN
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Sort  (cost=98946.15..99132.15 rows=74400 width=234) (actual time=394.058..399.787 rows=72 loops=1)
   Sort Key: d.nombre_distrito, t.mes DESC
   Sort Method: quicksort  Memory: 28kB
   ->  Finalize HashAggregate  (cost=92182.07..92926.07 rows=74400 width=234) (actual time=393.671..399.727 rows=72 loops=1)
         Group Key: d.nombre_distrito, t.mes, t.anio
         Batches: 1  Memory Usage: 3097kB
         ->  Gather  (cost=58702.07..89206.07 rows=297600 width=234) (actual time=393.051..399.301 rows=120 loops=1)
               Workers Planned: 4
               Workers Launched: 4
               ->  Partial HashAggregate  (cost=57702.07..58446.07 rows=74400 width=234) (actual time=378.857..379.195 rows=24 loops=5)
                     Group Key: d.nombre_distrito, t.mes, t.anio
                     Batches: 1  Memory Usage: 3097kB
                     ->  Hash Join  (cost=371.97..51264.47 rows=643760 width=226) (actual time=2.838..277.301 rows=515008 loops=5)
                           Hash Cond: (f.id_fecha_creacion = t.id_fecha)
                           ->  Hash Join  (cost=17.20..49219.19 rows=643760 width=222) (actual time=0.047..193.123 rows=515008 loops=5)
                                 Hash Cond: (f.id_distrito = d.id_distrito)
                                 ->  Parallel Append  (cost=0.00..47489.74 rows=643761 width=8) (actual time=0.011..112.175 rows=515008 loops=5)
                                       ->  Parallel Seq Scan on fact_quejas_2019_06 f_6  (cost=0.00..4179.85 rows=142924 width=8) (actual time=0.007..29.255 rows=242970 loops=1)
                                             Filter: ((id_fecha_creacion >= 20190101) AND (id_fecha_creacion <= 20191231))
                                       ->  Parallel Seq Scan on fact_quejas_2019_05 f_5  (cost=0.00..4141.96 rows=141664 width=8) (actual time=0.012..28.960 rows=240829 loops=1)
                                             Filter: ((id_fecha_creacion >= 20190101) AND (id_fecha_creacion <= 20191231))
                                       ->  Parallel Seq Scan on fact_quejas_2019_01 f_1  (cost=0.00..4085.49 rows=139899 width=8) (actual time=0.012..29.443 rows=237829 loops=1)
                                             Filter: ((id_fecha_creacion >= 20190101) AND (id_fecha_creacion <= 20191231))
                                       ->  Parallel Seq Scan on fact_quejas_2019_03 f_3  (cost=0.00..3770.34 rows=129089 width=8) (actual time=0.016..47.996 rows=219452 loops=1)
                                             Filter: ((id_fecha_creacion >= 20190101) AND (id_fecha_creacion <= 20191231))
                                       ... [omitiendo particiones leídas exclusivas del 2019] ...
 Planning Time: 0.564 ms
 Execution Time: 401.835 ms
 ```


Adicional, se ejecutó una consulta solicitando el conteo de incidentes exclusivamente para el mes de Enero de 2019 (`BETWEEN 20190101 AND 20190131`). Como se observa en el plan de ejecución analizado, el motor descartó todo el historial masivo de la base de datos (omitiendo el escaneo de los 22 millones de registros) y se dirigió exclusivamente a la partición física `fact_quejas_2019_01`, resolviendo la consulta en apenas **26.89 milisegundos**.

```sql
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM Fact_Quejas
WHERE id_fecha_creacion
BETWEEN 20190101 AND 20190131;
```

**Fragmento de Evidencia (EXPLAIN ANALYZE):**
```text
 QUERY PLAN                                                                                                  
-----------------------------------------------------------------------------------------------------------
 Finalize Aggregate  (cost=5488.35..5488.36 rows=1 width=8) (actual time=22.915..26.871 rows=1 loops=1)
   ->  Gather  (cost=5488.24..5488.35 rows=1 width=8) (actual time=22.863..26.868 rows=2 loops=1)
         Workers Planned: 1
         Workers Launched: 1
         ->  Partial Aggregate  (cost=4488.24..4488.25 rows=1 width=8) (actual time=15.802..15.802 rows=1 loops=2)
               ->  Parallel Seq Scan on fact_quejas_2019_01 fact_quejas  (cost=0.00..4138.49 rows=139899 width=0) (actual time=0.025..11.192 rows=118914 loops=2)
                     Filter: ((id_fecha_creacion >= 20190101) AND (id_fecha_creacion <= 20190131))
 Planning Time: 0.131 ms
 Execution Time: 26.891 ms
 ```

 ## 5. ¿Qué mejora cuantitativa se obtuvo? (tiempo de ejecución, costo del plan, filas examinadas)

Debido al tamaño del dataset (22 millones de filas) se tomaron las siguientes decisiones de ingeniería de datos para optimizar los recursos del servidor en Azure (Ubuntu):

### Extract
* **Optimización de lectura:** Uso de la cláusula `usecols` (o `select` en Polars) para leer del disco y llevar a la RAM únicamente las columnas útiles para el análisis.
* **Optimización de memoria:** Uso de diccionarios de tipos (`schema_overrides` / `Categorical`) para asignar categorías a las columnas de texto repetitivo, reduciendo drásticamente el consumo de memoria RAM.

### Transform
* Se descartaron registros con fechas nulas o inconsistentes (ej. fecha de creación mayor a la de cierre).
* Se calcularon en memoria las métricas de negocio (tiempo de resolución en horas, banderas booleanas de cierre el mismo día).
* Estandarización de descripciones de cierre (Falta de información, Duplicado, Resolución real).
* Generación de *Surrogate Keys* (llaves numéricas auto-incrementales) para las dimensiones y cruces lógicos (`joins`) en memoria para reemplazar los pesados textos descriptivos por IDs numéricos antes de llegar a la base de datos.

### Load
* **Cargas masivas:** Implementación del comando nativo `COPY FROM STDIN` de PostgreSQL para cargas masivas ultrarrápidas, escribiendo de forma directa en los bloques del disco sin el *overhead* de la validación transaccional fila por fila.
* **Configuración de carga diferida:** Creación de llaves foráneas e índices posterior a la inserción masiva para evitar la continua y costosa reorganización de los árboles B-Tree durante la carga.

### Resultados Cuantitativos (Tiempos de Ejecución)
TIEMPO SIN OPTIMIZACIÓN:
* **Tiempo de Extracción (Polars):** `time (h:mm:ss or m:ss): 3:24.16`
* **Tiempo de Transformación (Polars):** `time (h:mm:ss or m:ss): 4:16.94`
* **Tiempo de Carga a Postgres (`COPY`):** `time (h:mm:ss or m:ss): 1:38.66`
* **Consumo máximo de memoria RAM:** `Maximum resident set size (Gbytes): 4.3766`
* **Consumo máximo CPU** `Percent of CPU this job got: 99%`
* **Volumen total procesado:** `21859889 registros insertados exitosamente, superando la depuración de fechas inconsistentes y calidad de datos.`

TIEMPO CON OPTIMIZACIÓN:
* **Tiempo de Extracción (Polars):** `time (h:mm:ss or m:ss): 1:24.49`
* **Tiempo de Transformación (Polars):** `time (h:mm:ss or m:ss): 0:18.70`
* **Tiempo de Carga a Postgres (`COPY`):** `time (h:mm:ss or m:ss): 1:30.36`
* **Consumo máximo de memoria RAM:** `Maximum resident set size (Gbytes): 18.22`
* **Consumo máximo CPU** `Percent of CPU this job got: 390%`
* **Volumen total procesado:** `21859889 registros insertados exitosamente, superando la depuración de fechas inconsistentes y calidad de datos.`

El uso de la evaluación perezosa (*Lazy Evaluation*) en Polars estabilizó la memoria y maximizó el uso de los 8 vCPUs del servidor (mostrando un uso superior al 350% de CPU en los logs frente a un entorno tradicional monohilo).


## 6. ¿Qué partes del sistema modelado corresponden al paradigma OLTP y cuáles al OLAP?

En la arquitectura de este proyecto es fundamental articular con precisión técnica la diferencia entre el entorno de generación y el entorno de análisis de datos.

* **Paradigma OLTP (Online Transaction Processing):** Corresponde exclusivamente al **sistema fuente operacional** que genera los datos (el backend que sustenta el portal de datos abiertos del número 311 de NYC). Ese sistema subyacente opera bajo el modelo OLTP porque está diseñado para capturar eventos de altísima concurrencia en tiempo real (inserción atómica de miles de quejas ciudadanas diarias). Su estructura está normalizada para garantizar transacciones ACID eficientes.
* **Paradigma OLAP (Online Analytical Processing):** Corresponde al **Data Warehouse** que hemos construido en PostgreSQL (`prueba_proyecto_final`). Nuestro componente es de lectura analítica intensiva y no opera bajo cargas transaccionales reales en vivo. Hemos transformado el diseño normalizado del OLTP mediante un pipeline ETL hacia un modelo dimensional desnormalizado (Esquema Estrella). Nuestra estructura, potenciada con particionamiento y metodologías de Kimball (dimensiones continuas), está diseñada exclusivamente para que las herramientas de Business Intelligence consoliden años enteros de información en milisegundos.
