-- Responde a: ¿Cuál es el tiempo promedio de resolución de quejas (en horas/días), 
-- agrupado por Agencia, y cuáles han empeorado su tiempo de respuesta en el último año?
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
    WHERE f.id_fecha_creacion >= 20180101
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


-- Responde a: ¿Existen patrones estacionales marcados para los 5 problemas 
-- más comunes de la ciudad? (Ej. picos de quejas de calefacción vs. ruido).
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


--  Responde a: ¿Qué proporción de quejas se cierran el mismo día que son creadas, 
-- y corresponde esto a problemas de rápida solución o a cierres automáticos por falta de información?
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


-- Responde a: ¿Cómo varía el volumen de quejas entre días hábiles (lunes a viernes) 
-- y fines de semana, y cómo impacta este volumen en los tiempos de resolución del 
-- NYPD (Policía) frente al HPD (Vivienda)?
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


-- -------------------------------------------
-- Consultas para demostrar partition pruning
-- -------------------------------------------
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


EXPLAIN ANALYZE
SELECT COUNT(*)
FROM Fact_Quejas
WHERE id_fecha_creacion
BETWEEN 20190101 AND 20190131;
