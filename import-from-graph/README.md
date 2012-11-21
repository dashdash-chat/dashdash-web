Development Setup
-----------------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
0. Set up ejabberd and the leaf node(s), and create the graph XMPP user
  * Follow the instructions in https://github.com/lehrblogger/vine-xmpp/#development-setup
  * `sudo ejabberdctl register _graph dev.vine.im [graph_xmpp_password]` ([from vine-shared](https://github.com/lehrblogger/vine-shared/blob/master/env_vars.py#L15))
0. Create the graph-env virtualenv
  * `cd /vagrant`
  * `sudo virtualenv graph-env`  # this will fail the first time, but work the second time. TODO fix this
  * `sudo virtualenv graph-env`  # sudoing because python-dev changed python permissions
  * `cd graph-env`
  * `source bin/activate`
  * `bin/pip install mysql-python`
  * `bin/pip install pyasn1 pyasn1_modules` (first one might be optional)
  * `bin/pip-2.6 install dnspython`
  * `git://github.com/fritzy/SleekXMPP.git`  # need master for commits like [this](https://github.com/fritzy/SleekXMPP/commit/8c2ece3bca24c8b6452860db916713b55455050e)
  * `cd SleekXMPP` 
  * `../bin/python setup.py install`
  * `cd ..`
  * ...
  * `cd ..`
0. Download the vine-graph code (easier from your local machine)
  * `cd graph-env`
  * `git clone git@github.com:lehrblogger/vine-graph.git graph`
  * `cd graph`
  * ...
  * `cd ..`
  * `deactivate`
  * `cd ..`



Social Graph Description
------------------------
See [Data Models for Vine](https://docs.google.com/document/d/1MVF3_4WhT9_3okjllc4f9tfV9scTDVJ2bn8ilk1cJkU/edit) for more information.
