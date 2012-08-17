Development Setup
----------
0. Set up the base VM
  * Follow the instructions in https://github.com/lehrblogger/vine-shared/#development-setup
0. Create the graph-env virtualenv
  * `cd /vagrant`
  * `sudo virtualenv graph-env`  # this will fail the first time, but work the second time. TODO fix this
  * `sudo virtualenv graph-env`  # sudoing because python-dev changed python permissions
  * `cd graph-env`
  * `source bin/activate`
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

