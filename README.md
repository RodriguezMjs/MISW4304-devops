# MISW4304-devops — Microservicio de lista negra global

Microservicio en Flask para la Entrega 1 (despliegue manual en AWS Elastic Beanstalk + RDS PostgreSQL).

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
tests/                      # Pruebas con pytest (API y servicios)
postman/                    # Colección y environment de Postman
.ebextensions/              # Health check en /ping
.ebignore                   # Lo que no se sube al zip de Beanstalk
```

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

pytest                         # pruebas (no requieren base de datos)
python application.py          # http://localhost:8000
flask --app application generate-token   # token para Postman
```

Para correr la app se necesita PostgreSQL. Ajusta `DATABASE_URL` en `.env` según la base que uses: PostgreSQL local, en Docker o la de RDS. Por ejemplo, con Docker:

```bash
docker run -d --name blacklist-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=blacklist postgres:16
```

Las pruebas mockean la capa de servicio y la sesión de SQLAlchemy, así que corren sin base de datos. La integración real con PostgreSQL se valida con la colección de Postman contra el ambiente desplegado.

## Token de autorización

El enunciado permite un token estático. Es un JWT sin expiración firmado con `JWT_SECRET_KEY`:

1. Define un `JWT_SECRET_KEY` largo (≥ 32 caracteres) y compártelo por un canal privado del equipo, **no en el repo**.
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
