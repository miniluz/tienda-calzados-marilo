# tienda-calzado-marilo

## Desarrollo

### Requisitos previos

Tener instalados [uv](https://docs.astral.sh/uv/getting-started/installation/) y [Docker](https://docs.docker.com/engine/install/).

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

Ejecute la base de datos y el servidor de administración de la base de datos (por defecto, se ejecutan en 15432 y 15433 respectivamente):

```
docker compose up
```

Y ejecute el servidor de desarrollo:

```
uv run manage.py runserver
```

## Cuentas de administración

El sistema crea automáticamente una cuenta de administrador al iniciar la aplicación con las siguientes credenciales:

- **Email/Usuario:** `admin@calzmarilo.es`
- **Contraseña:** El valor de la variable de entorno `ADMIN_PASSWORD`

Con esa cuenta más pueden ser creadas desde el panel de control para el resto de empleados.

