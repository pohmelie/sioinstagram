import collections
import hmac
import hashlib
import urllib.parse
import uuid
import json
import time

from . import constants


__all__ = (
    "Request",
    "Response",
    "Protocol",
)

HEADERS = (
    ("Connection", "close"),
    ("Accept", "*/*"),
    ("Content-type", "application/x-www-form-urlencoded; charset=UTF-8"),
    ("Cookie2", "$Version=1"),
    ("Accept-Language", "en-US"),
    ("User-Agent", constants.USER_AGENT),
)

_Request = collections.namedtuple("Request", "method url params headers data")
Response = collections.namedtuple("Response", "cookies json")


def Request(method, url, *, params=None, headers=None, data=None):

    return _Request(
        method=method,
        url=constants.API_URL + url,
        params=params,
        headers=headers or dict(HEADERS),
        data=data,
    )


def encode_signature(signature):

    for key, value in signature.items():

        yield str.format("{}={}", key, value)


def generate_signature(**data):

    data_string = json.dumps(data)
    key = str.encode(constants.IG_SIG_KEY, "utf-8")
    h = hmac.new(key, str.encode(data_string, "utf-8"), hashlib.sha256)
    signed = str.format("{}.{}", h.hexdigest(), data_string)
    signature = dict(
        ig_sig_key_version=constants.SIG_KEY_VERSION,
        signed_body=urllib.parse.quote(signed),
    )
    return str.join("&", encode_signature(signature))


class Protocol:

    _COOKIES = ("csrftoken", "sessionid")

    def __init__(self, state=None):

        self.state = {} if state is None else state
        if "uuid" not in self.state:

            self.state["uuid"] = str(uuid.uuid4())

    @property
    def device_id(self):

        a = (self.state["username"] + self.state["password"]).encode("utf-8")
        b = (hashlib.md5(a).hexdigest() + "yoba").encode("utf-8")
        return "android-" + hashlib.md5(b).hexdigest()[:16]

    @property
    def cookies(self):

        return self.state.get("cookies", {})

    def login(self, username, password):

        self.state["username"] = username
        self.state["password"] = password

        response = yield Request(
            method="post",
            url="qe/sync/",
            data=generate_signature(
                id=str(uuid.uuid4()),
                experiments=constants.LOGIN_EXPERIMENTS,
            ),
        )

        response = yield Request(
            method="get",
            url="si/fetch_headers/",
            params=dict(
                challenge_type="signup",
                guid=str.replace(str(uuid.uuid4()), "-", ""),
            ),
        )

        response = yield Request(
            method="post",
            url="accounts/login/",
            data=generate_signature(
                phone_id=str(uuid.uuid4()),
                _csrftoken=response.cookies["csrftoken"],
                username=username,
                password=password,
                guid=self.state["uuid"],
                device_id=self.device_id,
                login_attempt_count=0,
            ),
        )

        self.state["username_id"] = response.json["logged_in_user"]["pk"]
        cookies = self.state["cookies"] = {}
        for name in self._COOKIES:

            if name in response.cookies:

                cookies[name] = response.cookies[name]

        self.state["rank_token"] = str.format(
            "{}_{}",
            self.state["username_id"],
            self.state["uuid"],
        )
        yield None

    def sync_features(self):

        yield Request(
            method="post",
            url="qe/sync/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                id=self.state["username_id"],
                experiments=constants.EXPERIMENTS,
            ),
        )
        yield None

    def autocomplete_user_list(self):

        yield Request(
            method="get",
            url="friendships/autocomplete_user_list/?version=2",
        )
        yield None

    def timeline_feed(self, max_id=None):

        params = dict(
            rank_token=self.state["rank_token"],
            ranked_content="true",
        )
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url="feed/timeline/",
            params=params
        )
        yield None

    def megaphone_log(self):

        uuid = str(time.time() * 1000).encode("utf-8")
        yield Request(
            method="post",
            url="megaphone/log/",
            data=urllib.parse.urlencode(dict(
                type="feed_aysf",
                action="seen",
                reason="",
                _uuid=self.state["uuid"],
                device_id=self.device_id,
                _csrftoken=self.state["cookies"]["csrftoken"],
                uuid=hashlib.md5(uuid).hexdigest(),
            )),
        )
        yield None

    def get_pending_inbox(self):

        yield Request(
            method="get",
            url="direct_v2/pending_inbox/?",
        )
        yield None

    def get_ranked_recipients(self):

        yield Request(
            method="get",
            url="direct_v2/ranked_recipients/",
            params=dict(
                show_threads="true",
            ),
        )
        yield None

    def get_recent_recipients(self):

        yield Request(
            method="get",
            url="direct_share/recent_recipients/"
        )
        yield None

    def explore(self):

        yield Request(
            method="get",
            url="discover/explore/",
        )
        yield None

    def discover_channels(self):

        yield Request(
            method="get",
            url="discover/channels_home/",
        )
        yield None

    def expose(self):

        yield Request(
            method="post",
            url="discover/channels_home/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                id=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                experiment="ig_android_profile_contextual_feed"
            ),
        )
        yield None

    def logout(self):

        yield Request(
            method="get",
            url="accounts/logout/",
        )
        yield None

    def direct_thread(self, thread_id):

        yield Request(
            method="get",
            url=str.format(
                "direct_v2/threads/{thread_id}/?",
                thread_id=thread_id
            ),
        )
        yield None

    def direct_thread_action(self, thread_id, action):

        yield Request(
            method="post",
            url=str.format(
                "direct_v2/threads/{thread_id}/{action}/",
                thread_id=thread_id,
                action=action,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def remove_self_tag(self, media_id):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/remove/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def media_edit(self, media_id, caption):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/edit_media/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                caption_text=caption,
            ),
        )
        yield None

    def media_info(self, media_id):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/info/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                media_id=media_id,
            ),
        )
        yield None

    def media_delete(self, media_id):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/delete/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                media_id=media_id,
            ),
        )
        yield None

    def media_comment(self, media_id, comment_text):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/comment/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                comment_text=comment_text,
            ),
        )
        yield None

    def media_comment_delete(self, media_id, comment_id):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/comment/{comment_id}/delete",
                media_id=media_id,
                comment_id=comment_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def media_comments_delete(self, media_id, comment_ids):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/comment/bulk_delete/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                comment_ids_to_delete=str.join(",", map(str, comment_ids)),
            ),
        )
        yield None

    def remove_profile_picture(self):

        yield Request(
            method="post",
            url="accounts/remove_profile_picture/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def set_private_account(self):

        yield Request(
            method="post",
            url="accounts/set_private/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def set_public_account(self):

        yield Request(
            method="post",
            url="accounts/set_public/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def get_profile_data(self):

        yield Request(
            method="post",
            url="accounts/current_user/?edit=true",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def edit_profile(self, url, phone, first_name, biography, mail, gender):

        yield Request(
            method="post",
            url="accounts/edit_profile/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                url=url,
                phone_number=phone,
                username=self.state["username"],
                first_name=first_name,
                biography=biography,
                email=mail,
                gender=gender,
            ),
        )
        yield None

    def change_password(self, old, new):

        yield Request(
            method="post",
            url="accounts/change_password/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                old_password=old,
                new_password1=new,
                new_password2=new,
            ),
        )
        yield None

    def get_username_info(self, username_id=None):

        username_id = username_id or self.state["username_id"]
        yield Request(
            method="get",
            url=str.format(
                "users/{username_id}/info/",
                username_id=username_id,
            ),
        )
        yield None

    def get_recent_activity(self):

        yield Request(
            method="get",
            url="news/inbox/?activity_module=all",
        )
        yield None

    def get_following_recent_activity(self, max_id=None):

        params = {}
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url="news/?",
            params=params,
        )
        yield None

    def get_v2_inbox(self):

        yield Request(
            method="get",
            url="direct_v2/inbox/?",
        )
        yield None

    def get_user_tags(self, username_id=None):

        yield Request(
            method="get",
            url=str.format(
                "usertags/{username_id}/feed/",
                username_id=username_id or self.state["username_id"],
            ),
            params=dict(
                rank_token=self.state["rank_token"],
                ranked_content="true",
            ),
        )
        yield None

    def get_media_likers(self, media_id):

        yield Request(
            method="get",
            url=str.format(
                "media/{media_id}/likers/",
                media_id=media_id,
            ),
        )
        yield None

    def get_geo_media(self, username_id=None):

        yield Request(
            method="get",
            url=str.format(
                "maps/user/{username_id}/",
                username_id=username_id or self.state["username_id"]
            ),
        )
        yield None

    def search_location(self, latitude, longitude, query=None):

        params = dict(
            rank_token=self.state["rank_token"],
            latitude=str(latitude),
            longitude=str(longitude),
        )
        if query is None:

            params["timestamp"] = int(time.time())

        else:

            params["search_query"] = query

        yield Request(
            method="get",
            url="location_search/",
            params=params,
        )
        yield None

    def facebook_user_search(self, query):

        yield Request(
            method="get",
            url="fbsearch/topsearch/",
            params=dict(
                context="blended",
                query=query,
                rank_token=self.state["rank_token"],
            ),
        )
        yield None

    def search_users(self, query):

        yield Request(
            method="get",
            url="users/search/",
            params=dict(
                ig_sig_key_version=constants.SIG_KEY_VERSION,
                is_typeahead="true",
                query=query,
                rank_token=self.state["rank_token"],
            ),
        )
        yield None

    def search_username(self, username):

        yield Request(
            method="get",
            url=str.format(
                "users/{username}/usernameinfo/",
                username=username,
            ),
        )
        yield None

    def search_tags(self, query):

        yield Request(
            method="get",
            url="tags/search/",
            params=dict(
                is_typeahead="true",
                q=query,
                rank_token=self.state["rank_token"],
            ),
        )
        yield None

    def get_reels_tray_feed(self):

        yield Request(
            method="get",
            url="feed/reels_tray/",
        )
        yield None

    def get_user_feed(self, username_id=None, max_id=None, min_timestamp=None):

        params = dict(
            rank_token=self.state["rank_token"],
            ranked_content="true",
        )
        if max_id is not None:

            params["max_id"] = max_id

        if min_timestamp is not None:

            params["min_timestamp"] = min_timestamp

        yield Request(
            method="get",
            url=str.format(
                "feed/user/{username_id}/",
                username_id=username_id or self.state["username_id"],
            ),
            params=params,
        )
        yield None

    def get_hashtag_feed(self, hashtag, max_id=None):

        params = {}
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url=str.format(
                "feed/tag/{hashtag}/",
                hashtag=hashtag,
            ),
            params=params,
        )
        yield None

    def search_facebook_location(self, query):

        yield Request(
            method="get",
            url="fbsearch/places/",
            params=dict(
                rank_token=self.state["rank_token"],
                query=query,
            ),
        )
        yield None

    def get_location_feed(self, location_id, max_id=None):

        params = {}
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url=str.format(
                "feed/location/{location_id}/",
                location_id=location_id,
            ),
            params=params,
        )
        yield None

    def get_popular_feed(self):

        yield Request(
            method="get",
            url="feed/popular/",
            params=dict(
                people_teaser_supported=1,
                rank_token=self.state["rank_token"],
                ranked_content="true",
            ),
        )
        yield None

    def get_user_followings(self, username_id=None, max_id=None):

        params = dict(
            rank_token=self.state["rank_token"],
        )
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url=str.format(
                "friendships/{username_id}/following/",
                username_id=username_id or self.state["username_id"],
            ),
            params=params,
        )
        yield None

    def get_user_followers(self, username_id=None, max_id=None):

        params = dict(
            rank_token=self.state["rank_token"],
        )
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url=str.format(
                "friendships/{username_id}/followers/",
                username_id=username_id or self.state["username_id"],
            ),
            params=params,
        )
        yield None

    def like(self, media_id):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/like/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                media_id=media_id,
            ),
        )
        yield None

    def unlike(self, media_id):

        yield Request(
            method="post",
            url=str.format(
                "media/{media_id}/unlike/",
                media_id=media_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                _csrftoken=self.state["cookies"]["csrftoken"],
                media_id=media_id,
            ),
        )
        yield None

    def get_media_comments(self, media_id, max_id=None):

        params = dict(
            ig_sig_key_version=constants.SIG_KEY_VERSION,
        )
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url=str.format(
                "media/{media_id}/comments/",
                media_id=media_id,
            ),
            params=params,
        )
        yield None

    def set_name_and_phone(self, name="", phone=""):

        yield Request(
            method="post",
            url="accounts/set_phone_and_name/",
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                first_name=name,
                phone_number=phone,
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def get_direct_share(self):

        yield Request(
            method="get",
            url="direct_share/inbox/?",
        )
        yield None

    def follow(self, user_id):

        yield Request(
            method="post",
            url=str.format(
                "friendships/create/{user_id}/",
                user_id=user_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def unfollow(self, user_id):

        yield Request(
            method="post",
            url=str.format(
                "friendships/destroy/{user_id}/",
                user_id=user_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def block(self, user_id):

        yield Request(
            method="post",
            url=str.format(
                "friendships/block/{user_id}/",
                user_id=user_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def unblock(self, user_id):

        yield Request(
            method="post",
            url=str.format(
                "friendships/unblock/{user_id}/",
                user_id=user_id,
            ),
            data=generate_signature(
                _uuid=self.state["uuid"],
                _uid=self.state["username_id"],
                user_id=user_id,
                _csrftoken=self.state["cookies"]["csrftoken"],
            ),
        )
        yield None

    def get_user_friendship(self, user_id):

        yield Request(
            method="get",
            url=str.format(
                "friendships/show/{user_id}/",
                user_id=user_id,
            ),
        )
        yield None

    def get_liked_media(self, max_id=None):

        params = {}
        if max_id is not None:

            params["max_id"] = max_id

        yield Request(
            method="get",
            url="feed/liked/",
            params=params,
        )
        yield None
