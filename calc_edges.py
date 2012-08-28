#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import logging
from optparse import OptionParser
from collections import defaultdict
import constants
import MySQLdb
from MySQLdb import IntegrityError, OperationalError
import sleekxmpp

THRESHOLD = 0
PAGESIZE = 20

class Recipients(object):
    def __init__(self):
        self._recipients = defaultdict(int)
        
    def increment(self, recipient):
        self._recipients[recipient] += 1
        
    def has_edge(self, recipient, message_threshold):
        return self._recipients[recipient] > message_threshold
    
    def delete_edge(self, recipient):
        if recipient in self._recipients:
            del self._recipients[recipient]


class Senders(object):
    def __init__(self):
        self._senders = defaultdict(Recipients)

    def increment(self, sender, recipient):
        self._senders[sender].increment(recipient)
        
    def has_edge(self, sender, recipient, message_threshold=THRESHOLD):
        return self._senders[sender].has_edge(recipient, message_threshold)
    
    def delete_edge(self, sender, recipient):
        if sender in self._senders:
               self._senders[sender].delete_edge(recipient)
        

class EdgeCalculator(sleekxmpp.ClientXMPP):
    def __init__(self):
        sleekxmpp.ClientXMPP.__init__(self, '%s@%s' % (constants.graph_xmpp_user, constants.server), constants.graph_xmpp_password)
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("message", self.message)
        self.db = None
        self.cursor = None
        self.senders = None
        self.db_connect()
        self.old_edge_offset = 0
        self.in_delete_phase = True

    def start(self, event):
        self.process_logs()
        self.update_next_old_edge()
        
    # override disconnect to make sure we finished and log errors if not
    # think through failure cases

    def process_logs(self):
        self.senders = Senders()
        offset = 0
        logs = True
        while logs:
            logging.info('next')
            logs = self.db_fetch_logs(offset)
            offset += PAGESIZE
            for log in logs:
                logging.info(log)
                self.senders.increment(log[0], log[1])
    
    def update_next_old_edge(self):
        pass
        # old_edge = # fetch next edge with offset = self.old_edge_offset, limit = 1
        # if old_edge:
        #     if self.senders.has_edge(old_edge.frm, old_edge.to):
        #         self.senders.delete_edge(old_edge.frm, old_edge.to)
        #         self.update_next_old_edge()
        #     else:
        #         self.send_message_to_leaf('/del_friendship %s %s' % (user1, user2))
        # else:
        #     self.in_delete_phase = False
        #     self.update_next_new_edge()
    
    def update_next_new_edge(self):
        new_edge = []# pop one from  self.senders:
        if new_edge:
            self.send_message_to_leaf('/new_friendship %s %s' % (user1, user2))
    
    def message(self, msg):
        logging.info(msg)
        if True: #got success response and if from leaf use
            # use Your /new_friendship command was successful. and Your /del_friendship command was successful.
            # put usernames in response
            if self.in_delete_phase:
                # delete edge from database
                self.update_next_old_edge()
                
            else: # was /new_friendship command:
                # create edge in the database
                self.update_next_new_edge()
            
    def send_message_to_leaf(self, body):
        msg = self.Message()
        msg['to'] = 'leaf1.dev.vine.im'
        msg['body'] = body
        msg.send()
    
    def db_fetch_logs(self, offset):
        messages = self.db_execute_and_fetchall("""SELECT sender.name, recipient.name, logs.body
                                                   FROM logs, log_recipients, users AS sender, users AS recipient
                                                   WHERE logs.id = log_recipients.log_id
                                                   AND sender.id = logs.author_id
                                                   AND recipient.id = log_recipients.recipient_id
                                                   AND logs.sent_on > %(startdate)s
                                                   LIMIT %(pagesize)s
                                                   OFFSET %(offset)s""",
                                                   {'startdate': 0, 'pagesize': PAGESIZE, 'offset': offset})
        whispers = self.db_execute_and_fetchall("""SELECT logs.id, sender.name, recipient.name, logs.body
                                                   FROM logs, log_recipients, users AS sender, users AS recipient
                                                   WHERE logs.id = log_recipients.log_id
                                                   AND sender.id = logs.author_id
                                                   AND recipient.id = log_recipients.recipient_id
                                                   AND logs.sent_on > %(startdate)s
                                                   LIMIT %(pagesize)s
                                                   OFFSET %(offset)s """,
                                                   {'startdate': 0, 'pagesize': PAGESIZE, 'offset': offset})
        # topics = self.db_execute_and_fetchall("""  SELECT logs.id, sender.name, recipient.name, logs.body
        #                                            FROM logs, log_recipients, users AS sender, users AS recipient
        #                                            WHERE logs.id = log_recipients.log_id
        #                                            AND sender.id = logs.author_id
        #                                            AND recipient.id = log_recipients.recipient_id
        #                                            AND logs.sent_on > %(startdate)s
        #                                            LIMIT %(pagesize)s;
        #                                            OFFSET %(offset)s """,
        #                                            {'startdate': 0, 'pagesize': PAGESIZE, 'offset': offset})
        return messages + whispers# + topics
        
    
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
