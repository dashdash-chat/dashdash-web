from shared import env_vars
debug = env_vars.debug

domain = env_vars.domain
server = '%s.%s' % ('xmpp', domain)

xmlrpc_port = env_vars.xmlrpc_port
web_xmlrpc_user  = '_web'
web_xmlrpc_password = env_vars.web_xmlrpc_password

web_mysql_user = 'web'
web_mysql_password = env_vars.web_mysql_password
db_host = env_vars.db_host
db_name = 'vine'

twitter_consumer_key = env_vars.twitter_consumer_key
twitter_consumer_secret = env_vars.twitter_consumer_secret

celery_mysql_user = 'celery'
celery_mysql_password = env_vars.celery_mysql_password
celery_db_name = 'celery_db'

aws_sqs_prefix = 'vine-dev-'
aws_access_key_id = env_vars.aws_access_key_id
aws_secret_access_key = env_vars.aws_secret_access_key  # if it's broken, regenerate this until you get one without a "/"

flask_secret_key = env_vars.flask_secret_key
