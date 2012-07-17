from flask import Flask, render_template, session, redirect, url_for, request, flash
from flaskext.oauth import OAuth
from sqlalchemy import create_engine, select, MetaData, Table
app = Flask(__name__)

dbhost = 'localhost'
dbuser = 'flask1'
dbpass = 'ish9gen8ob8hap7ac9hy'
dbname = 'vine'
engine = create_engine('mysql+mysqldb://' + dbuser + ':' + dbpass + '@' + dbhost + '/' + dbname)
metadata = MetaData()
metadata.bind = engine
users = Table('users', metadata, autoload=True)
conn = engine.connect()

oauth = OAuth()
twitter = oauth.remote_app('twitter',
    base_url='https://api.twitter.com/1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    consumer_key='7MDE19OK3Vk3e6QMJ0Xow',  #LATER move to constants file
    consumer_secret='VcUyKhrSP27HcW1iLLU8yKLlcpmtqDFyVtMQ7Tk1Y'  #LATER change and move to secrets file
)

@app.route("/")
def index():
    user = session.get('twitter_user')
    tweets = None
    if user:
        resp = twitter.get('statuses/home_timeline.json')
        if resp.status == 200:
            tweets = resp.data
        else:
            flash('Unable to load tweets from Twitter. Maybe out of '
                  'API calls or Twitter is overloaded.')   
    return render_template('home.html', user=user, tweets=tweets)

@twitter.tokengetter
def get_twitter_token():
    s = select([users.c.twitter_token, users.c.twitter_secret], users.c.name == session.get('twitter_user'))
    return conn.execute(s).fetchone()

@app.route('/login')
def login():
    return twitter.authorize()
    #return twitter.authorize(callback=url_for('oauth_authorized', next=request.args.get('next') or request.referrer or None))

@app.route('/logout')
def logout():
    session.pop('twitter_user', None)
    flash('You were signed out')
    return redirect(request.referrer or url_for('index'))

@app.route('/twitter/oauth_callback')
@twitter.authorized_handler
def oauth_authorized(resp):
    next_url = url_for('index') # request.args.get('next') or url_for('index')
    if resp is None:
        flash(u'You denied the request to sign in.')
        return redirect(next_url)
    s = select([users.c.twitter_token, users.c.twitter_secret], users.c.name == resp['screen_name'])
    found_user = conn.execute(s).fetchone()
    if found_user:
        if not found_user.twitter_token == resp['oauth_token'] or not found_user.twitter_secret == resp['oauth_token_secret']:
            u = users.update().\
                      where(users.c.name == resp['screen_name']).\
                      values(twitter_token=resp['oauth_token'], twitter_secret=resp['oauth_token_secret'])
            conn.execute(u)
    else:
        i = users.insert().\
                  values(name=resp['screen_name'], twitter_token=resp['oauth_token'], twitter_secret=resp['oauth_token_secret'])
        conn.execute(i)
    session['twitter_user'] = resp['screen_name']

    flash('You were signed in as %s' % resp['screen_name'])
    return redirect(next_url)


if __name__ == "__main__":
    app.secret_key = 'ksdfj321-jkhf2enmr 3njklm sdf,fgsd'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
