if [ $# -le 1 ]
then
  echo "$0 : You must supply the following 4 or 5 arguments: domain, username, password, URL hash, debug_flag"
  exit 1
fi

make
cp src/config.js.example htdocs.en/config.js
cd htdocs.en
perl -pi -e 's/var SITENAME = "localhost";/var SITENAME = "'$1'";/g' config.js
perl -pi -e 's/httpbase:"\/http-bind\/"/httpbase:"https:\/\/'$1':5281\/http-bind\/"/g' config.js
perl -pi -e 's/var GUEST_ACC = "";/var GUEST_ACC = "'$2'";/g' config.js
perl -pi -e 's/var GUEST_PWD = "";/var GUEST_PWD = "'$3'";/g' config.js
if [ $5 ]
then
  git clone git://github.com/lehrblogger/JSDebugger.git
  mv JSDebugger/* ./
  rm -r JSDebugger
  perl -pi -e 's/var DEBUG = false;/var DEBUG = true;/g' config.js
fi

cd ..
rm -rf /usr/local/nginx/html/demo/$4
cp -r htdocs.en /usr/local/nginx/html/demo/$4

echo "https://$1/demo/$4/"
