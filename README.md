# Pipeline de Ingeniería de Datos y Dashboard Analítico: Quejas 311 NYC
Proyecto Final curso Base de Datos II, ETL + Data Warehouse

Este proyecto implementa un pipeline ETL, optimización de base de datos en PostgreSQL y un dashboard analítico en Power BI para analizar más de 22 millones de quejas ciudadanas de NYC.

---

## 1. Preguntas de Negocio a Responder

1. **Eficiencia y Desempeño Operativo:** ¿Cuál es el tiempo promedio de resolución de quejas (en horas/días) agrupado por Agencia, y cuáles han empeorado críticamente su tiempo de respuesta en el último año? 
   * *Visualización:* Gráfico de Dispersión.
2. **Ciclos y Tendencias:** ¿Existen patrones estacionales marcados para los 5 problemas más comunes de la ciudad? (Ej. picos de quejas de calefacción en invierno vs. ruido en verano).
   * *Visualización:* Gráfico de Líneas (Tendencia Temporal).
3. **Calidad de Cierre (Auditoría):** ¿Qué proporción de quejas se cierran el mismo día que son creadas, y corresponde esto a problemas de rápida solución o a cierres automáticos por falta de información?
   * *Visualización:* Gráfico Combo de Columnas.
4. **Impacto Temporal:** ¿Cómo varía el volumen de quejas entre días hábiles (lunes a viernes) y fines de semana, y cómo impacta este volumen en los tiempos de resolución del NYPD (Policía) frente al HPD (Vivienda)?
   * *Visualización:* Gráfico de Columnas Agrupadas.

---

## 2. Prerrequisitos

### Opción A: Linux

```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv unrar postgresql postgresql-contrib -y
```

Configurar PostgreSQL:
```bash
sudo -i -u postgres psql
```
```sql
ALTER USER postgres PASSWORD 'root';
CREATE DATABASE prueba_proyecto_final;
\q
```

### Opción B: Windows

1. Instalar Python 3 desde [python.org](https://www.python.org/) marcando **"Add Python.exe to PATH"**.
2. Instalar WinRAR y añadir `C:\Program Files\WinRAR\` a las variables de entorno (`Path`).
3. Instalar PostgreSQL desde [EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads) usando `root` como contraseña del superusuario.
4. Crear la base de datos:
```sql
CREATE DATABASE prueba_proyecto_final;
```

---

## 3. Instalación del Entorno Virtual

**`requirements.txt`:**
```text
pandas>=2.0.0
numpy>=1.24.0
polars>=0.19.0
requests>=2.31.0
rarfile>=4.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
```

### Linux (Bash)
```bash
python3 -m venv mi_entorno
source mi_entorno/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)
```powershell
python -m venv mi_entorno
.\mi_entorno\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Configuración de la Base de Datos

La configuración está definida directamente en `load.py`:
```python
DB_CONFIG = {
    "host": "localhost",
    "database": "prueba_proyecto_final",
    "user": "postgres",
    "password": "root"
}
```

---

## 4. Ejecución del Pipeline ETL

### Linux
```bash
python3 extract.py
python3 transform.py
python3 load.py
```

### Windows
```powershell
python extract.py
python transform.py
python load.py
```

---

## 5. Conexión del Dashboard (Modo Import)

El archivo `.pbix` se conecta a PostgreSQL en modalidad **Import**. Las consultas SQL delegan el trabajo de agregación a PostgreSQL y exponen las dimensiones de **Distrito** y **Año** en el `SELECT` y `GROUP BY` para que los segmentadores de Power BI funcionen correctamente.
