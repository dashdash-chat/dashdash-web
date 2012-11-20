from flask import Flask, flash, render_template, redirect, request, session, url_for
from flask.ext.oauth import OAuth
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import select, and_

import xmlrpclib
import constants
from celery_tasks import fetch_follows

app = Flask(__name__)
app.debug = constants.debug
app.secret_key = constants.flask_secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://%s:%s@%s/%s' % (constants.web_mysql_user,
                                                                 constants.web_mysql_password,
                                                                 constants.db_host,
                                                                 constants.db_name)
app.config['SQLALCHEMY_POOL_SIZE'] = 100
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 10
app.config['SQLALCHEMY_POOL_RECYCLE'] = 3600
db = SQLAlchemy(app)
metadata = db.MetaData(bind = db.engine)
users = db.Table('users', metadata, autoload=True)
demos = db.Table('demos', metadata, autoload=True)
user_tasks = db.Table('user_tasks', metadata, autoload=True)
oauth = OAuth()
twitter = oauth.remote_app('twitter',
    base_url='https://api.twitter.com/1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    consumer_key=constants.twitter_consumer_key,
    consumer_secret=constants.twitter_consumer_secret
)
xmlrpc_server = xmlrpclib.ServerProxy('http://%s:%s' % (constants.xmlrpc_server, constants.xmlrpc_port))

@app.route("/")
def index():
    user = session.get('vine_user')
    return render_template('home.html', user=user)

@app.route('/login')
def login():
    return twitter.authorize()

@app.route('/logout')
def logout():
    session.pop('vine_user', None)
    flash('You were signed out', 'error')
    return redirect(request.referrer or url_for('index'))

@twitter.tokengetter
def get_twitter_token():
    s = select([users.c.twitter_token, users.c.twitter_secret], users.c.name == session.get('vine_user'))
    return db.session.execute(s).fetchone()

@app.route('/twitter/oauth_callback')
@twitter.authorized_handler
def oauth_authorized(resp):
    if resp is None:
        flash(u'You cancelled the Twitter authorization flow.', 'error')
        return redirect(url_for('index'))
    twitter_user = resp['screen_name'].lower()
    s = select([users.c.id, users.c.email, users.c.twitter_id, users.c.twitter_token, users.c.twitter_secret],
            and_(users.c.name == twitter_user))
    found_user = db.session.execute(s).fetchone()
    if found_user:
        if not found_user.twitter_id == resp['user_id'] or \
           not found_user.twitter_token == resp['oauth_token'] or \
           not found_user.twitter_secret == resp['oauth_token_secret']:
            db.session.execute(users.update().\
                         where(users.c.name == twitter_user).\
                         values(twitter_id=resp['user_id'],
                                twitter_token=resp['oauth_token'],
                                twitter_secret=resp['oauth_token_secret']))
        result = fetch_follows.delay(resp['user_id'], resp['oauth_token'], resp['oauth_token_secret'])
        db.session.execute(user_tasks.insert().\
                     values(user_id=found_user.id,
                            celery_task_id=result,
                            celery_task_type='fetch_follows'))
        db.session.commit()
        session['vine_user'] = twitter_user
        flash('You were signed in as %s' % twitter_user, 'error')
    else:    
        flash('Sorry, but we\'re in private beta. Come back later!', 'error')
    return redirect(url_for('index'))

@app.route("/demo/")
def no_demo():
    return redirect(url_for('index'))

@app.route("/demo/<token>/")
def demo(token):
    s = select([users.c.name, demos.c.password],
               and_(users.c.id == demos.c.user_id, demos.c.token == token))
    found_demo = db.session.execute(s).fetchone()
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
    #NOTE this code only gets run when you're using Flask's built-in server, so gunicorn never sees this code.
    app.run(host='0.0.0.0', port=8000)
