env_data = data_bag_item("dev_data", "dev_data")

git "check out JWChat" do
  repository "https://github.com/lehrblogger/JWChat.git"
  branch "vine"
  destination "#{node['vine_web']['jwchat_repo_dir']}"
  action :sync
end

if env_data['flask']['debug']
  git "install JSDebugger" do
    repository "https://github.com/lehrblogger/JSDebugger.git"
    branch "master"
    destination "#{node['vine_web']['jwchat_static_dir']}"
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
  cwd node['vine_web']['jwchat_repo_dir']
  action :run
end

template "#{node['vine_web']['jwchat_static_dir']}/config.js" do
  source "jwchat_config.js.erb"
  owner env_data["server"]["user"]
  group env_data["server"]["group"]
  mode 00644
  variables :env_data => env_data
end
