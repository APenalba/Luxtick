# Guia del Desarrollador -- LuxTick

Guia completa para desarrollar, testear, debugar y desplegar el proyecto.

---

## Tabla de Contenidos

1. [Requisitos previos](#1-requisitos-previos)
2. [Configuracion inicial del entorno](#2-configuracion-inicial-del-entorno)
3. [Linting y formateo](#3-linting-y-formateo)
4. [Type checking (mypy)](#4-type-checking-mypy)
5. [Tests](#5-tests)
   - 5.1 [Tests locales (sin PostgreSQL)](#51-tests-locales-sin-postgresql)
   - 5.2 [Tests con PostgreSQL](#52-tests-con-postgresql)
   - 5.3 [Todos los tests juntos](#53-todos-los-tests-juntos)
   - 5.4 [Opciones utiles de pytest](#54-opciones-utiles-de-pytest)
   - 5.5 [Coverage](#55-coverage)
6. [Base de datos y migraciones](#6-base-de-datos-y-migraciones)
7. [Debugging](#7-debugging)
8. [Ejecucion en desarrollo (dev)](#8-ejecucion-en-desarrollo-dev)
9. [Despliegue en produccion](#9-despliegue-en-produccion)
10. [CI/CD (GitHub Actions)](#10-cicd-github-actions)
11. [Estructura de archivos clave](#11-estructura-de-archivos-clave)
12. [Nota para Windows: Long Paths](#12-nota-para-windows-long-paths)
13. [Cheat sheet de comandos](#13-cheat-sheet-de-comandos)

---

## 1. Requisitos previos

| Herramienta       | Version minima | Para que sirve                         |
|-------------------|----------------|----------------------------------------|
| Python            | 3.12+          | Lenguaje del proyecto                  |
| Docker Desktop    | 24+            | Contenedores (PostgreSQL, despliegue)  |
| Docker Compose    | v2+            | Orquestacion de servicios              |
| Git               | 2.x            | Control de versiones                   |
| pip               | 23+            | Gestor de paquetes Python              |

**API Keys necesarias** (para ejecucion real del bot, no para tests):

- **Telegram Bot Token** -- obtener de [@BotFather](https://t.me/BotFather)
- **Google AI (Gemini) API Key** -- obtener en <https://aistudio.google.com/apikey>
- **OpenAI API Key** -- obtener en <https://platform.openai.com/api-keys>

---

## 2. Configuracion inicial del entorno

### 2.1 Clonar y crear el entorno virtual

```powershell
# Clonar el repositorio
git clone https://github.com/TU_USUARIO/chatbot.git
cd chatbot

# Crear entorno virtual
python -m venv .venv

# Activar (PowerShell)
.venv\Scripts\Activate.ps1

# Activar (CMD)
.venv\Scripts\activate.bat

# Activar (Linux/Mac)
source .venv/bin/activate
```

> **Nota Windows**: Si `litellm` falla al instalarse por rutas demasiado largas,
> crea el entorno en una ruta corta: `python -m venv C:\venv` y activa con
> `C:\venv\Scripts\Activate.ps1`. Ver [seccion 12](#12-nota-para-windows-long-paths).

### 2.2 Instalar dependencias

```powershell
# Dependencias de produccion + desarrollo (linters, pytest, mypy)
pip install -e ".[dev]"
```

El flag `-e` instala el proyecto en modo "editable", asi que los cambios en `src/`
se reflejan inmediatamente sin reinstalar.

### 2.3 Configurar variables de entorno

```powershell
# Copiar la plantilla
copy .env.example .env

# Editar .env con tus API keys reales
# (solo necesario para ejecutar el bot, NO para tests)
```

Las variables obligatorias para **ejecutar el bot** son:

| Variable              | Descripcion                                      |
|-----------------------|--------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`  | Token del bot de Telegram                        |
| `GEMINI_API_KEY`      | API key de Google AI para Gemini Flash           |
| `OPENAI_API_KEY`      | API key de OpenAI para GPT-4o (vision)           |
| `DATABASE_URL`        | URL de conexion a PostgreSQL (read-write)        |
| `DATABASE_URL_READONLY` | URL de conexion de solo lectura (text-to-SQL)  |

Para **tests** no necesitas configurar nada -- `tests/conftest.py` inyecta valores
de prueba automaticamente.

---

## 3. Linting y formateo

El proyecto usa **ruff** como linter y formateador (reemplaza flake8, isort, black).

### 3.1 Comprobar errores de linting (sin modificar archivos)

```powershell
ruff check src/ tests/
```

### 3.2 Corregir errores automaticamente

```powershell
ruff check src/ tests/ --fix
```

### 3.3 Comprobar formato (sin modificar archivos)

```powershell
ruff format --check src/ tests/
```

### 3.4 Aplicar formato automaticamente

```powershell
ruff format src/ tests/
```

### 3.5 Las dos cosas a la vez (comprobar que todo esta limpio)

```powershell
ruff check src/ tests/ && ruff format --check src/ tests/
```

**Configuracion de ruff** esta en `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "SIM", "TCH"]
```

Las reglas activas son:
- **E/W/F**: Errores y warnings basicos de estilo (pycodestyle, pyflakes)
- **I**: Orden de imports (isort)
- **N**: Convenciones de naming (pep8-naming)
- **UP**: Modernizacion de sintaxis para Python 3.12+ (pyupgrade)
- **B**: Deteccion de bugs comunes (flake8-bugbear)
- **A**: Shadowing de builtins (flake8-builtins)
- **SIM**: Simplificaciones de codigo
- **TCH**: Imports solo para type checking en bloque `TYPE_CHECKING`

---

## 4. Type checking (mypy)

```powershell
mypy src/ --ignore-missing-imports
```

La configuracion de mypy esta en `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

`--ignore-missing-imports` es necesario porque algunas dependencias (litellm, aiogram)
no tienen stubs de tipos completos.

---

## 5. Tests

El proyecto tiene **199 tests** organizados en 7 capas:

| Capa          | Directorio            | Necesita PostgreSQL | Tests |
|---------------|-----------------------|---------------------|-------|
| Unit          | `tests/unit/`         | No                  | 59    |
| Agent         | `tests/agent/`        | Parcialmente (3/20) | 20    |
| Bot           | `tests/bot/`          | No                  | 17    |
| Services      | `tests/services/`     | Si                  | 66    |
| Integration   | `tests/integration/`  | Si                  | 8     |
| Database      | `tests/db/`           | Si                  | 17    |

### 5.1 Tests locales (sin PostgreSQL)

Estos tests usan mocks para todo y no necesitan infraestructura externa.
**Son los que deberias ejecutar constantemente mientras desarrollas.**

```powershell
# Todos los tests que no necesitan PostgreSQL (104 tests)
pytest tests/unit/ tests/agent/ tests/bot/ -v -k "not ParseAndStore"
```

Desglose por area:

```powershell
# Solo unit tests (funciones puras, validaciones, config, middlewares)
pytest tests/unit/ -v

# Solo agent tests (agent core, tool executor, receipt parser mocked)
pytest tests/agent/ -v -k "not ParseAndStore"

# Solo bot handler tests (handlers de Telegram con bot mockeado)
pytest tests/bot/ -v
```

### 5.2 Tests con PostgreSQL

Estos tests necesitan una instancia real de PostgreSQL corriendo. Los tests usan una
**base de datos separada** (`luxtick_test`) para no interferir con los datos de
desarrollo. Esta BD se crea automaticamente al levantar Docker por primera vez.

**Paso 1: Levantar PostgreSQL con Docker**

```powershell
docker compose -f docker-compose.dev.yml up -d
```

Esto arranca un contenedor PostgreSQL 16 en `localhost:5433` con:
- Base de datos de desarrollo: `luxtick`
- Base de datos de tests: `luxtick_test` (creada por `scripts/init-test-db.sql`)
- Usuario: `bot` / Password: `bot_password`
- Usuario readonly: `bot_readonly` / Password: `readonly_password`

> **Nota**: El puerto externo es **5433** (no el 5432 por defecto de PostgreSQL) para
> evitar conflictos con otras instancias de PostgreSQL que puedas tener instaladas.

**Paso 2: Verificar que PostgreSQL esta listo**

```powershell
docker compose -f docker-compose.dev.yml ps
```

Deberias ver el contenedor con estado `healthy`.

**Paso 3: Ejecutar los tests**

```powershell
# Tests de servicios (66 tests -- queries reales contra PostgreSQL)
pytest tests/services/ -v

# Tests de base de datos (17 tests -- constraints, cascades, relationships)
pytest tests/db/ -v

# Tests de integracion end-to-end (8 tests -- flujos completos, solo LLM mockeado)
pytest tests/integration/ -v

# Tests de agent que necesitan DB (3 tests -- parse_and_store)
pytest tests/agent/test_receipt_parser.py::TestParseAndStore -v
```

**Paso 4: Parar PostgreSQL cuando termines**

```powershell
docker compose -f docker-compose.dev.yml down
```

Si quieres borrar tambien los datos persistidos:

```powershell
docker compose -f docker-compose.dev.yml down -v
```

> **Troubleshooting: "database luxtick_test does not exist"**
>
> Los scripts de inicializacion (`docker-entrypoint-initdb.d/`) solo se ejecutan la
> primera vez que se crea el volumen de Docker. Si ya tenias el contenedor creado antes
> de anadir `init-test-db.sql`, necesitas una de estas opciones:
>
> **Opcion A** -- Recrear el volumen (borra datos de desarrollo):
>
> ```powershell
> docker compose -f docker-compose.dev.yml down -v
> docker compose -f docker-compose.dev.yml up -d
> ```
>
> **Opcion B** -- Crear la BD manualmente (conserva datos existentes):
>
> ```powershell
> docker compose -f docker-compose.dev.yml exec db psql -U bot -d luxtick -c "CREATE DATABASE luxtick_test;"
> docker compose -f docker-compose.dev.yml exec db psql -U bot -d luxtick -c "GRANT ALL PRIVILEGES ON DATABASE luxtick_test TO bot;"
> docker compose -f docker-compose.dev.yml exec db psql -U bot -d luxtick -c "GRANT CONNECT ON DATABASE luxtick_test TO bot_readonly;"
> ```

### 5.3 Todos los tests juntos

Con PostgreSQL levantado:

```powershell
# Suite completa (199 tests)
pytest tests/ -v
```

### 5.4 Opciones utiles de pytest

```powershell
# Ejecutar un test especifico
pytest tests/unit/test_pure_functions.py::TestNormalizeStoreName::test_basic -v

# Ejecutar tests que coincidan con un patron
pytest tests/ -v -k "spending"

# Ejecutar tests por marcador
pytest tests/ -v -m unit          # Solo marcados @pytest.mark.unit
pytest tests/ -v -m service       # Solo marcados @pytest.mark.service
pytest tests/ -v -m integration   # Solo marcados @pytest.mark.integration
pytest tests/ -v -m "not db"      # Todos excepto marcados @pytest.mark.db

# Parar al primer fallo
pytest tests/ -v -x

# Mostrar traceback completo
pytest tests/ -v --tb=long

# Mostrar traceback corto (recomendado)
pytest tests/ -v --tb=short

# Mostrar print() y logging durante tests
pytest tests/ -v -s

# Ejecutar solo tests que fallaron la ultima vez
pytest tests/ --lf
```

### 5.5 Coverage

```powershell
# Generar reporte de cobertura en terminal
pytest tests/ --cov=src --cov-report=term-missing

# Generar reporte HTML (se abre en el navegador)
pytest tests/ --cov=src --cov-report=html
# Abrir htmlcov/index.html en el navegador
```

---

## 6. Base de datos y migraciones

### 6.1 Levantar PostgreSQL para desarrollo

```powershell
docker compose -f docker-compose.dev.yml up -d
```

### 6.2 Ejecutar migraciones existentes

```powershell
# Aplicar todas las migraciones pendientes
alembic upgrade head

# Ver el estado actual
alembic current

# Ver el historial de migraciones
alembic history
```

### 6.3 Crear una nueva migracion

Cuando modifiques modelos en `src/db/models.py`:

```powershell
# Auto-generar migracion basada en cambios del modelo
alembic revision --autogenerate -m "descripcion del cambio"

# IMPORTANTE: Revisa el archivo generado en alembic/versions/
# Alembic no siempre detecta todo correctamente

# Aplicar la nueva migracion
alembic upgrade head
```

### 6.4 Revertir una migracion

```powershell
# Revertir la ultima migracion
alembic downgrade -1

# Revertir a una revision especifica
alembic downgrade <revision_id>

# Revertir todas las migraciones
alembic downgrade base
```

### 6.5 Conectarse a la base de datos manualmente

```powershell
# Via Docker
docker compose -f docker-compose.dev.yml exec db psql -U bot -d luxtick

# Si tienes psql instalado localmente (puerto 5433)
psql -h localhost -p 5433 -U bot -d luxtick
```

Queries utiles para inspeccionar:

```sql
-- Ver todas las tablas
\dt

-- Ver estructura de una tabla
\d+ receipts

-- Contar registros
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM receipts;
SELECT COUNT(*) FROM receipt_items;
```

---

## 7. Debugging

### 7.1 Debugging con VS Code / Cursor

Crea o edita `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Run Bot",
            "type": "debugpy",
            "request": "launch",
            "module": "src.main",
            "envFile": "${workspaceFolder}/.env",
            "justMyCode": true
        },
        {
            "name": "Run Tests (unit)",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["tests/unit/", "-v", "--tb=short"],
            "justMyCode": true
        },
        {
            "name": "Run Tests (all)",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["tests/", "-v", "--tb=short"],
            "envFile": "${workspaceFolder}/.env",
            "justMyCode": true
        },
        {
            "name": "Run Specific Test File",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["${file}", "-v", "--tb=long"],
            "justMyCode": true
        }
    ]
}
```

Con esto puedes:
- Poner breakpoints haciendo clic en el margen izquierdo de cualquier linea
- Pulsar **F5** para ejecutar la configuracion seleccionada
- Inspeccionar variables, call stack, etc. en el panel de debug
- La configuracion "Run Specific Test File" ejecuta el archivo de test que tengas abierto

### 7.2 Debugging con breakpoints en el codigo

Puedes insertar un breakpoint programatico en cualquier punto:

```python
breakpoint()  # Se detiene aqui cuando ejecutas con el debugger
```

O usar `pdb` directamente:

```python
import pdb; pdb.set_trace()
```

### 7.3 Debugging con logs

El bot configura logging en `src/main.py`. Para aumentar la verbosidad:

```powershell
# En tu .env, cambia:
LOG_LEVEL=DEBUG
```

Tambien puedes anadir logs temporales en cualquier archivo:

```python
import logging
logger = logging.getLogger(__name__)
logger.debug("Variable x = %s", x)
```

### 7.4 Debugging de la base de datos

Para ver todas las queries SQL que SQLAlchemy ejecuta:

```powershell
# En tu .env:
LOG_LEVEL=DEBUG
```

O temporalmente en codigo:

```python
engine = create_async_engine(url, echo=True)  # echo=True muestra SQL
```

### 7.5 Debugging de llamadas al LLM

LiteLLM tiene su propio sistema de logs. Para ver lo que se envia/recibe:

```python
import litellm
litellm.set_verbose = True  # Muestra request/response completo
```

### 7.6 Debugging de tests

```powershell
# Ejecutar un solo test con output verbose
pytest tests/unit/test_pure_functions.py::TestNormalizeStoreName::test_basic -v -s --tb=long

# Ejecutar con pdb: se detiene automaticamente al fallar un test
pytest tests/unit/ --pdb

# Ejecutar con pdb en el primer fallo y parar
pytest tests/unit/ --pdb -x
```

---

## 8. Ejecucion en desarrollo (dev)

### 8.1 Setup completo paso a paso

```powershell
# 1. Activar entorno virtual
.venv\Scripts\Activate.ps1

# 2. Levantar la base de datos
docker compose -f docker-compose.dev.yml up -d

# 3. Ejecutar migraciones
alembic upgrade head

# 4. Ejecutar el bot (modo polling -- desarrollo)
python -m src.main
```

El bot arranca en **modo polling** (conecta a Telegram y escucha mensajes activamente).
No necesitas webhook, ni dominio publico, ni Caddy. Solo el token del bot.

### 8.2 Como funciona el modo polling vs webhook

| Aspecto        | Polling (dev)                        | Webhook (prod)                    |
|----------------|--------------------------------------|-----------------------------------|
| Activacion     | `BOT_WEBHOOK_URL` vacio/no definido  | `BOT_WEBHOOK_URL` con URL publica |
| Como funciona  | El bot pregunta a Telegram cada X ms | Telegram envia updates a tu URL   |
| Necesita IP publica | No                              | Si                                |
| Uso             | Desarrollo local                    | Produccion                        |

### 8.3 Hot reload

El proyecto no tiene hot reload integrado. Cuando hagas cambios en el codigo,
para el bot con `Ctrl+C` y vuelvelo a ejecutar:

```powershell
python -m src.main
```

Si quieres hot reload automatico, puedes usar `watchdog`:

```powershell
pip install watchdog
watchmedo auto-restart --patterns="*.py" --recursive -- python -m src.main
```

### 8.4 Probar el bot

1. Abre Telegram y busca tu bot por el nombre que le diste en BotFather
2. Envia `/start` -- deberia responderte con un mensaje de bienvenida
3. Envia un texto como "Cuanto he gastado este mes?" -- usara el agente LLM
4. Envia una foto de un ticket -- usara GPT-4o vision para parsearlo

---

## 9. Despliegue en produccion

### 9.1 Opcion A: Docker Compose en un VPS (recomendado)

**Paso 1: Preparar el servidor**

```bash
# En tu VPS (Ubuntu/Debian)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
```

**Paso 2: Clonar y configurar**

```bash
cd /opt
git clone https://github.com/TU_USUARIO/chatbot.git luxtick
cd luxtick

# Configurar variables de entorno
cp .env.example .env
nano .env  # Rellenar con valores reales de produccion
```

Variables criticas para produccion en `.env`:

```bash
TELEGRAM_BOT_TOKEN=tu-token-real
GEMINI_API_KEY=tu-key-real
OPENAI_API_KEY=tu-key-real

# Webhook (produccion) -- tu dominio publico
BOT_WEBHOOK_URL=https://tu-dominio.com
BOT_WEBHOOK_SECRET=un-string-aleatorio-largo

# Las DATABASE_URLs las sobreescribe docker-compose.yml,
# no necesitas cambiarlas
```

**Paso 3: Configurar el dominio (en `Caddyfile`)**

Edita `Caddyfile` para usar tu dominio real:

```
tu-dominio.com {
    reverse_proxy bot:8080
}
```

Caddy obtiene certificados HTTPS automaticamente via Let's Encrypt.

**Paso 4: Desplegar**

```bash
# Construir y arrancar todos los servicios
docker compose up -d --build

# Ejecutar migraciones
docker compose exec bot alembic upgrade head

# Verificar que todo esta corriendo
docker compose ps

# Ver logs del bot
docker compose logs -f bot
```

**Paso 5: Verificar**

```bash
# Los 3 servicios deberian estar "Up"
docker compose ps

# Deberia mostrar logs del bot arrancando
docker compose logs bot --tail 20
```

### 9.2 Opcion B: Despliegue automatico con GitHub Actions

El proyecto incluye un workflow de deploy en `.github/workflows/deploy.yml`.

**Configurar secrets en GitHub:**

Ve a tu repositorio > Settings > Secrets and variables > Actions, y anade:

| Secret          | Valor                                |
|-----------------|--------------------------------------|
| `VPS_HOST`      | IP o dominio de tu VPS               |
| `VPS_USER`      | Usuario SSH (ej: `deploy`)           |
| `VPS_SSH_KEY`   | Clave privada SSH para conectar      |

Cada push a `main` dispara automaticamente:

1. Pull del codigo en el VPS
2. Build de la imagen Docker
3. Reinicio de contenedores
4. Ejecucion de migraciones
5. Verificacion de que el bot esta corriendo

### 9.3 Comandos utiles en produccion

```bash
# Ver logs en tiempo real
docker compose logs -f bot

# Reiniciar solo el bot
docker compose restart bot

# Ejecutar una migracion
docker compose exec bot alembic upgrade head

# Conectarse a la DB de produccion
docker compose exec db psql -U bot -d luxtick

# Reconstruir sin cache (despues de cambiar dependencias)
docker compose build --no-cache bot
docker compose up -d

# Ver uso de recursos
docker stats
```

### 9.4 Backups de la base de datos

```bash
# Crear backup
docker compose exec db pg_dump -U bot luxtick > backup_$(date +%Y%m%d).sql

# Restaurar backup
cat backup_20260211.sql | docker compose exec -T db psql -U bot luxtick
```

---

## 10. CI/CD (GitHub Actions)

El proyecto tiene dos workflows:

### 10.1 CI (`.github/workflows/ci.yml`)

Se ejecuta en cada push a `main` y en cada Pull Request.

**Job 1: Lint & Type Check**
- Ejecuta `ruff check`
- Ejecuta `ruff format --check`
- Ejecuta `mypy`

**Job 2: Tests**
- Levanta un servicio PostgreSQL 16
- Instala dependencias
- Ejecuta migraciones con `alembic upgrade head`
- Ejecuta **toda** la suite de tests: `pytest tests/ -v --tb=short`

### 10.2 Deploy (`.github/workflows/deploy.yml`)

Se ejecuta en push a `main` (despues de CI) o manualmente desde GitHub.

Conecta por SSH a tu VPS y ejecuta el despliegue automatizado.

### 10.3 Ejecutar CI localmente (simulando lo que hace GitHub)

```powershell
# Paso 1: Lint
ruff check src/ tests/

# Paso 2: Format
ruff format --check src/ tests/

# Paso 3: Type check
mypy src/ --ignore-missing-imports

# Paso 4: Tests (necesita PostgreSQL levantado)
pytest tests/ -v --tb=short
```

---

## 11. Estructura de archivos clave

```
chatbot/
├── .env.example            # Plantilla de configuracion
├── .env                    # Tu configuracion local (NO se commitea)
├── .github/workflows/      # CI/CD pipelines
│   ├── ci.yml              # Lint + Tests en cada PR/push
│   └── deploy.yml          # Deploy automatico al VPS
│
├── alembic/                # Migraciones de base de datos
│   ├── env.py              # Config de Alembic (async)
│   └── versions/           # Archivos de migracion
│       └── 001_initial_schema.py
│
├── scripts/
│   ├── init-readonly-user.sql   # Crea el usuario read-only en PostgreSQL
│   └── init-test-db.sql         # Crea la BD de test (luxtick_test)
│
├── src/                         # Codigo fuente
│   ├── main.py                  # Punto de entrada (polling/webhook)
│   ├── config.py                # Settings desde variables de entorno
│   ├── agent/                   # Agente LLM
│   │   ├── core.py              # Bucle principal del agente
│   │   ├── prompts.py           # System prompts
│   │   ├── receipt_parser.py    # Parser de tickets con vision
│   │   ├── tool_executor.py     # Ejecutor de herramientas
│   │   └── tools.py             # Definiciones de herramientas (13 tools)
│   ├── bot/                     # Bot de Telegram
│   │   ├── router.py            # Setup del dispatcher aiogram
│   │   ├── handlers/            # Handlers de mensajes
│   │   └── middlewares/         # Auth y rate limiting
│   ├── db/                      # Capa de base de datos
│   │   ├── models.py            # Modelos SQLAlchemy (9 tablas)
│   │   └── session.py           # Gestion de sesiones async
│   └── services/                # Logica de negocio
│       ├── analytics.py         # Resumenes de gasto
│       ├── discount.py          # Gestion de descuentos
│       ├── product.py           # Matching fuzzy de productos
│       ├── purchase.py          # Operaciones de compra
│       ├── shopping_list.py     # Listas de la compra
│       └── text_to_sql.py       # SQL generado por LLM (solo lectura)
│
├── tests/                       # Suite de tests (199 tests)
│   ├── conftest.py              # Fixtures compartidos
│   ├── factories.py             # Fabricas de objetos de test
│   ├── unit/                    # Tests unitarios (59)
│   ├── agent/                   # Tests del agente (20)
│   ├── bot/                     # Tests de handlers (17)
│   ├── services/                # Tests de servicios (66)
│   ├── integration/             # Tests end-to-end (8)
│   └── db/                      # Tests de base de datos (17)
│
├── docker-compose.yml           # Produccion (bot + db + caddy)
├── docker-compose.dev.yml       # Desarrollo (solo db)
├── Dockerfile                   # Imagen del bot
├── Caddyfile                    # Config de reverse proxy
├── pyproject.toml               # Config del proyecto Python
├── alembic.ini                  # Config de Alembic
├── SPECS.md                     # Especificacion tecnica completa
├── CONTRIBUTING.md              # Guia de contribucion
└── README.md                    # Documentacion principal
```

---

## 12. Nota para Windows: Long Paths

Windows tiene un limite de 260 caracteres en las rutas de archivos. El paquete
`litellm` tiene dependencias con nombres de archivo muy largos, lo que puede causar
errores durante `pip install`.

### Solucion 1: Habilitar Long Paths en Windows (recomendado)

Abre PowerShell como Administrador:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

Reinicia el ordenador.

### Solucion 2: Usar una ruta corta para el venv

```powershell
python -m venv C:\venv
C:\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

---

## 13. Cheat sheet de comandos

### Desarrollo diario

```powershell
# Activar entorno
.venv\Scripts\Activate.ps1

# Levantar PostgreSQL
docker compose -f docker-compose.dev.yml up -d

# Correr migraciones
alembic upgrade head

# Ejecutar el bot
python -m src.main

# Parar el bot
Ctrl+C

# Parar PostgreSQL
docker compose -f docker-compose.dev.yml down
```

### Calidad de codigo

```powershell
# Lint (comprobar)
ruff check src/ tests/

# Lint (corregir automatico)
ruff check src/ tests/ --fix

# Formato (comprobar)
ruff format --check src/ tests/

# Formato (aplicar)
ruff format src/ tests/

# Type check
mypy src/ --ignore-missing-imports

# TODO junto (lo que ejecuta CI)
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ --ignore-missing-imports
```

### Tests

```powershell
# Tests rapidos (sin PostgreSQL) -- ejecutar frecuentemente
pytest tests/unit/ tests/agent/ tests/bot/ -v -k "not ParseAndStore"

# Tests con PostgreSQL (necesita docker compose up)
pytest tests/services/ tests/db/ tests/integration/ -v

# Suite completa
pytest tests/ -v

# Con coverage
pytest tests/ --cov=src --cov-report=term-missing

# Un test especifico
pytest tests/unit/test_pure_functions.py::TestNormalizeStoreName::test_basic -v

# Parar al primer fallo
pytest tests/ -v -x

# Debug al fallar
pytest tests/ --pdb -x
```

### Base de datos

```powershell
# Levantar
docker compose -f docker-compose.dev.yml up -d

# Parar
docker compose -f docker-compose.dev.yml down

# Parar y borrar datos
docker compose -f docker-compose.dev.yml down -v

# Migraciones
alembic upgrade head        # Aplicar
alembic downgrade -1        # Revertir ultima
alembic current             # Ver estado
alembic history             # Ver historial
alembic revision --autogenerate -m "descripcion"  # Crear nueva

# Conectarse a la DB
docker compose -f docker-compose.dev.yml exec db psql -U bot -d luxtick
```

### Produccion

```bash
# Desplegar
docker compose up -d --build
docker compose exec bot alembic upgrade head

# Logs
docker compose logs -f bot

# Reiniciar
docker compose restart bot

# Backup
docker compose exec db pg_dump -U bot luxtick > backup.sql
```
