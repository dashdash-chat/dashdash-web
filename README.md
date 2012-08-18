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

Social Graph Description
----------
See [Data Models for Vine](https://docs.google.com/document/d/1MVF3_4WhT9_3okjllc4f9tfV9scTDVJ2bn8ilk1cJkU/edit) for more information.
