Development Setup
-----------------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
0. Install nginx (on the machine that has the vine.im or dev.vine.im URL)
  * `sudo apache2ctl -k stop`  # since otherwise nginx can't run on port 80
  * `cd ~`
  * `wget http://superb-dca3.dl.sourceforge.net/project/pcre/pcre/8.31/pcre-8.31.tar.gz`
  * `tar xvzf pcre-8.31.tar.gz `
  * `cd pcre-8.31/`
  * `./configure`
  * `make`
  * `sudo make install`
  * `sudo ldconfig`
  * `cd ..`
  * `wget http://nginx.org/download/nginx-1.2.0.tar.gz`
  * `gunzip -c nginx-1.2.0.tar.gz | tar xf -`
  * `cd nginx-1.2.0/`
  * `./configure --with-http_ssl_module`
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
  * `bin/pip install gunicorn`
  * `bin/pip install flask Flask-OAuth Flask-WTF`
  * `bin/pip install mysql-python sqlalchemy`
  * `cd ..`
0. Download the vine-web code (easier from your local machine) and run the web server (from the VM)
  * `cd web-env`
  * `git clone git@github.com:lehrblogger/vine-web.git web`
  * `cd web`
  * `../bin/gunicorn -w 4 myapp:app -b 0.0.0.0:8000`
  * Visit http://dev.vine.im:8000/ in a browser
  * Control-c to stop the web server
  * `cd ..`
  * `deactivate`
  * `cd ..`
  * `sudo cp /vagrant/web-env/web/nginx.conf /usr/local/nginx/conf/ && sudo /usr/local/nginx/sbin/nginx -s reload`

To Run the Web Server
---------------------
  * `cd /vagrant/web-env/web && ../bin/python myapp.py && cd ..`
  * `cd /vagrant/web-env/web && ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0 && cd ..`

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
