Development Setup
-----------------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
0. Install nginx (on the machine that has the vine.im or dev.vine.im URL)
  * I have notes about running `sudo easy_install pyasn1` and `sudo easy_install pyasn1_modules` but can't figure out at which point or why... just FYI
  * `sudo apache2ctl -k stop`  # since otherwise nginx can't run on port 80
  * `cd ~`
  * `wget http://superb-dca3.dl.sourceforge.net/project/pcre/pcre/8.31/pcre-8.31.tar.gz`
  * `tar xvzf pcre-8.31.tar.gz `
  * `cd pcre-8.31/`
  * `./configure`
  * `make`
  * If that fails (in prod), run `sudo yum groupinstall "Development Tools"` first
  * `sudo make install`
  * `sudo ldconfig` and/or `sudo ln -s /lib64/libpcre.so.0.0.1 /lib64/libpcre.so.1`
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
  * `sudo /usr/local/nginx/sbin/nginx`  # to start nginx
  * Try navigating to http://vine.im or http://dev.vine.im in your browser
0. Create the web-env virtualenv on the VM
  * `cd /vagrant`
  * `sudo virtualenv web-env`  # this will fail the first time, but work the second time. TODO fix this
  * `sudo virtualenv web-env`  # sudoing because python-dev changed python permissions
  * `cd web-env`
  * `source bin/activate`
  * `bin/pip install mysql-python sqlalchemy`
  * `bin/pip install gunicorn celery`
  * `bin/pip install flask Flask-OAuth Flask-WTF Flask-SQLAlchemy`
  * `cd ..`
0. Install necessary Perl modules
  * `sudo apt-get install yum`
  * `sudo yum install cpan`
  * `cpan` and type `yes` at the prompt to have it configure as much as possible
  * `o conf urllist`  # Make sure there are valid mirrors, and if not, try adding the following
  * `o conf urllist push http://cpan.strawberryperl.com/`
  * `o conf commit`
  * Control-d to leave the cpan prompt
  * `sudo cpan Locale::Maketext::Fuzzy`  # And repeat for any other necessary modules, noting that error messages like "Can't locate Locale/Maketext/Fuzzy.pm in @INC" when running install.sh below mean you should try commands like the one mentioned
0. Download the JWChat code and prepare the static files
  * `cd /vagrant` or `cd /home/ec2-user`
  * `git clone git://github.com/lehrblogger/JWChat.git jwchat`
  * `cd jwchat`
  * `git checkout --track -b vine origin/vine`
  * `make`
  * `cd ..`
  * Optionally get the debugger for JWChat:
     * `git clone git://github.com/lehrblogger/JSDebugger.git`
     * `mv JSDebugger/* ./jwchat/htdocs.en`
     * `perl -pi -e 's/var DEBUG = false;/var DEBUG = true;/g' ./jwchat/htdocs.en/config.dev.vine.im.js`
0. Download the vine-web code (easier from your local machine) and run the web server (from the VM)
  * `cd web-env`
  * `git clone git@github.com:lehrblogger/vine-web.git web`
  * `cd web`
  * `git submodule init`
  * `git submodule update`
  * In prod, also init the vine-secrets submodule:
     * `cd shared/`
     * `git submodule init`
     * `git submodule update`
     * `cd ..`
  * `source bin/activate`
  * `../bin/gunicorn -w 4 myapp:app -b 0.0.0.0:8000`
  * Visit http://dev.vine.im:8000/ in a browser
  * Control-c to stop the web server
  * `cd ..`
  * `deactivate`
  * `cd ..`
  * `sudo cp /vagrant/web-env/web/shared/nginx.conf /usr/local/nginx/conf/ && sudo /usr/local/nginx/sbin/nginx -s reload` or 
  `sudo cp /home/ec2-user/web-env/web/shared/secrets/nginx.conf /usr/local/nginx/conf/ && sudo /usr/local/nginx/sbin/nginx -s reload`
0. Install and configure [Supervisor](http://supervisord.org/) to run/manage the web server (and eventually [Celery](http://celeryproject.org/))
  * `sudo pip install supervisor==3.0a10` # The current version, 3.0b1, wasn't working I think because of [this bug](https://github.com/Supervisor/supervisor/issues/121).
  * `sudo mkdir /var/log/supervisord`
  * `sudo chown vagrant /var/log/supervisord`
  * `sudo supervisord -c /vagrant/web-env/web/shared/supervisord.conf` or `sudo supervisord -c /home/ec2-user/web-env/web/shared/secrets/supervisord.conf`
  * Wait a moment, and then verify that `supervisorctl -c /home/ec2-user/web-env/web/shared/`(`secrets/`)`supervisord.conf status` lists gunicorn as running
  * If nginx is running and working properly, you should be able to visit http://dev.vine.im/supervisor/ or http://vine.im/supervisor/ and control supervisor from the browser.

To Run the Web Server
---------------------
  * Note that supervisor will do this for you, but for dev you might want to use the command line
  * `cd ./web-env/web && ../bin/python flask_app.py && cd ..` (Flask's built-in server restarts itself for you if any files have changed.)
  * `cd ./web-env/web && ../bin/gunicorn -w 4 flask_app:app -b 0.0.0.0 && cd ..` (Gunicorn needs you to restart it manually if any files have changed.)
  * To run in prod, `cd /home/ec2-user/web-env && source bin/activate ** cd web && nohup ../bin/gunicorn flask_app:app -b 0.0.0.0:8000 --workers=4 >> /home/ec2-user/logs/gunicorn.log &`

To Run the Celery Worker
------------------------
  * `celery -A celery_tasks worker --loglevel debug` is useful for development

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
