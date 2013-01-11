#
# Cookbook Name:: vine_web
# Recipe:: jwchat
#
# Copyright 2012, Vine.IM
#
# All rights reserved - Do Not Redistribute
#

jwchat_repo_dir = "#{node['dirs']['source']}/jwchat"
jwchat_static_dir = "#{jwchat_repo_dir}/htdocs.en"

git "check out JWChat" do
  repository "https://github.com/lehrblogger/JWChat.git"
  branch "vine"
  destination jwchat_repo_dir
  action :sync
end

if node.chef_environment == 'dev'
  git "install JSDebugger" do
    repository "https://github.com/lehrblogger/JSDebugger.git"
    branch "master"
    destination jwchat_static_dir
    action :sync
  end
end

["Regexp::Common",
 "Locale::Maketext::Lexicon",
 "Locale::Maketext::Fuzzy"
].each do |perl_module|
  cpan_client perl_module do
      user 'root'
      group 'root'
      version '0' 
      install_type 'cpan_module'
      action :install
  end
end

execute "make JWChat" do
  command "make"
  cwd jwchat_repo_dir
  action :run
end

template "#{jwchat_static_dir}/config.js" do
  source "jwchat_config.js.erb"
  owner node.run_state['config']['user']
  group node.run_state['config']['group']
  mode 00644
end
