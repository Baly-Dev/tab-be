import uuid
from types import SimpleNamespace

from auth.utils.sessions.refresh_session import (
    _CONSUME_LUA,
    _ROTATE_LUA,
    FAMILY_KEY_PREFIX,
    RefreshSessionService,
)
from auth.utils.tokens import generate_refresh_token_plain, hash_refresh_token
from config.settings import Settings


class _FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    def pipeline(self) -> "_Pipeline":
        return _Pipeline(self)

    def _hset(self, key: str, mapping: dict | None = None, **kwargs) -> int:
        fields = dict(mapping or {})
        if not fields and kwargs:
            fields = kwargs
        bucket = self.hashes.setdefault(key, {})
        bucket.update({str(name): str(value) for name, value in fields.items()})
        return len(fields)

    async def hset(self, key: str, mapping: dict | None = None, **kwargs) -> int:
        return self._hset(key, mapping=mapping, **kwargs)

    def _hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def hgetall(self, key: str) -> dict[str, str]:
        return self._hgetall(key)

    def _expire(self, key: str, seconds: int) -> bool:
        _ = seconds
        return key in self.hashes or key in self.strings or key in self.sets

    async def expire(self, key: str, seconds: int) -> bool:
        return self._expire(key, seconds)

    def _sadd(self, key: str, *members: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(str(member) for member in members)
        return len(bucket) - before

    async def sadd(self, key: str, *members: str) -> int:
        return self._sadd(key, *members)

    def _srem(self, key: str, *members: str) -> int:
        bucket = self.sets.get(key)
        if not bucket:
            return 0
        removed = 0
        for member in members:
            if str(member) in bucket:
                bucket.remove(str(member))
                removed += 1
        return removed

    async def srem(self, key: str, *members: str) -> int:
        return self._srem(key, *members)

    def _smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def smembers(self, key: str) -> set[str]:
        return self._smembers(key)

    def _get(self, key: str) -> str | None:
        return self.strings.get(key)

    async def get(self, key: str) -> str | None:
        return self._get(key)

    def _set(self, key: str, value: str, ex: int | None = None) -> bool:
        _ = ex
        self.strings[key] = str(value)
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        return self._set(key, value, ex=ex)

    def _delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            existed = key in self.hashes or key in self.strings or key in self.sets
            self.hashes.pop(key, None)
            self.strings.pop(key, None)
            self.sets.pop(key, None)
            if existed:
                removed += 1
        return removed

    async def delete(self, *keys: str) -> int:
        return self._delete(*keys)

    async def eval(self, script: str, numkeys: int, *keys_and_args):
        keys = [str(item) for item in keys_and_args[:numkeys]]
        argv = [str(item) for item in keys_and_args[numkeys:]]
        if script == _ROTATE_LUA:
            return self._eval_rotate(keys, argv)
        if script == _CONSUME_LUA:
            return self._eval_consume(keys, argv)
        raise AssertionError("unexpected lua script")

    def _eval_rotate(self, keys: list[str], argv: list[str]) -> list[str]:
        old_key, replay_key, new_key, grace_key = keys
        ttl, grace_raw, old_hash, new_hash, new_plain, family_prefix = argv
        data = self._hgetall(old_key)
        if not data:
            return []
        user_id = data.get("user_id")
        family_id = data.get("family_id")
        if not user_id or not family_id:
            self._delete(old_key)
            return []
        family_key = f"{family_prefix}{family_id}:tokens"
        self._delete(old_key)
        self._set(replay_key, family_id, ex=int(ttl))
        self._srem(family_key, old_hash)
        self._hset(new_key, mapping={"user_id": user_id, "family_id": family_id})
        self._expire(new_key, int(ttl))
        self._sadd(family_key, new_hash)
        self._expire(family_key, int(ttl))
        if int(float(grace_raw)) > 0:
            self._set(grace_key, f"{new_plain}\n{user_id}\n{family_id}", ex=int(float(grace_raw)))
        return [user_id, family_id]

    def _eval_consume(self, keys: list[str], argv: list[str]) -> list[str]:
        rt_key, replay_key = keys
        ttl, old_hash, family_prefix = argv
        data = self._hgetall(rt_key)
        if not data:
            return []
        user_id = data.get("user_id")
        family_id = data.get("family_id")
        self._delete(rt_key)
        if family_id:
            self._set(replay_key, family_id, ex=int(ttl))
            self._srem(f"{family_prefix}{family_id}:tokens", old_hash)
        if not user_id or not family_id:
            return []
        return [user_id, family_id]


class _Pipeline:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple, dict]] = []

    def hset(self, *args, **kwargs):
        self._ops.append(("hset", args, kwargs))
        return self

    def expire(self, *args, **kwargs):
        self._ops.append(("expire", args, kwargs))
        return self

    def sadd(self, *args, **kwargs):
        self._ops.append(("sadd", args, kwargs))
        return self

    def delete(self, *args, **kwargs):
        self._ops.append(("delete", args, kwargs))
        return self

    def set(self, *args, **kwargs):
        self._ops.append(("set", args, kwargs))
        return self

    async def execute(self) -> list:
        out = []
        for name, args, kwargs in self._ops:
            fn = getattr(self._redis, f"_{name}", None)
            if fn is None:
                fn = getattr(self._redis, name)
            if name in {"hset", "expire", "sadd", "srem", "delete", "set", "get", "hgetall"}:
                out.append(fn(*args, **kwargs))
            else:
                out.append(await fn(*args, **kwargs))
        return out


class _RedisService:
    def __init__(self, client: _FakeRedis) -> None:
        self._client = client

    def get_client(self) -> _FakeRedis:
        return self._client


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="ada@example.com",
        username="ada",
        status="active",
        email_verified_at="yes",
    )


def _db(user: SimpleNamespace):
    class _Session:
        async def get(self, _model, pk):
            return user if pk == user.id else None

    return _Session()


def _service(fake: _FakeRedis, *, grace: int = 10) -> RefreshSessionService:
    settings = Settings(
        jwt_secret="test-refresh-secret",
        refresh_token_store="redis",
        redis_url="redis://localhost:6379/0",
        refresh_rotation_grace_seconds=grace,
    )
    return RefreshSessionService(settings=settings, redis=_RedisService(fake))


async def test_rotate_lua_uses_family_prefix() -> None:
    assert FAMILY_KEY_PREFIX == "tn:family:"
    assert "HGETALL" in _ROTATE_LUA
    assert "DEL" in _ROTATE_LUA


async def test_single_rotate_replaces_the_current_token() -> None:
    fake = _FakeRedis()
    user = _user()
    svc = _service(fake)
    plain = generate_refresh_token_plain()
    await svc.persist(_db(user), user_id=user.id, plain=plain)

    rotated = await svc.rotate(_db(user), plain)
    assert rotated is not None
    record, new_plain, loaded = rotated
    assert loaded.id == user.id
    assert record.family_id
    assert await svc.find_valid(_db(user), plain=plain) is None
    assert await svc.find_valid(_db(user), plain=new_plain) is not None
    assert hash_refresh_token(plain, settings=svc._settings) != hash_refresh_token(
        new_plain, settings=svc._settings
    )


async def test_parallel_rotate_returns_the_same_successor() -> None:
    fake = _FakeRedis()
    user = _user()
    svc = _service(fake, grace=10)
    plain = generate_refresh_token_plain()
    await svc.persist(_db(user), user_id=user.id, plain=plain)

    first = await svc.rotate(_db(user), plain)
    second = await svc.rotate(_db(user), plain)
    assert first is not None and second is not None
    assert first[1] == second[1]
    live = await svc.find_valid(_db(user), plain=first[1])
    assert live is not None
    assert live.family_id == first[0].family_id


async def test_reuse_after_grace_revokes_the_family() -> None:
    fake = _FakeRedis()
    user = _user()
    svc = _service(fake, grace=10)
    plain = generate_refresh_token_plain()
    await svc.persist(_db(user), user_id=user.id, plain=plain)

    first = await svc.rotate(_db(user), plain)
    assert first is not None
    new_plain = first[1]
    await fake.delete(svc._grace_key(hash_refresh_token(plain, settings=svc._settings)))

    replayed = await svc.rotate(_db(user), plain)
    assert replayed is None
    assert await svc.find_valid(_db(user), plain=new_plain) is None


async def test_zero_grace_treats_the_second_caller_as_reuse() -> None:
    fake = _FakeRedis()
    user = _user()
    svc = _service(fake, grace=0)
    plain = generate_refresh_token_plain()
    await svc.persist(_db(user), user_id=user.id, plain=plain)

    first = await svc.rotate(_db(user), plain)
    second = await svc.rotate(_db(user), plain)
    assert first is not None
    assert second is None
    assert await svc.find_valid(_db(user), plain=first[1]) is None


async def test_revoke_consumes_the_token_so_rotate_cannot_reissue_it() -> None:
    fake = _FakeRedis()
    user = _user()
    svc = _service(fake)
    plain = generate_refresh_token_plain()
    await svc.persist(_db(user), user_id=user.id, plain=plain)

    assert await svc.revoke_plain(_db(user), plain) is True
    assert await svc.rotate(_db(user), plain) is None
    assert await svc.find_valid(_db(user), plain=plain) is None