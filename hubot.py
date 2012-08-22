from config import CHATROOM_PRESENCE
from errbot import botcmd, BotPlugin
import coffeescript
import re
import logging
from spidermonkey import Runtime
from os import path, sep
from random import choice
import urllib2

class HubotHttp(object):
    def __init__(self, url):
        self.url = url
    def get(self):
        err = None
        response = None
        res = None
        try:
            response = urllib2.urlopen(self.url)
        except URLError as error:
            err = error.reason
        return err, res, response.read()

class HubotMessage(object):
    """Emulates the behavior of a hubot message
    """
    def __init__(self, callback, mess, match):
        self.callback = callback
        self.mess = mess
        self.match = match.groups()

    def send(self, msg):
        logging.debug("Hubot send: "+ msg)
        room = CHATROOM_PRESENCE[0]
        self.callback.send(room, msg, message_type='groupchat')

    def random(self, array):
        return choice(array)

    def reply(self, text):
        logging.debug("Hubot reply: "+ text)
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


    def activate(self):
        super(Hubot, self).activate()
        self.process = HubotProcess(self)
        self.rt = Runtime()
        if not self.get('scripts', None):
            self['scripts'] = {}
        else:
            for name, snippet in self['scripts'].iteritems():
                logging.debug("Inserting %s... " % name)
                self.add_snippet(snippet)


    def callback_message(self, conn, mess):
        logging.debug("Hubot is hearing [%s]" % mess.getBody())
        for pattern in self.hear_matchers:
            match = re.match(pattern, mess.getBody())
            if match:
                self.hear_matchers[pattern](HubotMessage(self, mess, match))

    def hear(self, pattern, function):
        """The hubot callback to register a listening function
        """
        regexp, modifiers = repr(pattern).split('/')[1:]
        logging.debug("Registering a hubot snippet %s -> %s" % (regexp, repr(function)))
        self.hear_matchers[regexp] = function

    def respond(self, pattern, function):
        """The hubot callback to register a listening function to himself only
        TODO dissociate from hear
        """
        regexp, modifiers = repr(pattern).split('/')[1:]
        logging.debug("Registering a hubot snippet %s -> %s" % (regexp, repr(function)))
        self.hear_matchers[regexp] = function


    def add_snippet(self, coffee):
        logging.debug("Trying to insert this gloubiboulga [%s]" % coffee)
        logging.debug("Creating a face Hubot context...")
        module = HubotModule()
        cx = self.rt.new_context()
        cx.add_global("module", module)
        cx.add_global("process", self.process)
        logging.debug("Compiling coffeescript...")
        js = coffeescript.compile(coffee, bare=True)
        logging.debug("Executing Hubot script...")
        cx.execute(js)
        module.exports(self) # triggers the listening callbacks

    @botcmd
    def hubot_add(self, mess, args):
        """Adds a hubot script in the bot
        takes an url has parameter directly from the row github file for example  : !hubot add https://raw.github.com/github/hubot-scripts/master/src/scripts/botsnack.coffee
        """
        script_name = args.split('/')[-1].replace('.coffee', '')
        res = urllib2.urlopen(args)
        script = res.read()
        logging.debug("Adding script %s -> %s", (script_name, script))
        copy = self['scripts']
        copy[script_name] = script
        self['scripts'] = copy
        self.add_snippet(script)
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

