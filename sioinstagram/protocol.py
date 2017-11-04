import collections
import hmac
import hashlib
import urllib.parse
import uuid
import json
import time
import functools

from . import constants
from .exceptions import InstagramProtocolError


__all__ = (
    "Protocol",
)

HEADERS = {
    "Connection": "close",
    "Accept": "*/*",
    "Content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie2": "$Version=1",
    "Accept-Language": "en-US",
    "User-Agent": constants.USER_AGENT,
}


def encode_signature(signature):
    for key, value in signature.items():
        yield f"{key}={value}"


def generate_signature(**data):
    data_string = json.dumps(data)
    key = constants.IG_SIG_KEY.encode("utf-8")
    h = hmac.new(key, data_string.encode("utf-8"), hashlib.sha256)
    signed = f"{h.hexdigest()}.{data_string}"
    signature = dict(ig_sig_key_version=constants.SIG_KEY_VERSION,
                     signed_body=urllib.parse.quote(signed))
    return "&".join(encode_signature(signature))


def with_relogin(generator):

    @functools.wraps(generator)
    def wrapper(self, *args, **kwargs):
        response = None
        instance = generator(self, *args, **kwargs)
        while True:
            response = yield instance.send(response)
            if response.status_code != 200:
                if response.json.get("message") == "login_required":
                    self._init_state()
                    self.state["cookies"] = {}
                    yield from self.login()
                    response = None
                    instance = generator(self, *args, **kwargs)
                else:
                    raise InstagramProtocolError(response)

    return wrapper


def update_cookies(generator):

    @functools.wraps(generator)
    def wrapper(self, *args, **kwargs):
        response = None
        instance = generator(self, *args, **kwargs)
        while True:
            response = yield instance.send(response)
            if "cookies" not in self.state:
                self.state["cookies"] = {}
            self.state["cookies"].update(response.cookies)

    return wrapper


class Protocol:

    _COOKIES = ("csrftoken", "sessionid")
    Request = collections.namedtuple("Request", "method url params headers data cookies")
    Response = collections.namedtuple("Response", "cookies json status_code")

    def __init__(self, username, password, state=None):
        self.username = username
        self.password = password
        self._init_state(state)

    def _init_state(self, state=None):
        if state is None:
            self.state = {}
        else:
            self.state = state
        if "uuid" not in self.state:
            self.state["uuid"] = str(uuid.uuid4())

    def _request(self, method, url, *, params=None, data=None):
        return self.Request(method=method, url=constants.API_URL + url, params=params, headers=HEADERS,
                            data=data, cookies=self.cookies)

    @property
    def device_id(self):
        a = (self.username + self.password).encode("utf-8")
        b = (hashlib.md5(a).hexdigest() + "yoba").encode("utf-8")
        return "android-" + hashlib.md5(b).hexdigest()[:16]

    @property
    def cookies(self):
        return self.state.get("cookies", {})

    @update_cookies
    def login(self):
        response = yield self._request(
            method="post",
            url="qe/sync/",
            data=generate_signature(
                id=str(uuid.uuid4()),
                experiments=constants.LOGIN_EXPERIMENTS,
            ),
        )
        response = yield self._request(
            method="get",
            url="si/fetch_headers/",
            params=dict(
                challenge_type="signup",
                guid=str(uuid.uuid4()).replace("-", ""),
            ),
        )
        response = yield self._request(
            method="post",
            url="accounts/login/",
            data=generate_signature(
                phone_id=str(uuid.uuid4()),
                _csrftoken=response.cookies["csrftoken"],
                username=self.username,
                password=self.password,
                guid=self.state["uuid"],
                device_id=self.device_id,
                login_attempt_count=0,
            ),
        )
        uid = self.state["username_id"] = response.json["logged_in_user"]["pk"]
        self.state["rank_token"] = f"{uid}_{self.state['uuid']}"

    @update_cookies
    @with_relogin
    def sync_features(self):
        yield self._request(
            method="post",
            url="qe/sync/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                id=self.state["username_id"],
                experiments=constants.EXPERIMENTS,
            ),
        )

    @update_cookies
    @with_relogin
    def autocomplete_user_list(self):
        yield self._request(
            method="get",
            url="friendships/autocomplete_user_list/?version=2",
        )

    @update_cookies
    @with_relogin
    def timeline_feed(self, max_id=None):
        params = dict(rank_token=self.state["rank_token"],
                      ranked_content="true")
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url="feed/timeline/",
            params=params
        )

    @update_cookies
    @with_relogin
    def megaphone_log(self):
        uuid = str(time.time() * 1000).encode("utf-8")
        yield self._request(
            method="post",
            url="megaphone/log/",
            data=urllib.parse.urlencode(dict(
                type="feed_aysf",
                action="seen",
                reason="",
                _uuid=self.state["uuid"],
                device_id=self.device_id,
                _csrftoken=self.cookies["csrftoken"],
                uuid=hashlib.md5(uuid).hexdigest(),
            )),
        )

    @update_cookies
    @with_relogin
    def get_pending_inbox(self):
        yield self._request(
            method="get",
            url="direct_v2/pending_inbox/?",
        )

    @update_cookies
    @with_relogin
    def get_ranked_recipients(self):
        yield self._request(
            method="get",
            url="direct_v2/ranked_recipients/",
            params=dict(
                show_threads="true",
            ),
        )

    @update_cookies
    @with_relogin
    def get_recent_recipients(self):
        yield self._request(
            method="get",
            url="direct_share/recent_recipients/"
        )

    @update_cookies
    @with_relogin
    def explore(self):
        yield self._request(
            method="get",
            url="discover/explore/",
        )

    @update_cookies
    @with_relogin
    def discover_channels(self):
        yield self._request(
            method="get",
            url="discover/channels_home/",
        )

    @update_cookies
    @with_relogin
    def expose(self):
        yield self._request(
            method="post",
            url="discover/channels_home/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                id=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                experiment="ig_android_profile_contextual_feed"
            ),
        )

    @update_cookies
    @with_relogin
    def logout(self):
        yield self._request(
            method="get",
            url="accounts/logout/",
        )

    @update_cookies
    @with_relogin
    def direct_thread(self, thread_id):
        yield self._request(
            method="get",
            url=f"direct_v2/threads/{thread_id}/?",
        )

    @update_cookies
    @with_relogin
    def direct_thread_action(self, thread_id, action):
        yield self._request(
            method="post",
            url=f"direct_v2/threads/{thread_id}/{action}/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def remove_self_tag(self, media_id):
        yield self._request(
            method="post",
            url=f"media/{media_id}/remove/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def media_edit(self, media_id, caption):
        yield self._request(
            method="post",
            url=f"media/{media_id}/edit_media/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                caption_text=caption,
            ),
        )

    @update_cookies
    @with_relogin
    def media_info(self, media_id):
        yield self._request(
            method="post",
            url=f"media/{media_id}/info/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                media_id=media_id,
            ),
        )

    @update_cookies
    @with_relogin
    def media_delete(self, media_id):
        yield self._request(
            method="post",
            url=f"media/{media_id}/delete/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                media_id=media_id,
            ),
        )

    @update_cookies
    @with_relogin
    def media_comment(self, media_id, comment_text):
        yield self._request(
            method="post",
            url=f"media/{media_id}/comment/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                comment_text=comment_text,
            ),
        )

    @update_cookies
    @with_relogin
    def media_comment_delete(self, media_id, comment_id):
        yield self._request(
            method="post",
            url=f"media/{media_id}/comment/{comment_id}/delete",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def media_comments_delete(self, media_id, comment_ids):
        yield self._request(
            method="post",
            url=f"media/{media_id}/comment/bulk_delete/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                comment_ids_to_delete=",".join(map(str, comment_ids)),
            ),
        )

    @update_cookies
    @with_relogin
    def remove_profile_picture(self):
        yield self._request(
            method="post",
            url="accounts/remove_profile_picture/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def set_private_account(self):
        yield self._request(
            method="post",
            url="accounts/set_private/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def set_public_account(self):
        yield self._request(
            method="post",
            url="accounts/set_public/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def get_profile_data(self):
        yield self._request(
            method="post",
            url="accounts/current_user/?edit=true",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def edit_profile(self, url, phone, first_name, biography, mail, gender):
        yield self._request(
            method="post",
            url="accounts/edit_profile/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                url=url,
                phone_number=phone,
                username=self.username,
                first_name=first_name,
                biography=biography,
                email=mail,
                gender=gender,
            ),
        )

    @update_cookies
    @with_relogin
    def change_password(self, old, new):
        yield self._request(
            method="post",
            url="accounts/change_password/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                old_password=old,
                new_password1=new,
                new_password2=new,
            ),
        )

    @update_cookies
    @with_relogin
    def get_username_info(self, username_id=None):
        if username_id is None:
            username_id = self.state["username_id"]
        yield self._request(
            method="get",
            url=f"users/{username_id}/info/",
        )

    @update_cookies
    @with_relogin
    def get_recent_activity(self):
        yield self._request(
            method="get",
            url="news/inbox/?activity_module=all",
        )

    @update_cookies
    @with_relogin
    def get_following_recent_activity(self, max_id=None):
        params = {}
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url="news/?",
            params=params,
        )

    @update_cookies
    @with_relogin
    def get_v2_inbox(self):
        yield self._request(
            method="get",
            url="direct_v2/inbox/?",
        )

    @update_cookies
    @with_relogin
    def get_user_tags(self, username_id=None):
        if username_id is None:
            username_id = self.state["username_id"]
        yield self._request(
            method="get",
            url=f"usertags/{username_id}/feed/",
            params=dict(
                rank_token=self.state["rank_token"],
                ranked_content="true",
            ),
        )

    @update_cookies
    @with_relogin
    def get_media_likers(self, media_id):
        yield self._request(
            method="get",
            url=f"media/{media_id}/likers/",
        )

    @update_cookies
    @with_relogin
    def get_geo_media(self, username_id=None):
        if username_id is None:
            username_id = self.state["username_id"]
        yield self._request(
            method="get",
            url=f"maps/user/{username_id}/",
        )

    @update_cookies
    @with_relogin
    def search_location(self, latitude, longitude, query=None):
        params = dict(rank_token=self.state["rank_token"],
                      latitude=str(latitude),
                      longitude=str(longitude))
        if query is None:
            params["timestamp"] = int(time.time())
        else:
            params["search_query"] = query
        yield self._request(
            method="get",
            url="location_search/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def facebook_user_search(self, query):
        yield self._request(
            method="get",
            url="fbsearch/topsearch/",
            params=dict(
                context="blended",
                query=query,
                rank_token=self.state["rank_token"],
            ),
        )

    @update_cookies
    @with_relogin
    def search_users(self, query):
        yield self._request(
            method="get",
            url="users/search/",
            params=dict(
                ig_sig_key_version=constants.SIG_KEY_VERSION,
                is_typeahead="true",
                query=query,
                rank_token=self.state["rank_token"],
            ),
        )

    @update_cookies
    @with_relogin
    def search_username(self, username):
        yield self._request(
            method="get",
            url=f"users/{username}/usernameinfo/",
        )

    @update_cookies
    @with_relogin
    def search_tags(self, query):
        yield self._request(
            method="get",
            url="tags/search/",
            params=dict(
                is_typeahead="true",
                q=query,
                rank_token=self.state["rank_token"],
            ),
        )

    @update_cookies
    @with_relogin
    def get_reels_tray_feed(self):
        yield self._request(
            method="get",
            url="feed/reels_tray/",
        )

    @update_cookies
    @with_relogin
    def get_user_feed(self, username_id=None, max_id=None, min_timestamp=None):
        params = dict(rank_token=self.state["rank_token"],
                      ranked_content="true")
        if max_id is not None:
            params["max_id"] = max_id
        if min_timestamp is not None:
            params["min_timestamp"] = min_timestamp
        if username_id is None:
            username_id = self.state["username_id"]
        yield self._request(
            method="get",
            url=f"feed/user/{username_id}/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def get_hashtag_feed(self, hashtag, max_id=None):
        params = {}
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url=f"feed/tag/{hashtag}/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def search_facebook_location(self, query):
        yield self._request(
            method="get",
            url="fbsearch/places/",
            params=dict(
                rank_token=self.state["rank_token"],
                query=query,
            ),
        )

    @update_cookies
    @with_relogin
    def get_location_feed(self, location_id, max_id=None):
        params = {}
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url=f"feed/location/{location_id}/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def get_popular_feed(self):
        yield self._request(
            method="get",
            url="feed/popular/",
            params=dict(
                people_teaser_supported=1,
                rank_token=self.state["rank_token"],
                ranked_content="true",
            ),
        )

    @update_cookies
    @with_relogin
    def get_user_followings(self, username_id=None, max_id=None):
        if username_id is None:
            username_id = self.state["username_id"]
        params = dict(rank_token=self.state["rank_token"])
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url=f"friendships/{username_id}/following/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def get_user_followers(self, username_id=None, max_id=None):
        if username_id is None:
            username_id = self.state["username_id"]
        params = dict(rank_token=self.state["rank_token"])
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url=f"friendships/{username_id}/followers/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def like(self, media_id, module_name="feed_timeline"):
        yield self._request(
            method="post",
            url=f"media/{media_id}/like/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                media_id=media_id,
                radio_type="wifi-none",
                module_name=module_name,
            ),
        )

    @update_cookies
    @with_relogin
    def unlike(self, media_id):
        yield self._request(
            method="post",
            url=f"media/{media_id}/unlike/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.cookies["csrftoken"],
                media_id=media_id,
            ),
        )

    @update_cookies
    @with_relogin
    def get_media_comments(self, media_id, max_id=None):
        params = dict(ig_sig_key_version=constants.SIG_KEY_VERSION)
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url=f"media/{media_id}/comments/",
            params=params,
        )

    @update_cookies
    @with_relogin
    def set_name_and_phone(self, name="", phone=""):
        yield self._request(
            method="post",
            url="accounts/set_phone_and_name/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                first_name=name,
                phone_number=phone,
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def get_direct_share(self):
        yield self._request(
            method="get",
            url="direct_share/inbox/?",
        )

    @update_cookies
    @with_relogin
    def follow(self, user_id):
        yield self._request(
            method="post",
            url=f"friendships/create/{user_id}/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def unfollow(self, user_id):
        yield self._request(
            method="post",
            url=f"friendships/destroy/{user_id}/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def block(self, user_id):
        yield self._request(
            method="post",
            url=f"friendships/block/{user_id}/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def unblock(self, user_id):
        yield self._request(
            method="post",
            url=f"friendships/unblock/{user_id}/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.cookies["csrftoken"],
            ),
        )

    @update_cookies
    @with_relogin
    def get_user_friendship(self, user_id):
        yield self._request(
            method="get",
            url=f"friendships/show/{user_id}/",
        )

    @update_cookies
    @with_relogin
    def get_liked_media(self, max_id=None):
        params = {}
        if max_id is not None:
            params["max_id"] = max_id
        yield self._request(
            method="get",
            url="feed/liked/",
            params=params,
        )
