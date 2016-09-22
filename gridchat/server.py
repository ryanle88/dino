from flask import redirect, url_for, request, render_template, session, Flask
from flask_socketio import emit, SocketIO
from functools import wraps
from typing import Union

from gridchat.forms import LoginForm
from gridchat import api
from gridchat.env import env, ConfigKeys

__author__ = 'Oscar Eriksson <oscar@thenetcircle.com>'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!fdsa'
socketio = SocketIO(app, logger=env.config.get(ConfigKeys.LOGGER),
                    message_queue='redis://%s' % env.config.get(ConfigKeys.REDIS_HOST))

env.config[ConfigKeys.SESSION] = session


def respond_with(gn_event_name=None):
    def factory(view_func):
        @wraps(view_func)
        def decorator(*args, **kwargs):
            status_code, data = view_func(*args, **kwargs)
            if data is None:
                emit(gn_event_name, {'status_code': status_code})
            else:
                emit(gn_event_name, {'status_code': status_code, 'data': data})
        return decorator
    return factory


@app.route('/', methods=['GET', 'POST'])
def index():
    form = LoginForm()
    if form.validate_on_submit():
        # temporary until we get ID from community
        session['user_name'] = form.user_id.data
        session['user_id'] = int(float(''.join([str(ord(x)) for x in form.user_id.data])) % 1000000)
        return redirect(url_for('.chat'))
    elif request.method == 'GET':
        form.user_id.data = session.get('user_id', '')
    return render_template('index.html', form=form)


@app.route('/chat')
def chat():
    user_id = session.get('user_id', '')
    user_name = session.get('user_name', '')
    if user_id == '':
        return redirect(url_for('.index'))

    return render_template(
            'chat.html', name=user_id, room=user_id, user_id=user_id, user_name=user_name,
            version=env.config.get(ConfigKeys.VERSION))


@socketio.on('connect', namespace='/chat')
@respond_with('gn_connect')
def connect() -> (int, None):
    """
    connect to the server

    :return: json if ok, {'status_code': 200}
    """
    return 200, None


@socketio.on('user_info', namespace='/chat')
@respond_with('gn_user_info')
def user_connection(data: dict) -> (int, str):
    return api.user_connection(data)


@socketio.on('message', namespace='/chat')
@respond_with('gn_message')
def on_message(data):
    return api.on_message(data)


@socketio.on('set_acl', namespace='/chat')
@respond_with('gn_set_acl')
def on_set_acl(data: dict) -> (int, str):
    return api.on_set_acl(data)


@socketio.on('get_acl', namespace='/chat')
@respond_with('gn_get_acl')
def on_get_acl(data: dict) -> (int, Union[str, dict]):
    return api.on_get_acl(data)


@socketio.on('status', namespace='/chat')
@respond_with('gn_status')
def on_status(data: dict) -> (int, Union[str, None]):
    return api.on_status(data)


@socketio.on('join', namespace='/chat')
@respond_with('gn_join')
def on_join(data: dict) -> (int, Union[str, None]):
    return api.on_join(data)


@socketio.on('users_in_room', namespace='/chat')
@respond_with('gn_users_in_room')
def on_users_in_room(data: dict) -> (int, Union[dict, str]):
    return api.on_users_in_room(data)


@socketio.on('list_rooms', namespace='/chat')
@respond_with('gn_list_rooms')
def on_list_rooms(data: dict) -> (int, Union[dict, str]):
    return api.on_list_rooms(data)


@socketio.on('leave', namespace='/chat')
@respond_with('gn_leave')
def on_leave(data: dict) -> (int, Union[str, None]):
    return api.on_leave(data)


@socketio.on('disconnect', namespace='/chat')
@respond_with('gn_disconnect')
def on_disconnect() -> (int, None):
    return api.on_disconnect()
