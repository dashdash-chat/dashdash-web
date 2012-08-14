To install on a clean Mac running OS X 10.8
----------
Note: shell commands start with a lowercase letter, instructions start with an uppercase letter.

0. Install Xcode Command Line Tools (skip if you have git installed, or would rather install manually)
  * Install Xcode 4.4 from the App Store
  * Launch Xcode
  * Go to the Downloads tab of Preferences
  * Click Install
0. Install VirtualBox and Vagrant on your local machine
  * Download the latest version from https://www.virtualbox.org/wiki/Downloads
  * Download the latest version from http://vagrantup.com/
  * Follow the instructions in both the standard OS X installer packages
  * vagrant box add lucid32 http://files.vagrantup.com/lucid32.box
  * mkdir vagrant
  * cd vagrant
  * touch Vagrantfile # with no extension
  * Add the contents of https://github.com/lehrblogger/vine-shared/blob/master/Vagrantfile to the VagrantFile
  * vagrant up
0. Prepare the VM and create a virtualenv in the VM
  * vagrant ssh
  * sudo apt-get install python-dev
  * sudo apt-get install mysql-server libmysqlclient-dev
  * mysql -u root -p
  * Paste the contents of https://github.com/lehrblogger/vine-shared/blob/master/init_tables.sql into the mysql prompt
  * Control-d out of mysql
  * sudo apt-get install python-pip
  * sudo pip install virtualenv
  * cd /vagrant
  * sudo virtualenv web-env  # this will fail the first time, but work the second time. TODO fix this
  * sudo virtualenv web-env  # sudoing because python-dev changed python permissions
0. Set up the virtualenv
  * cd web-env
  * source bin/activate
  * bin/pip install gunicorn
  * bin/pip install flask Flask-OAuth Flask-WTF
  * bin/pip install mysql-python sqlalchemy
  * cd ..
0. Download the vine-web code (easier from your local machine) and run the web server (from the VM)
  * cd web-env
  * git clone git@github.com:lehrblogger/vine-web.git web
  * cd web
  * ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0:8000
  * Visit http://127.0.0.1:8000/ in a browser
  * cd ..
  * deactivate
  * cd ..

To Run
------
cd /vagrant/web-env/web && ../bin/python myapp.py && cd ..  
cd /vagrant/web-env/web && ../bin/gunicorn -w 4 myapp:app -b 0.0.0.0 && cd ..