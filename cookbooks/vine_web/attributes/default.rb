default['vine_web']['jwchat_repo_dir'] = "#{Chef::Environment.load(node.chef_environment).default_attributes['source_dir']}/jwchat"
default['vine_web']['vine_repo_dir']   = "#{Chef::Environment.load(node.chef_environment).default_attributes['source_dir']}/vine-web"
default['vine_web']['static_dir'] = "#{node['vine_web']['vine_repo_dir']}/static"
