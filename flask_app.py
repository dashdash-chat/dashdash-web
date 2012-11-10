from flask import Flask, render_template, redirect, url_for
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

@app.route("/demo/")
def no_demo():
    return redirect(url_for('index'))

@app.route("/demo/<token>/")
def demo(token):
    s = select([users.c.name, demos.c.password],
               and_(users.c.id == demos.c.user_id, demos.c.token == token))
    found_demo = conn.execute(s).fetchone()
    if found_demo:
        return render_template('demo.html', server=constants.domain, username=found_demo['name'], password=found_demo['password'])
    return redirect(url_for('index'))

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
