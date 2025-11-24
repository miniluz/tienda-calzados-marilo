# Guía de despliegue en producción - Tienda Calzados Marilo

## Introducción

Este documento proporciona las instrucciones necesarias para desplegar el sistema de comercio electrónico de Calzados Marilo en un entorno de producción. El sistema está desarrollado con Django 5.2 y está diseñado para gestionar el catálogo de productos, procesar pedidos de clientes, gestionar el inventario y las operaciones administrativas de la tienda.

Esta guía está dirigida al equipo técnico responsable del despliegue, ya sea personal interno de Calzados Marilo o un proveedor de servicios de hosting. Se asume un conocimiento básico de administración de sistemas Linux y gestión de aplicaciones web.

## Requisitos previos

Antes de proceder con el despliegue, es necesario contar con los siguientes componentes:

* **Python 3.12.11**: Las versiones anteriores a 3.12 no son compatibles debido a las características del lenguaje utilizadas en el código. En teoría, se podría usar una versión superior, pero el equipo de desarrollo ha realizado las pruebas con la versión 3.12.11.

* **PostgreSQL 17**: Sistema de gestión de bases de datos requerido para el entorno de producción. Aunque el sistema soporta SQLite para desarrollo, **nuestras pruebas de concurrencia fallan sistemáticamente con SQLite**. Esto significa que en un entorno de producción con múltiples usuarios simultáneos, SQLite causará errores de bloqueo de escritura y pérdida de datos, incluyendo posiblemente que un usuario **compre más zapatos de los que hay en el inventario**. Utilizar PostgreSQL es **obligatorio** para garantizar la integridad de los datos en producción.

* **Cuenta de Stripe**: Necesaria para procesar los pagos de los clientes. Deberá crear una cuenta en Stripe (<https://stripe.com>) y obtener las claves API correspondientes. Stripe proporciona claves de prueba para desarrollo y claves de producción que deberán utilizarse en el entorno real.

* **Servidor SMTP**: Requerido para el envío de correos electrónicos de confirmación de pedidos y notificaciones a los clientes. Puede utilizarse cualquier proveedor SMTP como Gmail, SendGrid, u Amazon SES. Será necesario contar con las credenciales de autenticación correspondientes.

* **Docker** (opcional): Recomendado para simplificar el despliegue. Si se opta por usar Docker, no será necesario instalar Python ni las dependencias manualmente, ya que la imagen de Docker incluye todo lo necesario.

## Configuración del entorno

El sistema se configura mediante variables de entorno, lo que permite ajustar el comportamiento de la aplicación sin modificar el código. Todas las variables deben definirse en un archivo `.env` ubicado en el directorio raíz del proyecto, o bien proporcionarse directamente al sistema según el método de despliegue elegido. Proveemos un archivo `.env.production.example` como plantilla.

### Variables de Django

**DJANGO_SECRET_KEY** es una clave criptográfica utilizada para firmar sesiones, tokens CSRF y otros elementos de seguridad de Django. Debe ser una cadena aleatoria y suficientemente larga, de al menos 50 caracteres. Nunca debe compartirse públicamente ni incluirse en el control de versiones. Puede generarse una clave segura ejecutando el siguiente comando en Python:

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Un ejemplo de valor sería:
```
DJANGO_SECRET_KEY=django-insecure-k8j2h$9sd@j1k2h3$jkds092j3klds9j2k3h$jkds092j3k
```

**DJANGO_DEBUG** controla si el modo de depuración está activo. En producción, esta variable debe estar completamente vacía (sin ningún valor). Cuando el modo de depuración está activo, Django muestra información detallada sobre errores que puede exponer detalles internos del sistema. En producción:

```
DJANGO_DEBUG=
```

**ALLOWED_HOSTS** especifica los nombres de dominio desde los cuales se permitirá acceder a la aplicación. Es una medida de seguridad para prevenir ataques de tipo Host Header. Debe incluir todos los dominios y subdominios por los que los clientes accederán al sitio, separados por comas:

```
ALLOWED_HOSTS=calzadosmarilo.es,www.calzadosmarilo.es
```

**CSRF_TRUSTED_ORIGINS** especifica los dominios para los que Django aceptará peticiones POST. Se pueden especificar
varios, separados por comas

```
CSRF_TRUSTED_ORIGINS=https://www.calzadosmarilo.es
```

### Variables de base de datos

**USE_SQLITE** debe dejarse completamente vacía en producción. Como se mencionó anteriormente, **las pruebas de concurrencia del sistema fallan con SQLite**, lo que resultará en errores cuando múltiples usuarios intenten realizar pedidos simultáneamente, entre otros casos:

```
USE_SQLITE=
```

**POSTGRES_HOST** es la dirección del servidor de base de datos PostgreSQL. Si la base de datos está en el mismo servidor que la aplicación, puede usarse `localhost`. Si se usa un servidor dedicado o un servicio en la nube, debe especificarse la dirección correspondiente:

```
POSTGRES_HOST=localhost
```

**POSTGRES_PORT** es el puerto en el que PostgreSQL está escuchando. El valor por defecto es 5432:

```
POSTGRES_PORT=5432
```

**POSTGRES_USER** es el nombre de usuario para conectarse a PostgreSQL:

```
POSTGRES_USER=marilo
```

**POSTGRES_PASSWORD** es la contraseña del usuario de PostgreSQL. Debe ser una contraseña segura:

```
POSTGRES_PASSWORD=contraseña_segura_de_base_de_datos
```

**POSTGRES_DB** es el nombre de la base de datos que utilizará la aplicación. Esta base de datos debe crearse previamente en PostgreSQL:

```
POSTGRES_DB=tienda_marilo
```

### Cuenta de Administrador

**ADMIN_PASSWORD** es la contraseña que se asignará a la cuenta de administrador que el sistema crea automáticamente. El usuario de esta cuenta es siempre `admin@calzmarilo.es`. Es importante elegir una contraseña robusta, ya que esta cuenta tiene acceso completo al sistema:

```
ADMIN_PASSWORD=Contraseña_Segura_Admin_2025
```

### Reglas de negocio

Estas variables permiten configurar aspectos del comportamiento comercial de la tienda sin necesidad de modificar código. Todas tienen valores por defecto que pueden omitirse si se desea usar la configuración recomendada.

**TAX_RATE** define el porcentaje de IVA que se aplicará a los pedidos (por defecto, el 21% de IVA):

```
TAX_RATE=21.0
```

**DELIVERY_COST** establece el coste fijo de envío que se añadirá a cada pedido, expresado en euros (por defecto, 5€):

```
DELIVERY_COST=5.0
```

**CHECKOUT_FORM_WINDOW_MINUTES** determina cuántos minutos tiene un cliente para completar los formularios de datos personales y dirección de envío una vez que ha añadido productos al carrito. Durante este tiempo, el stock de los productos queda reservado para ese cliente (por defecto, 10):

```
CHECKOUT_FORM_WINDOW_MINUTES=10
```

**PAYMENT_WINDOW_MINUTES** establece cuántos minutos tiene el cliente para completar el pago una vez que ha enviado sus datos. Si no completa el pago en este plazo, el pedido se marca como expirado y el stock se libera. Debe ser de más de 30 minutos (por defecto 31):

```
PAYMENT_WINDOW_MINUTES=31
```

**CLEANUP_CRON_MINUTES** define cada cuántos minutos el sistema ejecutará una tarea automática de limpieza que elimina pedidos expirados y libera el stock reservado (por defecto, 5):

```
CLEANUP_CRON_MINUTES=5
```

### Stripe (Pagos)

Para procesar pagos con tarjeta de crédito, el sistema utiliza Stripe. Es necesario crear una cuenta en Stripe y configurar el webhook endpoint en el panel de Stripe para recibir notificaciones de eventos de pago.

**STRIPE_PUBLISHABLE_KEY** es la clave pública de Stripe, que se utiliza en el navegador del cliente. Esta clave comienza con `pk_live_` en producción o `pk_test_` en modo de pruebas:

```
STRIPE_PUBLISHABLE_KEY=pk_live_51K...
```

**STRIPE_SECRET_KEY** es la clave secreta de Stripe, que se utiliza en el servidor para comunicarse con la API de Stripe. Esta clave comienza con `sk_live_` en producción o `sk_test_` en modo de pruebas. Debe mantenerse confidencial:

```
STRIPE_SECRET_KEY=sk_live_51K...
```

**STRIPE_WEBHOOK_SECRET** es el secreto del webhook que Stripe proporciona cuando se configura un endpoint de webhook en su panel. El sistema necesita este secreto para verificar que las notificaciones provienen realmente de Stripe. Este valor comienza con `whsec_`:

```
STRIPE_WEBHOOK_SECRET=whsec_...
```

Es fundamental utilizar las claves de producción (`pk_live_` y `sk_live_`) en el entorno real. Las claves de prueba solo deben usarse durante el desarrollo y testing.

### Correo electrónico

El sistema envía correos electrónicos de confirmación de pedidos y notificaciones a los clientes.

**USE_CONSOLE_MAIL** debe estar vacía en producción para que los correos se envíen. Si tiene algún valor, los correos solo se mostrarán en los logs del servidor:

```
USE_CONSOLE_MAIL=
```

**WEBSITE_URL** es la URL completa del sitio web, incluyendo el protocolo. Esta URL se utiliza en los enlaces de los correos electrónicos:

```
WEBSITE_URL=https://www.calzadosmarilo.es
```

**EMAIL_HOST** es la dirección del servidor SMTP:

```
EMAIL_HOST=smtp.gmail.com
```

**EMAIL_PORT** es el puerto del servidor SMTP. Los valores comunes son 587 para TLS o 465 para SSL:

```
EMAIL_PORT=587
```

**EMAIL_HOST_USER** es el nombre de usuario o dirección de correo para autenticarse en el servidor SMTP:

```
EMAIL_HOST_USER=noreply@calzadosmarilo.es
```

**EMAIL_HOST_PASSWORD** es la contraseña del correo. Si se usa Gmail, se recomienda utilizar una contraseña de aplicación en lugar de la contraseña principal de la cuenta:

```
EMAIL_HOST_PASSWORD=contraseña_del_correo
```

**EMAIL_USE_TLS** debe establecerse a `True` si el servidor SMTP usa TLS (normalmente, en el puerto 587):

```
EMAIL_USE_TLS=True
```

**EMAIL_USE_SSL** debe establecerse a `True` si el servidor SMTP usa SSL (normalmente, en el puerto 465). Solo una de estas dos opciones debe estar activa:

```
EMAIL_USE_SSL=
```

## Instalación de dependencias

El sistema requiere varias bibliotecas de Python que deben instalarse antes de ejecutar la aplicación.

### Con UV (recomendado)

UV es una herramienta moderna y rápida para gestionar dependencias de Python, y fue la usada durante el desarrollo.
Garantiza que exactamente la misma versión de cada dependencia es usada que en el desarrollo.
Si se opta por usar UV, primero debe instalarse siguiendo las instrucciones en <https://docs.astral.sh/uv/getting-started/installation/>.

Una vez instalado UV, las dependencias se instalan ejecutando:

```bash
uv sync --no-dev --frozen
```

Este comando lee el archivo `pyproject.toml` e instala todas las dependencias necesarias en un entorno virtual gestionado por UV.

### Sin UV (tradicional)

Alternativamente, se proporciona un archivo `requirements.txt` que lista las dependencias en formato tradicional. Para instalar usando pip:

```bash
pip install -r requirements.txt
```

Se recomienda realizar esta instalación dentro de un entorno virtual de Python para aislar las dependencias del sistema:

```bash
python -m venv .venv
source .venv/bin/activate  # En Linux/Mac
pip install -r requirements.txt
```

## Preparación de la base de datos

Antes de ejecutar la aplicación por primera vez, es necesario crear la base de datos en PostgreSQL y aplicar las migraciones que crean la estructura de tablas necesaria.

Primero, conéctese a PostgreSQL como usuario administrador y cree la base de datos:

```sql
CREATE DATABASE tienda_marilo;
CREATE USER marilo WITH PASSWORD 'su_contraseña_segura';
GRANT ALL PRIVILEGES ON DATABASE tienda_marilo TO marilo;
```

Una vez creada la base de datos, ejecute las migraciones de Django:

```bash
python manage.py migrate
```

Este comando crea todas las tablas necesarias en la base de datos, incluyendo tablas para usuarios, productos, pedidos, carritos de compra, y demás entidades del sistema.

## Métodos de ejecución

Existen tres métodos principales para ejecutar la aplicación en producción.

### Ejecución directa con Python

El servidor de desarrollo integrado de Django puede ejecutarse con:

```bash
python manage.py runserver 0.0.0.0:8000
```

Sin embargo, este método está diseñado solo para desarrollo y pruebas. No debe utilizarse en producción porque:

- Maneja solo una petición a la vez, sin concurrencia real
- No está optimizado para rendimiento
- No incluye características de seguridad necesarias en producción
- No es estable para ejecución continua

Este método solo se menciona con propósitos de testing inicial.

### Ejecución con Gunicorn

Gunicorn es un servidor WSGI robusto y ampliamente utilizado para aplicaciones Python en producción.
Es el método recomendado cuando se despliega directamente en un servidor Linux.

Primero, instale Gunicorn si no está incluido en las dependencias:

```bash
pip install gunicorn
```

La aplicación puede ejecutarse con:

```bash
gunicorn tienda_calzados_marilo.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 60
```

Los parámetros importantes son:

- `--bind 0.0.0.0:8000` especifica la dirección y puerto donde el servidor escuchará peticiones
- `--workers 4` define el número de procesos worker que manejarán peticiones concurrentes
- `--timeout 60` establece el tiempo máximo en segundos que un worker puede tardar en procesar una petición

#### Archivos estáticos

Cuando se usa Gunicorn, los archivos estáticos (CSS, JavaScript, imágenes) y los archivos multimedia (imágenes de productos subidas por los usuarios) deben recolectarse y servirse por separado. Ejecute:

```bash
python manage.py collectstatic --noinput
```

Este comando copia todos los archivos estáticos al directorio `./staticfiles/`. Estos archivos, junto con el directorio `./media/`, deben servirse mediante un servidor web como Nginx o Apache configurado como proxy inverso frente a Gunicorn:

- El directorio `./staticfiles/` debe servirse en la URL `/static/`
- El directorio `./media/` debe servirse en la URL `/media/`

### Ejecución con Docker

Docker proporciona un método de despliegue aislado y reproducible, empaquetando la aplicación con todas sus dependencias en un contenedor.
Es el método recomendado para desplegar la aplicación.

#### Construcción de la imagen

Desde el directorio raíz del proyecto, construya la imagen de Docker:

```bash
docker build -t tienda-marilo .
```

Este proceso puede tardar varios minutos la primera vez, ya que descarga la imagen base de Python e instala todas las dependencias.

#### Variables de entorno

Las variables de entorno pueden proporcionarse de dos formas. La primera es mediante un archivo `.env` usando la opción `--env-file`:

```bash
docker run -d -p 8000:8000 --env-file .env tienda-marilo
```

La segunda es pasando cada variable individualmente con la opción `-e`:

```bash
docker run -d -p 8000:8000 \
  -e DJANGO_SECRET_KEY="..." \
  -e POSTGRES_HOST="..." \
  -e POSTGRES_PASSWORD="..." \
  tienda-marilo
```

#### Volúmenes y archivos estáticos

El contenedor ejecuta automáticamente las migraciones de base de datos y recolecta los archivos estáticos al iniciar. Los archivos estáticos se guardan en `/app/staticfiles/` y los archivos multimedia en `/app/media/` dentro del contenedor.

Para acceder a estos archivos desde fuera del contenedor y poder servirlos con un servidor web, debe mapear estos directorios a volúmenes del host:

```bash
docker run -d -p 8000:8000 \
  --env-file .env \
  -v /var/www/tienda-marilo/static:/app/staticfiles \
  -v /var/www/tienda-marilo/media:/app/media \
  tienda-marilo
```

Con esta configuración, los archivos estarán disponibles en el servidor host y deben servirse mediante un servidor web:

- `/var/www/tienda-marilo/static` debe servirse en la URL `/static/`
- `/var/www/tienda-marilo/media` debe servirse en la URL `/media/`

Si la base de datos PostgreSQL también se ejecuta en un contenedor (no recomendado para producción, pero posible para instalaciones simples), también necesitará un volumen para persistir los datos:

```bash
docker run -d \
  --name postgres-marilo \
  -e POSTGRES_PASSWORD=contraseña \
  -e POSTGRES_DB=tienda_marilo \
  -e POSTGRES_USER=marilo \
  -v /var/lib/postgresql/data:/var/lib/postgresql/data \
  postgres:17.6
```

#### Logs del contenedor

Para ver los logs de la aplicación ejecutándose en Docker:

```bash
docker logs -f tienda-marilo
```

Para detener el contenedor:

```bash
docker stop tienda-marilo
```

Para reiniciar tras cambios:

```bash
docker stop tienda-marilo
docker rm tienda-marilo
docker build -t tienda-marilo .
docker run -d -p 8000:8000 --env-file .env -v /var/www/tienda-marilo/static:/app/staticfiles tienda-marilo
```

## Cuenta de administrador y gestión del sistema

### Cuenta de administrador automática

El sistema crea automáticamente una cuenta de administrador la primera vez que se inicia la aplicación. Esta cuenta permite el acceso completo al panel de administración sin necesidad de crearla manualmente mediante comandos.

Las credenciales de esta cuenta son:

- **Usuario:** `admin@calzmarilo.es`
- **Contraseña:** El valor configurado en la variable de entorno `ADMIN_PASSWORD`

Para acceder al sistema, navegue a la página principal del sitio web y haga clic en "Iniciar sesión" en la barra de navegación. Introduzca estas credenciales para acceder.

### Panel de administración

Una vez iniciada sesión con la cuenta de administrador (usando el botón "Iniciar sesión" en la esquina superior derecha), aparecerá un elemento en la barra de navegación llamado "Panel de Administración". Desde este panel es posible:

- Crear nuevas cuentas de administrador para otros miembros del personal
- Gestionar marcas y categorías de productos
- Añadir y editar productos del catálogo
- Gestionar el stock de cada talla de producto
- Administrar cuentas de clientes
- Ver y gestionar pedidos
- Ver el catálogo tal como lo ven los clientes
- Ejecutar manualmente la limpieza de pedidos expirados para reclamar stock reservado

Cada cuenta de personal creada tendrá acceso completo al panel de gestión. El sistema proporciona una interfaz intuitiva para todas estas operaciones de administración.

## Mantenimiento básico

### Respaldos de base de datos

Es fundamental realizar respaldos regulares de la base de datos para proteger la información de productos, pedidos y clientes. La frecuencia recomendada es al menos una vez al día, preferiblemente de forma automática mediante una tarea programada.

Para crear un respaldo de la base de datos PostgreSQL:

```bash
pg_dump -U marilo -d tienda_marilo > respaldo_$(date +%Y%m%d).sql
```

Si se usa Docker para la base de datos:

```bash
docker exec postgres-marilo pg_dump -U marilo tienda_marilo > respaldo_$(date +%Y%m%d).sql
```

Para restaurar un respaldo:

```bash
psql -U marilo -d tienda_marilo < respaldo_20250124.sql
```

Se recomienda mantener los respaldos en un servidor diferente o servicio de almacenamiento en la nube para protegerse contra fallos de hardware.

### Monitorización de logs

Los logs del sistema contienen información valiosa sobre el funcionamiento de la aplicación, errores que puedan ocurrir, y actividad de usuarios. Es importante revisarlos periódicamente.

Si se usa Gunicorn con systemd:

```bash
sudo journalctl -u tienda-marilo -f
```

Si se usa Docker:

```bash
docker logs -f tienda-marilo
```

Los logs de acceso y errores ayudan a identificar problemas de configuración, intentos de acceso no autorizados, o errores en la lógica de negocio que deban reportarse al equipo de desarrollo.

### Limpieza automática de pedidos

El sistema incluye una tarea automática de limpieza que se ejecuta periódicamente según la configuración de `CLEANUP_CRON_MINUTES`. Esta tarea:

- Identifica pedidos que han expirado (clientes que no completaron el pago a tiempo)
- Cancela estos pedidos automáticamente
- Libera el stock que estaba reservado para esos pedidos
- Elimina los registros de pedidos no completados para mantener la base de datos limpia

Esta limpieza es completamente automática y no requiere intervención manual. Sin embargo, es útil verificar ocasionalmente en los logs que la tarea se está ejecutando correctamente.
De ser necesario, también puede ser ejecutada manualmente desde el panel de administración.

## Entorno de referencia

Los desarrolladores probaron ejecutar la aplicación en un entorno similar al de producción
usando el entorno definido en `docker-compose.prod.yml`.
No es necesario desplegar con este archivo,
pero puede ser usado como referencia para ver cómo se conectan los componentes del sistema.

En particular, `nginx.conf` muestra cómo configurar Nginx correctamente,
incluyendo servir los archivos estáticos.
