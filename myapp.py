import datetime
from flask import Flask, render_template, session, redirect, url_for, request, flash
from flask.ext.oauth import OAuth
from flask.ext.wtf import Form, TextField, Required
from sqlalchemy import create_engine, select, and_, MetaData, Table
app = Flask(__name__)

dbhost = 'localhost'
dbuser = 'flask1'
dbpass = 'ish9gen8ob8hap7ac9hy'
dbname = 'vine'
engine = create_engine('mysql+mysqldb://' + dbuser + ':' + dbpass + '@' + dbhost + '/' + dbname)
metadata = MetaData()
metadata.bind = engine
users = Table('users', metadata, autoload=True)
invites = Table('invites', metadata, autoload=True)
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


class InviteCodeForm(Form):
    code = TextField('code', validators=[Required()])

@app.route("/")
def index():
    user = session.get('twitter_user')
    unused_invites = None
    used_invites = None
    tweets = None
    if user:
        user_id = conn.execute(select([users.c.id], users.c.name == session.get('twitter_user'))).fetchone()['id']
        s = select([invites.c.code, invites.c.recipient],
                    and_(invites.c.sender == user_id, invites.c.recipient == None))
        unused_invites = conn.execute(s).fetchall()
        s = select([invites.c.code, users.c.name, invites.c.used],
                   and_(invites.c.sender == user_id, invites.c.recipient == users.c.id, ))
        used_invites = conn.execute(s).fetchall()
        resp = twitter.get('statuses/home_timeline.json')
        if resp.status == 200:
            tweets = resp.data
        else:
            flash('Unable to load tweets from Twitter. Maybe out of '
                  'API calls or Twitter is overloaded.', 'error')
    return render_template('home.html', user=user, unused_invites=unused_invites, used_invites=used_invites, tweets=tweets)

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
    flash('You were signed out', 'error')
    return redirect(request.referrer or url_for('index'))

@app.route('/twitter/oauth_callback')
@twitter.authorized_handler
def oauth_authorized(resp):
    next_url = url_for('index') # request.args.get('next') or url_for('index')
    if resp is None:
        flash(u'You cancelled the Twitter authorization flow.', 'error')
        return redirect(next_url)
    s = select([users.c.twitter_token, users.c.twitter_secret], users.c.name == resp['screen_name'])
    found_user = conn.execute(s).fetchone()
    if found_user:
        if not found_user.twitter_token == resp['oauth_token'] or not found_user.twitter_secret == resp['oauth_token_secret']:
            conn.execute(users.update().\
                      where(users.c.name == resp['screen_name']).\
                      values(twitter_token=resp['oauth_token'], twitter_secret=resp['oauth_token_secret']))
        session['twitter_user'] = resp['screen_name']
        flash('You were signed in as %s' % resp['screen_name'], 'error')
    else:
        if session.get('invite_code'):
            s = select([invites], and_(invites.c.code == session['invite_code'], invites.c.recipient == None))
            if conn.execute(s).fetchone():
                user_id = conn.execute(users.insert().\
                                             values(name=resp['screen_name'],
                                             twitter_token=resp['oauth_token'],
                                             twitter_secret=resp['oauth_token_secret'])).lastrowid
                conn.execute(invites.update().\
                                     where(invites.c.code == session['invite_code']).\
                                     values(recipient=user_id, used=datetime.datetime.now()))
                session['twitter_user'] = resp['screen_name']
                flash('You signed up as %s' % resp['screen_name'], 'error')
            else:
                flash('Sorry, that invite code is not valid.', 'error')
        else:
            flash('Sorry, but you need an invite code to sign up.', 'error')
    return redirect(next_url)

@app.route('/invite/<code>')
def invite(code):
    user = session.get('twitter_user')
    form = InviteCodeForm()
    if user:
        return redirect(url_for('index'))
    invite = conn.execute(select([users.c.name, invites.c.recipient],
                                 and_(users.c.id == invites.c.sender, invites.c.code == code))).fetchone()
    if invite:
        if invite['recipient']:
            flash('Sorry, that invite code has already been used.', 'error')
        else:
            session['invite_code'] = code
            return render_template('invite.html', sender=invite[0])
    else:
        flash('Sorry, that invite code isn\'t valid.', 'error')
    return render_template('invite.html', form=form)

@app.route('/check_invite', methods=['POST'])
def check_invite():
    form = InviteCodeForm(request.form)
    if form.validate():
        code = form.code.data
        return redirect(url_for('invite', code=code))
    flash('Please enter an invite code.', 'error')
    return redirect(request.referrer or url_for('index'))

if __name__ == "__main__":
    app.secret_key = 'ksdfj321-jkhf2enmr 3njklm sdf,fgsd'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
