# Scale Scheduler / Services API

This document describes how to develop on the scheduler and services API portion of the Scale project. The scheduler and
services are written in Python 2.7 using the Django framework - Python 3 support is coming. A PostgreSQL 9.4+ database
with PostGIS extensions must be accessible to your environment. The following sections detail the steps to set up your
development environment for various platforms. Linux or MacOS are the preferred platforms for local development as you
will have a much simpler configuration path for Scale build time dependencies.

## Development

Isolation of development dependencies is done via virtualenv. This is a standard way to ensure system and project
dependencies are separated for Python development. The configuration of virtualenv for your chosen development platform
is detailed in the [Development Platforms](#development-platforms) section below. Whenever you start a development
session, you should activate your virtualenv:

```bash
source environment/scale/bin/activate
```

When you are done, you can either run the following command or just close the terminal window:

```bash
deactivate
```

### Project Settings

All Scale configuration settings are stored following Django convention within `scale/settings.py`. These settings may
be overridden for development purposes in `scale/local_settings.py` or `scale/local_settings_docker.py` for deployment
within Docker. One of the first required steps when beginning development is to make a copy of
`scale/local_settings_dev.py` to `scale/local_settings.py` and updating with your environment specific settings -
primarily database connection settings.

### Migrations

Migrations are the mechanism by which Django tracks changes to the database.
Whenever you pull updates from Git, make sure that you perform a migration. This will ensure that your database is
up-to-date with the latest model changes. To migrate any changes and apply fixtures, run the following from your
terminal:

```bash
python manage.py migrate
python manage.py load_all_data
```

When making Scale model changes, it is your responsibility to generate the appropriate migrations. This will encapsulate
the model changes in migration files that can be used to update the database and keep everybody in sync. The following
command will generate the migration files (ensure you commit these files):

```bash
python manage.py makemigrations
```

### Web Server

In order to use the Django web server in development, you may launch by running the following from the terminal:

```bash
python manage.py runserver 0.0.0.0:8080
```

Port 8080 is recommend as it will be consistently supported across all platforms. Cloud9 imposes restrictions on the
ports that can be exposed to the internet.

### Unit Tests

Scale makes extensive use of unit tests as a first line of defense against software regressions. All new features must
be covered by unit tests that exercise both success and failure cases. The entire unit test suite may be executed by
running the following from the terminal:

```bash
python manage.py test
```

Individual Django apps within the Scale project may also be tested individually (using `job` app for example):

```bash
python manage.py test job
```

### Documentation

Scale uses Sphinx for project and REST API documentation. With `docs` as your current working directory, the following
commands run from the terminal will generate the documentation:

```bash
make code_docs
make html
```

### Definition of Done

We welcome community contributions to the Scale project, and the following guidelines will help with making Pull
Requests (PRs) that ensure the projects long term maintainability. Before PRs are accepted, your code must meet all
conditions of the "Definition of Done."

1. Proper heading in all files
1. Properly organized imports in all files, organized first in three separate sections separated by a new line (section
ordering below), `import FOO` statements precede `from FOO import BAR` statements and finally ordered alphabetically
    1. Standard Python imports (math, logging, etc)
    1. Python library imports (Django, etc)
    1. Scale code imports
1. Add or update necessary unit tests for code updates
1. All unit tests run successfully and there are no deprecation warnings (ignore warnings for dependencies)
1. No Pep8 warnings in code
1. All Python files have appropriate docstring information filled out
1. Any necessary updates are made to the documentation
1. All documentation is generated successfully with no warnings

### Development Platforms

Scale development requires a local Postgres database with PostGIS extensions installed. The easiest way to get started
on most platforms is with a Docker container and all the bootstrap configurations described, except Cloud9, use this
method. The following are the baseline prerequisites for Scale development:

- Running Docker Community Edition 1.11+ Engine (use Docker for Windows or Mac on those platforms)
- Python 2.7.x

The core Scale team uses JetBrains PyCharm or Cloud9 IDE for development. These are in no way required but are
our preferred choices.

#### Cloud IDEs

[Cloud9](https://aws.amazon.com/cloud9/) makes development of Scale both
portable and quick to start using a hosted cloud environment. AWS provides integrated instance provisioning and 
management, so cost will be negligable if being used in an ad-hoc manner. An AWS account with a linked
credit card will be required. Once your workspace has initialized, open the terminal and 
enter the following commands to initialize for development:

```bash
# Undo alias for python to make virtualenv work
sed -i 's|^alias python|#alias python|' ~/.bashrc 

# Pull down code
git clone https://github.com/ngageoint/scale.git 

# Change to Python code directory
cd scale/scale

# Initialize database and install Scale Python packages.
sudo sh environment/cloud-init.sh
```

#### Linux

Platform specific prerequisites:
- Root access on CentOS7 / RHEL7 Linux OS

From a fresh clone of Scale run the following commands to initialize your environment:

```bash
# Change to Python code directory
cd scale

# Initialize database and install native dependencies.
sudo sh environment/cent7-init.sh

# Activate virtualenv
source environment/scale/bin/activate
```
Going forward, anytime you need to develop Scale, just activate your virtualenv and you're ready:

```bash
# Activate virtualenv
source environment/scale/bin/activate
```

#### MacOS

Platform specific prerequisites:
- Homebrew
- Docker for Mac 1.17 installed and running

From a fresh clone of Scale run the following commands to initialize your environment:

```bash
# Change to Python code directory
cd scale

# Initialize database and install native dependencies.
sh environment/mac-init.sh

# Activate virtualenv
source environment/scale/bin/activate
```
Going forward, anytime you need to develop Scale, just activate your virtualenv and you're ready:

```bash
# Activate virtualenv
source environment/scale/bin/activate
```

#### Windows (10+ only)

Platform specific prerequisites:
- Python 2.7 installed and included in PATH
- Virtualenv installed and included in PATH (Usually installed to `C:\Python27\Scripts\virtualenv.exe`)
- OSGeo4W install of GDAL, GEOS and PROJ included in PATH
(https://docs.djangoproject.com/en/1.11/ref/contrib/gis/install/#modify-windows-environment)
- Docker for Windows 1.17 installed and included in PATH

From a fresh clone of Scale run the following commands to initialize your environment:

```bat
REM Change to Python code directory
cd scale

REM Initialize database and configure Scale to point to it.
environment\win-init.bat

REM Activate virtualenv
environment\scale\Scripts\activate.bat
```

Going forward, anytime you need to develop Scale, just activate your virtualenv and you're ready:

```bat
REM Activate virtualenv
environment\scale\Scripts\activate.bat
```

#### Legacy Cloud9 IDE

**Cloud9 has been purchased by AWS and will likely go away at some point. The 
AWS offering provides improved hosted workspaces that allow for larger instance
types and full Docker development support. This support will be removed in the
near future.**

Once your workspace has initialized, open the terminal and enter the following commands to initialize for development:

```bash
# Change to Python code directory
cd scale

# Initialize database and install Scale Python packages.
sudo sh environment/legacy-cloud-init.sh
```

Virtual environments have not been used for cloud IDE providers as workspaces are already sandboxed eliminating the need
to isolate dependencies per project.
=======
## Deployment / Configuration

As a result, of being Scale being packaged as a Docker image for distribution most of the setting that
can be configured are exposed as environment variables. The complete list of exposed variables is found 
below for reference.

| Env Var                     | Default Value                   | Meaning                                    |
| --------------------------- | ------------------------------- | -------------------------------------------|
| CONFIG_URI                  | None                            | A URI or URL to docker credentials file    |
| DCOS_OAUTH_TOKEN            | None                            | Authentication token for DCOS bootstrap    |
| DCOS_PACKAGE_FRAMEWORK_NAME | None                            | Unique name for Scale cluster framework    |
| DCOS_PASS                   | None                            | Password for DCOS bootstrap                |
| DCOS_SERVICE_ACCOUNT        | None                            | DCOS account name with access to secrets   |
| DCOS_USER                   | None                            | Privileged username for DCOS bootstrap     |
| DEPLOY_WEBSERVER            | 'true'                          | Should UI and API be installed?            |
| ENABLE_BOOTSTRAP            | 'true'                          | Bootstrap Scale support containers         |
| ENABLE_WEBSERVER            | 'true' or None                  | Used by bootstrap to enable UI and API     |
| LOGSTASH_DOCKER_IMAGE       | 'geoint/logstash-elastic-ha'    | Docker image for logstash                  |
| MARATHON_APP_DOCKER_IMAGE   | 'geoint/scale'                  | Scale docker image name                    |
| MESOS_MASTER_URL            | 'zk://localhost:2181/scale'     | Mesos master location                      |
| SCALE_BROKER_URL            | None                            | broker configuration for messaging         |
| DATABASE_URL                | sqlite://db.sqlite3             | PostGIS url as defined by dj-database-url  |
| DJANGO_DEBUG                | ''                              | Change to '1' to enable debugging in DJANGO|
| SCALE_DOCKER_IMAGE          | 'geoint/scale'                  | Scale docker image name                    |
| SCALE_ELASTICSEARCH_URLS    | None (auto-detected in DCOS)    | Comma-delimited Elasticsearch node URLs    |
| SCALE_ELASTICSEARCH_VERSION | 2.4                             | Version of elasticserach used for logging  |
| SCALE_ELASTICSEARCH_LB      | 'true'                          | Is Elasticsearch behind a load balancer?   |
| SCALE_LOGGING_ADDRESS       | None                            | Logstash URL. By default set by bootstrap  |
| SCALE_QUEUE_NAME            | 'scale-command-messages'        | Queue name for messaging backend           |
| SCALE_WEBSERVER_CPU         | 1                               | UI/API CPU allocation during bootstrap     |
| SCALE_WEBSERVER_MEMORY      | 2048                            | UI/API memory allocation during bootstrap  |
| SCALE_ZK_URL                | None                            | Scale master location                      |
| SECRETS_SSL_WARNINGS        | 'true'                          | Should secrets SSL warnings be raised?     |
| SECRETS_TOKEN               | None                            | Authentication token for secrets service   |
| SECRETS_URL                 | None                            | API endpoint for a secrets service         |
| SYSTEM_LOGGING_LEVEL        | None                            | System wide logging level. INFO-CRITICAL   |

