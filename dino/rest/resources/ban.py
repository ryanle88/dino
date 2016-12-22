#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import traceback

from dino import environ
from dino.db.manager import UserManager
from dino.rest.resources.base import BaseResource
from dino.exceptions import UnknownBanTypeException
from dino.exceptions import NoSuchUserException

from flask import request

logger = logging.getLogger(__name__)

__author__ = 'Oscar Eriksson <oscar.eriks@gmail.com>'


class BanResource(BaseResource):
    def __init__(self):
        super(BanResource, self).__init__()
        self.user_manager = UserManager(environ.env)
        self.request = request

    def do_post(self):
        is_valid, msg, json = self.validate_json()
        output = dict()
        if not is_valid:
            logger.error('invalid json: %s' % msg)
            raise RuntimeError('invalid json')

        if json is None:
            raise RuntimeError('no json in request')
        if not isinstance(json, dict):
            raise RuntimeError('need a dict of user-room keys')

        for user_id, ban_info in json.items():
            target_id = ban_info['target']
            target_type = ban_info['type']
            duration = ban_info['duration']

            try:
                self.user_manager.ban_user(user_id, target_id, duration, target_type)
                output[user_id] = {
                    'status': 'OK'
                }
            except ValueError as e:
                logger.error('invalid ban duration "%s" for user %s: %s' % (duration, user_id, str(e)))
                output[user_id] = {
                    'status': 'FAIL',
                    'message': 'invalid ban duration [%s]' % duration
                }
            except NoSuchUserException as e:
                logger.error('no such user %s: %s' % (user_id, str(e)))
                output[user_id] = {
                    'status': 'FAIL',
                    'message': 'no such user'
                }
            except UnknownBanTypeException as e:
                logger.error('unknown ban type "%s" for user %s: %s' % (target_type, user_id, str(e)))
                output[user_id] = {
                    'status': 'FAIL',
                    'message': 'unknown ban type [%s]' % target_type
                }
            except Exception as e:
                logger.error('could not ban user %s: %s' % (user_id, str(e)))
                logger.error(traceback.format_exc())
                output[user_id] = {
                    'status': 'FAIL',
                    'message': str(e)
                }
        return output

    def validate_json(self):
        try:
            return True, None, self.request.get_json(silent=False)
        except Exception as e:
            logger.error('error: %s' % str(e))
            logger.exception(traceback.format_exc())
            return False, 'invalid json in request', None
