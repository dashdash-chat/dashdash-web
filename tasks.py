from celery import Celery
from kombu import Exchange, Queue
import constants
from time import sleep

celery = Celery('tasks')
celery.conf.update(
    CELERY_CREATE_MISSING_QUEUES = False,
    CELERY_TASK_SERIALIZER = 'json',
    CELERY_RESULT_SERIALIZER = 'json',
    CELERY_RESULT_BACKEND = 'database',
    CELERY_RESULT_DBURI = 'mysql://%s:%s@%s/%s' % (constants.celery_mysql_user, constants.celery_mysql_password, constants.db_host, constants.celery_db_name),
    #CELERY_RESULT_ENGINE_OPTIONS = {"echo": True},
    BROKER_URL = 'sqs://%s:%s@' % (constants.aws_access_key_id, constants.aws_secret_access_key),
    BROKER_TRANSPORT_OPTIONS = {
        'region': 'us-east-1',
        'queue_name_prefix': constants.aws_sqs_prefix,
    }
)

@celery.task
def add(x, y):
    return x + y
