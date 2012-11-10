from shared import env_vars

domain = env_vars.domain
server = '%s.%s' % ('xmpp', domain)

xmlrpc_port = env_vars.xmlrpc_port
web_xmlrpc_user  = '_web'
web_xmlrpc_password = env_vars.web_xmlrpc_password

web_mysql_user = 'web'
web_mysql_password = env_vars.web_mysql_password
db_host = env_vars.db_host
db_name = 'vine'
