#!/usr/bin/env bash

# Clean up old Postgres and install 9.4 version
service postgresql stop
apt-get --purge remove -y postgresql\*
su -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
apt-get update
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt-get install -y --force-yes  postgresql-9.4 postgresql-contrib-9.4 postgresql-9.4-postgis-2.3
sed 's^local   all             all                                     peer^local   all             all                                     trust^g' -i /etc/postgresql/9.4/main/pg_hba.conf
service postgresql start
update-rc.d postgresql enable

# Install RabbitMQ as broker for messaging
apt-get install -y rabbitmq-server
service rabbitmq-server start
update-rc.d rabbitmq-server enable

# Install all python dependencies (gotta pin setuptools due to errors during pycparser install)
apt-get install -y build-essential libssl-dev libffi-dev python-dev
pip install -U pip
pip install setuptools==33.1.1
pip install -r pip/requirements.txt

cat << EOF > database-commands.sql
CREATE USER scale PASSWORD 'scale' SUPERUSER;
CREATE DATABASE scale OWNER=scale;
EOF
su postgres -c "psql -f database-commands.sql"
rm database-commands.sql
su postgres -c "psql scale -c 'CREATE EXTENSION postgis'"

cp scale/local_settings_dev.py scale/local_settings.py
cat << EOF >> scale/local_settings.py
POSTGIS_TEMPLATE = 'template_postgis'

DATABASES = {'default': dj_database_url.config(default='postgis://scale:scale@localhost:5432/scale')}
EOF
EOF

# Load up database with schema migrations to date and fixtures
python manage.py migrate
python manage.py load_all_data

# Clean up logs to eliminate permission issues
rm -fr ../scale/logs