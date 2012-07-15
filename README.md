vine-web
========

sudo easy_install virtualenv
cd /vagrant/
sudo virtualenv /vagrant/web/
cd web-env/
source bin/activate
./bin/easy_install gunicorn
git clone https://github.com/lehrblogger/vine-web.git web
cd web
../bin/gunicorn -w 4 myapp:app -b 0.0.0.0:8000

For Vagrantfile:
  config.vm.forward_port 8000, 8000