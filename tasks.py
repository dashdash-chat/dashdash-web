from celery import Celery
from flask.ext.oauth import OAuth
from kombu import Exchange, Queue
from time import sleep
import constants

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
oauth = OAuth()
twitter = oauth.remote_app('twitter',
    base_url='https://api.twitter.com/1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    consumer_key=constants.twitter_consumer_key,
    consumer_secret=constants.twitter_consumer_secret
)

@celery.task
def fetch_follows(token, secret):
    resp = twitter.get('friends/ids.json', data={'stringify_ids': True}, token=(token, secret))
    if resp.status == 200:
        print resp.data
        #TODO paginated results https://dev.twitter.com/docs/api/1.1/get/friends/ids
    else:
        print "Request failed"
        print resp.headers
        print resp.data
        print resp.raw_data
        print resp.status

@twitter.tokengetter
def split_twitter_token_pair(token_pair):
    return token_pair

@celery.task
def add(x, y):
    return x + y
