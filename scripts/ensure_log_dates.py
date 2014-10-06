# -*- coding: utf-8 -*-

import datetime
import logging
import sys

from modularodm import Q

from website.models import NodeLog

from bson import ObjectId
from nose.tools import *

from tests.base import OsfTestCase
from tests.factories import NodeLogFactory


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def find_invalid_logs():
    for log in NodeLog.find(Q('action', 'eq', NodeLog.WIKI_DELETED)):
        # Derive UTC datetime object from ObjectId
        id_date = ObjectId(log._id).generation_time
        id_date = id_date.replace(tzinfo=None) - id_date.utcoffset()

        if id_date > log.date:
            yield log


def fix_invalid_log(log):
    new_dt = ObjectId(log._id).generation_time
    new_dt = new_dt.replace(tzinfo=None) - new_dt.utcoffset()
    NodeLog._fields['date'].__set__(
        log,
        new_dt,
        safe=False
    )
    log.save()


if __name__ == '__main__':
    if 'dry' in sys.argv:
        for log in find_invalid_logs():
            print(log._id)
    else:
        for log in find_invalid_logs():
            fix_invalid_log(log)


class TestEnsureLogDates(OsfTestCase):

    def setUp(self):
        super(TestEnsureLogDates, self).setUp()
        self.good_log = NodeLogFactory(action=NodeLog.WIKI_DELETED)
        self.bad_log = NodeLogFactory(action=NodeLog.WIKI_DELETED)

        self.mongo = self.good_log._storage[0].db['nodelog']

        self.mongo.update(
            {'_id': self.bad_log._id},
            {'$set': {'date': datetime.datetime.utcnow() - datetime.timedelta(weeks=52)}},
        )
        self.bad_log.reload()

    def tearDown(self):
        super(TestEnsureLogDates, self).tearDown()

    def test_find_invalid_logs(self):
        assert_equal(
            1,
            len(list(find_invalid_logs()))
        )

    def test_fix_invalid_log(self):
        fix_invalid_log(self.bad_log)
        assert_true(
            self.good_log.date - self.bad_log.date < datetime.timedelta(seconds=1)
        )


