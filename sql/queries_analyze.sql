--1.  tendencia mensual de quejas
EXPLAIN ANALYZE
SELECT t.anio,
       t.mes,
       COUNT(*) AS total_quejas
FROM Fact_Quejas f
JOIN Dim_Tiempo t
    ON f.id_fecha_creacion = t.id_fecha
WHERE t.anio = 2019
GROUP BY t.anio, t.mes
ORDER BY t.mes;

--2.Tipos de queja mas frecuentes
EXPLAIN ANALYZE
SELECT tq.descripcion_queja,
       COUNT(*) AS total_quejas
FROM Fact_Quejas f
JOIN Dim_Tipo_Queja tq
    ON f.id_tipo_queja = tq.id_tipo_queja
GROUP BY tq.descripcion_queja
ORDER BY total_quejas DESC
LIMIT 10;


--3. Distritos con mas quejas
EXPLAIN ANALYZE
SELECT d.nombre_distrito,
       COUNT(*) AS total_quejas
FROM Fact_Quejas f
JOIN Dim_Distrito d
    ON f.id_distrito = d.id_distrito
WHERE f.id_fecha_creacion BETWEEN 20190101 AND 20191231
GROUP BY d.nombre_distrito
ORDER BY total_quejas DESC;


--4.  agencias con mayor tiempo promedio de resolucion
EXPLAIN ANALYZE
SELECT a.nombre_completo,
       AVG(f.tiempo_resolucion_horas) AS promedio_horas
FROM Fact_Quejas f
JOIN Dim_Agencia a
    ON f.id_agencia = a.id_agencia
GROUP BY a.nombre_completo
ORDER BY promedio_horas DESC
LIMIT 10;

--5. evidencia de partition pruning
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM Fact_Quejas
WHERE id_fecha_creacion
BETWEEN 20190101 AND 20190131;
