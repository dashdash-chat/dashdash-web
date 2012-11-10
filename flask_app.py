from flask import Flask, render_template, redirect
from sqlalchemy import create_engine, select, and_, MetaData, Table
import xmlrpclib
import constants

app = Flask(__name__)
server = 'dev.vine.im'
xmlrpc_server = xmlrpclib.ServerProxy('http://%s:%s' % (constants.server, constants.xmlrpc_port))
engine = create_engine('mysql+mysqldb://' + constants.web_mysql_user + ':' + constants.web_mysql_password + '@' + constants.db_host + '/' + constants.db_name)
metadata = MetaData()
metadata.bind = engine
users = Table('users', metadata, autoload=True)
demos = Table('demos', metadata, autoload=True)
conn = engine.connect()

@app.route("/")
def index():
    return render_template('home.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/demo")
def demo():
    return render_template('demo.html', server=server, username='alice', password='demo_password')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def page_not_found(e):
    return render_template('500.html'), 500

if __name__ == "__main__":
    app.secret_key = 'ksdfj321-jkhf2enmr 3njklm sdf,fgsd'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
