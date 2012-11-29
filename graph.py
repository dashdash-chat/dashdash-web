#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, timedelta
import json
import MySQLdb
from MySQLdb import IntegrityError, OperationalError
import re
import sleekxmpp
import sys
import constants

PAGESIZE = 100
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
    def __init__(self, logger, user_id=None):
        self.logger = logger
        self.user_id = user_id
        sleekxmpp.ClientXMPP.__init__(self, constants.graph_xmpp_jid, constants.graph_xmpp_password)
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("message", self.message)
        self.old_edge_offset = 0
        self.db = None
        self.cursor = None
        self.db_connect()
        self.scores = RelationshipScores()
        self.start_time = datetime.now()
    
    def start(self, event):
        self.send_presence()
        self.process_logs()
        self.process_blocks()
        self.logger.info('\n' + str(self.scores))
        self.update_next_old_edge()
    
    def process_logs(self):
        def process_log_type(db_query_fn, multiplier_fn):
            offset = 0
            rows = True
            while rows:
                rows = db_query_fn(offset)
                offset += PAGESIZE
                for row in rows:
                    sender, recipient, content = row
                    self.scores.adjust_score(sender, recipient, multiplier_fn(content))
        process_log_type(self.db_fetch_artificial_follows, lambda s: 10000)
        process_log_type(self.db_fetch_account_invites,    lambda s: 10000)
        process_log_type(self.db_fetch_twitter_follows,    lambda s: 300)
        process_log_type(self.db_fetch_messages, lambda s: len(s))
        process_log_type(self.db_fetch_topics,   lambda s: len(s))
        process_log_type(self.db_fetch_whispers, lambda s: 2 * len(s))
        process_log_type(self.db_fetch_invites,  lambda s: 100)
        process_log_type(self.db_fetch_kicks,    lambda s: -100)
    
    def process_blocks(self):
        offset = 0
        blocks = True
        while blocks:
            blocks = self.db_fetch_blocks(offset)
            offset += PAGESIZE
            for block in blocks:
                sender, recipient = block
                self.scores.delete_score(sender, recipient)
    
    def update_next_old_edge(self):
        old_edge = self.db_fetch_next_old_edge()
        if old_edge:
            sender, recipient = old_edge[0]
            self.logger.info('in update_next_old_edge for %s, %s' % (sender, recipient))
            if self.scores.check_score(sender, recipient):
                # this edge should continue to exist, so remove it from scores so we don't try to add it again later
                self.scores.delete_score(sender, recipient)
                self.update_next_old_edge()
            else:
                # otherwise we've found an edge in the database that no longer meets the threshold, so delete the vinebot (and, after receiving a response, the edge)
                self.scores.delete_score(sender, recipient)
                self.send_message_to_leaf('/del_edge %s %s' % (sender, recipient))
        else:
            self.update_next_new_edge()
    
    def update_next_new_edge(self):
        sender, recipient = self.scores.get_user_pair()
        if sender and recipient:
            self.logger.info('in update_next_new_edge for %s, %s' % (sender, recipient))
            if self.scores.check_score(sender, recipient):
                # this is an edge that now does meet the threshold and didn't before, so create the vinebot (and, after receiving a response, the edge)
                self.scores.delete_score(sender, recipient)
                self.send_message_to_leaf('/new_edge %s %s' % (sender, recipient))
            else:
                # this is an edge that didn't exist before, and still shouldn't exist now, so go on to the next one
                self.scores.delete_score(sender, recipient)
                self.update_next_new_edge()
        else:
            self.cleanup()  # to disconnect when finished
    
    def message(self, msg):
        # *** %s and %s now have a directed edge between them.
        # *** Sorry, %s and %s already have a directed edge between them.
        # *** Sorry, %s and %s do not have a directed edge between them.
        # *** %s and %s no longer have a directed edge between them.
        m = re.match(r'\*\*\* (?P<sorry>Sorry\, )?(?P<sender>\w+) and (?P<recipient>\w+) (?P<result>.*)\.', msg['body'])
        if m:
            sorry     = m.groupdict()['sorry']
            sender    = m.groupdict()['sender']
            recipient = m.groupdict()['recipient']
            result    = m.groupdict()['result']
            if result in ['no longer have a directed edge between them', 'do not have a directed edge between them']:
                if sorry:
                    self.logger.warning('Tried to delete edge for %s and %s, but it didn\'t exist.' % (sender, recipient))
                self.update_next_old_edge()
                return
            elif result in ['now have a directed edge between them', 'already have a directed edge between them']:
                if sorry:
                    self.logger.warning('Tried to create edge for %s and %s, but it already existed.' % (sender, recipient))
                self.update_next_new_edge()
                return
        self.logger.error('Received unexpected response from %s: %s' % (msg['from'], msg['body']))
        self.logger.error('Are you sure the leaf is running?')
        self.cleanup()  # to disconnect if something goes wrong
    
    def send_message_to_leaf(self, body):
        msg = self.Message()
        msg['to'] = constants.leaves_jid
        msg['body'] = body
        msg.send()
        self.logger.info("SENT %s" % body)
    
    def db_fetch_artificial_follows(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name, NULL
                                               FROM artificial_follows, users as from_user, users as to_user
                                               WHERE to_user.id = artificial_follows.to_user_id
                                               AND from_user.id = artificial_follows.from_user_id
                                               AND from_user.id LIKE %(user_id)s
                                               ORDER BY artificial_follows.created DESC
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_account_invites(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name, NULL
                                               FROM invites, users as from_user, users as to_user
                                               WHERE to_user.id = invites.recipient
                                               AND from_user.id = invites.sender
                                               AND invites.used > %(startdate)s
                                               AND from_user.id LIKE %(user_id)s
                                               ORDER BY invites.created DESC
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_twitter_follows(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name, NULL
                                               FROM twitter_follows, users as from_user, users as to_user
                                               WHERE to_user.twitter_id = twitter_follows.to_twitter_id
                                               AND from_user.twitter_id = twitter_follows.from_twitter_id
                                               AND from_user.id LIKE %(user_id)s
                                               ORDER BY twitter_follows.last_updated_on DESC
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_messages(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, messages.body
                                               FROM messages, recipients, users as sender, users as recipient
                                               WHERE messages.id = recipients.message_id
                                               AND messages.parent_command_id IS NULL
                                               AND messages.sender_id IS NOT NULL
                                               AND sender.id = messages.sender_id
                                               AND recipient.id = recipients.recipient_id
                                               AND messages.sent_on > %(startdate)s
                                               AND sender.id LIKE %(user_id)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_topics(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, commands.string
                                               FROM commands, messages, recipients, users as sender, users as recipient
                                               WHERE commands.command_name = 'topic'
                                               AND commands.sender_id = sender.id
                                               AND commands.id = messages.parent_command_id
                                               AND messages.id = recipients.message_id
                                               AND recipient.id = recipients.recipient_id
                                               AND sender.id != recipients.recipient_id
                                               AND commands.string IS NOT NULL
                                               AND commands.sent_on > %(startdate)s
                                               AND sender.id LIKE %(user_id)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_whispers(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, messages.body
                                               FROM commands, messages, recipients, users as sender, users as recipient
                                               WHERE commands.command_name = 'whisper'
                                               AND messages.id = recipients.message_id
                                               AND messages.sender_id IS NOT NULL
                                               AND sender.id = messages.sender_id
                                               AND recipient.id = recipients.recipient_id
                                               AND commands.id = messages.parent_command_id
                                               AND commands.sent_on > %(startdate)s
                                               AND sender.id LIKE %(user_id)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_invites(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, commands.token, messages.body
                                               FROM commands, messages, recipients, users as sender
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
                                               AND messages.id = recipients.message_id
                                               AND recipients.recipient_id = sender.id
                                               AND commands.sent_on > %(startdate)s
                                               AND sender.id LIKE %(user_id)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_kicks(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, commands.token, messages.body
                                               FROM commands, messages, recipients, users as sender
                                               WHERE commands.sender_id IS NOT NULL
                                               AND sender.id = commands.sender_id
                                               AND commands.sent_on > %(startdate)s
                                               AND commands.is_valid IS TRUE
                                               AND commands.command_name = 'kick'
                                               AND messages.sender_id IS NULL
                                               AND messages.parent_message_id IS NULL
                                               AND messages.parent_command_id = commands.id
                                               AND messages.body NOT LIKE 'Sorry, %%'
                                               AND messages.id = recipients.message_id
                                               AND recipients.recipient_id = sender.id
                                               AND sender.id LIKE %(user_id)s
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_blocks(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name
                                               FROM blocks, users as from_user, users as to_user
                                               WHERE to_user.id = blocks.to_user_id
                                               AND from_user.id = blocks.from_user_id
                                               AND from_user.id LIKE %(user_id)s
                                               ORDER BY blocks.created DESC
                                               LIMIT %(pagesize)s
                                               OFFSET %(offset)s
                                            """, {
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_next_old_edge(self):
        # This let's us cycle through the current edges one at a time, to figure out which we need to delete.
        old_edge = self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name
                                                   FROM edges, users as from_user, users as to_user
                                                   WHERE to_user.id = edges.to_id
                                                   AND from_user.id = edges.from_id
                                                   AND from_user.id LIKE %(user_id)s
                                                   ORDER BY edges.id DESC
                                                   LIMIT 1
                                                   OFFSET %(old_edge_offset)s
                                                """, {
                                                   'user_id': self.user_id if self.user_id else '%',
                                                   'old_edge_offset': self.old_edge_offset
                                                })
        self.old_edge_offset += 1
        return old_edge
    
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
        #self.logger.info(query % data)
        if not self.db or not self.cursor:
            self.logger.info("Database connection missing, attempting to reconnect and retry query")
            if self.db:
                self.db.close()
            self.db_connect()
        try:
            self.cursor.execute(query, data)
        except MySQLdb.OperationalError, e:
            self.logger.info('Database OperationalError %s for query, will retry: %s' % (e, query % data))
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
            self.logger.info("Database connection created")
        except MySQLdb.Error, e:
            self.logger.error('Database connection and/or cursor creation failed with %d: %s' % (e.args[0], e.args[1]))
            self.cleanup()
    
    def cleanup(self):
        if self.db:
            self.db.close()
        sys.exit(1)
    

