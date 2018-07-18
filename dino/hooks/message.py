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

from dino import environ
from dino import utils
from dino.config import ConfigKeys
from dino.utils.decorators import timeit

import logging
import traceback
import eventlet
import sys

__author__ = 'Oscar Eriksson <oscar.eriks@gmail.com>'

logger = logging.getLogger(__name__)


class OnMessageHooks(object):
    @staticmethod
    def do_process(arg: tuple) -> None:
        def send(_data: dict, _room: str, _json: bool=True, _broadcast: bool=True) -> None:
            environ.env.emit('message', _data, json=_json, room=_room, broadcast=_broadcast)

        @timeit(logger, 'on_message_hooks_publish_activity')
        def publish_activity() -> None:
            user_name = activity.actor.display_name
            if utils.is_base64(user_name):
                user_name = utils.b64d(user_name)

            activity_json = utils.activity_for_message(user_id, user_name)
            environ.env.publish(activity_json, external=True)

        @timeit(logger, 'on_message_hooks_broadcast')
        def broadcast():
            room_id = activity.target.id
            if utils.user_is_invisible(user_id):
                data['actor']['attachments'] = utils.get_user_info_attachments_for(user_id)

            if activity.target.object_type == 'private':
                owners = environ.env.db.get_owners_room(activity.target.id)
                if owners is None or len(owners) == 0:
                    send(data, _room=room_id)
                else:
                    for owner in owners:
                        send(data, _room=owner)
            else:
                send(data, _room=room_id)

        @timeit(logger, 'on_message_hooks_store')
        def store() -> None:
            try:
                environ.env.storage.store_message(activity)
            except Exception as e:
                logger.error('could not store message %s because: %s' % (activity.id, str(e)))
                logger.error(str(data))
                logger.exception(traceback.format_exc())
                environ.env.capture_exception(sys.exc_info())
                return

            if not environ.env.config.get(ConfigKeys.DELIVERY_GUARANTEE, False) or \
                    activity.target.object_type != 'private':
                return

            owners = environ.env.db.get_owners_room(activity.target.id)
            environ.env.storage.mark_as_read({activity.id}, activity.actor.id, activity.target.id)
            if owners is None or len(owners) == 0:
                return

            for receiver_id in owners:
                if activity.actor.id == receiver_id:
                    continue
                environ.env.storage.mark_as_unacked(activity.id, receiver_id, activity.target.id)

        data, activity = arg
        user_id = activity.actor.id
        word = utils.used_blacklisted_word(activity)

        if word is None:
            store()
            broadcast()
            publish_activity()
        else:
            blacklist_activity = utils.activity_for_blacklisted_word(activity, word)
            environ.env.publish(blacklist_activity, external=True)
            send(data, _room=user_id, _broadcast=False)

            admins_in_room = environ.env.db.get_admins_in_room(activity.target.id)
            if len(admins_in_room) > 0:
                for admin_user_id in admins_in_room:
                    send(data, _room=admin_user_id, _broadcast=False)


@environ.env.observer.on('on_message')
def _on_message_broadcast(arg: tuple) -> None:
    OnMessageHooks.do_process(arg)
