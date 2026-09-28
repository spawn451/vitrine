#!/bin/sh
# Lance manage.py avec les variables de /var/www/vitrine/.env, exactement comme
# Gunicorn les voit (systemd, EnvironmentFile). À appeler sous le compte vitrine :
#   sudo -u vitrine /var/www/vitrine/src/deploy/manage.sh migrate
#   sudo -u vitrine /var/www/vitrine/src/deploy/manage.sh collectstatic --noinput
#   sudo -u vitrine /var/www/vitrine/src/deploy/manage.sh reservations
# Les valeurs du .env contenant des espaces ou des caractères spéciaux doivent
# être entre guillemets doubles (voir .env.example) ; systemd les accepte aussi.
set -e
ROOT=/var/www/vitrine
set -a
. "$ROOT/.env"
set +a
cd "$ROOT/src"
exec "$ROOT/venv/bin/python" manage.py "$@"
