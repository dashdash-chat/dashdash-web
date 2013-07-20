#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, timedelta
import json
import MySQLdb
from MySQLdb import IntegrityError, OperationalError
import re
from sleekxmpp import ClientXMPP
import sys
import constants

PAGESIZE = 5000
NUM_DAYS = 365
sys.setrecursionlimit(5000)

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
        if sender != recipient and sender not in constants.protected_users and recipient not in constants.protected_users:
            # Don't update relationships for admins! It would be more efficient to not even fetch these results from the database, but also much more verbose.
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
    

class EdgeCalculator(ClientXMPP):
    def __init__(self, logger, user_id=None):
        self.logger = logger
        self.user_id = user_id
        ClientXMPP.__init__(self, constants.graph_jid, constants.graph_xmpp_password)
        self.add_event_handler("session_start", self.handle_start)
        self.add_event_handler("message", self.handle_message)
        self.old_edge_offset = 0
        self.db = None
        self.cursor = None
        self.db_connect()
        self.scores = RelationshipScores()
        self.start_time = datetime.now()
        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0004') # Data Forms
        self.register_plugin('xep_0060') # PubSub
        self.register_plugin('xep_0199') # XMPP Ping
    
    def handle_start(self, event):
        self.logger.info('Starting EdgeCalculator for user.id=%s' % self.user_id)
        self.send_presence()
        self.process_logs()
        self.process_blocks()
        self.logger.info('\n' + str(self.scores))
        self.update_next_old_edge()
    
    def process_logs(self):
        def process_log_type(db_query_fn, weight):
            self.logger.info('Processing logs from %s' % db_query_fn.__name__)
            offset = 0
            rows = True
            while rows:
                rows = db_query_fn(offset)
                offset += PAGESIZE
                for row in rows:
                    sender, recipient, score = row
                    self.scores.adjust_score(sender, recipient, score * weight if type(score) == int else weight)
        process_log_type(self.db_fetch_edges_for_new_users,     20000)
        process_log_type(self.db_fetch_artificial_follows,      10000)
        process_log_type(self.db_fetch_account_invites,         10000)
        process_log_type(self.db_fetch_multiuse_invite_signups, 1000)
        process_log_type(self.db_fetch_twitter_follows,         300)
        process_log_type(self.db_fetch_messages,                1)
        process_log_type(self.db_fetch_topics,                  1)
        process_log_type(self.db_fetch_whispers,                2)
        process_log_type(self.db_fetch_invites,                 100)
        process_log_type(self.db_fetch_kicks,                   -100)
    
    def process_blocks(self):
        self.logger.info('Processing blocks')
        offset = 0
        blocks = True
        while blocks:
            blocks = self.db_fetch_blocks(offset)
            offset += PAGESIZE
            for block in blocks:
                sender, recipient = block
                self.scores.delete_score(sender, recipient)
                self.scores.delete_score(recipient, sender)
    
    def update_next_old_edge(self):
        old_edge = self.db_fetch_next_old_edge()
        if old_edge:
            sender, recipient = old_edge[0]
            self.logger.info('In update_next_old_edge for %s, %s' % (sender, recipient))
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
            self.logger.info('In update_next_new_edge for %s, %s' % (sender, recipient))
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
    
    def handle_message(self, msg):
        # *** %s and %s now have a directed edge between them.
        # *** Sorry, %s and %s already have a directed edge between them.
        # *** Sorry, %s and %s do not have a directed edge between them.
        # *** %s and %s no longer have a directed edge between them.
        m = re.match(r'\/\*\* (?P<sorry>Sorry\, )?(?P<sender>\w+) and (?P<recipient>\w+) (?P<result>.*)\.', msg['body'])
        if m:
            sorry     = m.groupdict()['sorry']
            sender    = m.groupdict()['sender']
            recipient = m.groupdict()['recipient']
            result    = m.groupdict()['result']
            if result in ['no longer have a directed edge between them', 'do not have a directed edge between them']:
                if sorry:
                    self.logger.debug('Tried to delete edge for %s and %s, but it didn\'t exist.' % (sender, recipient))
                self.update_next_old_edge()
                return
            elif result in ['now have a directed edge between them', 'already have a directed edge between them']:
                if sorry:
                    self.logger.debug('Tried to create edge for %s and %s, but it already existed.' % (sender, recipient))
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
        self.logger.debug("SENT %s" % body)
    
    def db_fetch_edges_for_new_users(self, offset):
        # Fetch edges for the user(s) that haven't sent a message to a group conversation
        usernames = self.db_execute_and_fetchall("""SELECT users.name
                                                    FROM users
                                                    WHERE (SELECT COUNT(*)
                                                           FROM messages
                                                           WHERE messages.sender_id = users.id
                                                           AND (SELECT COUNT(*)
                                                                FROM recipients
                                                                WHERE messages.id = recipients.message_id
                                                               ) >= 2
                                                          ) = 0
                                                    AND users.id LIKE %(user_id)s
                                                    GROUP BY users.name
                                                    ORDER BY users.created DESC
                                                    LIMIT %(offset)s, %(pagesize)s
                                                 """, {
                                                    'user_id': self.user_id if self.user_id else '%',
                                                    'pagesize': PAGESIZE,
                                                    'offset': offset
                                                 }, strip_pairs=True)
        return [(constants.helpbot_jid_user, username, None) for username in usernames] + \
               [(username, constants.helpbot_jid_user, None) for username in usernames]
    
    def db_fetch_artificial_follows(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name, NULL
                                               FROM artificial_follows, users AS from_user, users AS to_user
                                               WHERE to_user.id = artificial_follows.to_user_id
                                               AND from_user.id = artificial_follows.from_user_id
                                               AND (from_user.id LIKE %(user_id)s OR to_user.id LIKE %(user_id)s)
                                               ORDER BY artificial_follows.created DESC
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_account_invites(self, offset):
        return self.db_execute_and_fetchall("""SELECT first_user.name, second_user.name, NULL
                                               FROM invitees, invites, users AS first_user, users AS second_user
                                               WHERE invites.id = invitees.invite_id
                                               AND ((first_user.id = invites.sender AND second_user.id = invitees.invitee_id)
                                                OR (second_user.id = invites.sender AND first_user.id = invitees.invitee_id))
                                               AND (invitees.invitee_id LIKE %(user_id)s OR invites.sender LIKE %(user_id)s)
                                               AND invitees.used > %(startdate)s
                                               ORDER BY invites.created DESC
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_multiuse_invite_signups(self, offset):
        return self.db_execute_and_fetchall("""SELECT first_user.name, second_user.name, NULL
                                               FROM invitees AS first_invitees, invitees AS second_invitees, invites, users AS first_user, users AS second_user
                                               WHERE first_invitees.invite_id = invites.id
                                               AND first_invitees.invite_id = second_invitees.invite_id
                                               AND first_invitees.invitee_id != second_invitees.invitee_id
                                               AND first_user.id = first_invitees.invitee_id
                                               AND second_user.id = second_invitees.invitee_id
                                               AND (first_user.id LIKE %(user_id)s OR second_user.id LIKE %(user_id)s)
                                               AND first_invitees.used > %(startdate)s
                                               AND second_invitees.used > %(startdate)s
                                               ORDER BY invites.created DESC
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_twitter_follows(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name, NULL
                                               FROM twitter_follows, users AS from_user, users AS to_user
                                               WHERE to_user.twitter_id = twitter_follows.to_twitter_id
                                               AND from_user.twitter_id = twitter_follows.from_twitter_id
                                               AND (from_user.id LIKE %(user_id)s OR to_user.id LIKE %(user_id)s)
                                               ORDER BY twitter_follows.last_updated_on DESC
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_messages(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, CHAR_LENGTH(messages.body)
                                               FROM messages
                                               INNER JOIN recipients ON recipients.message_id = messages.id
                                               INNER JOIN users sender ON sender.id = messages.sender_id
                                               INNER JOIN users recipient ON recipient.id = recipients.recipient_id
                                               WHERE messages.sent_on > %(startdate)s
                                               AND (messages.sender_id LIKE %(user_id)s OR recipients.recipient_id LIKE %(user_id)s)
                                               AND messages.sender_id IS NOT NULL
                                               AND messages.parent_command_id IS NULL
                                               ORDER BY messages.sent_on
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_topics(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, CHAR_LENGTH(commands.string)
                                               FROM commands, messages, recipients, users AS sender, users AS recipient
                                               WHERE commands.command_name = 'topic'
                                               AND commands.sender_id = sender.id
                                               AND commands.id = messages.parent_command_id
                                               AND messages.id = recipients.message_id
                                               AND recipient.id = recipients.recipient_id
                                               AND sender.id != recipients.recipient_id
                                               AND commands.string IS NOT NULL
                                               AND commands.sent_on > %(startdate)s
                                               AND (sender.id LIKE %(user_id)s OR recipient.id LIKE %(user_id)s)
                                               ORDER BY commands.sent_on
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_whispers(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, CHAR_LENGTH(messages.body)
                                               FROM commands, messages, recipients, users AS sender, users AS recipient
                                               WHERE commands.command_name = 'whisper'
                                               AND messages.id = recipients.message_id
                                               AND messages.sender_id IS NOT NULL
                                               AND sender.id = messages.sender_id
                                               AND recipient.id = recipients.recipient_id
                                               AND commands.id = messages.parent_command_id
                                               AND commands.sent_on > %(startdate)s
                                               AND (sender.id LIKE %(user_id)s OR recipient.id LIKE %(user_id)s)
                                               ORDER BY commands.sent_on
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_invites(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, commands.token, messages.body
                                               FROM commands, messages, recipients, users AS sender, users AS target
                                               WHERE commands.command_name = 'invite'
                                               AND commands.sender_id IS NOT NULL
                                               AND sender.id = commands.sender_id
                                               AND commands.sent_on > %(startdate)s
                                               AND commands.is_valid IS TRUE
                                               AND messages.sender_id IS NULL
                                               AND messages.parent_message_id IS NULL
                                               AND messages.parent_command_id = commands.id
                                               AND messages.body NOT LIKE 'Sorry, %%'
                                               #TODO fix this ugly hack, which assumes that if a response to a command begins with 'Sorry',
                                               # there was an ExecutionError, and all other responses indicate a successful command.
                                               AND messages.id = recipients.message_id
                                               AND recipients.recipient_id = sender.id
                                               AND target.name = commands.token
                                               AND (sender.id LIKE %(user_id)s OR target.id LIKE %(user_id)s)
                                               ORDER BY commands.sent_on
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_kicks(self, offset):
        return self.db_execute_and_fetchall("""SELECT sender.name, commands.token, messages.body
                                               FROM commands, messages, recipients, users AS sender, users AS target
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
                                               AND target.name = commands.token
                                               AND (sender.id LIKE %(user_id)s OR target.id LIKE %(user_id)s)
                                               ORDER BY commands.sent_on
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'startdate': self.start_time - timedelta(days=NUM_DAYS),
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_blocks(self, offset):
        return self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name
                                               FROM blocks, users AS from_user, users AS to_user
                                               WHERE to_user.id = blocks.to_user_id
                                               AND from_user.id = blocks.from_user_id
                                               AND (from_user.id LIKE %(user_id)s OR to_user.id LIKE %(user_id)s)
                                               ORDER BY blocks.created DESC
                                               LIMIT %(offset)s, %(pagesize)s
                                            """, {
                                               'user_id': self.user_id if self.user_id else '%',
                                               'pagesize': PAGESIZE,
                                               'offset': offset
                                            })
    
    def db_fetch_next_old_edge(self):
        # This let's us cycle through the current edges one at a time, to figure out which we need to delete.
        old_edge = self.db_execute_and_fetchall("""SELECT from_user.name, to_user.name
                                                   FROM edges, users AS from_user, users AS to_user
                                                   WHERE to_user.id = edges.to_id
                                                   AND from_user.id = edges.from_id
                                                   AND (from_user.id LIKE %(user_id)s OR to_user.id LIKE %(user_id)s)
                                                   ORDER BY edges.id DESC
                                                   LIMIT %(old_edge_offset)s, 1
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
    

