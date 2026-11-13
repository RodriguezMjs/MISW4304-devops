# MISW4304-devops — Microservicio de lista negra global

Microservicio en Flask con RDS PostgreSQL, pruebas unitarias para integración continua y despliegues manuales en Elastic Beanstalk (entregas anteriores) y AWS Fargate (entrega 3).

## Despliegue en AWS Fargate (entrega 3)

Validación funcional del 12 de noviembre de 2026: `/ping` responde
`200` con `{"status":"ok"}` y todas las pruebas de la colección de Postman
aprobaron contra el ALB. El ambiente utiliza un servicio ECS sobre Fargate,
una imagen privada en ECR y PostgreSQL en RDS.

### Recursos del ambiente

| Recurso | Valor |
|---|---|
| Región | Ohio (`us-east-2`) |
| Cuenta AWS | `955501536413` |
| URL base | `http://blacklist-alb-1700016469.us-east-2.elb.amazonaws.com` |
| Clúster ECS | `blacklist-cluster` |
| Servicio ECS | `blacklist-service` |
| Controlador de despliegue | `CODE_DEPLOY` |
| Tareas deseadas | `1` |
| Definición de tarea inicial | `arn:aws:ecs:us-east-2:955501536413:task-definition/blacklist-task:1` |
| Plataforma | Fargate, Linux/X86_64, red `awsvpc` |
| Recursos de tarea | 256 unidades de CPU (0.25 vCPU), 512 MiB |
| Contenedor / puerto | `blacklist-api` / TCP `8000` (HTTP) |
| Repositorio ECR privado | `955501536413.dkr.ecr.us-east-2.amazonaws.com/blacklist-api` |
| Etiqueta inicial | `manual-9ed93840d3f1` |
| Digest de imagen | `sha256:9ed93840d3f120fce0a4b2dcbfbe511f499af8ed9fab6afc27270d9a4d1cd88c` |
| Balanceador | `blacklist-alb`, público, IPv4 |
| Listener productivo | HTTP `80`, inicialmente hacia `blacklist-blue` al 100 % |
| Target groups | `blacklist-blue` y `blacklist-green`, tipo IP, HTTP `8000` |
| ARN target group azul | `arn:aws:elasticloadbalancing:us-east-2:955501536413:targetgroup/blacklist-blue/d9bb0c5a11164225` |
| Health check del ALB | HTTP `/ping`, puerto de tráfico, éxito `200` |
| Periodo de gracia del servicio | `60` segundos |
| Rol de ejecución | `ecsTaskExecutionRole` |
| Rol de tarea | Sin rol de aplicación |
| Logs CloudWatch | `/ecs/blacklist-task`, región `us-east-2`, prefijo `ecs` |

### Red y base de datos

| Recurso | Configuración |
|---|---|
| VPC | `vpc-0dff2d1e5ebc79bbb` |
| Subred us-east-2a | `subnet-02869fc23f7919d86` |
| Subred us-east-2b | `subnet-048c9254e66bcc53c` |
| IP pública de tareas | Activada para salida a ECR, Secrets Manager y CloudWatch desde las subredes públicas |
| SG del ALB | `blacklist-alb-sg` / `sg-0f22e6568d5511396`: entrada TCP `80` desde `0.0.0.0/0` |
| SG de tareas | `blacklist-tasks-sg` / `sg-056c624822e8555d5`: entrada TCP `8000` solo desde el SG del ALB |
| Instancia RDS | `blacklist-db`, PostgreSQL, acceso público desactivado |
| Base / puerto | `blacklist` / `5432` |
| Endpoint RDS | `blacklist-db.croguoka4iq3.us-east-2.rds.amazonaws.com` |
| SG de RDS | `blacklist-rds-sg` / `sg-0e104a2c8361a157e`: entrada PostgreSQL desde el SG de tareas y la regla existente de Beanstalk |

RDS se reutiliza del ambiente anterior. La consulta de configuración de Beanstalk
confirmó `HasCoupledDatabase=false`: la instancia no está acoplada al ciclo de
vida de ese entorno. Se mantiene el acceso de Beanstalk a la base de datos.
ALB y tareas usan las dos subredes indicadas; la conexión a RDS utiliza su endpoint
privado. En Fargate se usa `PROXY_COUNT=1` porque solo hay un ALB delante de Gunicorn.

### Variables y secretos de ECS

| Variable | Tipo | Valor o referencia |
|---|---|---|
| `PROXY_COUNT` | Valor | `1` |
| `DATABASE_URL` | ValueFrom | `arn:aws:secretsmanager:us-east-2:955501536413:secret:blacklist/entrega3/database-url-oyIDnV` |
| `JWT_SECRET_KEY` | ValueFrom | `arn:aws:secretsmanager:us-east-2:955501536413:secret:blacklist/entrega3/jwt-secret-LMmfZ8` |

Cada secreto contiene una cadena de **texto sin formato**, sin JSON ni comillas
externas. `DATABASE_URL` contiene la URI completa con `sslmode=require` y
`JWT_SECRET_KEY` contiene la clave de firma. El rol `ecsTaskExecutionRole` tiene
la política insertada `blacklist-entrega3-read-secrets`, con
`secretsmanager:GetSecretValue` sobre esos dos ARN. ECS obtiene los valores al
iniciar cada tarea; los cambios de secretos requieren tareas nuevas para aplicarse.
El repositorio documenta las referencias a los secretos; sus valores y los tokens
de acceso se administran fuera del código fuente.

### Validación funcional

Para Postman, asignar la URL del ALB a `base_url` y un JWT firmado con el secreto
de Fargate a `token`. Esta variable contiene el JWT, sin el prefijo `Bearer`;
Authorization usa Bearer Token con `{{token}}`. El secreto de firma no es el token.

```bash
curl --fail --max-time 15 http://blacklist-alb-1700016469.us-east-2.elb.amazonaws.com/ping
```

La verificación del despliegue comprende el estado RUNNING de la tarea, un destino
Healthy en `blacklist-blue`, la respuesta del endpoint de salud y la ejecución
de la colección de Postman contra la URL del ALB. El health check no requiere
autenticación; las operaciones de lista negra requieren un JWT válido.

### Estado de la integración con CI/CD

El servicio está configurado con el controlador `CODE_DEPLOY` y dispone de los
grupos de destino `blacklist-blue` y `blacklist-green` para despliegues blue/green.
El listener productivo HTTP:80 dirige inicialmente el tráfico al grupo azul;
no hay un listener de prueba configurado.

Al 12 de noviembre de 2026, el despliegue manual y la validación funcional están
completados. La aplicación y el grupo de despliegue de CodeDeploy, la construcción
y publicación automatizadas de imágenes y su conexión en CodePipeline están
pendientes de configuración. Los escenarios de CI fallido, CI/CD exitosos y CI
exitoso con CD fallido aún no se han validado en este ambiente.

La imagen inicial usa una etiqueta manual basada en su identificador de imagen.
La publicación automatizada debe utilizar etiquetas únicas asociadas al commit
para mantener la trazabilidad de las versiones.

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/blacklists` | Bearer | Agrega un email a la lista negra global |
| `GET` | `/blacklists/<email>` | Bearer | Indica si el email está en la lista negra y el motivo |
| `GET` | `/ping` | — | Health check para Beanstalk y Fargate |

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
