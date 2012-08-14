To Install on a clean Mac
----------
1. Make sure the Mac is running OS X 10.8
2. Install Xcode 4.4 from the App Store
3. Install Xcode Command Line Tools
  * Launch Xcode
  * Go to the Downloads tab of Preferences
  * Click Install
4. Install wget
  * curl -O http://ftp.gnu.org/gnu/wget/wget-1.13.4.tar.gz
  * tar -xzvf wget-1.13.4.tar.gz
  * cd wget-1.13.4
  * ./configure --with-ssl=openssl
  * make
  * sudo make install
5. Install pip (Pip Installs Python)
  * wget http://pypi.python.org/packages/source/p/pip/pip-0.7.2.tar.gz
  * tar xzf pip-0.7.2.tar.gz
  * cd pip-0.7.2
  * sudo python setup.py install
6. Create the virtualenv
  * sudo pip install virtualenv
  * mkdir vagrant
  * cd vagrant
  * mkdir web-env
  * virtualenv web-env/
  * cd web-env/
7. Set up the virtualenv
  * source bin/activate
  * ./bin/easy_install gunicorn
  * ./bin/easy_install flask
  * ./bin/easy_install Flask-OAuth
  * ./bin/pip install Flask-WTF
  * ./bin/pip install mysql-python
  * ./bin/pip install sqlalchemy
10. Grab and run the code
  * git clone https://github.com/lehrblogger/vine-web.git web
  * cd web
  * ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0:8000

For Vagrantfile
---------------
  config.vm.forward_port 8000, 8000

To Run
------
cd /vagrant/web-env/
cd /vagrant/web-env/web && ../bin/python myapp.py && cd ..
cd /vagrant/web-env/web && ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0 && cd ..