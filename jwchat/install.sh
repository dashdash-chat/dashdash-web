if [ $# -le 3 ]
then
  echo "$0 : You must supply the following 4 or 5 arguments: domain, username, password, URL hash, debug_flag"
  exit 1
fi

make
cd htdocs.en
if [ $5 ]
then
  git clone git://github.com/lehrblogger/JSDebugger.git
  mv JSDebugger/* ./
  rm -r JSDebugger
  perl -pi -e 's/var DEBUG = false;/var DEBUG = true;/g' config.js
fi

cd ..
rm -rf /usr/local/nginx/html/demo/$4
mv htdocs.en /usr/local/nginx/html/demo/$4
rm -rf htdocs

echo "https://$1/demo/$4/"
