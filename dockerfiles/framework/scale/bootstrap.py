#!/bin/python
from __future__ import print_function

from marathon import MarathonClient, MarathonApp
from marathon import NotFoundError

import json
import os
import sys
import time

import requests
from mesoshttp.acs import DCOSServiceAuth

APPLICATION_GROUP = os.getenv('APPLICATION_GROUP', None)
FRAMEWORK_NAME = os.getenv('DCOS_PACKAGE_FRAMEWORK_NAME', 'scale')
SCALE_LOGGING_ADDRESS = os.getenv('SCALE_LOGGING_ADDRESS', '')
DEPLOY_WEBSERVER = os.getenv('DEPLOY_WEBSERVER', 'true')
SERVICE_SECRET = os.getenv('SERVICE_SECRET')


def dcos_login():
    # Defaults servers for both DCOS 1.10+ CE and EE.
    servers = os.getenv('MARATHON_SERVERS',
                        'https://marathon.mesos:8443,http://marathon.mesos:8080').split(',')

    if SERVICE_SECRET:
        print('Attempting token auth to Marathon...')
        client = MarathonClient(servers, auth_token=DCOSServiceAuth(json.loads(SERVICE_SECRET)).token, verify=False)
    else:
        print('Attempting unauthenticated access to Marathon...')
        client = MarathonClient(servers, verify=False)

    return client


def run(client):
    elasticsearch_app_name = '%s-elasticsearch' % FRAMEWORK_NAME
    rabbitmq_app_name = '%s-rabbitmq' % FRAMEWORK_NAME
    log_app_name = '%s-logstash' % FRAMEWORK_NAME
    db_app_name = '%s-db' % FRAMEWORK_NAME

    blocking_apps = []

    # Determine if elasticsearch should be deployed. If SCALE_ELASTICSEARCH_URLS is unset we need to deploy it
    es_urls = os.getenv('SCALE_ELASTICSEARCH_URLS', '')
    es_ver = os.getenv('SCALE_ELASTICSEARCH_VERSION', '2.4')
    if not len(es_urls):
        deploy_elasticsearch(client, elasticsearch_app_name)
        es_urls = "http://%s.marathon.l4lb.thisdcos.directory:9200" % subdomain_gen(elasticsearch_app_name)
        blocking_apps.append(elasticsearch_app_name)
    print("ELASTICSEARCH_URLS=%s" % (es_urls))

    # Determine if rabbitmq should be deployed. If SCALE_BROKER_URL is unset we need to deploy it
    broker_url = os.getenv('SCALE_BROKER_URL', '')
    if not len(broker_url):
        deploy_rabbitmq(client, rabbitmq_app_name)
        broker_url = 'amqp://guest:guest@%s.marathon.l4lb.thisdcos.directory:5672//' % subdomain_gen(rabbitmq_app_name)
        print("BROKER_URL=%s" % broker_url)
        blocking_apps.append(rabbitmq_app_name)

    # Determine if db should be deployed.
    db_url = os.getenv('DATABASE_URL', '')
    if not len(db_url):
        deploy_database(client, db_app_name)
        db_url = "postgis://scale:scale@%s.marathon.l4lb.thisdcos.directory:5432/scale" % subdomain_gen(db_app_name)
        print("DATABASE_URL=%s" % db_url)
        blocking_apps.append(db_app_name)

    # Determine if Logstash should be deployed.
    if not len(SCALE_LOGGING_ADDRESS):
        deploy_logstash(client, log_app_name, es_urls)
        print("LOGGING_ADDRESS=tcp://%s.marathon.l4lb.thisdcos.directory:8000" % subdomain_gen(log_app_name))
        print("LOGGING_HEALTH_ADDRESS=%s.marathon.l4lb.thisdcos.directory:8080" % subdomain_gen(log_app_name))
        blocking_apps.append(log_app_name)

    # Determine if Web Server should be deployed.
    if DEPLOY_WEBSERVER.lower() == 'true':
        app_name = '%s-webserver' % FRAMEWORK_NAME
        webserver_port = deploy_webserver(client, app_name, es_urls, db_url, broker_url, es_ver)
        print("WEBSERVER_ADDRESS=http://%s.marathon.mesos:%s" % (subdomain_gen(app_name), webserver_port))

    # Wait for all needed apps to be healthy
    for app_name in blocking_apps:
        get_host_port_from_healthy_app(client, app_name, 0)


def subdomain_gen(app_name):
    prefix = APPLICATION_GROUP if APPLICATION_GROUP else ""

    return "%s%s" % (prefix, app_name)


def delete_marathon_app(client, app_name, fail_on_error=False, sleep_secs=5):
    print("Attempting delete of Marathon app: %s" % app_name)
    try:
        response = client.delete_app(get_group_app_name(app_name), force=True)
        print(response, file=sys.stderr)
    except NotFoundError:
        if fail_on_error:
            raise
        else:
            print('Not found. Ignoring...')

    while (check_app_exists(client, app_name)):
        print('Waiting for delete of Marathon App: %s' % app_name)
        time.sleep(sleep_secs)


def deploy_marathon_app(client, marathon_json, sleep_secs=10, retries=3):
    app_id = marathon_json['id']

    CONFIG_URI = os.getenv('CONFIG_URI')
    if CONFIG_URI:
        marathon_json['uris'].append(CONFIG_URI)

    print("Attempting deploy Marathon app with id: %s" % app_id)
    print(marathon_json, file=sys.stderr)
    marathon_app = MarathonApp.from_json(marathon_json)

    # We are going to retry, in the case of blocked deployments
    attempt = 0
    while attempt < retries:
        try:
            response = client.create_app(app_id, marathon_app)
            print(response, file=sys.stderr)
            print('Deployment succeeded.')
            break
        except Exception, ex:
            attempt += 1
            print(ex.message)
            print('Failure attempting to deploy app. Retrying...')
            time.sleep(sleep_secs)


def apply_set_envs(marathon_json, env_pairs):
    # Env pairs of as follows:
    # {'source_env':'target_env'}

    # For all optional environment variable that are set pass them on.
    for env in env_pairs:
        env_value = os.getenv(env)
        if env_value:
            marathon_json['env'][env_pairs[env]] = str(env_value)


def check_app_exists(client, app_name):
    try:
        client.get_app(get_group_app_name(app_name))
        return True
    except NotFoundError:
        return False


def get_host_port_from_healthy_app(client, app_name, port_index):
    group_app_name = get_group_app_name(app_name)

    wait_app_healthy(client, group_app_name)

    return get_marathon_app_single_task_host_port(client, group_app_name, port_index)


def get_marathon_app_single_task_host_port(client, app_name, port_index):
    app = client.get_app(app_name)
    return app.tasks[0].ports[port_index]


def get_group_app_name(app_name):
    # Add in the application group, if specified
    if APPLICATION_GROUP:
        group_app_name = '/%s/%s' % (APPLICATION_GROUP, app_name)
    else:
        group_app_name = '/%s' % app_name

    return group_app_name


def initialize_app_template(template_name, app_name, image_name):
    # Load template file
    marathon_json_file = open('app-templates/%s.json' % template_name)
    marathon = json.load(marathon_json_file)
    marathon_json_file.close()

    # Update id and VIPs to reflect app_name
    marathon = search_replace(marathon, 'scale-template-%s' % template_name, get_group_app_name(app_name))

    # Set container.docker.image
    if image_name:
        marathon['container']['docker']['image'] = image_name
    return marathon


def search_replace(marathon_json, search, replace):
    stringified = json.dumps(marathon_json)
    output = stringified.replace(search, replace)

    return json.loads(output)


def wait_app_healthy(client, app_name, sleep_secs=5):
    while client.get_app(app_name).tasks_healthy < 1:
        print('Waiting for healthy app %s.' % app_name)
        time.sleep(sleep_secs)


def deploy_webserver(client, app_name, es_urls, db_url, broker_url, es_ver):
    # attempt to delete an old instance..if it doesn't exists it will error but we don't care so we ignore it
    delete_marathon_app(client, app_name)

    # Load marathon template file
    marathon = initialize_app_template('webserver', app_name,
                                       os.getenv('MARATHON_APP_DOCKER_IMAGE'))

    vhost = os.getenv('SCALE_VHOST')
    cpu = os.getenv('SCALE_WEBSERVER_CPU', 1)
    memory = os.getenv('SCALE_WEBSERVER_MEMORY', 2048)

    # Set resources of webserver
    marathon['cpus'] = int(cpu)
    marathon['mem'] = int(memory)

    # Set attributes for secrets
    secrets_dcos_sa = os.environ.get('DCOS_SERVICE_ACCOUNT', '')
    secrets_ssl_warn = os.environ.get('SECRETS_SSL_WARNINGS', '')
    secrets_token = os.environ.get('SECRETS_TOKEN', '')
    secrets_url = os.environ.get('SECRETS_URL', '')

    # Set attributes for logging
    system_logging_level = os.environ.get('SYSTEM_LOGGING_LEVEL', 'INFO')

    env_map = {
        'SCALE_ALLOWED_HOSTS': 'SCALE_ALLOWED_HOSTS',
        'SCALE_SECRET_KEY': 'SCALE_SECRET_KEY',
        'SCALE_QUEUE_NAME': 'SCALE_QUEUE_NAME'
    }
    apply_set_envs(marathon, env_map)

    arbitrary_env = {
        'DCOS_PACKAGE_FRAMEWORK_NAME': FRAMEWORK_NAME,
        'DCOS_SERVICE_ACCOUNT': str(secrets_dcos_sa),
        'ENABLE_WEBSERVER': 'true',
        'SCALE_BROKER_URL': broker_url,
        'DATABASE_URL': db_url,
        'SCALE_STATIC_URL': '/service/%s/static/' % FRAMEWORK_NAME,
        'SCALE_WEBSERVER_CPU': str(cpu),
        'SCALE_WEBSERVER_MEMORY': str(memory),
        'SCALE_ELASTICSEARCH_URLS': es_urls,
        'SCALE_ELASTICSEARCH_VERSION': es_ver,
        'SECRETS_SSL_WARNINGS': str(secrets_ssl_warn),
        'SECRETS_TOKEN': str(secrets_token),
        'SECRETS_URL': str(secrets_url),
        'SYSTEM_LOGGING_LEVEL': system_logging_level
    }
    # For all environment variable that are set add to marathon json.
    for env in arbitrary_env:
        marathon['env'][env] = arbitrary_env[env]

    marathon['labels']['DCOS_SERVICE_NAME'] = FRAMEWORK_NAME
    marathon['labels']['HAPROXY_0_VHOST'] = vhost

    deploy_marathon_app(client, marathon)

    webserver_port = get_host_port_from_healthy_app(client, app_name, 0)

    return webserver_port


def deploy_database(client, app_name):
    # Check if scale-db is already running
    if not check_app_exists(client, app_name):
        # Load marathon template file
        marathon = initialize_app_template('db', app_name,
                                           os.getenv('DB_DOCKER_IMAGE'))

        # Set persistence
        DB_HOST_VOL = os.environ.get('SCALE_DB_HOST_VOL', '')
        if DB_HOST_VOL != '':
            marathon['container']['volumes'] = [
                {"containerPath": "/var/lib/pgsql/data", "hostPath": DB_HOST_VOL, "mode": "RW"}]

        env_map = {}
        apply_set_envs(marathon, env_map)

        deploy_marathon_app(client, marathon)


def get_elasticsearch_urls():
    response = requests.get('http://elasticsearch.marathon.mesos:31105/v1/tasks')
    endpoints = ['http://%s' % x['http_address'] for x in json.loads(response.text)]
    es_urls = ','.join(endpoints)
    return es_urls


def deploy_rabbitmq(client, app_name):
    # Check if rabbitmq is already running
    if not check_app_exists(client, app_name):
        # Load marathon template file
        marathon = initialize_app_template('rabbitmq',
                                           app_name,
                                           os.getenv('RABBITMQ_DOCKER_IMAGE'))

        deploy_marathon_app(client, marathon)


def deploy_elasticsearch(client, app_name):
    # Check if elasticsearch is already running
    if not check_app_exists(client, app_name):
        # Load marathon template file
        marathon = initialize_app_template('elasticsearch',
                                           app_name,
                                           os.getenv('ELASTICSEARCH_DOCKER_IMAGE'))

        deploy_marathon_app(client, marathon)


def deploy_logstash(client, app_name, es_urls):
    # attempt to delete an old instance..if it doesn't exists it will error, but we don't care, so we ignore it
    delete_marathon_app(client, app_name)

    #default based on MARATHON_APP_DOCKER_IMAGE with repo/scale:tag updated to repo/scale-logstash:tag
    marathon_img_default = os.getenv('MARATHON_APP_DOCKER_IMAGE')
    if marathon_img_default.endswith(':'):
        logstash_docker_img_default = marathon_img_default.replace(':', '-logstash:')
    else:
        logstash_docker_img_default = marathon_img_default + '-logstash'

    # Load marathon template file
    marathon = initialize_app_template('logstash', app_name, os.getenv(
        'LOGSTASH_DOCKER_IMAGE', logstash_docker_img_default))

    arbitrary_env = {
        'ELASTICSEARCH_URLS': es_urls,
    }
    # For all environment variable that are set add to marathon json.
    for env in arbitrary_env:
        marathon['env'][env] = arbitrary_env[env]

    env_map = {
        'LOGSTASH_TEMPLATE_URI': 'TEMPLATE_URI',
        'LOGSTASH_DEBUG': 'LOGSTASH_DEBUG'
    }
    apply_set_envs(marathon, env_map)
    deploy_marathon_app(client, marathon)


if __name__ == '__main__':
    # ensure this doesn't try and run if imported
    client = dcos_login()
    run(client)
