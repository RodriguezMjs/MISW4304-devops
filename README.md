# MISW4304-devops — Microservicio de lista negra global

Microservicio en Flask con despliegue manual en AWS Elastic Beanstalk + RDS PostgreSQL y pruebas unitarias para integración continua.

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/blacklists` | Bearer | Agrega un email a la lista negra global |
| `GET` | `/blacklists/<email>` | Bearer | Indica si el email está en la lista negra y el motivo |
| `GET` | `/ping` | — | Health check para Beanstalk |

**POST /blacklists** — body JSON:

```json
{
  "email": "spam@example.com",
  "app_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "blocked_reason": "Envío de spam"
}
```

- `email` (obligatorio, email válido) · `app_uuid` (obligatorio, UUID) · `blocked_reason` (opcional, máx. 255).
- Internamente guarda la IP de origen y la fecha/hora de la solicitud.
- Respuestas: `201` creado · `400` datos inválidos · `401` sin token · `409` email ya registrado.

**GET /blacklists/&lt;email&gt;** → `200`:

```json
{ "email": "spam@example.com", "is_blacklisted": true, "blocked_reason": "Envío de spam" }
```

## Stack

Python · Flask · Flask-SQLAlchemy · Flask-RESTful · Flask-Marshmallow · Flask-JWT-Extended · Werkzeug · PostgreSQL · gunicorn

## Estructura

```
application.py              # Punto de entrada (Beanstalk busca la variable `application`)
app/
  __init__.py               # create_app, rutas, comando `generate-token`
  config.py                 # Config por variables de entorno (DATABASE_URL / RDS_*)
  extensions.py             # Instancias de db, ma y jwt (evita imports circulares)
  blacklist/                # Dominio: lista negra
    models.py               # Tabla Blacklist (SQLAlchemy)
    schemas.py              # Validación y serialización (Marshmallow)
    services.py             # Lógica de negocio, sin dependencias de HTTP
    resources.py            # Endpoints HTTP (Flask-RESTful), delegan en services
  health/
    resources.py            # GET /ping
tests/
  conftest.py               # Fixtures compartidas: app, cliente, token y contexto
  test_blacklist_api.py     # Pruebas HTTP con servicios simulados
  test_blacklist_services.py # Pruebas de negocio con consultas y sesión simuladas
postman/                    # Colección y environment de Postman
.ebextensions/              # Health check en /ping
.ebignore                   # Lo que no se sube al zip de Beanstalk
```

## Desarrollo local

Entorno de pruebas verificado con Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env

python -m pytest -v             # pruebas (no requieren base de datos)
python application.py          # http://localhost:8000
flask --app application generate-token   # token para Postman
```

Para correr la app se necesita PostgreSQL. Ajusta `DATABASE_URL` en `.env` según la base que uses: PostgreSQL local, en Docker o la de RDS. Por ejemplo, con Docker:

```bash
docker run -d --name blacklist-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=blacklist postgres:16
```

## Pruebas automatizadas

Después de instalar `requirements-dev.txt` y activar el entorno virtual:

```bash
python -m pytest -v                         # suite completa
python -m pytest -v tests/test_blacklist_api.py -k post  # escenarios del POST
python -m pytest -v tests/test_blacklist_services.py     # lógica de negocio
python -m pytest --junitxml=reports/pytest.xml            # reporte para CI
```

Ejecuta los comandos desde la raíz del repositorio. Para correr únicamente las pruebas no necesitas un archivo `.env`, PostgreSQL, credenciales de AWS ni un token externo. Pytest devuelve un código de salida distinto de cero si una prueba falla; el proceso de integración continua debe conservar ese resultado.

### Configuración y aislamiento

`tests/conftest.py` proporciona fixtures con alcance por prueba:

| Fixture | Propósito |
|---|---|
| `app` | Crea la aplicación con `TestConfig`, `TESTING=True` y creación de tablas desactivada |
| `client` | Cliente HTTP de Flask para realizar solicitudes sin levantar un servidor |
| `token` | JWT generado con el secreto exclusivo de pruebas |
| `auth` | Encabezado `Authorization: Bearer <token>` |
| `app_context` | Contexto de aplicación para las pruebas que usan Flask-SQLAlchemy |

El aislamiento se realiza con mocks de `unittest.mock`: las pruebas HTTP reemplazan las funciones de servicio donde las usa `app.blacklist.resources`; las pruebas de negocio reemplazan las consultas del modelo y la sesión de SQLAlchemy. `TestConfig` contiene una URI de PostgreSQL de prueba que selecciona explícitamente el driver `psycopg2` instalado por el proyecto, pero estas pruebas no abren conexiones ni crean tablas. Las nuevas pruebas deben mantener ese aislamiento y simular cualquier acceso a persistencia.

Este enfoque permite ejecutar la suite localmente y en CI sin un servidor de base de datos. Comprueba la validación, autenticación, respuestas HTTP y lógica de negocio; la persistencia real y las restricciones de PostgreSQL se verifican por separado mediante la colección de Postman contra el ambiente desplegado.

### Escenarios del POST `/blacklists`

| Escenario | Resultado esperado |
|---|---|
| Solicitud válida con token | `201`, email serializado y envío de la IP de origen al servicio |
| Email ya registrado | `409` con mensaje de duplicado |
| UUID inválido | `400` con error en `app_uuid` |
| Email mal formado | `400` con error en `email` |
| Motivo de 256 caracteres | `400` con error en `blocked_reason` |
| Solicitud sin token | `401`, sin invocar el servicio |
| Motivo omitido | `201`, motivo enviado como `None` |
| Motivo de exactamente 255 caracteres | `201` |
| Campos obligatorios ausentes | `400` con los campos correspondientes |

La suite también incluye consultas GET, health check y pruebas de normalización y almacenamiento mediante mocks. Los casos de validación tienen identificadores descriptivos para facilitar la lectura de los resultados en la terminal y en los reportes de CI.

## Token de autorización

El enunciado permite un token estático. Es un JWT sin expiración firmado con `JWT_SECRET_KEY`:

1. Define un `JWT_SECRET_KEY` largo (≥ 32 caracteres).
2. Genera el token con ese mismo secreto: `JWT_SECRET_KEY=... flask --app application generate-token`.
3. Usa ese token en Postman (variable `token`) y en `Authorization: Bearer <token>`.

Si se cambia el `JWT_SECRET_KEY` en Beanstalk, hay que regenerar el token.

## Despliegue en Elastic Beanstalk

Plataforma: **Python 3.x en Amazon Linux 2023**.

Variables de entorno del ambiente (Configuración → Actualizaciones, monitoreo y registro → Propiedades del entorno):

| Variable | Valor |
|---|---|
| `JWT_SECRET_KEY` | Secreto compartido del equipo |
| `DATABASE_URL` | `postgresql://<usuario>:<clave>@<endpoint-rds>:5432/<db>` |

Si la base de RDS se crea **asociada** al ambiente de Beanstalk, no hace falta `DATABASE_URL`: la app usa las variables `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME` y `RDS_PASSWORD` que Beanstalk inyecta. Para las pruebas de estrategias de despliegue es preferible una RDS **independiente**, así no se recrea con el ambiente.

Las URI con esquema `postgres://` o `postgresql://` se normalizan a `postgresql+psycopg2://` para usar el driver instalado por el proyecto. La configuración mediante `RDS_*` también selecciona `psycopg2`. Las URI que ya indican un driver se conservan; ese driver debe estar instalado en el ambiente.

El security group de RDS debe permitir el puerto 5432 desde el security group de las instancias de Beanstalk.

Generar el zip para subirlo por la consola:

```bash
git archive -o deploy.zip HEAD -- application.py app requirements.txt .ebextensions
```

Las tablas se crean automáticamente al arrancar (`db.create_all()`).

`PROXY_COUNT` (por defecto `2`) es la cantidad de proxies delante de gunicorn y sirve para registrar la IP real del cliente: ALB + nginx = 2. En un ambiente de una sola instancia (sin balanceador) usa `1`.

## Postman

Documentación publicada de la API: https://documenter.getpostman.com/view/14556408/2sBYHSxLjW#blacklist-api-misw4304

| Archivo | Uso |
|---|---|
| `postman/blacklists.postman_collection.json` | Colección con 12 escenarios, tests y ejemplos para la documentación |
| `postman/blacklists.postman_environment.json` | Environment local (`http://localhost:8000`) |
| `postman/blacklists-aws.postman_environment.json` | Environment de AWS (ajusta `base_url` a la URL del ambiente de Beanstalk) |

En el environment, reemplaza `[TOKEN_ESTATICO]` por el token. `test_email` y `app_uuid` se generan solos en cada corrida. Ejecuta la colección completa y en orden: el detalle de cada escenario está en la descripción de la colección.

Correr la colección desde la terminal:

```bash
npx newman run postman/blacklists.postman_collection.json   -e postman/blacklists-aws.postman_environment.json   --env-var base_url=http://<tu-ambiente>.elasticbeanstalk.com   --env-var token=<token>
``` 

