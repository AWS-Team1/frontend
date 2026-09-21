"""Valkey-backed browser session storage.

The browser only receives an opaque session id and a CSRF token. Internal
JWTs remain server-side in Valkey and are never written to browser storage.
"""

import hashlib
import hmac
import os
import secrets
import time

import redis
from redis.cluster import RedisCluster
from redis.exceptions import RedisError


class SessionStoreUnavailable(RuntimeError):
    """Raised when a security-critical Valkey operation cannot complete."""


def create_valkey_client():
    """Create the shared Valkey client from either URL or discrete settings."""
    redis_url = os.getenv("REDIS_URL")
    common = {
        "decode_responses": True,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "health_check_interval": 30,
    }
    if redis_url:
        return redis.Redis.from_url(redis_url, **common)

    host = os.getenv("VALKEY_HOST")
    if not host:
        raise SessionStoreUnavailable("VALKEY_HOST or REDIS_URL is required")

    use_tls = os.getenv("VALKEY_TLS", "true").lower() == "true"
    client_class = (RedisCluster if os.getenv(
        "VALKEY_CLUSTER_MODE", "true").lower() == "true" else redis.Redis)
    return client_class(
        host=host,
        port=int(os.getenv("VALKEY_PORT", "6379")),
        username=os.getenv("VALKEY_USERNAME"),
        password=os.getenv("VALKEY_PASSWORD"),
        ssl=use_tls,
        ssl_cert_reqs="required" if use_tls else None,
        **common,
    )


class SessionStore:
    """Fail-closed Valkey session store with idle and absolute expiration."""

    SESSION_PREFIX = "boa:session:{{{}}}:"
    USER_INDEX_PREFIX = "boa:user-sessions:{{{}}}"

    _LIMIT_SESSIONS_LUA = """
    local index_key = KEYS[1]
    local session_prefix = ARGV[1]
    local current_member = ARGV[2]
    local score = tonumber(ARGV[3])
    local max_sessions = tonumber(ARGV[4])
    local index_ttl = tonumber(ARGV[5])

    local members = redis.call('ZRANGE', index_key, 0, -1)
    for _, member in ipairs(members) do
      if redis.call('EXISTS', session_prefix .. member) == 0 then
        redis.call('ZREM', index_key, member)
      end
    end

    redis.call('ZADD', index_key, score, current_member)
    redis.call('EXPIRE', index_key, index_ttl)
    while redis.call('ZCARD', index_key) > max_sessions do
      local oldest = redis.call('ZPOPMIN', index_key, 1)
      if oldest[1] then
        redis.call('DEL', session_prefix .. oldest[1])
      end
    end
    return redis.call('ZCARD', index_key)
    """

    _TOUCH_LUA = """
    if redis.call('EXISTS', KEYS[1]) == 0 then
      return 0
    end
    redis.call('HSET', KEYS[1], 'last_seen_at', ARGV[1])
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
    """

    _UPDATE_ACCESS_LUA = """
    if redis.call('EXISTS', KEYS[1]) == 0 then
      return 0
    end
    redis.call('HSET', KEYS[1], 'access_token', ARGV[1])
    return 1
    """

    def __init__(self, client, idle_ttl=300, absolute_ttl=3600, max_sessions=3):
        self.client = client
        self.idle_ttl = idle_ttl
        self.absolute_ttl = absolute_ttl
        self.max_sessions = max_sessions

    @staticmethod
    def _digest(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _user_tag(self, username):
        return self._digest(username.lower())[:32]

    def _session_key(self, session_id):
        try:
            user_tag, _ = session_id.split(".", 1)
            if len(user_tag) != 32 or any(
                    character not in "0123456789abcdef" for character in user_tag):
                raise ValueError("invalid user tag")
        except (AttributeError, ValueError):
            return None
        return self.SESSION_PREFIX.format(user_tag) + self._digest(session_id)

    def _user_index_key(self, username):
        return self.USER_INDEX_PREFIX.format(self._user_tag(username))

    def ping(self):
        try:
            return bool(self.client.ping())
        except RedisError as err:
            raise SessionStoreUnavailable("Valkey is unavailable") from err

    def create(self, access_token, refresh_token, claims):
        now = int(time.time())
        user_tag = self._user_tag(str(claims["user"]))
        session_id = user_tag + "." + secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        member = self._digest(session_id)
        session_prefix = self.SESSION_PREFIX.format(user_tag)
        session_key = session_prefix + member
        username = str(claims["user"])

        session = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": username,
            "acct": str(claims["acct"]),
            "name": str(claims["name"]),
            "created_at": str(now),
            "last_seen_at": str(now),
            "absolute_expires_at": str(now + self.absolute_ttl),
            "csrf_hash": self._digest(csrf_token),
        }
        try:
            pipeline = self.client.pipeline(transaction=True)
            pipeline.hset(session_key, mapping=session)
            pipeline.expire(session_key, self.idle_ttl)
            pipeline.execute()
            self.client.eval(
                self._LIMIT_SESSIONS_LUA,
                1,
                self._user_index_key(username),
                session_prefix,
                member,
                now,
                self.max_sessions,
                self.absolute_ttl,
            )
        except RedisError as err:
            try:
                self.client.delete(session_key)
            except RedisError:
                pass
            raise SessionStoreUnavailable("Unable to create session") from err
        return session_id, csrf_token

    def get(self, session_id, touch=True):
        if not session_id:
            return None
        key = self._session_key(session_id)
        if key is None:
            return None
        try:
            session = self.client.hgetall(key)
            if not session:
                return None
            now = int(time.time())
            absolute_expires_at = int(session["absolute_expires_at"])
            remaining = absolute_expires_at - now
            if remaining <= 0:
                self.revoke(session_id, session.get("user"))
                return None
            if touch:
                ttl = min(self.idle_ttl, remaining)
                touched = self.client.eval(self._TOUCH_LUA, 1, key, now, ttl)
                if touched != 1:
                    return None
                session["last_seen_at"] = str(now)
            return session
        except (RedisError, KeyError, TypeError, ValueError) as err:
            raise SessionStoreUnavailable("Unable to read session") from err

    def update_access_token(self, session_id, access_token):
        try:
            key = self._session_key(session_id)
            if key is None:
                return False
            updated = self.client.eval(
                self._UPDATE_ACCESS_LUA,
                1,
                key,
                access_token,
            )
            if updated != 1:
                return False
            return True
        except RedisError as err:
            raise SessionStoreUnavailable("Unable to refresh session token") from err

    def revoke(self, session_id, username=None):
        if not session_id:
            return
        member = self._digest(session_id)
        key = self._session_key(session_id)
        if key is None:
            return
        try:
            if username is None:
                username = self.client.hget(key, "user")
            pipeline = self.client.pipeline(transaction=True)
            pipeline.delete(key)
            if username:
                pipeline.zrem(self._user_index_key(username), member)
            pipeline.execute()
        except RedisError as err:
            raise SessionStoreUnavailable("Unable to revoke session") from err

    def verify_csrf(self, session, submitted_token, cookie_token):
        if not submitted_token or not cookie_token:
            return False
        if not hmac.compare_digest(submitted_token, cookie_token):
            return False
        expected = session.get("csrf_hash", "")
        return hmac.compare_digest(self._digest(submitted_token), expected)
