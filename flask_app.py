from flask import Flask, render_template, redirect
app = Flask(__name__)
server = 'dev.vine.im'

@app.route("/")
def index():
    return render_template('home.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/demo")
def demo():
    return render_template('demo.html', server=server, username='alice', password='demo_password')
    
@app.route("/demo/jwchat-config.js")
def jwchat_config():
    return render_template('jwchat-config.js', server=server, username='alice', password='demo_password')

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
