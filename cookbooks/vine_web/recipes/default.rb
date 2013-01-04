#
# Cookbook Name:: vine_web
# Recipe:: default
#
# Copyright 2012, Vine.IM
#
# All rights reserved - Do Not Redistribute
#

#TODO this should be in a cookbook for role[base] in the vine-chef repo, I think, but don't know how to do that yet with Berkshelf and etc
#node.chef_environment
env_data = data_bag_item("dev_data", "dev_data")
# prod_data = Chef::EncryptedDataBagItem.load("prod_data", "mysql")
# username = prod_data["prod"]["username"]
# password = prod_data["prod"][:password]

# Prepare the virtualenv for the vine-web repo
python_virtualenv "#{node['vine_web']['web_env_dir']}" do
  owner env_data["server"]["user"]
  group env_data["server"]["group"]
  action :create
end
["mysql-python", "sqlalchemy",
 "dnspython", "pyasn1", "pyasn1_modules",
 "gunicorn", "boto", "celery", "sleekxmpp",
 "flask", "Flask-OAuth", "Flask-WTF", "Flask-SQLAlchemy"
].each do |library|
  python_pip "#{library}" do
    virtualenv "#{node['vine_web']['web_env_dir']}"
    action :install
  end
end

# Check out the application files and render the python constants template
deploy_wrapper 'web' do
    ssh_wrapper_dir node['dirs']['ssl']
    ssh_key_dir node['dirs']['ssl']
    ssh_key_data env_data['server']['web_deploy_key']
    sloppy true
end
git "#{node['vine_web']['web_repo_dir']}" do
    repository "git@github.com:lehrblogger/vine-web.git"
    branch "alpha"
    destination "#{node['vine_web']['web_repo_dir']}"
    ssh_wrapper "#{node['dirs']['ssl']}/web_deploy_wrapper.sh"
    action :sync
end
template "constants.py" do
  path "#{node['vine_web']['web_repo_dir']}/constants.py"
  source "constants.py.erb"
  owner env_data["server"]["user"]
  group env_data["server"]["group"]
  mode 0644
  variables :env_data => env_data
end

# Render the vine-web's app-specific nginx templates
template "nginx_app_locations.conf" do
  path "#{node['nginx']['dir']}/nginx_app_locations.conf"
  source "nginx_app_locations.conf.erb"
  owner "root"
  group "root"
  mode 0644
  notifies :reload, 'service[nginx]'
end

# Create the supervisor programs
supervisor_service "gunicorn" do
  command "#{node['vine_web']['web_env_dir']}/bin/gunicorn flask_app:app -b localhost:8000 --workers=4"
  directory node['vine_web']['web_repo_dir']
  user env_data['server']['user']
  stdout_logfile "#{node['supervisor']['log_dir']}/gunicorn.log"
  stderr_logfile "#{node['supervisor']['log_dir']}/gunicorn.log"
  numprocs 1
  autostart true
  autorestart true
  priority 1
  action :enable
end
supervisor_service "celeryd" do
  command "#{node['vine_web']['web_env_dir']}/bin/celeryd --app=celery_tasks --loglevel=INFO"
  directory node['vine_web']['web_repo_dir']
  user env_data['server']['user']
  stdout_logfile "#{node['supervisor']['log_dir']}/celery.log"
  stderr_logfile "#{node['supervisor']['log_dir']}/celery.log"
  numprocs 1
  autostart false
  autorestart false
  priority 20
  stopwaitsecs 300
  action :enable
end
supervisor_service "celerybeat" do
  command "#{node['vine_web']['web_env_dir']}/bin/celerybeat --app=celery_tasks --schedule={node['vine_web']['web_repo_dir']}/celerybeat-schedule --loglevel=INFO"
  directory node['vine_web']['web_repo_dir']
  user env_data['server']['user']
  stdout_logfile "#{node['supervisor']['log_dir']}/celerybeat.log"
  stderr_logfile "#{node['supervisor']['log_dir']}/celerybeat.log"
  numprocs 1
  autostart false
  autorestart false
  priority 30
  startsecs 10
  stopwaitsecs 300
  action :enable
end

# Don't forget JWChat for the web-based demo
include_recipe "vine_web::jwchat"
