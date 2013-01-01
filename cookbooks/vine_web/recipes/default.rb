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


# Make the SSH key for github access and create the wrapper script
template "#{node['dirs']['ssl']}/deploy_key" do
  source "deploy_key.erb"
  owner "root"
  group "root"
  mode 0600
  variables :deploy_key => env_data["server"]["deploy_key"] 
end
template "#{node['dirs']['ssl']}/ssh_wrapper.sh" do
  source "ssh_wrapper.sh.erb"
  owner "root"
  group "root"
  mode 0700
  variables :deploy_key_path => "#{node['dirs']['ssl']}/deploy_key"
end

# Prepare the virtualenv for the vine-web repo
python_virtualenv "#{node['vine_web']['vine_venv_dir']}" do
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
    virtualenv "#{node['vine_web']['vine_venv_dir']}"
    action :install
  end
end

# Check out the application files and render the python constants template
git "#{node['vine_web']['vine_repo_dir']}" do
  repository "git@github.com:lehrblogger/vine-web.git"
  branch "alpha"
  destination "#{node['vine_web']['vine_repo_dir']}"
  ssh_wrapper "#{node['dirs']['ssl']}/ssh_wrapper.sh"
  action :sync
end
template "constants.py" do
  path "#{node['vine_web']['vine_repo_dir']}/constants.py"
  source "constants.py.erb"
  owner env_data["server"]["user"]
  group env_data["server"]["group"]
  mode 0644
  variables :env_data => env_data
end

# Render the vine-web's app-specific nginx and supervisord conf templates
template "nginx_app_locations.conf" do
  path "#{node['nginx']['dir']}/nginx_app_locations.conf"
  source "nginx_app_locations.conf.erb"
  owner "root"
  group "root"
  mode 0644
  notifies :reload, 'service[nginx]'
end
["gunicorn",
 "celeryd",
 "celerybeat"
].each do |program_name|
  template "supervisord_#{program_name}.conf" do
    path "/etc/supervisor/conf.dovisord_#{program_name}.conf"
    source "supervisord_#{program_name}.conf.erb"
    owner "root"
    group "root"
    mode 0644
    variables ({
      :logs_dir => node['vine_shared']['supervisord_log_dir'],
      :env_data => env_data
    })
    notifies :reload, 'service[supervisor]', :delayed
  end
end

# Don't forget JWChat for the web-based demo
include_recipe "vine_web::jwchat"

# Add commonly-used commands to the bash history (env_data['mysql']['root_password'] is nil in prod, which works perfectly)
["mysql -u root -p#{env_data['mysql']['root_password']} -h #{env_data['mysql']['host']} -D #{env_data['mysql']['main_name']}",
 "tail -f #{node['vine_shared']['supervisord_log_dir']}/"
].each do |command|
  ruby_block "append line to history" do
    block do
      file = Chef::Util::FileEdit.new("/home/#{env_data["server"]["user"]}/.bash_history")
      file.insert_line_if_no_match("/[^\s\S]/", command)  # regex never matches anything
      file.write_file
    end
  end
end
