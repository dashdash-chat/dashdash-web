Development Setup
-----------------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
0. If you want to run the score_edges Celery task, set up ejabberd and the leaf node(s)
  * Follow the instructions in https://github.com/lehrblogger/vine-xmpp/#development-setup
  * `sudo ejabberdctl register _graph dev.vine.im [graph_xmpp_password]` ([from vine-shared](https://github.com/lehrblogger/vine-shared/blob/master/env_vars.py#L15))
0. Install and configure [Supervisor](http://supervisord.org/) to run/manage the web server (and eventually [Celery](http://celeryproject.org/))
  * `sudo pip install supervisor==3.0a10` # The current version, 3.0b1, wasn't working I think because of [this bug](https://github.com/Supervisor/supervisor/issues/121).
  * `sudo mkdir /var/log/supervisord`
  * `sudo chown vagrant /var/log/supervisord`
  * `sudo supervisord -c /vagrant/web-env/web/shared/supervisord.conf` or `sudo supervisord -c /home/ec2-user/web-env/web/shared/secrets/supervisord.conf`
  * Wait a moment, and then verify that `supervisorctl -c /home/ec2-user/web-env/web/shared/`(`secrets/`)`supervisord.conf status` lists gunicorn as running
  * If nginx is running and working properly, you should be able to visit http://dev.vine.im/supervisor/ or http://vine.im/supervisor/ and control supervisor from the browser.
  * Be sure to check on the SQS queue permissions before starting Celery! You'll probably need to give the right AWS IAM user permissions to create queues, since one of them uses the box's name in it.

To Run the Web Server
---------------------
  * Note that supervisor will do this for you, but for dev you might want to use the command line
  * `cd ./web-env/web && ../bin/python flask_app.py && cd ..` (Flask's built-in server restarts itself for you if any files have changed.)
  * `cd ./web-env/web && ../bin/gunicorn -w 4 flask_app:app -b 0.0.0.0 && cd ..` (Gunicorn needs you to restart it manually if any files have changed.)
  * To run in prod, `cd /home/ec2-user/web-env && source bin/activate ** cd web && nohup ../bin/gunicorn flask_app:app -b 0.0.0.0:8000 --workers=4 >> /home/ec2-user/logs/gunicorn.log &`

To Run the Celery Worker
------------------------
  * `celery -A celery_tasks worker --loglevel debug` is useful for development

Social Graph Description
------------------------
See [Data Models for Vine](https://docs.google.com/document/d/1MVF3_4WhT9_3okjllc4f9tfV9scTDVJ2bn8ilk1cJkU/edit) for more information.

Google Form HTML (for lack of a better place to put it)
-------------------------------------------------------
  ```<!DOCTYPE html>
  <html lang="en">
  	<head>
  		<meta charset="utf-8" />
  		<title>Vine.IM</title>
  	</head>
  	<body>
  		<iframe src="https://docs.google.com/spreadsheet/embeddedform?formkey=dEduRlNBODVMMjBqZE8xdmZTYWc3aHc6MQ" width="760" height="1541" frameborder="0" marginheight="0" marginwidth="0">Loading...</iframe>
  	</body>
  </html>```
