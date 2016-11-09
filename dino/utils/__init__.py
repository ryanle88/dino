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

from activitystreams import Activity
from typing import Union
import logging

from dino.config import SessionKeys
from dino.config import ConfigKeys
from dino import environ
from dino.validation.duration import DurationValidator
from dino.validation.generic import GenericValidator
from dino import validation
from dino.config import RedisKeys
from dino.config import UserKeys
from dino.config import ApiActions
from dino.config import ApiTargets
from datetime import timedelta
from datetime import datetime

from dino.exceptions import NoOriginRoomException
from dino.exceptions import NoTargetRoomException
from dino.exceptions import NoTargetChannelException
from dino.exceptions import NoOriginChannelException
from dino.exceptions import ValidationException
from dino.exceptions import NoSuchUserException

__author__ = 'Oscar Eriksson <oscar.eriks@gmail.com>'

logger = logging.getLogger(__name__)


def activity_for_leave(user_id: str, user_name: str, room_id: str, room_name: str) -> dict:
    return {
        'actor': {
            'id': user_id,
            'summary': user_name
        },
        'target': {
            'id': room_id,
            'displayName': room_name
        },
        'verb': 'leave'
    }


def activity_for_user_joined(user_id: str, user_name: str, room_id: str, room_name: str, image_url: str) -> dict:
    return {
        'actor': {
            'id': environ.env.db.get_private_room(user_id)[0],
            'summary': user_name,
            'image': {
                'url': image_url
            }
        },
        'target': {
            'id': room_id,
            'displayName': room_name,
            'objectType': 'group'
        },
        'verb': 'join'
    }


def activity_for_user_kicked(
        kicker_id: str, kicker_name: str, kicked_id: str, kicked_name: str, room_id: str, room_name: str) -> dict:
    return {
        'actor': {
            'id': kicker_id,
            'summary': kicker_name
        },
        'object': {
            'id': kicked_id,
            'summary': kicked_name
        },
        'target': {
            'id': room_id,
            'displayName': room_name,
            'objectType': 'group'
        },
        'verb': 'kick'
    }


def activity_for_disconnect(user_id: str, user_name: str) -> dict:
    return {
        'actor': {
            'id': user_id,
            'summary': user_name
        },
        'verb': 'disconnect'
    }


def activity_for_connect(user_id: str, user_name: str) -> dict:
    return {
        'actor': {
            'id': user_id,
            'summary': user_name
        },
        'verb': 'connect'
    }


def activity_for_create_room(activity: Activity) -> dict:
    return {
        'actor': {
            'id': activity.actor.id,
            'content': activity.actor.content
        },
        'object': {
            'id': activity.object.id,
            'content': activity.object.content,
            'url': activity.object.url
        },
        'target': {
            'id': activity.target.id,
            'displayName': activity.target.display_name
        },
        'verb': 'create'
    }


def activity_for_history(activity: Activity, messages: list) -> dict:
    response = {
        'object': {
            'objectType': 'messages'
        },
        'verb': 'history',
        'target': {
            'id': activity.target.id,
            'displayName': get_room_name(activity.target.id)
        }
    }

    response['object']['attachments'] = list()
    for msg_id, timestamp, user_name, msg in messages:
        response['object']['attachments'].append({
            'id': msg_id,
            'content': msg,
            'summary': user_name,
            'published': timestamp
        })

    return response


def activity_for_join(activity: Activity, acls: dict, messages: list, owners: dict, users: dict) -> dict:
    response = {
        'object': {
            'objectType': 'room',
            'attachments': list()
        },
        'verb': 'join',
        'target': {
            'id': activity.target.id,
            'displayName': get_room_name(activity.target.id)
        }
    }

    acl_activity = activity_for_get_acl(activity, acls)
    response['object']['attachments'].append({
        'objectType': 'acl',
        'attachments': acl_activity['object']['attachments']
    })

    history_activity = activity_for_history(activity, messages)
    response['object']['attachments'].append({
        'objectType': 'history',
        'attachments': history_activity['object']['attachments']
    })

    owners_activity = activity_for_owners(activity, owners)
    response['object']['attachments'].append({
        'objectType': 'owner',
        'attachments': owners_activity['object']['attachments']
    })

    users_in_room_activity = activity_for_users_in_room(activity, users)
    response['object']['attachments'].append({
        'objectType': 'user',
        'attachments': users_in_room_activity['object']['attachments']
    })

    return response


def activity_for_owners(activity: Activity, owners: dict) -> dict:
    response = {
        'object': {
            'objectType': 'owner'
        },
        'target': {
            'id': activity.target.id,
            'displayName': activity.target.display_name
        },
        'verb': 'list'
    }

    response['object']['attachments'] = list()
    for user_id, user_name in owners.items():
        response['object']['attachments'].append({
            'id': user_id,
            'content': user_name
        })

    return response


def activity_for_list_channels(activity: Activity, channels: dict) -> dict:
    response = {
        'object': {
            'objectType': 'channels'
        },
        'verb': 'list'
    }

    response['object']['attachments'] = list()
    for channel_id, channel_name in channels.items():
        response['object']['attachments'].append({
            'id': channel_id,
            'content': channel_name
        })

    return response


def activity_for_invite(
        inviter_id: str, inviter_name: str, room_id: str, room_name: str,
        channel_id: str, channel_name: str) -> dict:
    return {
        'actor': {
            'id': inviter_id,
            'summary': inviter_name
        },
        'verb': 'invite',
        'object': {
            'url': channel_id,
            'summary': channel_name
        },
        'target': {
            'id': room_id,
            'displayName': room_name
        }
    }


def activity_for_list_rooms(activity: Activity, rooms: dict) -> dict:
    response = {
        'object': {
            'id': activity.object.id,
            'objectType': 'rooms'
        },
        'verb': 'list'
    }

    response['object']['attachments'] = list()
    for room_id, room_name in rooms.items():
        response['object']['attachments'].append({
            'id': room_id,
            'content': room_name
        })

    return response


def activity_for_users_in_room(activity: Activity, users: dict) -> dict:
    response = {
        'target': {
            'id': activity.target.id,
            'displayName': activity.target.display_name
        },
        'object': {
            'objectType': 'users'
        },
        'verb': 'list'
    }

    response['object']['attachments'] = list()
    for user_id, user_name in users.items():
        response['object']['attachments'].append({
            'id': user_id,
            'content': user_name
        })

    return response


def activity_for_get_acl(activity: Activity, acl_values: dict) -> dict:
    response = {
        'target': {
            'id': activity.target.id
        },
        'object': {
            'objectType': 'acl'
        },
        'verb': 'get'
    }

    response['object']['attachments'] = list()
    for api_action, acls in acl_values.items():
        for acl_type, acl_value in acls.items():
            response['object']['attachments'].append({
                'objectType': acl_type,
                'content': acl_value,
                'summary': api_action
            })

    return response


def is_user_in_room(user_id, room_id):
    if room_id is None or len(room_id.strip()) == 0:
        return False
    return environ.env.db.room_contains(room_id, user_id)


# TODO: use env.db instead of env.redis
def set_sid_for_user_id(user_id: str, sid: str) -> None:
    environ.env.redis.hset(RedisKeys.sid_for_user_id(), user_id, sid)


def set_name_for_user_id(user_id: str, user_name: str) -> None:
    environ.env.db.set_user_name(user_id, user_name)


# TODO: use env.db instead of env.redis
def get_sid_for_user_id(user_id: str) -> str:
    return environ.env.redis.hmget(RedisKeys.sid_for_user_id(), user_id)


def is_banned_globally(user_id: str) -> (bool, Union[str, None]):
    user_is_banned, timestamp = environ.env.db.is_banned_globally(user_id)
    if not user_is_banned or timestamp is None or timestamp == '':
        return False, None

    now = datetime.utcnow()
    end = datetime.strptime(timestamp, ConfigKeys.DEFAULT_DATE_FORMAT)
    diff = (end - now)
    if diff.seconds < 0:
        logger.error(
                'is_banned_globally(): time left for ban "%s" is negative for user_id "%s"' %
                (str(diff.seconds), user_id))


def is_banned(user_id: str, room_id: str) -> (bool, Union[str, None]):
    bans = environ.env.db.get_user_ban_status(room_id, user_id)

    global_time = bans['global']
    channel_time = bans['channel']
    room_time = bans['room']
    now = datetime.utcnow()

    if global_time != '':
        end = datetime.fromtimestamp(int(global_time))
        return True, 'banned globally for another "%s" seconds"' % str((end - now).seconds)

    if channel_time != '':
        end = datetime.fromtimestamp(int(channel_time))
        return True, 'banned from channel for another "%s" seconds"' % str((end - now).seconds)

    if room_time != '':
        end = datetime.fromtimestamp(int(room_time))
        return True, 'banned from room for another "%s" seconds"' % str((end - now).seconds)

    return False, None


def kick_user(room_id: str, user_id: str) -> None:
    environ.env.db.kick_user(room_id, user_id)


def ban_user(room_id: str, private_room_id: str, ban_duration: str) -> None:
    user_id = environ.env.db.get_user_for_private_room(private_room_id)
    if user_id is None:
        raise NoSuchUserException(private_room_id)
    ban_timestamp = ban_duration_to_timestamp(ban_duration)
    environ.env.db.ban_user_room(user_id, ban_timestamp, ban_duration, room_id)


# TODO: not used since new acls implemented, maybe use in the future?
def get_current_user_role() -> str:
    # if is_admin(environ.env.config.get(SessionKeys.USER_ID)):
    #     return 'admin'
    return 'user'


def ban_duration_to_timestamp(ban_duration: str) -> str:
    DurationValidator(ban_duration)

    days = 0
    hours = 0
    seconds = 0
    duration_unit = ban_duration[-1]
    ban_duration = ban_duration[:-1]

    try:
        if duration_unit == 'd' and GenericValidator.is_digit(ban_duration):
            days = int(ban_duration)
        elif duration_unit == 'h' and GenericValidator.is_digit(ban_duration):
            hours = int(ban_duration)
        elif duration_unit == 'm' and GenericValidator.is_digit(ban_duration):
            seconds = int(ban_duration) * 60
        elif duration_unit == 's' and GenericValidator.is_digit(ban_duration):
            seconds = int(ban_duration)
        else:
            raise ValidationException(
                'unknown ban duration: %s, allowed units are: %s' %
                (ban_duration, DurationValidator.durations_help))
    except ValueError as e:
        environ.env.logger.error('could not convert ban duration "%s" to int: %s' % (ban_duration, str(e)))
        raise ValidationException('invalid ban duration, not a number: %s' % ban_duration)

    if days < 0 or hours < 0 or seconds < 0:
        raise ValidationException('need positive ban duration, got: %sd, %sh %ss' % (str(days), str(hours), str(seconds)))

    now = datetime.utcnow()
    ban_time = timedelta(days=days, hours=hours, seconds=seconds)
    end_date = now + ban_time

    return str(int(end_date.timestamp()))


def is_super_user(user_id: str) -> bool:
    return environ.env.db.is_super_user(user_id)


def is_owner(room_id: str, user_id: str) -> bool:
    return environ.env.db.is_owner(room_id, user_id)


def is_owner_channel(channel_id: str, user_id: str) -> bool:
    return environ.env.db.is_owner_channel(channel_id, user_id)


def is_moderator(room_id: str, user_id: str) -> bool:
    return environ.env.db.is_moderator(room_id, user_id)


def is_admin(channel_id: str, user_id: str) -> bool:
    return environ.env.db.is_admin(channel_id, user_id)


def get_users_in_room(room_id: str) -> dict:
    return environ.env.db.users_in_room(room_id)


def get_acls_in_room_for_action(room_id: str, action: str) -> dict:
    return environ.env.db.get_acls_in_room_for_action(room_id, action)


def get_acls_in_channel_for_action(channel_id: str, action: str) -> dict:
    return environ.env.db.get_acls_in_channel_for_action(channel_id, action)


def get_acls_for_room(room_id: str) -> dict:
    return environ.env.db.get_all_acls_room(room_id)


def get_acls_for_channel(channel_id: str) -> dict:
    return environ.env.db.get_all_acls_channel(channel_id)


def get_owners_for_room(room_id: str) -> dict:
    return environ.env.db.get_owners_room(room_id)


def channel_exists(channel_id: str) -> bool:
    return environ.env.db.channel_exists(channel_id)


def get_user_name_for(user_id: str) -> str:
    return environ.env.config.get(SessionKeys.user_name.value)


def get_channel_name(channel_id: str) -> str:
    return environ.env.db.get_channel_name(channel_id)


def get_room_name(room_id: str) -> str:
    return environ.env.db.get_room_name(room_id)


def room_exists(channel_id: str, room_id: str) -> bool:
    return environ.env.db.room_exists(channel_id, room_id)


def can_send_cross_room(activity: Activity, from_room_uuid: str, to_room_uuid: str) -> bool:
    if from_room_uuid is None:
        raise NoOriginRoomException()
    if to_room_uuid is None:
        raise NoTargetRoomException()

    if not hasattr(activity, 'provider') or activity.provider is None or not hasattr(activity.provider, 'url'):
        raise NoOriginChannelException()
    if activity.provider.url is None or len(activity.provider.url.strip()) == 0:
        raise NoOriginChannelException()

    if not hasattr(activity, 'object') or activity.object is None or not hasattr(activity.object, 'url'):
        raise NoTargetChannelException()
    if activity.object.url is None or len(activity.object.url.strip()) == 0:
        raise NoTargetChannelException()

    if from_room_uuid == to_room_uuid:
        return True

    from_channel_id = activity.object.url
    to_channel_id = activity.provider.url

    # can not sent between channels
    if from_channel_id != to_channel_id:
        return False

    channel_acls = get_acls_in_channel_for_action(to_channel_id, ApiActions.CROSSROOM)
    is_valid, msg = validation.acl.validate_acl_for_action(
        activity, ApiTargets.CHANNEL, ApiActions.CROSSROOM, channel_acls or dict())
    if not is_valid:
        logger.debug('not allowed to send crossroom in channel: %s' % msg)
        return False

    room_acls = get_acls_in_room_for_action(to_room_uuid, ApiActions.CROSSROOM)
    is_valid, msg = validation.acl.validate_acl_for_action(
        activity, ApiTargets.ROOM, ApiActions.CROSSROOM, room_acls or dict())
    if not is_valid:
        logger.debug('not allowed to send crossroom in room: %s' % msg)
        return False

    return is_valid


def get_channel_for_room(room_id: str) -> str:
    return environ.env.db.channel_for_room(room_id)


def is_room_private(room_id: str) -> bool:
    return environ.env.db.is_room_private(room_id)


def user_is_allowed_to_delete_message(room_id: str, user_id: str) -> bool:
    channel_id = get_channel_for_room(room_id)
    if is_owner(room_id, user_id):
        return True
    if is_moderator(room_id, user_id):
        return True
    if is_owner_channel(channel_id, user_id):
        return True
    if is_admin(channel_id, user_id):
        return True
    if is_super_user(user_id):
        return True

    return False


def get_history_for_room(room_id: str, user_id: str, last_read: str = None) -> list:
    history = environ.env.config.get(
            ConfigKeys.TYPE,
            domain=ConfigKeys.HISTORY,
            default=ConfigKeys.DEFAULT_HISTORY_STRATEGY)

    limit = environ.env.config.get(
            ConfigKeys.LIMIT,
            domain=ConfigKeys.HISTORY,
            default=ConfigKeys.DEFAULT_HISTORY_LIMIT)

    if history == 'top':
        return environ.env.storage.get_history(room_id, limit)

    if last_read is None:
        last_read = get_last_read_for(room_id, user_id)
        if last_read is None:
            return list()

    return environ.env.storage.get_unread_history(room_id, last_read)


def remove_user_from_room(user_id: str, user_name: str, room_id: str) -> None:
    environ.env.leave_room(room_id)
    environ.env.db.leave_room(user_id, room_id)


def join_private_room(user_id: str, user_name: str, room_id: str) -> None:
    environ.env.db.join_private_room(user_id, user_name, room_id)
    environ.env.join_room(room_id)


def join_the_room(user_id: str, user_name: str, room_id: str, room_name: str) -> None:
    environ.env.db.join_room(user_id, user_name, room_id, room_name)
    environ.env.join_room(room_id)
    environ.env.logger.debug('user %s (%s) is joining %s (%s)' % (user_id, user_name, room_id, room_name))


def get_user_status(user_id: str) -> str:
    return environ.env.db.get_user_status(user_id)


def get_last_read_for(room_id: str, user_id: str) -> str:
    return environ.env.db.get_last_read_timestamp(room_id, user_id)


def update_last_reads(room_id: str) -> None:
    users_in_room = get_users_in_room(room_id)
    online_users_in_room = set()

    for user_id, _ in users_in_room.items():
        status = get_user_status(user_id)
        if status in [None, UserKeys.STATUS_UNAVAILABLE, UserKeys.STATUS_UNKNOWN]:
            continue

        online_users_in_room.add(user_id)

    time_stamp = int(datetime.utcnow().strftime('%s'))
    environ.env.db.update_last_read_for(online_users_in_room, room_id, time_stamp)
