from functools import wraps
from typing import Union

from dino import api
from dino import environ
from dino.forms import LoginForm
from dino.server import app, socketio
from dino.config import ConfigKeys


def respond_with(gn_event_name=None):
    def factory(view_func):
        @wraps(view_func)
        def decorator(*args, **kwargs):
            status_code, data = view_func(*args, **kwargs)
            if status_code != 200:
                environ.env.logger.info('in decorator, status_code: %s, data: %s' % (status_code, str(data)))
            if data is None:
                environ.env.emit(gn_event_name, {'status_code': status_code})
            else:
                environ.env.emit(gn_event_name, {'status_code': status_code, 'data': data})
        return decorator
    return factory


@app.route('/', methods=['GET', 'POST'])
def index():
    form = LoginForm.create()
    if form.validate_on_submit():
        # temporary until we get ID from community
        environ.env.session['user_name'] = form.user_name.data
        environ.env.session['user_id'] = int(float(''.join([str(ord(x)) for x in form.user_name.data])) % 1000000)
        environ.env.session['age'] = form.age.data
        environ.env.session['gender'] = form.gender.data
        environ.env.session['membership'] = form.membership.data
        environ.env.session['fake_checked'] = form.fake_checked.data
        environ.env.session['has_webcam'] = form.has_webcam.data
        environ.env.session['image'] = form.image.data
        environ.env.session['country'] = form.country.data
        environ.env.session['city'] = form.city.data
        return environ.env.redirect(environ.env.url_for('.chat'))
    elif environ.env.request.method == 'GET':
        form.user_name.data = environ.env.session.get('user_name', '')
        form.age.data = environ.env.session.get('age', '')
        form.gender.data = environ.env.session.get('gender', '')
        form.membership.data = environ.env.session.get('membership', '')
        form.fake_checked.data = environ.env.session.get('fake_checked', '')
        form.has_webcam.data = environ.env.session.get('has_webcam', '')
        form.image.data = environ.env.session.get('image', '')
        form.country.data = environ.env.session.get('country', '')
        form.city.data = environ.env.session.get('city', '')
    return environ.env.render_template('index.html', form=form)


@app.route('/chat')
def chat():
    user_id = environ.env.session.get('user_id', '')
    user_name = environ.env.session.get('user_name', '')
    if user_id == '':
        return environ.env.redirect(environ.env.url_for('.index'))

    return environ.env.render_template(
            'chat.html', name=user_id, room=user_id, user_id=user_id, user_name=user_name,
            gender=environ.env.session.get('gender', ''),
            age=environ.env.session.get('age', ''),
            membership=environ.env.session.get('membership', ''),
            fake_checked=environ.env.session.get('fake_checked', ''),
            has_webcam=environ.env.session.get('has_webcam', ''),
            image=environ.env.session.get('image', ''),
            country=environ.env.session.get('country', ''),
            city=environ.env.session.get('city', ''),
            version=environ.env.config.get(ConfigKeys.VERSION))


@app.route('/js/<path:path>')
def send_js(path):
    return environ.env.send_from_directory('templates/js', path)


@app.route('/css/<path:path>')
def send_css(path):
    return environ.env.send_from_directory('templates/css', path)


@socketio.on('connect', namespace='/chat')
@respond_with('gn_connect')
def connect() -> (int, None):
    try:
        return api.on_connect()
    except Exception as e:
        environ.env.logger.error('connect: %s' % str(e))
        return 500, str(e)


@socketio.on('login', namespace='/chat')
@respond_with('gn_login')
def on_login(data: dict) -> (int, str):
    try:
        return api.on_login(data)
    except Exception as e:
        environ.env.logger.error('login: %s' % str(e))
        return 500, str(e)


@socketio.on('message', namespace='/chat')
@respond_with('gn_message')
def on_message(data):
    try:
        return api.on_message(data)
    except Exception as e:
        environ.env.logger.error('message: %s' % str(e))
        return 500, str(e)


@socketio.on('create', namespace='/chat')
@respond_with('gn_create')
def on_create(data):
    try:
        return api.on_create(data)
    except Exception as e:
        environ.env.logger.error('create: %s' % str(e))
        return 500, str(e)


@socketio.on('kick', namespace='/chat')
@respond_with('gn_kick')
def on_create(data):
    try:
        return api.on_kick(data)
    except Exception as e:
        environ.env.logger.error('kick: %s' % str(e))
        return 500, str(e)


@socketio.on('set_acl', namespace='/chat')
@respond_with('gn_set_acl')
def on_set_acl(data: dict) -> (int, str):
    try:
        return api.on_set_acl(data)
    except Exception as e:
        environ.env.logger.error('set_acl: %s' % str(e))
        return 500, str(e)


@socketio.on('get_acl', namespace='/chat')
@respond_with('gn_get_acl')
def on_get_acl(data: dict) -> (int, Union[str, dict]):
    try:
        return api.on_get_acl(data)
    except Exception as e:
        environ.env.logger.error('get_acl: %s' % str(e))
        return 500, str(e)


@socketio.on('status', namespace='/chat')
@respond_with('gn_status')
def on_status(data: dict) -> (int, Union[str, None]):
    try:
        return api.on_status(data)
    except Exception as e:
        environ.env.logger.error('status: %s' % str(e))
        return 500, str(e)


@socketio.on('history', namespace='/chat')
@respond_with('gn_history')
def on_history(data: dict) -> (int, Union[str, None]):
    try:
        return api.on_history(data)
    except Exception as e:
        environ.env.logger.error('history: %s' % str(e))
        return 500, str(e)


@socketio.on('join', namespace='/chat')
@respond_with('gn_join')
def on_join(data: dict) -> (int, Union[str, None]):
    try:
        return api.on_join(data)
    except Exception as e:
        environ.env.logger.error('join: %s' % str(e))
        return 500, str(e)


@socketio.on('users_in_room', namespace='/chat')
@respond_with('gn_users_in_room')
def on_users_in_room(data: dict) -> (int, Union[dict, str]):
    try:
        return api.on_users_in_room(data)
    except Exception as e:
        environ.env.logger.error('users_in_room: %s' % str(e))
        return 500, str(e)


@socketio.on('list_rooms', namespace='/chat')
@respond_with('gn_list_rooms')
def on_list_rooms(data: dict) -> (int, Union[dict, str]):
    try:
        return api.on_list_rooms(data)
    except Exception as e:
        environ.env.logger.error('list_rooms: %s' % str(e))
        return 500, str(e)


@socketio.on('leave', namespace='/chat')
@respond_with('gn_leave')
def on_leave(data: dict) -> (int, Union[str, None]):
    try:
        return api.on_leave(data)
    except Exception as e:
        environ.env.logger.error('leave: %s' % str(e))
        return 500, str(e)


@socketio.on('disconnect', namespace='/chat')
@respond_with('gn_disconnect')
def on_disconnect() -> (int, None):
    try:
        return api.on_disconnect()
    except Exception as e:
        environ.env.logger.error('disconnect: %s' % str(e))
        return 500, str(e)
