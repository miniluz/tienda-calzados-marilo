# tienda-calzado-marilo

## Desarrollo

### Requisitos previos

Tener instalados [uv](https://docs.astral.sh/uv/getting-started/installation/).
Si se quiere usar Postgres, se recomienda usar [Docker](https://docs.docker.com/engine/install/).

### Puesta en marcha

Instale los paquetes del proyecto:
```
uv sync
```

Monte las git hooks para garantizar la calidad:

```
uv run pre-commit install
```

Copie la envfile de desarrollo de ejemplo:

```
cp .env.development.example .env
```

Si quiere usar SQLite, ponga en el .env la variable `USE_SQLITE` a cualquier valor (ej. `True`).
Si no, Ejecute la base de datos y el servidor de administración de la base de datos (por defecto, se ejecutan en 15432 y 15433 respectivamente):

```
docker compose up
```

Para ver los correos en consola sin configurar SMTP, ponga `USE_CONSOLE_MAIL=True` en el `.env`.

Ejecute las migraciones de la base de datos:

```
uv run manage.py migrate
```

Pueble la base de datos con datos de ejemplo (opcional):

```
uv run manage.py seed
```

Este comando ejecuta automáticamente `seeders.py` en cada aplicación instalada que lo tenga definido.

Y ejecute el servidor de desarrollo:

```
uv run manage.py runserver
```

### Prueba con Docker

Para probar el comportamiento en producción localmente, use `docker-compose.prod.yml`:

Construir imagen:

```
docker compose -f docker-compose.prod.yml build
```

Iniciar contenedores:

```
docker compose -f docker-compose.prod.yml up -d
```

La aplicación estará en `http://localhost:8000` usando Gunicorn con 4 workers.

Ver logs:

```
docker compose -f docker-compose.prod.yml logs -f web
```

Reiniciar tras cambios:

```
docker compose -f docker-compose.prod.yml up -d --build
```

Shell de Django:

```
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

Poblar base de datos:

```
docker compose -f docker-compose.prod.yml exec web python manage.py seed
```

Detener contenedores:

```
docker compose -f docker-compose.prod.yml down
```

Respaldo de base de datos:

```
docker compose -f docker-compose.prod.yml exec db pg_dump -U marilo marilo > backup.sql
docker compose -f docker-compose.prod.yml exec -T db psql -U marilo marilo < backup.sql
```

## Cuentas de administración

El sistema crea automáticamente una cuenta de administrador al iniciar la aplicación con las siguientes credenciales:

- **Email/Usuario:** `admin@calzmarilo.es`
- **Contraseña:** El valor de la variable de entorno `ADMIN_PASSWORD`

Con esa cuenta más pueden ser creadas desde el panel de control para el resto de empleados.

## Producción con Docker

### Requisitos

- [Docker](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Configuración

Copie el archivo de ejemplo:

```
cp .env.production.example .env
```

Edite `.env` y cambie como mínimo:

```
DJANGO_SECRET_KEY=clave-secreta-aleatoria-muy-larga
ADMIN_PASSWORD=contraseña-segura
POSTGRES_PASSWORD=contraseña-base-datos-segura
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
```

### Construcción y ejecución

Construya la imagen:

```
docker compose -f docker-compose.prod.yml build
```

Inicie los contenedores:

```
docker compose -f docker-compose.prod.yml up -d
```

La aplicación estará en `http://localhost:8000`

### Comandos útiles

Ver logs:

```
docker compose -f docker-compose.prod.yml logs -f web
```

Detener contenedores:

```
docker compose -f docker-compose.prod.yml down
```

Reiniciar tras cambios:

```
docker compose -f docker-compose.prod.yml up -d --build
```

Shell de Django:

```
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

Poblar base de datos:

```
docker compose -f docker-compose.prod.yml exec web python manage.py seed
```

### Respaldo de base de datos

Crear respaldo:

```
docker compose -f docker-compose.prod.yml exec db pg_dump -U marilo_user tienda_marilo > backup.sql
```

Restaurar respaldo:

```
docker compose -f docker-compose.prod.yml exec -T db psql -U marilo_user tienda_marilo < backup.sql
```

