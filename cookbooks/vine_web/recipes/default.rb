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

directory "#{node['source_dir']}" do
  mode 0644
  owner "root"
  group "root"
  action :create
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
