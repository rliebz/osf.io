import logging
import httplib as http
from dateutil.parser import parse as parse_date

from modularodm.exceptions import ValidationError

from framework import (
    get_user,
    must_be_logged_in,
    request,
    redirect,
)
from framework.auth.decorators import collect_auth
from framework.exceptions import HTTPError
from framework.forms.utils import sanitize
from framework.auth import get_current_user
from framework.auth import utils as auth_utils

from website.models import ApiKey, User
from website.views import _render_nodes
from website import settings
from website.profile import utils as profile_utils
from website.util.sanitize import deep_clean

logger = logging.getLogger(__name__)


def get_public_projects(uid=None, user=None):
    user = user or User.load(uid)
    return _render_nodes([
        node
        for node in user.node__contributed
        if node.category == 'project'
        and node.is_public
        and not node.is_registration
        and not node.is_deleted
    ])


def get_public_components(uid=None, user=None):
    user = user or User.load(uid)
    return _render_nodes([
        node
        for node in user.node__contributed
        if node.category != 'project'
        and node.is_public
        and not node.is_registration
        and not node.is_deleted
    ])


def date_or_none(date):
    try:
        return parse_date(date)
    except Exception as error:
        logger.exception(error)
        return None


def _profile_view(uid=None):

    user = get_current_user()
    profile = get_user(id=uid) if uid else user

    if not (uid or user):
        return redirect('/login/?next={0}'.format(request.path))

    if profile:
        profile_user_data = profile_utils.serialize_user(profile, full=True)
        # TODO: Fix circular import
        from website.addons.badges.util import get_sorted_user_badges
        return {
            'profile': profile_user_data,
            'assertions': get_sorted_user_badges(profile),
            'badges': _get_user_created_badges(profile),
            'user': {
                'is_profile': user == profile,
                'can_edit': None,  # necessary for rendering nodes
                'permissions': [], # necessary for rendering nodes
            },
        }

    raise HTTPError(http.NOT_FOUND)


def _get_user_created_badges(user):
    addon = user.get_addon('badges')
    if addon:
        return [badge for badge in addon.badge__creator if not badge.is_system_badge]
    return []


def profile_view():
    return _profile_view()


def profile_view_id(uid):
    return _profile_view(uid)


@must_be_logged_in
def edit_profile(**kwargs):

    user = kwargs['auth'].user

    form = request.form

    response_data = {'response': 'success'}
    if form.get('name') == 'fullname' and form.get('value', '').strip():
        user.fullname = sanitize(form['value'])
        user.save()
        response_data['name'] = user.fullname
    return response_data


def get_profile_summary(user_id, formatter='long'):

    user = User.load(user_id)
    return user.get_summary(formatter)


@must_be_logged_in
def user_profile(auth, **kwargs):
    user = auth.user
    return {
        'user_id': user._id,
        'user_api_url': user.api_url,
    }

@must_be_logged_in
def user_addons(auth, **kwargs):

    user = auth.user

    out = {}

    addons_enabled = []
    addon_enabled_settings = []

    for addon in user.get_addons():

        addons_enabled.append(addon.config.short_name)

        if 'user' in addon.config.configs:
            addon_enabled_settings.append(addon.config.short_name)

    out['addon_categories'] = settings.ADDON_CATEGORIES
    out['addons_available'] = [
        addon
        for addon in settings.ADDONS_AVAILABLE
        if 'user' in addon.owners
            and not addon.short_name in settings.SYSTEM_ADDED_ADDONS['user']
    ]
    out['addons_enabled'] = addons_enabled
    out['addon_enabled_settings'] = addon_enabled_settings
    return out


@must_be_logged_in
def profile_addons(**kwargs):
    user = kwargs['auth'].user
    return {
        'user_id': user._primary_key,
    }


@must_be_logged_in
def user_choose_addons(**kwargs):
    auth = kwargs['auth']
    json_data = deep_clean(request.get_json())
    auth.user.config_addons(json_data, auth)


@must_be_logged_in
def get_keys(**kwargs):
    user = kwargs['auth'].user
    return {
        'keys': [
            {
                'key': key._id,
                'label': key.label,
            }
            for key in user.api_keys
        ]
    }


@must_be_logged_in
def create_user_key(**kwargs):

    # Generate key
    api_key = ApiKey(label=request.form['label'])
    api_key.save()

    # Append to user
    user = kwargs['auth'].user
    user.api_keys.append(api_key)
    user.save()

    # Return response
    return {
        'response': 'success',
    }


@must_be_logged_in
def revoke_user_key(**kwargs):

    # Load key
    api_key = ApiKey.load(request.form['key'])

    # Remove from user
    user = kwargs['auth'].user
    user.api_keys.remove(api_key)
    user.save()

    # Return response
    return {'response': 'success'}


@must_be_logged_in
def user_key_history(**kwargs):

    api_key = ApiKey.load(kwargs['kid'])
    return {
        'key': api_key._id,
        'label': api_key.label,
        'route': '/settings',
        'logs': [
            {
                'lid': log._id,
                'nid': log.node__logged[0]._id,
                'route': log.node__logged[0].url,
            }
            for log in api_key.nodelog__created
        ]
    }


@must_be_logged_in
def impute_names(**kwargs):
    name = request.args.get('name', '')
    return auth_utils.impute_names(name)


@must_be_logged_in
def serialize_names(**kwargs):
    user = kwargs['auth'].user
    return {
        'full': user.fullname,
        'given': user.given_name,
        'middle': user.middle_names,
        'family': user.family_name,
        'suffix': user.suffix,
    }


def get_target_user(auth, uid=None):
    target = User.load(uid) if uid else auth.user
    if target is None:
        raise HTTPError(http.NOT_FOUND)
    return target


def fmt_date_or_none(date, fmt='%Y-%m-%d'):
    if date:
        return date.strftime(fmt)
    return None


def append_editable(data, auth, uid=None):
    target = get_target_user(auth, uid)
    data['editable'] = auth.user == target


def serialize_social_addons(user):
    out = {}
    for user_settings in user.get_addons():
        config = user_settings.config
        if user_settings.public_id:
            out[config.short_name] = user_settings.public_id
    return out


@collect_auth
def serialize_social(auth, uid=None, **kwargs):
    target = get_target_user(auth, uid)
    out = target.social
    append_editable(out, auth, uid)
    if out['editable']:
        out['addons'] = serialize_social_addons(target)
    out['gravatar_url'] = auth.user.gravatar_url
    return out


def serialize_job(job):
    return {
        'institution': job.get('institution'),
        'department': job.get('department'),
        'title': job.get('title'),
        'start': fmt_date_or_none(job.get('start')),
        'end': fmt_date_or_none(job.get('end')),
    }


def serialize_school(school):
    return {
        'institution': school.get('institution'),
        'department': school.get('department'),
        'degree': school.get('degree'),
        'start': fmt_date_or_none(school.get('start')),
        'end': fmt_date_or_none(school.get('end')),
    }


def serialize_contents(field, func, auth, uid=None):
    target = get_target_user(auth, uid)
    out = {
        'contents': [
            func(content)
            for content in getattr(target, field)
        ]
    }
    append_editable(out, auth, uid)
    return out


@collect_auth
def serialize_jobs(auth, uid=None, **kwargs):
    out = serialize_contents('jobs', serialize_job, auth, uid)
    append_editable(out, auth, uid)
    return out


@collect_auth
def serialize_schools(auth, uid=None, **kwargs):
    out = serialize_contents('schools', serialize_school, auth, uid)
    append_editable(out, auth, uid)
    return out


@must_be_logged_in
def unserialize_names(**kwargs):
    user = kwargs['auth'].user
    json_data = deep_clean(request.get_json())
    user.fullname = json_data.get('full')
    user.given_name = json_data.get('given')
    user.middle_names = json_data.get('middle')
    user.family_name = json_data.get('family')
    user.suffix = json_data.get('suffix')
    user.save()


def verify_user_match(auth, **kwargs):
    uid = kwargs.get('uid')
    if uid and uid != auth.user._id:
        raise HTTPError(http.FORBIDDEN)


@must_be_logged_in
def unserialize_social(auth, **kwargs):

    verify_user_match(auth, **kwargs)

    user = auth.user
    json_data = deep_clean(request.get_json())

    user.social['personal'] = json_data.get('personal')
    user.social['orcid'] = json_data.get('orcid')
    user.social['researcherId'] = json_data.get('researcherId')
    user.social['twitter'] = json_data.get('twitter')
    user.social['github'] = json_data.get('github')
    user.social['scholar'] = json_data.get('scholar')
    user.social['linkedIn'] = json_data.get('linkedIn')

    try:
        user.save()
    except ValidationError:
        raise HTTPError(http.BAD_REQUEST)


def unserialize_job(job):
    return {
        'institution': job.get('institution'),
        'department': job.get('department'),
        'title': job.get('title'),
        'start': date_or_none(job.get('start')),
        'end': date_or_none(job.get('end')),
    }


def unserialize_school(school):
    return {
        'institution': school.get('institution'),
        'department': school.get('department'),
        'degree': school.get('degree'),
        'start': date_or_none(school.get('start')),
        'end': date_or_none(school.get('end')),
    }


def unserialize_contents(field, func, auth):
    user = auth.user
    json_data = deep_clean(request.get_json())
    setattr(
        user,
        field,
        [
            func(content)
            for content in json_data.get('contents', [])
        ]
    )
    user.save()


@must_be_logged_in
def unserialize_jobs(auth, **kwargs):
    verify_user_match(auth, **kwargs)
    unserialize_contents('jobs', unserialize_job, auth)


@must_be_logged_in
def unserialize_schools(auth, **kwargs):
    verify_user_match(auth, **kwargs)
    unserialize_contents('schools', unserialize_school, auth)
