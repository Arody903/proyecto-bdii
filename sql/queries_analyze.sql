
EXPLAIN ANALYZE
SELECT a.nombre_completo,
       t.anio,
       AVG(f.tiempo_resolucion_horas) AS promedio_horas
FROM Fact_Quejas f
JOIN Dim_Agencia a
    ON f.id_agencia = a.id_agencia
JOIN Dim_Tiempo t
    ON f.id_fecha_creacion = t.id_fecha
GROUP BY a.nombre_completo, t.anio
ORDER BY promedio_horas DESC;


EXPLAIN ANALYZE
SELECT t.nombre_mes,
       tq.descripcion_queja,
       COUNT(*) AS total_quejas
FROM Fact_Quejas f
JOIN Dim_Tiempo t
    ON f.id_fecha_creacion = t.id_fecha
JOIN Dim_Tipo_Queja tq
    ON f.id_tipo_queja = tq.id_tipo_queja
WHERE tq.descripcion_queja IN (
    'Noise - Residential',
    'Noise - Street/Sidewalk',
    'Blocked Driveway',
    'HEAT/HOT WATER',
    'Illegal Parking'
)
GROUP BY t.nombre_mes, tq.descripcion_queja
ORDER BY total_quejas DESC;


EXPLAIN ANALYZE
SELECT er.tipo_cierre,
       f.cerrado_mismo_dia,
       COUNT(*) AS total_quejas
FROM Fact_Quejas f
JOIN Dim_Estado_Resolucion er
    ON f.id_estado_resolucion = er.id_estado_resolucion
GROUP BY er.tipo_cierre, f.cerrado_mismo_dia
ORDER BY total_quejas DESC;


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
ORDER BY total_quejas DESC;


EXPLAIN ANALYZE
SELECT COUNT(*)
FROM Fact_Quejas
WHERE id_fecha_creacion
BETWEEN 20190101 AND 20190131;
