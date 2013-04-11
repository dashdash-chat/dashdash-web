#
# Cookbook Name:: vine_web
# Recipe:: default
#
# Copyright 2013, Dashdash, Inc.
#
# All rights reserved - Do Not Redistribute
#

web_env_dir = "#{node['dirs']['source']}/web-env"
web_repo_dir = "#{web_env_dir}/web"
web_static_dir = "#{web_repo_dir}/static"

# Prepare the virtualenv for the vine-web repo
python_virtualenv web_env_dir do
  owner node.run_state['config']['user']
  group node.run_state['config']['group']
  action :create
end
["mysql-python", "sqlalchemy",
 "dnspython", "pyasn1", "pyasn1_modules",
 "gunicorn", "boto", "celery", "sleekxmpp",
 "flask", "Flask-OAuth", "Flask-WTF", "Flask-SQLAlchemy"
].each do |library|
  python_pip library do
    virtualenv web_env_dir
    action :install
  end
end

# Check out the application files and render the python constants template
deploy_wrapper 'web' do
    ssh_wrapper_dir node['dirs']['ssl']
    ssh_key_dir node['dirs']['ssl']
    ssh_key_data Chef::EncryptedDataBagItem.load(node.chef_environment, "vine_web")['deploy_key']
    sloppy true
end
git web_repo_dir do
    repository "git@github.com:lehrblogger/vine-web.git"
    branch "master"
    destination web_repo_dir
    ssh_wrapper "#{node['dirs']['ssl']}/web_deploy_wrapper.sh"
    action :sync
end
template "constants.py" do
  path "#{web_repo_dir}/constants.py"
  source "constants.py.erb"
  owner node.run_state['config']['user']
  group node.run_state['config']['group']
  mode 00644
end

# Include JWChat for the web-based demo (run it here, so we have the attribute for the next template)
include_recipe "vine_web::jwchat"
#TODO these lines are copy-pasted from vine_web::jwchat, figure out a better way
jwchat_repo_dir = "#{node['dirs']['source']}/jwchat"
jwchat_static_dir = "#{jwchat_repo_dir}/htdocs.en"

# Render the vine-web's app-specific nginx templates
template "nginx_app_locations.conf" do
  path "#{node['nginx']['dir']}/nginx_app_locations.conf"
  source "nginx_app_locations.conf.erb"
  owner "root"
  group "root"
  mode 00644
  variables ({
    :web_static_dir => web_static_dir,
    :jwchat_static_dir => jwchat_static_dir
  })
  notifies :reload, 'service[nginx]'
end

# Create the supervisor programs. These should be accessible at http://#{domain}/supervisor/
# Be sure to check on the SQS queue permissions before starting Celery!
# You'll probably need to give the right AWS IAM user permissions to create queues, since one of them uses the box's name in it.
supervisor_service "gunicorn" do
  command "#{web_env_dir}/bin/gunicorn flask_app:app -b localhost:8000 --workers=4"
  directory web_repo_dir
  user node.run_state['config']['user']
  stdout_logfile "#{node['supervisor']['log_dir']}/gunicorn.log"
  stderr_logfile "#{node['supervisor']['log_dir']}/gunicorn.log"
  numprocs 1
  autostart true
  autorestart true
  priority 1
  action :enable
end
supervisor_service "celeryd" do
  command "#{web_env_dir}/bin/celeryd --app=celery_tasks --loglevel=INFO"
  directory web_repo_dir
  user node.run_state['config']['user']
  stdout_logfile "#{node['supervisor']['log_dir']}/celery.log"
  stderr_logfile "#{node['supervisor']['log_dir']}/celery.log"
  numprocs 1
  autostart false
  autorestart true
  priority 20
  stopwaitsecs 300
  action :enable
end
supervisor_service "celerybeat" do
  command "#{web_env_dir}/bin/celerybeat --app=celery_tasks --schedule=#{node['dirs']['other']}/celerybeat-schedule --pidfile=#{node['dirs']['other']}/celerybeat.pid --loglevel=INFO"
  directory web_repo_dir
  user node.run_state['config']['user']
  stdout_logfile "#{node['supervisor']['log_dir']}/celerybeat.log"
  stderr_logfile "#{node['supervisor']['log_dir']}/celerybeat.log"
  numprocs 1
  autostart false
  autorestart true
  priority 30
  startsecs 10
  stopwaitsecs 300
  action :enable
end

# Send the Gunicorn and Celery logs to Papertrail
node.set['papertrail']['watch_files']["#{node['dirs']['log']}/supervisor/gunicorn.log"  ] = 'gunicorn'
node.set['papertrail']['watch_files']["#{node['dirs']['log']}/supervisor/celery.log"    ] = 'celery'
node.set['papertrail']['watch_files']["#{node['dirs']['log']}/supervisor/celerybeat.log"] = 'celerybeat'

# Add commonly-used commands to the bash history
["cd #{web_repo_dir} && ../bin/gunicorn -b localhost:8000 --workers=4 --log-level=DEBUG",
 "cd #{web_repo_dir} && ../bin/python flask_app.py",  # Flask's built-in server restarts itself for you if any files have changed
 "cd #{web_repo_dir} && ../bin/celery -A celery_tasks worker --loglevel debug",
 "cd #{web_env_dir} && source bin/activate && cd #{web_repo_dir}" 
].each do |command|
  ruby_block "append line to history" do
    block do
      file = Chef::Util::FileEdit.new("/home/#{node.run_state['config']['user']}/.bash_history")
      file.insert_line_if_no_match("/[^\s\S]/", command)  # regex never matches anything
      file.write_file
    end
  end
end
