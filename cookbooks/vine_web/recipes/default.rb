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

# Make sure our directories exist
["#{node['source_dir']}"].each do |dir|
  directory dir do
    mode 0644
    owner env_data["server"]["user"]
    group env_data["server"]["user"]
    recursive true
    action :create
  end
end
directory "#{node['source_dir']}/.ssh" do
  owner "root"
  group "root"
  mode 0644
  action :create
end

# Set up the SSH key for github access
template "#{node['source_dir']}/.ssh/deploy_key" do
  source "deploy_key.erb"
  owner "root"
  group "root"
  mode 0644
  variables :deploy_key => env_data["server"]["deploy_key"] 
end
# And then set up the SSH wrapper with that key
template "#{node['source_dir']}/ssh_wrapper.sh" do
  source "ssh_wrapper.sh.erb"
  owner "root"
  group "root"
  mode 0755
  variables :deploy_key_path => "#{node['source_dir']}/.ssh/deploy_key"
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

git "#{node['vine_web']['vine_repo_dir']}" do
  repository "git@github.com:lehrblogger/vine-web.git"
  branch "alpha"
  destination "#{node['vine_web']['vine_repo_dir']}"
  ssh_wrapper "#{node['source_dir']}/ssh_wrapper.sh"
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

template "ssl_web.crt" do
  path "#{node['source_dir']}/ssl_web.crt"
  source "ssl.crt.erb"
  owner "root"
  group "root"
  variables :ssl_crt => env_data["server"]["web_ssl_crt"]
  mode 0644
end
template "ssl_web.key" do
  path "#{node['source_dir']}/ssl_web.key"
  source "ssl.key.erb"
  owner "root"
  group "root"
  variables :ssl_key => env_data["server"]["web_ssl_key"]
  mode 0644
end

template "nginx.conf" do
  path "#{node['nginx']['dir']}/nginx.conf"
  source "nginx.conf.erb"
  owner "root"
  group "root"
  mode 0644
  variables :env_data => env_data
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
    notifies :restart, 'service[supervisor]', :delayed
  end
end

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
