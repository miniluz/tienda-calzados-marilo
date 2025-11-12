# Deploying for dev

You will need an account on <https://eu.pythonanywhere.com>.
Create a web service picking the manual option,
then open a console to run the bash commands
(there's a separate console menu, it's not on the web server menu).

```sh
git clone https://github.com/miniluz/tienda-calzados-marilo
cd tienda-calzados-marilo
git checkout main
uv sync --no-dev --frozen
cp .env.production.example .env
vi .env
python manage.py migrate
# on test version:
python manage.py seed
```

On the web service settings,
set the source code and working directory to `/home/username/tienda-calzados-marilo`,
configure `/static/` to statically serve `/home/username/tienda-calzados-marilo/static`,
and set the venv to `/home/username/tienda-calzados-marilo/.venv`.

Modify WSGI to contain:

```py
import os
import sys

path = '/home/username/tienda-calzados-marilo'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'tienda_calzados_marilo.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

To update:
```sh
cd tienda-calzados-marilo
git pull
python manage.py migrate
# on test version:
python manage.py seed
```
