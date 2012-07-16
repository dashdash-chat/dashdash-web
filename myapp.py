from flask import Flask, render_template, session, redirect, url_for, request, flash
from flaskext.oauth import OAuth
app = Flask(__name__)


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
def home():
    user = None
    tweets = None
    if 'twitter_token' in session and session['twitter_token']:
        user = session['twitter_user']
        resp = twitter.get('statuses/home_timeline.json')
        if resp.status == 200:
            tweets = resp.data
        else:
            flash('Unable to load tweets from Twitter. Maybe out of '
                  'API calls or Twitter is overloaded.')   
    return render_template('home.html', user=user, tweets=tweets)

@twitter.tokengetter
def get_twitter_token():
    return session.get('twitter_token')

@app.route('/login')
def login():
    return twitter.authorize()
    #return twitter.authorize(callback=url_for('oauth_authorized', next=request.args.get('next') or request.referrer or None))

@app.route('/twitter/oauth_callback')
@twitter.authorized_handler
def oauth_authorized(resp):
    next_url = url_for('home') # request.args.get('next') or url_for('index')
    if resp is None:
        flash(u'You denied the request to sign in.')
        return redirect(next_url)

    session['twitter_token'] = (
        resp['oauth_token'],
        resp['oauth_token_secret']
    )
    session['twitter_user'] = resp['screen_name']

    flash('You were signed in as %s' % resp['screen_name'])
    return redirect(next_url)


if __name__ == "__main__":
    app.secret_key = 'ksdfj321-jkhf2enmr 3njklm sdf,fgsd'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
