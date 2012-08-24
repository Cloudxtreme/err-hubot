import sys
from config import CHATROOM_PRESENCE
from errbot import botcmd, BotPlugin
import coffeescript
import re
import logging
from spidermonkey import Runtime, JSError, Object
from os import path, sep
from random import choice
import urllib, urllib2
import simplejson

def numerotatedJS(js):
    return '\n'.join(('%3i: %s' % (line, text) for line, text in enumerate(js.split('\n'), 1)))

class JSONStub(object):

    def stringify(self, str):
        return simplejson.dumps(str)

    def parse(self, str):
        return simplejson.loads(str)

class HubotHttp(object):
    def __init__(self, url):
        self.url = url
        self.query_dict = None

    def query(self, coffee_dict):
        self.query_dict = {k: coffee_dict[k] for k in coffee_dict}
        return self

    def get(self):
        err = None
        response = None
        res = None
        try:
            url = self.url + '?' + urllib.urlencode(self.query_dict) if self.query_dict else self.url
            response = urllib2.urlopen(url).read()
        except urllib2.URLError as error:
            err = error.reason
        return lambda f : f(err, res, response)


class HubotMessage(object):
    """Emulates the behavior of a hubot message
    """

    def __init__(self, callback, mess, match):
        self.callback = callback
        self.mess = mess
        matchs = [mess, ]
        matchs.extend(match.groups())
        self.match = matchs

    def send(self, msg):
        logging.debug("Hubot send: " + msg)
        room = CHATROOM_PRESENCE[0]
        self.callback.send(room, msg, message_type='groupchat')

    def random(self, array):
        return choice(array)

    def reply(self, text):
        logging.debug("Hubot reply: " + text)
        self.callback.send(self.mess.getFrom(), text, mess)

    def http(self, url):
        return HubotHttp(url)


class HubotModule(object):
    """Emulates the behavior of a hubot module
    """
    exports = None


def config_get_attr(self, name):
    return self.cb.config.get(name, None)


class HubotEnv(object):
    """Emulates the behavior of a hubot environment
    """

    def __init__(self, cb):
        self.cb = cb

    __getattr__ = config_get_attr
    __getitem__ = config_get_attr


class HubotProcess(object):
    """Emulates the behavior of a hubot process
    """

    def __init__(self, cb):
        self.env = HubotEnv(cb)


class Hubot(BotPlugin):
    # Store here the patterns to listen to
    hear_matchers = {}
    js_cache = {}

    def activate(self):
        super(Hubot, self).activate()
        self.process = HubotProcess(self)
        self.rt = Runtime()
        if not self.get('scripts', None):
            self['scripts'] = {}
        else:
            for name, snippet in self['scripts'].iteritems():
                logging.debug("Inserting %s... " % name)
                self.add_snippet(name, snippet)


    def callback_message(self, conn, mess):
        logging.debug("Hubot is hearing [%s]" % mess.getBody())
        try:
            for pattern in self.hear_matchers:
                match = re.match(pattern, mess.getBody())
                if match:
                    self.hear_matchers[pattern](HubotMessage(self, mess, match))
        except JSError as jse:
            logging.exception("Error interpreting Javascript")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_next = exc_traceback
            js_error = '\n\n Guessed stacktrack from JS:'
            while tb_next:
                code = tb_next.tb_frame.f_code
                if code.co_name == 'JavaScript code':
                    js = self.js_cache[code.co_filename]
                    ln = code.co_firstlineno
                    lines = js.split('\n')
                    js_error += '\n\n   ' + lines[ln - 2 ] + '\n-->' + lines[ln - 1] + '\n   ' + lines[ln]
                tb_next = tb_next.tb_next
            self.send(mess.getFrom(), str(jse) + js_error, mess)


    def hear(self, pattern, function):
        """The hubot callback to register a listening function
        """
        pattern = repr(pattern)
        first_slash = pattern.index('/')
        last_slash = pattern.rindex('/')
        regexp = pattern[first_slash+1:last_slash]
        modifiers = pattern[last_slash:]
        logging.debug("Registering a hubot snippet %s -> %s" % (regexp, repr(function)))
        self.hear_matchers[regexp] = function

    def respond(self, pattern, function):
        """The hubot callback to register a listening function to himself only
        TODO dissociate from hear
        """
        pattern = repr(pattern)
        first_slash = pattern.index('/')
        last_slash = pattern.rindex('/')
        regexp = pattern[first_slash+1:last_slash]
        modifiers = pattern[last_slash:]
        logging.debug("Registering a hubot snippet %s -> %s" % (regexp, repr(function)))
        self.hear_matchers[regexp] = function


    def add_snippet(self, name, coffee):
        #logging.debug("Trying to insert this gloubiboulga [%s]" % coffee)
        logging.debug("Creating a face Hubot context...")
        module = HubotModule()
        cx = self.rt.new_context()
        cx.add_global("module", module)
        cx.add_global("process", self.process)
        cx.add_global("JSON", JSONStub())
        logging.debug("Compiling coffeescript...")
        js = coffeescript.compile(coffee, bare=True)
        nummed_js = numerotatedJS(js)
        self.js_cache[name] = nummed_js
        logging.debug("Translated JS:\n" + nummed_js)
        logging.debug("Executing Hubot script...")
        cx.execute(code = js, filename = name)
        module.exports(self) # triggers the listening callbacks

    @botcmd
    def hubot_add(self, mess, args):
        """Adds a hubot script in the bot
        takes an url has parameter directly from the row github file for example  : !hubot add https://raw.github.com/github/hubot-scripts/master/src/scripts/botsnack.coffee
        """
        script_name = args.split('/')[-1].replace('.coffee', '')
        res = urllib2.urlopen(args)
        script = res.read()
        logging.debug("Adding script %s -> %s" % (script_name, script))
        copy = self['scripts']
        copy[script_name] = script
        self['scripts'] = copy
        self.add_snippet(script_name, script)
        return 'Script %s added.' % script_name

    @botcmd
    def hubot_del(self, mess, args):
        """remove a hubot script in from the bot. You need to restart the hubot plugin to make it effective.
        takes the name of the script for example : !hubot del botsnack
        """
        copy = self['scripts']
        copy.pop(args)
        self['scripts'] = copy
        return 'Done'

    @botcmd
    def hubot_list(self, mess, args):
        return '\n'.join(self['scripts'].keys())


