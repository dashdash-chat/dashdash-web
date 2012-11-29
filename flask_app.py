import datetime
from flask import Flask, flash, render_template, redirect, request, session, url_for
from flask.ext.oauth import OAuth, OAuthException
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.wtf import Form, TextField, PasswordField, Required, Email, EqualTo
from sqlalchemy import select, and_
import xmlrpclib
import constants
from celery import chain
from celery_tasks import fetch_follows, score_edges

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
demos = db.Table('demos', metadata, autoload=True)
users = db.Table('users', metadata, autoload=True)
invites = db.Table('invites', metadata, autoload=True)
user_tasks = db.Table('user_tasks', metadata, autoload=True)
edges = db.Table('edges', metadata, autoload=True)
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
    if user:
        user_id = db.session.execute(select([users.c.id], users.c.name == user)).fetchone()['id'] # TODO fix indexing
        s = select([invites.c.code, invites.c.recipient],
                   and_(invites.c.sender == user_id, invites.c.recipient == None))
        unused_invites = db.session.execute(s).fetchall()
        s = select([invites.c.code, users.c.name, invites.c.used],
                   and_(invites.c.sender == user_id, invites.c.recipient == users.c.id, ))
        used_invites = db.session.execute(s).fetchall()
    return render_template('home.html', domain=constants.domain, user=user, unused_invites=unused_invites, used_invites=used_invites)

@app.route('/login')
def login():
    return twitter.authorize()

@app.route('/invite/')
@app.route('/invite/<code>')
def invite(code=None):
    user = session.get('vine_user')
    if user:
        return redirect(url_for('index'))
    invite = db.session.execute(select([users.c.name, invites.c.recipient],
                                and_(users.c.id == invites.c.sender, invites.c.code == code))).fetchone()
    form = InviteCodeForm()
    if invite:
        if invite['recipient']:
            flash('Sorry, that invite code has already been used.', 'invite_error')
            return render_template('invite.html', form=form)
        else:
            session['invite_code'] = code
            return render_template('invite.html', sender=invite[0])
    else:
        if code:
            flash('Sorry, %s is not a valid invite code. Enter a different one?' % code, 'invite_error')
        else:
            flash('Sorry, but you need to be invited before you can sign up. Enter an invite code below?', 'invite_error')
        return render_template('invite.html', form=form)

@app.route('/check_invite', methods=['POST'])
def check_invite():
    form = InviteCodeForm(request.form)
    if form.validate():
        code = form.code.data
        return redirect(url_for('invite', code=code))
    flash('Please enter an invite code below.', 'invite_error')
    return redirect(request.referrer or url_for('index'))

@app.route('/logout')
def logout():
    session.pop('vine_user', None)
    session.pop('twitter_user', None)
    session.pop('invite_code', None)
    flash('You were signed out', 'success')
    return redirect(url_for('index'))

@twitter.tokengetter
def get_twitter_token():
    s = select([users.c.twitter_token, users.c.twitter_secret], users.c.name == session.get('vine_user'))
    return db.session.execute(s).fetchone()

def clear_bad_oauth_cookies(fn):
    def wrapped():
        try:
            return fn()
        except OAuthException, e:
            if e.message == 'Invalid response from twitter':
                session.pop('vine_user', None)
                return fn()
            else:
                raise e
    return wrapped
@app.route('/twitter/oauth_callback')
@clear_bad_oauth_cookies
@twitter.authorized_handler
def oauth_authorized(resp):
    if resp is None:
        flash(u'You cancelled the Twitter authorization flow.', 'failure')
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
        result = chain(fetch_follows.s(found_user.id, resp['user_id'], resp['oauth_token'], resp['oauth_token_secret']),
                       score_edges.s())()
        db.session.execute(user_tasks.insert().\
                           values(user_id=found_user.id,
                                  celery_task_id=result,
                                  celery_task_type='fetch_follows'))
        db.session.commit()
        if found_user.email:
            session['vine_user'] = twitter_user
            flash('You were signed in as %s' % twitter_user, 'success')
            return redirect(url_for('index'))
        else:
            session['twitter_user'] = twitter_user
            return redirect(url_for('create_account'))
    else:  # still store the user object and tokens, but elsewhere only set the session['vine_user'] if we have an email already!
        db.session.execute(users.insert().\
                           values(name=twitter_user,
                                  twitter_token=resp['oauth_token'],
                                  twitter_secret=resp['oauth_token_secret']))
        db.session.commit()
        if session.get('invite_code'):
            session['twitter_user'] = twitter_user
            return redirect(url_for('create_account'))
        else:
            return redirect(url_for('invite'))

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():    
    if session.get('vine_user'):
        return redirect(url_for('settings'))
    twitter_user = session.get('twitter_user')
    invite_code = session.get('invite_code')
    found_user = None
    has_unused_invite = None
    user_used_invite = None
    if twitter_user:
        s = select([users.c.id, users.c.name, users.c.email], and_(users.c.name == twitter_user))
        found_user = db.session.execute(s).fetchone()
    if invite_code:
        s = select([invites.c.id], and_(invites.c.code == invite_code, invites.c.recipient == None))
        has_unused_invite = db.session.execute(s).fetchone()
    if found_user:
        s = select([invites], and_(invites.c.recipient == found_user.id))
        user_used_invite = db.session.execute(s).fetchone()
    if request.method == 'GET':
        if found_user:
            if found_user.email:
                session['vine_user'] = found_user.name
                flash('You signed in as %s' % found_user.name, 'success')
                return redirect(url_for('index'))
            if user_used_invite:
                form = CreateAccountForm()
                return render_template('create_account.html', user=found_user.name, form=form)
            if has_unused_invite:
                db.session.execute(invites.update().\
                               where(invites.c.id == has_unused_invite.id).\
                               values(recipient=found_user.id, used=datetime.datetime.now()))
                db.session.commit()
                form = CreateAccountForm()
                return render_template('create_account.html', user=found_user.name, form=form)
            return redirect(url_for('invite') + invite_code)
        else:
            flash('Sorry, first you\'ll need to sign in with Twitter and have a valid invite code!', 'failure')
            return redirect(url_for('index'))
    else:
        if found_user and (has_unused_invite or user_used_invite):
            form = CreateAccountForm(request.form)
            if form.validate():
                try:
                    _register(found_user.name, form.password.data)
                except xmlrpclib.ProtocolError, e:
                    flash('There was an error creating your XMPP account.', 'failure')
                    return redirect(url_for('create_account'))
                db.session.execute(users.update().\
                               where(users.c.id == found_user.id).\
                               values(email=form.email.data))
                db.session.execute(invites.update().\
                                 where(invites.c.code == session['invite_code']).\
                                 values(recipient=found_user.id, used=datetime.datetime.now()))
                db.session.commit()
                session['vine_user'] = found_user.name
                session.pop('twitter_user', None)
                session.pop('invite_code', None)
                flash('You signed up as %s' % found_user.name, 'success')
                return redirect(url_for('index'))
            else:
                flash('There was an error in the form.', 'failure')
                return redirect(url_for('create_account'))
        else:        
            flash('Sorry, that POST request was invalid.', 'failure')
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

@app.route("/setup")
def setup():
    user = session.get('vine_user')
    return render_template('setup.html', user=user)

@app.route("/settings")
def settings():
    user = session.get('vine_user')
    if not user:
        return redirect(url_for('index'))
    if request.method == 'GET':
        user_email = db.session.execute(select([users.c.email], users.c.name == user)).fetchone()
        form = ChangeEmailForm()
        form.email.data = user_email.email
    else:
        form = ChangeEmailForm(request.form)
        if form.validate():
            db.session.execute(users.update().where(users.c.name == user).values(email=form.email.data))
            db.session.commit()
            flash('Your email address has been changed.', 'success')
    return render_template('settings.html', user=user, form=form)

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
                flash('Your password has been changed.', 'success')
            except xmlrpclib.ProtocolError, e:
                flash('There was an error changing your XMPP password.', 'failure')
                return redirect(url_for('change_password'))
    return render_template('change_password.html', user=user, form=form)

@app.route("/contacts")
def contacts():
    def filter_admins(user_rows):
        users = [user_row.name for user_row in user_rows]
        jids_to_filter = constants.admin_jids + [constants.leaves_jid, constants.graph_xmpp_jid]
        users_to_filter = [jid.split('@')[0] for jid in jids_to_filter] + [constants.web_xmlrpc_user]
        return set(users).difference(users_to_filter)
    user = session.get('vine_user')
    if user:
        user_id = db.session.execute(select([users.c.id], users.c.name == user)).fetchone()['id']
        s = select([users.c.name], and_(edges.c.from_id == user_id, edges.c.to_id == users.c.id))
        outgoing = filter_admins(db.session.execute(s).fetchall())
        s = select([users.c.name], and_(edges.c.to_id == user_id, edges.c.from_id == users.c.id))
        incoming = filter_admins(db.session.execute(s).fetchall())
        friends = outgoing.intersection(incoming)
        return render_template('contacts.html', user=user,
                                                friends=friends,
                                                incomings=incoming.difference(outgoing),
                                                outgoings=outgoing.difference(incoming))
    return redirect(url_for('index'))

@app.route("/about")
def about():
    user = session.get('vine_user')
    return render_template('about.html', user=user)

@app.route("/legal")
def legal():
    user = session.get('vine_user')
    return render_template('legal.html', user=user)

@app.errorhandler(404)
def page_not_found(e=None):
    return render_template('404.html'), 404

@app.route("/50x.html")
@app.errorhandler(500)
def page_not_found(e=None):
    return render_template('500.html'), 500

def _register(user, password):
    _xmlrpc_command('register', {
        'user': user,
        'host': constants.domain,
        'password': password
    })
def _change_password(user, password):
    _xmlrpc_command('change_password', {
        'user': user,
        'host': constants.domain,
        'newpass': password
    })
def _xmlrpc_command(command, data):
    fn = getattr(xmlrpc_server, command)
    return fn({
        'user': constants.web_xmlrpc_user,
        'server': constants.domain,
        'password': constants.web_xmlrpc_password
    }, data)

if __name__ == "__main__":
    #NOTE this code only gets run when you're using Flask's built-in server, so gunicorn never sees this code.
    app.run(host='0.0.0.0', port=8000)
