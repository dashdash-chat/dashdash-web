var jid, pass, register, prio, connect_host, connect_port, connect_secure;
var jwchats = new Array();
var JABBERSERVER;
var HTTPBASE;
var BACKEND_TYPE;
function launchDemoClient(username, password, confirm) {
    if (password != confirm || password == '') {
        return false;
    }
    jid = username + "@" + JABBERSERVER + "/" + DEFAULTRESOURCE + Math.round(Math.random()*1000);
    pass = password;
    register = false;
    prio = DEFAULTPRIORITY;
    connect_secure = false;
    jwchats[jid] = window.open("/static/jwchat/jwchat.html",makeWindowName(jid),'width=320,height=390,resizable=yes');
    $(jwchats[jid]).load(function() {
      $('form.vine-form').submit();
    });
    return false;
}
function init() {
    var servers_allowed = BACKENDS[0].servers_allowed,
        default_server = BACKENDS[0].default_server;
    HTTPBASE = BACKENDS[0].httpbase;
    BACKEND_TYPE = BACKENDS[0].type;
    JABBERSERVER = servers_allowed[0];
}
onload = init;
