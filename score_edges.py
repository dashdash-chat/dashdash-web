#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import logging
from optparse import OptionParser
from collections import defaultdict
from datetime import datetime, timedelta
import json
import re
import constants
import MySQLdb
from MySQLdb import IntegrityError, OperationalError
import sleekxmpp

PAGESIZE = 20
NUM_DAYS = 90

class RelationshipScores(object):
    def __init__(self, threshold=0):
        self.threshold = threshold
        self._scores = defaultdict(lambda : defaultdict(int))
    
    def delete_score(self, sender, recipient):
        if sender in self._scores:
            if recipient in self._scores[sender]:
                del self._scores[sender][recipient]
            if len(self._scores[sender]) == 0:
                del self._scores[sender]
    
    def adjust_score(self, sender, recipient, amount):
        self._scores[sender][recipient] += amount
    
    def check_score(self, sender, recipient):
        if sender in self._scores and recipient in self._scores[sender]:
            return self._scores[sender][recipient] > self.threshold
        return False
    
    def get_user_pair(self):
        sender = None
        recipient = None
        senders = self._scores.keys()
        if len(senders) > 0:
            sender = senders[0]  # pick the first sender
            recipients = self._scores[sender].keys()
            recipient = recipients[0]  # and the first recipient (assuming delete_score properly handles senders with no recipients)
        return sender, recipient
    
    def __str__(self):
        return json.dumps(self._scores, indent=4)
    

class EdgeCalculator(sleekxmpp.ClientXMPP):
    def __init__(self):
        sleekxmpp.ClientXMPP.__init__(self, '%s@%s' % (constants.graph_xmpp_user, constants.domain), constants.graph_xmpp_password)
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("message", self.message)
        self.db = None
        self.cursor = None
        self.db_connect()
        self.scores = RelationshipScores()
        self.start_time = datetime.now()
    
    def start(self, event):
        self.process_logs()
        self.update_next_old_edge()
    
    def process_logs(self):
        def process_log_type(db_query_fn, multiplier_fn):
            offset = 0
            messages = True
            while messages:
                messages = db_query_fn(offset)
                offset += PAGESIZE
                for message in messages:
                    sender, recipient, body = message
                    self.scores.adjust_score(sender, recipient, multiplier_fn(body))
        # process_log_type(self.db_fetch_messages, lambda s: len(s))
        # process_log_type(self.db_fetch_topics,  lambda s: len(s))
        # process_log_type(self.db_fetch_whispers, lambda s: 2 * len(s))
        # process_log_type(self.db_fetch_invites,  lambda s: 100)
        # process_log_type(self.db_fetch_kicks,  lambda s: -100)
        process_log_type(self.db_fetch_twitter_follows,  lambda s: 300)
        logging.info('\n' + str(self.scores))
    
    def update_next_old_edge(self):
        old_edge = self.db_fetch_edge()
        if old_edge:
            sender, recipient = old_edge[0]
            if self.scores.check_score(sender, recipient):
                # this edge should continue to exist, so remove it from scores so we don't try to add it again later
                self.scores.delete_score(sender, recipient)
                self.update_next_old_edge()
            else:
                # otherwise we've found an edge in the database that no longer meets the threshold, so delete the vinebot (and, after receiving a response, the edge)
                self.send_message_to_leaf('/del_friendship %s %s' % (sender, recipient))
        else:
            self.update_next_new_edge()
    
    def update_next_new_edge(self):
        sender, recipient = self.scores.get_user_pair()
        if sender and recipient:
            logging.info('in update_next_new_edge for %s, %s' % (sender, recipient))
            if self.scores.check_score(sender, recipient):
                # this is an edge that now does meet the threshold and didn't before, so create the vinebot (and, after receiving a response, the edge)
                self.scores.delete_score(sender, recipient)
                self.send_message_to_leaf('/new_friendship %s %s' % (sender, recipient))
            else:
                # this is an edge that didn't exist before, and still shouldn't exist now, so go on to the next one
                self.scores.delete_score(sender, recipient)
                self.update_next_new_edge()
        else:
            self.cleanup()  # to disconnect when finished
    
    def message(self, msg):
        # %s and %s are now friends.
        # Sorry, %s and %s were not already friends.
        # Sorry, %s and %s were already friends.
        # %s and %s are no longer friends.
        m = re.match(r'(?P<sorry>Sorry\, )?(?P<sender>\w+) and (?P<recipient>\w+) (?P<result>.*)\.', msg['body'])
        if m:
            sorry     = m.groupdict()['sorry']
            sender    = m.groupdict()['sender']
            recipient = m.groupdict()['recipient']
            result    = m.groupdict()['result']
            if result in ['are no longer friends', 'were not already friends']:
                if sorry:
                    logging.warning('Tried to delete friendship for %s and %s, but they were not already friends' % (sender, recipient))
                self.db_delete_edge(sender, recipient)
                self.update_next_old_edge()
                return
            elif result in ['are now friends', 'were already friends']:
                if sorry:
                    logging.warning('Tried to create friendship for %s and %s, but they were already friends' % (sender, recipient))
                self.db_insert_edge(sender, recipient)
                self.update_next_new_edge()
                return
        logging.error('Received unexpected response from %s: %s' % (msg['from'], msg['body']))
        self.cleanup()  # to disconnect if something goes wrong
    
    def send_message_to_leaf(self, body):
        logging.info("SENDING %s" % body)
        msg = self.Message()
        msg['to'] = 'leaf1.dev.vine.im'
        msg['body'] = body
        msg.send()
    
    def db_fetch_messages(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, messages.body
                                               FROM messages, message_recipients, users as sender, users as recipient
                                               WHERE messages.id = message_recipients.message_id
                                               AND messages.parent_command_id IS NULL
                                               AND messages.sender_id IS NOT NULL
                                               AND sender.id = messages.sender_id
                                               AND recipient.id = message_recipients.recipient_id
                                               AND messages.sent_on > %(startdate)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_topics(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, commands.string
                                               FROM commands, messages, message_recipients, users as sender, users as recipient
                                               WHERE commands.command_name = 'topic'
                                               AND commands.sender_id = sender.id
                                               AND commands.id = messages.parent_command_id
                                               AND messages.id = message_recipients.message_id
                                               AND recipient.id = message_recipients.recipient_id
                                               AND sender.id != message_recipients.recipient_id
                                               AND commands.string IS NOT NULL
                                               AND commands.sent_on > %(startdate)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_whispers(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, messages.body
                                               FROM commands, messages, message_recipients, users as sender, users as recipient
                                               WHERE commands.command_name = 'whisper'
                                               AND messages.id = message_recipients.message_id
                                               AND messages.sender_id IS NOT NULL
                                               AND sender.id = messages.sender_id
                                               AND recipient.id = message_recipients.recipient_id
                                               AND commands.id = messages.parent_command_id
                                               AND commands.sent_on > %(startdate)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_invites(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, commands.token, messages.body
                                               FROM commands, messages, message_recipients, users as sender
                                               WHERE commands.command_name = 'invite'
                                               AND commands.sender_id IS NOT NULL
                                               AND sender.id = commands.sender_id
                                               AND commands.is_valid IS TRUE
                                               AND messages.sender_id IS NULL
                                               AND messages.parent_message_id IS NULL
                                               AND messages.parent_command_id = commands.id
                                               AND messages.body NOT LIKE 'Sorry, %%'
                                               #TODO fix this ugly hack, which assumes that if a response to a command begins with 'Sorry', 
                                               # there was an ExecutionError, and all other responses indicate a successful command.
                                               AND messages.id = message_recipients.message_id
                                               AND message_recipients.recipient_id = sender.id
                                               AND commands.sent_on > %(startdate)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_kicks(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, commands.token, messages.body
                                               FROM commands, messages, message_recipients, users as sender
                                               WHERE commands.sender_id IS NOT NULL
                                               AND sender.id = commands.sender_id
                                               AND commands.sent_on > %(startdate)s
                                               AND commands.is_valid IS TRUE
                                               AND commands.command_name = 'kick'
                                               AND messages.sender_id IS NULL
                                               AND messages.parent_message_id IS NULL
                                               AND messages.parent_command_id = commands.id
                                               AND messages.body NOT LIKE 'Sorry, %%'
                                               AND messages.id = message_recipients.message_id
                                               AND message_recipients.recipient_id = sender.id
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_twitter_follows(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name, NULL
                                               FROM twitter_follows, users as from_user, users as to_user
                                               WHERE to_user.twitter_id = twitter_follows.to_twitter_id
                                               AND from_user.twitter_id = twitter_follows.from_twitter_id
                                               ORDER BY twitter_follows.last_updated_on DESC
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_edge(self):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name
                                               FROM edges, users as from_user, users as to_user
                                               WHERE edges.last_updated_on < %(start_time)s
                                               AND edges.from_id = from_user.id
                                               AND edges.to_id = to_user.id
                                               LIMIT 1
                                            """, {
                                               'start_time': self.start_time
                                            })
    
    def db_insert_edge(self, sender, recipient):
        self.db_execute("""INSERT INTO edges (from_id, to_id)
                           VALUES ((SELECT id FROM users WHERE name = %(recipient)s LIMIT 1),
                                   (SELECT id FROM users WHERE name = %(sender)s LIMIT 1))
                        """, {
                           'sender': sender,
                           'recipient': recipient
                        })
    
    def db_delete_edge(self, sender, recipient):
        self.db_execute("""DELETE FROM edges
                              WHERE edges.to_id = (SELECT id FROM users WHERE name = %(recipient)s LIMIT 1)
                              AND edges.from_id = (SELECT id FROM users WHERE name = %(sender)s LIMIT 1)
                           """, {
                              'sender': sender,
                              'recipient': recipient
                           })
    
    def db_execute_and_fetchall(self, query, data={}, strip_pairs=False):
        self.db_execute(query, data)
        fetched = self.cursor.fetchall()
        if fetched and len(fetched) > 0:
            if strip_pairs:
                return [result[0] for result in fetched]
            else:
                return fetched
        return []
    
    def db_execute(self, query, data={}):
        #logging.info(query % data)
        if not self.db or not self.cursor:
            logging.info("Database connection missing, attempting to reconnect and retry query")
            if self.db:
                self.db.close()
            self.db_connect()
        try:
            self.cursor.execute(query, data)
        except MySQLdb.OperationalError, e:
            logging.info('Database OperationalError %s for query, will retry: %s' % (e, query % data))
            self.db_connect()  # Try again, but only once
            self.cursor.execute(query, data)
        return self.db.insert_id()
    
    def db_connect(self):
        try:
            self.db = MySQLdb.connect(constants.db_host,
                                      constants.graph_mysql_user,
                                      constants.graph_mysql_password,
                                      constants.db_name)
            self.db.autocommit(True)
            self.cursor = self.db.cursor()
            logging.info("Database connection created")
        except MySQLdb.Error, e:
            logging.error('Database connection and/or cursor creation failed with %d: %s' % (e.args[0], e.args[1]))
            self.cleanup()
    
    def cleanup(self):
        if self.db:
            self.db.close()
        sys.exit(1)
    

if __name__ == '__main__':
    optp = OptionParser()
    optp.add_option('-q', '--quiet', help='set logging to ERROR',
                    action='store_const', dest='loglevel',
                    const=logging.ERROR, default=logging.INFO)
    optp.add_option('-v', '--verbose', help='set logging to COMM',
                    action='store_const', dest='loglevel',
                    const=5, default=logging.INFO)
    opts, args = optp.parse_args()
    
    logging.basicConfig(level=opts.loglevel,
                        format='%(asctime)-15s graph %(levelname)-8s %(message)s')
    
    calculator = EdgeCalculator()
    calculator.register_plugin('xep_0030') # Service Discovery
    calculator.register_plugin('xep_0004') # Data Forms
    calculator.register_plugin('xep_0060') # PubSub
    calculator.register_plugin('xep_0199') # XMPP Ping
    
    if calculator.connect((constants.server_ip, constants.client_port)):# caused a weird _der_cert error
        calculator.process(block=True)
        logging.info("Done")
    else:
        logging.info("Unable to connect.")
