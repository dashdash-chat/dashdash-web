To Install
----------
sudo easy_install virtualenv
cd /vagrant/
sudo virtualenv /vagrant/web/
cd web-env/
source bin/activate
./bin/easy_install gunicorn
./bin/easy_install flask
./bin/easy_install Flask-OAuth
./bin/pip mysql-python
./bin/pip sqlalchemy
git clone https://github.com/lehrblogger/vine-web.git web
cd web
../bin/gunicorn -w 4 myapp:app -b 0.0.0.0:8000

For Vagrantfile
---------------
  config.vm.forward_port 8000, 8000

To Run
------
cd /vagrant/web-env/
cd /vagrant/web-env/web && ../bin/python myapp.py && cd ..
cd /vagrant/web-env/web && ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0 && cd ..