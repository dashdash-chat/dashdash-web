#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from optparse import OptionParser
from collections import defaultdict
import constants

THRESHOLD = 0
PAGESIZE = 20

class Recipients(object):
    def __init__(self):
        self._recipients = defaultdict(int)
        
    def increment(self, recipient):
        self._recipients[recipient] += 1
        
    def has_edge(self, recipient, message_threshold):
        return self._recipients[recipient] > message_threshold


class Senders(object):
    def __init__(self):
        self._senders = defaultdict(Recipients)

    def increment(self, sender, recipient):
        self._senders[sender].increment(recipient)
        
    def has_edge(self, sender, recipient, message_threshold=THRESHOLD):
        self._senders[sender].has_edge(recipient, message_threshold)


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
                        format='%%(asctime)-15s leaf%(leaf_id)-3s %%(levelname)-8s %%(message)s' % {'leaf_id': opts.leaf_id})

    #TODO put in functions for garbage collection
    logging.info('starting')
    senders = Senders()
    messages = # select messages from database from last three months, going PAGESIZE at a time
    for message in messages:
        recipients = # select recipients for a given message
        for recipient in recipients:
            senders.increment(message.sender, recipients)
            
    old_edges = # select all edges from database
    new_edges = []
    for old_edge in old_edges:
        if senders.has_edge(old_edge.frm, old_edge.to):
            senders.delete_edge(old_edge.frm, old_edge.to)
        else:
            # delete edge from database, kill idle vinebots
    for remaining edges in senders:
        # create edge in database, create vinebots
    
    logging.info("Done")

