# This is a sample file that can be used as a starting place for creating a local_settings.py file for development
# purposes. Copy this file and rename it to local_settings.py. Then make any additional changes you need to configure it
# for your development environment.

# Include all the default settings.
from settings import *

# Use the following lines to enable developer/debug mode.
DEBUG = True
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG

# Set the external URL context here
FORCE_SCRIPT_NAME = '/scale-dev/api'
USE_X_FORWARDED_HOST = True

STATIC_ROOT = 'static/'
STATIC_URL = '/scale/static/'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# Not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'UTC'

# The template database to use when creating your new database.
# By using your own template that already includes the postgis extension,
# you can avoid needing to run the unit tests as a PostgreSQL superuser.
POSTGIS_TEMPLATE = 'template1'

# Broker URL for connection to messaging backend
BROKER_URL = 'amqp://guest:guest@localhost:5672//'

# Example settings for using PostgreSQL database with PostGIS.
DATABASES = {'default': dj_database_url.config(default='postgis://user:pass@localhost:5432/scale')}

# Logging configuration
LOGGING = LOG_CONSOLE_FILE_DEBUG

# Mesos connection information. Default for -m
# This can be something like "127.0.0.1:5050"
# or a zookeeper url like 'zk://host1:port1,host2:port2,.../path`
MESOS_MASTER = None

# Zookeeper URL for scheduler leader election. If this is None, only a single not is used and election isn't performed.
SCHEDULER_ZK = None

# The full name for the Scale Docker image (without version tag)
SCALE_DOCKER_IMAGE = 'geoint/scale'
