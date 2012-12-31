Development Setup
-----------------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
0. If you want to run the score_edges Celery task, set up ejabberd and the leaf node(s)
  * Follow the instructions in https://github.com/lehrblogger/vine-xmpp/#development-setup
  * `sudo ejabberdctl register _graph dev.vine.im [graph_xmpp_password]` ([from vine-shared](https://github.com/lehrblogger/vine-shared/blob/master/env_vars.py#L15))
0. Install nginx (on the machine that has the vine.im or dev.vine.im URL)
  * I have notes about running `sudo easy_install pyasn1` and `sudo easy_install pyasn1_modules` but can't figure out at which point or why... just FYI
  * `sudo apache2ctl -k stop`  # since otherwise nginx can't run on port 80
  * To get a C compiler, try `sudo apt-get install build-essential` in dev, or `sudo yum groupinstall "Development Tools"` in prod. 
  * `cd ~`
  * `wget http://superb-dca3.dl.sourceforge.net/project/pcre/pcre/8.31/pcre-8.31.tar.gz`
  * `tar xvzf pcre-8.31.tar.gz `
  * `cd pcre-8.31/`
  * `./configure`
  * `make`
  * `sudo make install`
  * `cd ..`
  * `wget http://nginx.org/download/nginx-1.2.0.tar.gz`
  * `gunzip -c nginx-1.2.0.tar.gz | tar xf -`
  * `cd nginx-1.2.0/`
  * `./configure --with-http_ssl_module`
  * If that fails (in prod), run this instead:
     * `cd ..`
     * `wget http://www.openssl.org/source/openssl-1.0.1c.tar.gz`
     * `tar xvzf openssl-1.0.1c.tar.gz`
     * `cd nginx-1.2.0/`
     * `./configure --with-http_ssl_module --with-openssl='../openssl-1.0.1c' --without-http_gzip_module`
  * `make`
  * `sudo make install`
  * `sudo ldconfig` and/or `sudo ln -s /lib64/libpcre.so.0.0.1 /lib64/libpcre.so.1`
  * `sudo /usr/local/nginx/sbin/nginx`  # to start nginx
  * Try navigating to http://vine.im or http://dev.vine.im in your browser
0. Create the web-env virtualenv on the VM
  * `cd /vagrant`
  * (`sudo` if you have to)`virtualenv web-env`  # this will fail the first time, but work the second time. TODO fix this
  * `sudo virtualenv web-env`  # sudoing because python-dev changed python permissions
  * `cd web-env`
  * `source bin/activate`
  * `bin/pip install mysql-python sqlalchemy`
  * `bin/pip install dnspython pyasn1 pyasn1_modules`
  * `bin/pip install gunicorn boto celery`
  * `bin/pip install flask Flask-OAuth Flask-WTF Flask-SQLAlchemy`
  * `bin/pip install sleekxmpp`
  * Note that maybe you need to install SleekXMPP from master for commits like [this](https://github.com/fritzy/SleekXMPP/commit/8c2ece3bca24c8b6452860db916713b55455050e)?
     * `git clone git@github.com:fritzy/SleekXMPP.git`
     * `cd SleekXMPP` 
     * `../bin/python setup.py install`
     * `cd ..`
  * `cd ..`
0. Download the vine-web code (easier from your local machine) and run the web server (from the VM)
  * `cd /vagrant/web-env` or `cd /home/ec2-user/web-env`
  * `git clone git@github.com:lehrblogger/vine-web.git web`
  * `cd web` 
  * `git checkout --track -b demo origin/demo`
  * `git submodule init`
  * `git submodule update`
  * `sudo cp /vagrant/web-env/web/shared/nginx.conf /usr/local/nginx/conf/ && sudo /usr/local/nginx/sbin/nginx -s reload` or 
    `sudo cp /home/ec2-user/web-env/web/shared/secrets/nginx.conf /usr/local/nginx/conf/ && sudo /usr/local/nginx/sbin/nginx -s reload`
  * In prod, also init the vine-secrets submodule:
     * `cd shared/`
     * `git submodule init`
     * `git submodule update`
     * `cd ..`
  * `cd ..`
  * `source bin/activate`
  * `cd web`
  * `../bin/gunicorn -w 4 flask_app:app -b 0.0.0.0:8000`
  * Visit http://dev.vine.im:8000/ in a browser
  * Control-c to stop the web server
  * `cd ..`
  * `deactivate`
  * `cd ..`
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
