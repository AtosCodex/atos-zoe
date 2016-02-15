import logging
import json
import datetime

import dateutil.parser

from zoe_lib.query import ZoeQueryAPI
from zoe_lib.executions import ZoeExecutionsAPI
from zoe_lib.containers import ZoeContainerAPI
from zoe_observer.config import get_conf

log = logging.getLogger(__name__)

IDLE_TIME = 4 * 60 * 60  # 4h


def check_guests(swarm):
    query_api = ZoeQueryAPI(get_conf().scheduler_url, 'zoeadmin', get_conf().zoeadmin_password)
    exec_api = ZoeExecutionsAPI(get_conf().scheduler_url, 'zoeadmin', get_conf().zoeadmin_password)
    cont_api = ZoeContainerAPI(get_conf().scheduler_url, 'zoeadmin', get_conf().zoeadmin_password)

    guests = query_api.query('user', role='guest')
    execs = exec_api.list()
    for guest in guests:
        my_execs = [e for e in execs if e['owner'] == guest['id']]
        if len(my_execs) > 1:
            log.warning('User {} is a guest and has more than one execution!')
        elif len(my_execs) == 0:
            continue
        my_exec = my_execs[0]
        my_exec_since_started = datetime.datetime.now() - dateutil.parser.parse(my_exec['time_started'])
        my_exec_since_started = my_exec_since_started.total_seconds()
        for c in my_exec['containers']:
            c = cont_api.get(c)
            for port in c['ports']:
                if port['name'] == 'Spark application web interface':
                    if check_spark_job(swarm, c['docker_id'], my_exec_since_started):
                        log.info('Execution {} for user {} has been idle for too long, terminating...'.format(my_exec['name'], guest['name']))
                        exec_api.terminate(my_exec['id'])


def check_if_kill(idle_seconds):
    if idle_seconds > get_conf().spark_activity_timeout:
        return True
    else:
        return False


def check_spark_job(swarm, docker_id, time_started):
    swarm_exec = swarm.cli.exec_create(docker_id, 'curl http://localhost:4040/api/v1/applications/pyspark-shell/jobs', stderr=False)
    output = swarm.cli.exec_start(swarm_exec['Id'])
    try:
        output = json.loads(output.decode('utf-8'))
    except ValueError:
        return check_if_kill(time_started)
    if len(output) == 0:
        return check_if_kill(time_started)

    seconds_since_last_job = None
    for job in output:
        if 'submissionTime' not in job:
            continue
        job_time = dateutil.parser.parse(job['submissionTime'])
        job_time_diff = datetime.datetime.now(datetime.timezone.utc) - job_time
        if seconds_since_last_job is None or job_time_diff < seconds_since_last_job:
            seconds_since_last_job = job_time_diff

    if seconds_since_last_job is None:
        return check_if_kill(time_started)
    else:
        return check_if_kill(seconds_since_last_job.total_seconds())