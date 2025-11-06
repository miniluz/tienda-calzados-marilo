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
