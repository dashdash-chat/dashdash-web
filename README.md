Development Setup
----------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
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

To Run the Web Server
------
  * `cd /vagrant/web-env/web && ../bin/python myapp.py && cd ..`
  * `cd /vagrant/web-env/web && ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0 && cd ..`