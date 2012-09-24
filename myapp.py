import datetime
from flask import Flask, render_template, session, redirect, url_for, request, flash
from flask.ext.oauth import OAuth
from flask.ext.wtf import Form, TextField, PasswordField, Required, Email, EqualTo
from sqlalchemy import create_engine, select, and_, MetaData, Table
import xmlrpclib
app = Flask(__name__)

server = 'dev.vine.im'
web_xmlrpc_password = 'ev5birc6yoj5cem5lalg'
xmlrpc_server = xmlrpclib.ServerProxy('http://%s:%s' % (server, 4560))
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

class CreateAccountForm(Form):
    email = TextField('Email', [Required(), Email(message='Please enter a valid email address.')])
    password = PasswordField('New Password', [Required(), EqualTo('confirm', message='Passwords must match')])
    confirm  = PasswordField('Repeat Password')

class ChangeEmailForm(Form):
    email = TextField('Email', [Required(), Email(message='Please enter a valid email address.')])

class ChangePasswordForm(Form):
    password = PasswordField('New Password', [Required(), EqualTo('confirm', message='Passwords must match')])
    confirm  = PasswordField('Repeat Password')
    
    
@app.route("/")
def index():
    user = session.get('vine_user')
    unused_invites = None
    used_invites = None
    tweets = None
    if user:
        user_id = conn.execute(select([users.c.id], users.c.name == user)).fetchone()['id'] # TODO fix indexing
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

@app.route("/about")
def about():
    user = session.get('vine_user')
    return render_template('about.html', user=user)

@app.route("/legal")
def legal():
    user = session.get('vine_user')
    return render_template('legal.html', user=user)

@app.route("/setup")
def setup():
    user = session.get('vine_user')
    return render_template('setup.html', user=user)

@app.route("/contacts")
def contacts():
    user = session.get('vine_user')
    return render_template('contacts.html', user=user)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def page_not_found(e):
    return render_template('500.html'), 500


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user = session.get('vine_user')
    if not user:
        return redirect(url_for('index'))
    if request.method == 'GET':
        user_email = conn.execute(select([users.c.email], users.c.name == user)).fetchone()
        form = ChangeEmailForm()
        form.email.data = user_email.email
    else:
        form = ChangeEmailForm(request.form)
        if form.validate():
            conn.execute(users.update().where(users.c.name == user).values(email=form.email.data))
            flash('Your email address has been changed.', 'error')
    return render_template('settings.html', form=form)

@app.route('/settings/change_password', methods=['GET', 'POST'])
def change_password():
    user = session.get('vine_user')
    if not user:
        return redirect(url_for('index'))
    if request.method == 'GET':
        form = ChangePasswordForm()
    else:
        form = ChangePasswordForm(request.form)
        if form.validate():
            try:
                _change_password(user, form.password.data)
                flash('Your password has been changed.', 'error')
            except xmlrpclib.ProtocolError, e:
                flash('There was an error changing your XMPP password.', 'error')
                return redirect(url_for('change_password'))
    return render_template('change_password.html', form=form)
    
@twitter.tokengetter
def get_twitter_token():
    s = select([users.c.twitter_token, users.c.twitter_secret], users.c.name == session.get('vine_user'))
    return conn.execute(s).fetchone()


#TODO unique invite codes

@app.route('/login')
def login():
    return twitter.authorize()
    #return twitter.authorize(callback=url_for('oauth_authorized', next=request.args.get('next') or request.referrer or None))

@app.route('/logout')
def logout():
    session.pop('vine_user', None)
    flash('You were signed out', 'error')
    return redirect(request.referrer or url_for('index'))

@app.route('/twitter/oauth_callback')
@twitter.authorized_handler
def oauth_authorized(resp):
    if resp is None:
        flash(u'You cancelled the Twitter authorization flow.', 'error')
        return redirect(url_for('index'))
    twitter_user = resp['screen_name'].lower()
    s = select([users.c.email, users.c.twitter_token, users.c.twitter_secret],
            and_(users.c.name == twitter_user))
    found_user = conn.execute(s).fetchone()
    if found_user:
        if not found_user.twitter_token == resp['oauth_token'] or not found_user.twitter_secret == resp['oauth_token_secret']:
            conn.execute(users.update().\
                         where(users.c.name == twitter_user).\
                         values(twitter_token=resp['oauth_token'], twitter_secret=resp['oauth_token_secret']))
    else:
        conn.execute(users.insert().\
                           values(name=twitter_user,
                                  twitter_token=resp['oauth_token'],
                                  twitter_secret=resp['oauth_token_secret']))
    if found_user and found_user.email:  # if we have a user that's finished the process
        session['vine_user'] = twitter_user
        flash('You were signed in as %s' % twitter_user, 'error')
    else:
        if session.get('invite_code'):
            s = select([invites], and_(invites.c.code == session['invite_code'], invites.c.recipient == None))
            if conn.execute(s).fetchone():
                session['twitter_user'] = twitter_user
                return redirect(url_for('create_account'))
            else:
                flash('Sorry, that invite code is not valid.', 'error')
        else:
            flash('Sorry, but you need an invite code to sign up.', 'error')
    return redirect(url_for('index'))

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'GET':
        user = session.get('twitter_user')
        form = CreateAccountForm()
        return render_template('create_account.html', user=user, form=form)
    else:       
        if session.get('invite_code'):
            s = select([invites], and_(invites.c.code == session['invite_code'], invites.c.recipient == None))
            if conn.execute(s).fetchone():
                form = CreateAccountForm(request.form)
                if form.validate():
                    try:
                        #_register(session.get('twitter_user'), form.password.data) # commented out because xmpp server does not exist on my machine
                        conn.execute(users.update().\
                                       where(users.c.name == session.get('twitter_user')).\
                                       values(email=form.email.data))
                        user_id = conn.execute(select([users.c.id], users.c.name == session.get('twitter_user'))).fetchone()[0]
                        conn.execute(invites.update().\
                                         where(invites.c.code == session['invite_code']).\
                                         values(recipient=user_id, used=datetime.datetime.now()))
                        session['vine_user'] = session.get('twitter_user')
                        session.pop('twitter_user')
                        session.pop('invite_code')
                        flash('You signed up as %s' % session.get('vine_user'), 'error')
                    except xmlrpclib.ProtocolError, e:
                        flash('There was an error creating your XMPP account.', 'error')
                        return redirect(url_for('create_account'))
                else:
                    #flash('There was an error in the form.', 'error')
                    return redirect(url_for('create_account'))
            else:
                flash('Sorry, that invite code is not valid.', 'error')
        else:
            flash('Sorry, but you need an invite code to sign up.', 'error')
        return redirect(url_for('index'))

def _register(user, password):
    _xmlrpc_command('register', {
        'user': user,
        'host': server,
        'password': password
    })
def _change_password(user, password):
    _xmlrpc_command('change_password', {
        'user': user,
        'host': server,
        'newpass': password
    })
def _xmlrpc_command(command, data):
    fn = getattr(xmlrpc_server, command)
    return fn({
        'user': '_web0',
        'server': server,
        'password': web_xmlrpc_password
    }, data)
    
@app.route('/invite/<code>')
def invite(code):
    user = session.get('vine_user')
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
