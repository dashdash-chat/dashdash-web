# -*- coding: utf-8 -*-
import datetime
from random import choice
from flask import Flask, flash, render_template, redirect, request, session, url_for
from flask.ext.oauth import OAuth, OAuthException
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.wtf import Form
from wtforms import TextField, PasswordField
from wtforms.validators import Required, Email, EqualTo
from mailsnake import MailSnake
from mailsnake.exceptions import *
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm.exc import NoResultFound
import xmlrpclib
import constants
import wonderland
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
invitees = db.Table('invitees', metadata, autoload=True)
user_tasks = db.Table('user_tasks', metadata, autoload=True)
edges = db.Table('edges', metadata, autoload=True)
blocks = db.Table('blocks', metadata, autoload=True)
oauth = OAuth()
twitter = oauth.remote_app('twitter',
    base_url='https://api.twitter.com/1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    consumer_key=constants.twitter_consumer_key,
    consumer_secret=constants.twitter_consumer_secret
)
xmlrpc_server = xmlrpclib.ServerProxy('http://%s:%s' % (constants.server_ip, constants.xmlrpc_port))

class InviteCodeForm(Form):
    code = TextField('code', validators=[Required()])
class CreateAccountForm(Form):
    email = TextField('Email', [Required(), Email(message='Please enter a valid email address.')])
    password = PasswordField('New Password', [Required(), EqualTo('confirm', message='Passwords must match')])
    confirm  = PasswordField('Repeat Password')
class AddEmailForm(Form):
    email = TextField('Email', [Required(), Email(message='Please enter a valid email address.')])
class ChangeEmailForm(Form):
    email = TextField('Email', [Required(), Email(message='Please enter a valid email address.')])
class ChangePasswordForm(Form):
    password = PasswordField('New Password', [Required(), EqualTo('confirm', message='Passwords must match')])
    confirm  = PasswordField('Repeat Password')

@app.route("/")
def index():
    user = session.get('dashdash_user')
    session.pop('invite_code', None)  # pop the invite code so the user can't accidentally sign up from the sign in button
    unused_invites = None
    multi_invites = None
    used_invites = None
    user_id = None
    if user:
        s = select([users.c.id],
                   and_(users.c.name == user,
                        users.c.is_active == True))
        user_id = db.session.execute(s).fetchone() # TODO fix indexing
        if user_id:
            user_id = user_id[0]
            q = db.session.query(invites.c.code).\
                           outerjoin(invitees).\
                           filter(invitees.c.invite_id == None,
                                  invites.c.sender == user_id,
                                  invites.c.visible == True,
                                  invites.c.max_uses == 1)
            unused_invites = q.all()
            def count_uses(invite_id):  # UGH I hate doing this query here, but SQLAlchemy is incomprehensible and I can't make the subquery work
                subq = db.session.query(func.count('*')).\
                                  filter(invitees.c.invite_id == invite_id)
                return subq.scalar()
            q = db.session.query(invites.c.id, invites.c.code, invites.c.max_uses).\
                           outerjoin(invitees).\
                           filter(invites.c.sender == user_id,
                                  invites.c.visible == True,
                                  invites.c.max_uses > 1).\
                           group_by(invites.c.id)
            multi_invites = filter(lambda invite_pair: invite_pair[1] > 0, [(invite.code, invite.max_uses - count_uses(invite.id)) for invite in q.all()])
            q = db.session.query(invites.c.code, users.c.name, invitees.c.used).\
                           filter(invitees.c.invite_id == invites.c.id,
                                  invitees.c.invitee_id == users.c.id,
                                  invites.c.sender == user_id,
                                  users.c.is_active == True).\
                           order_by(desc(invitees.c.used))
            used_invites = q.all()
    return render_wonderland_template('home.html', domain=constants.domain,
                                                   user=user,
                                                   unused_invites=unused_invites,
                                                   multi_invites=multi_invites,
                                                   used_invites=used_invites)

@app.route('/signin')
def signin():
    user = session.get('dashdash_user')
    if user:
        flash('You were already signed in', 'success')
        return redirect(url_for('index'))
    return render_template('signin.html')

@app.route('/login')
def login():
    return twitter.authorize()

@app.route('/signup')
def signup():
    return twitter.authorize()

@app.route('/invite/')
@app.route('/invite/<code>')
def invite(code=None):
    user = session.get('dashdash_user')
    if user:
        return redirect(url_for('index'))
    form = InviteCodeForm()
    if not code:
        flash('Enter an invite code if you have one, or sign up without one below:', 'invite_error')
        return render_wonderland_template('invite.html', form=form)
    try:
        q = db.session.query(invites.c.id, users.c.name, invites.c.max_uses).\
                       filter(invites.c.sender == users.c.id,
                              invites.c.code == code)
        invite_id, sender_name, max_uses = q.one()
    except NoResultFound:
        flash('Sorry, \"%s\" isn\'t a valid invite code. Try another, or sign up without one below:' % code, 'invite_error')
        return render_wonderland_template('invite.html', form=form)
    q = db.session.query(users.c.name).\
                   outerjoin(invitees).\
                   filter(invitees.c.invite_id == invite_id)
    recipients = [r.name for r in q.all()]
    if len(recipients) == 1 and max_uses == 1:
        return render_wonderland_template('invite.html', form=form, sender=sender_name, recipient=recipients[0])
    elif len(recipients) >= max_uses:
        flash('Sorry, this invite code has been used. Try another, or sign up without one below:', 'invite_error')
        return render_wonderland_template('invite.html', form=form)
    else:
        session['invite_code'] = code
        return render_wonderland_template('invite.html', sender=sender_name)

@app.route('/check_invite', methods=['POST'])
def check_invite():
    form = InviteCodeForm(request.form)
    if form.validate():
        code = form.code.data
        return redirect(url_for('invite', code=code))
    flash('Please enter a valid invite code, or sign up without one below:', 'invite_error')
    return redirect(request.referrer or url_for('index'))

@app.route('/logout')
def logout():
    session.pop('dashdash_user', None)
    session.pop('twitter_user', None)
    session.pop('invite_code', None)
    flash('You signed out', 'success')
    return redirect(url_for('index'))

@twitter.tokengetter
def get_twitter_token():
    s = select([users.c.twitter_token, users.c.twitter_secret],
               and_(users.c.name == session.get('dashdash_user'),
                    users.c.is_active == True))
    return db.session.execute(s).fetchone()

def clear_bad_oauth_cookies(fn):
    def wrapped():
        try:
            return fn()
        except OAuthException, e:
            if e.message == 'Invalid response from twitter':
                session.pop('dashdash_user', None)
                return fn()
            else:
                raise e
    return wrapped

@app.route('/twitter/oauth_callback')
@clear_bad_oauth_cookies
@twitter.authorized_handler
def oauth_authorized(resp):
    def launch_celery_tasks(user_id, user_twitter_id, token, secret, future_scorings=[]):
        result = chain(fetch_follows.si(user_id, user_twitter_id, token, secret),
                       score_edges.si(user_id))()
        db.session.execute(user_tasks.insert().\
                           values(user_id=user_id,
                                  celery_task_id=result,
                                  celery_task_type='fetch_follows'))
        for minute_countdown in future_scorings:
            result = score_edges.apply_async(args=[user_id], countdown=(minute_countdown * 60))
            db.session.execute(user_tasks.insert().\
                               values(user_id=user_id,
                                      celery_task_id=result,
                                      celery_task_type='fetch_follows'))
        db.session.commit()
    if resp is None:
        flash(u'You cancelled the Twitter authorization flow.', 'failure')
        return redirect(url_for('signin'))
    twitter_user = resp['screen_name'].lower()
    s = select([users.c.id, users.c.email, users.c.twitter_id, users.c.twitter_token, users.c.twitter_secret, users.c.is_active],
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
            db.session.commit()  # commit before we kick off the celery task, just in case
        if found_user.email and found_user.is_active:
            session['dashdash_user'] = twitter_user
            flash('You signed in as %s' % twitter_user, 'success')
            launch_celery_tasks(found_user.id, resp['user_id'], resp['oauth_token'], resp['oauth_token_secret'])
            return redirect(url_for('index'))
        else:
            if not found_user.is_active:
                db.session.execute(users.update().\
                                   where(users.c.name == twitter_user).\
                                   values(is_active=True))
                db.session.commit()
            session['twitter_user'] = twitter_user
            launch_celery_tasks(found_user.id, resp['user_id'], resp['oauth_token'], resp['oauth_token_secret'], future_scorings=[10, 30, 90, 180])
            return redirect(url_for('create_account'))
    else:
        result = db.session.execute(users.insert().\
                                    values(name=twitter_user,
                                           twitter_id=resp['user_id'],
                                           twitter_token=resp['oauth_token'],
                                           twitter_secret=resp['oauth_token_secret'],
                                           stage='welcome'))
        db.session.commit()
        session['twitter_user'] = twitter_user
        launch_celery_tasks(result.lastrowid, resp['user_id'], resp['oauth_token'], resp['oauth_token_secret'], future_scorings=[10, 30, 90, 180])
        return redirect(url_for('create_account'))

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():    
    if session.get('dashdash_user'):
        return redirect(url_for('settings'))
    twitter_user = session.get('twitter_user')
    invite_code = session.get('invite_code')
    found_user = None
    has_unused_invite = None
    user_used_invite = None
    if twitter_user:
        s = select([users.c.id, users.c.name, users.c.email],
                   and_(users.c.name == twitter_user,
                        users.c.is_active == True))
        found_user = db.session.execute(s).fetchone()
    if invite_code:
        try:
            q = db.session.query(invites.c.id, invites.c.max_uses).\
                           filter(invites.c.code == invite_code,
                                  invites.c.sender != found_user.id if found_user else None)
            has_unused_invite = q.one()
            q = db.session.query(invitees).\
                           filter(invitees.c.invite_id == has_unused_invite.id)
            if q.count() >= has_unused_invite.max_uses:
                has_unused_invite = None
        except NoResultFound:
            has_unused_invite = None
    if found_user:
        try:
            q = db.session.query(invites).\
                           outerjoin(invitees).\
                           filter(invitees.c.invitee_id == found_user.id)
            user_used_invite = q.one()
        except NoResultFound:
            user_used_invite = None
    if request.method == 'GET':
        if found_user:
            session['account_exists'] = _check_account(found_user.name)
            if found_user.email and session.get('account_exists'):
                session['dashdash_user'] = found_user.name
                flash('You signed in as %s' % found_user.name, 'success')
                return redirect(url_for('index'))
            if session.get('account_exists') and not found_user.email:
                form = AddEmailForm()
            else:
                form = CreateAccountForm()
            if user_used_invite:
                db.session.execute(invitees.update().\
                                   where(and_(invitees.c.invitee_id == found_user.id,
                                         invitees.c.used == '0000-00-00 00:00:00')).\
                                   values(used=datetime.datetime.now()))
                db.session.commit()
                return render_wonderland_template('create_account.html', user=found_user.name, form=form, account_exists=session.get('account_exists'))
            if has_unused_invite:
                db.session.execute(invitees.insert().\
                                   values(invite_id=has_unused_invite.id,
                                          invitee_id=found_user.id,
                                          used=datetime.datetime.now()))
                db.session.commit()
            return render_wonderland_template('create_account.html', user=found_user.name, form=form, account_exists=session.get('account_exists'))
        else:
            flash('Sorry, first you need to sign in with Twitter!', 'failure')
            return redirect(url_for('signin'))
    else:  # request.method == 'POST':
        if found_user:
            if session.get('account_exists'):
                form = AddEmailForm(request.form)
            else:
                form = CreateAccountForm(request.form)
            if form.validate():
                if not session.get('account_exists'):
                    try:
                        _register(found_user.name, form.password.data)
                    except xmlrpclib.ProtocolError, e:
                        flash('There was an error creating your XMPP account.', 'failure')
                        return redirect(url_for('create_account'))
                try:
                    db.session.execute(users.update().\
                                       where(users.c.id == found_user.id).\
                                       values(email=form.email.data))
                except: #TODO handle the IntegrityError properly!
                    flash('This email address has already been used - try another?', 'failure')
                    return redirect(url_for('create_account'))
                if has_unused_invite and invite_code:
                    try:
                        db.session.execute(invitees.insert().\
                                           values(invite_id=has_unused_invite.id,
                                                  invitee_id=found_user.id,
                                                  used=datetime.datetime.now()))
                    except: #TODO handle the IntegrityError properly!
                        pass
                db.session.commit()
                result = score_edges.delay(found_user.id)  # Score edges again after the invites have been updated  #TODO keep track of this user's task progress
                session['dashdash_user'] = found_user.name
                session.pop('twitter_user', None)
                session.pop('invite_code', None)
                session.pop('account_exists', None)
                flash('You signed up as %s!' % found_user.name, 'success')
                return redirect(url_for('help'))
            else:
                flash('Please be sure to enter a valid email address and matching passwords.', 'failure')
                return redirect(url_for('create_account'))
        else:
            flash('Sorry, that POST request was invalid.', 'failure')
            return redirect(url_for('signin'))

@app.route("/demo/")
def no_demo():
    return redirect(url_for('index'))

@app.route("/demo/<token>/")
def demo(token):
    s = select([users.c.name, demos.c.password],
               and_(users.c.id == demos.c.user_id,
                    demos.c.token == token,
                    users.c.is_active == True))
    found_demo = db.session.execute(s).fetchone()
    if found_demo:
        return render_template('demo.html', domain=constants.domain, username=found_demo['name'], password=found_demo['password'])
    return redirect(url_for('index'))

@app.route("/help/")
@app.route("/help")
@app.route("/help/<client>")
def help(client='adium'):
    user = session.get('dashdash_user')
    if not user:
        return redirect(url_for('signin'))
    return render_template('help.html', client=client, user=user, domain=constants.domain, helpbot=constants.helpbot_jid_user)

@app.route("/settings", methods=['GET', 'POST'])
def settings():
    user = session.get('dashdash_user')
    if not user:
        return redirect(url_for('signin'))
    if request.method == 'GET':
        user_email = db.session.execute(select([users.c.email], users.c.name == user)).fetchone()
        form = ChangeEmailForm()
        form.email.data = user_email.email if user_email else None
    else:
        form = ChangeEmailForm(request.form)
        if form.validate():
            try:
                db.session.execute(users.update().where(users.c.name == user).values(email=form.email.data))
                db.session.commit()
                flash('Your email address has been changed.', 'success')
            except: #TODO handle the IntegrityError properly!
                flash('This email address has already been used - try another?', 'failure')
        else:    
            flash('Please enter a valid email address.', 'failure')
    return render_wonderland_template('settings.html', user=user, form=form)

@app.route('/settings/change_password', methods=['GET', 'POST'])
def change_password():
    user = session.get('dashdash_user')
    if not user:
        return redirect(url_for('signin'))
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
        else:
            flash('Are you sure you entered the same valid password twice? Please try again.', 'failure')
    return render_wonderland_template('change_password.html', user=user, form=form)

@app.route("/contacts")
def contacts():
    user = session.get('dashdash_user')
    if not user:
        return redirect(url_for('signin'))        
    def filter_admins(user_rows):
        users = [user_row.name for user_row in user_rows]
        return set(users).difference(constants.protected_users)
    user_id = db.session.execute(select([users.c.id], users.c.name == user)).fetchone()['id']
    s = select([users.c.name],
               and_(edges.c.from_id == user_id,
                    edges.c.to_id == users.c.id,
                    users.c.is_active == True))
    outgoing = filter_admins(db.session.execute(s).fetchall())
    s = select([users.c.name],
               and_(edges.c.to_id == user_id,
                    edges.c.from_id == users.c.id,
                    users.c.is_active == True))
    incoming = filter_admins(db.session.execute(s).fetchall())
    friends = outgoing.intersection(incoming)
    s = select([users.c.name],
               and_(blocks.c.from_user_id == user_id,
                    blocks.c.to_user_id == users.c.id,
                    users.c.is_active == True))
    blockees = filter_admins(db.session.execute(s).fetchall())
    return render_wonderland_template('contacts.html', user=user,
                                            friends=friends,
                                            incomings=incoming.difference(outgoing),
                                            outgoings=outgoing.difference(incoming),
                                            blockees=blockees)
    return redirect(url_for('index'))

@app.route("/about")
def about():
    user = session.get('dashdash_user')
    return render_wonderland_template('about.html', user=user)

@app.route("/terms")
def terms():
    user = session.get('dashdash_user')
    return render_wonderland_template('legal_terms.html', user=user)

@app.route("/privacy")
def privacy():
    user = session.get('dashdash_user')
    return render_wonderland_template('legal_privacy.html', user=user)

@app.errorhandler(404)
def page_not_found(e=None):
    return render_wonderland_template('404.html'), 404

@app.route("/50x.html")
@app.errorhandler(500)
def page_not_found(e=None):
    return render_wonderland_template('500.html'), 500

def render_wonderland_template(template_name_or_list, **context):
    context['wonderland_paragraphs'] = choice(wonderland.snippets)
    return render_template(template_name_or_list, **context)
    
def _check_account(user):
    return _xmlrpc_command('check_account', {
        'user': user,
        'host': constants.domain
    })['res'] == 0

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
