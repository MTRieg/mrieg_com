from typing import Optional
import uuid

try:
    import redis.asyncio as redis
except Exception as e:
    raise ImportError(
        "redis.asyncio is required for infrastructure.redis. Install 'redis>=4.2.0'."
    ) from e


class RedisClient:
    """Simple async Redis client wrapper with lifecycle management and locks.

    Usage:
        client = RedisClient.from_url("redis://localhost:6379/0")
        await client.init()
        r = client.get()
        await r.set("foo", "bar")
        await client.close()
    """

    def __init__(self, url: str, *, decode_responses: bool = True):
        self.url = url
        self.decode_responses = decode_responses
        self._client: Optional[redis.Redis] = None

    @classmethod
    def from_url(cls, url: str, **kwargs) -> "RedisClient":
        return cls(url, **kwargs)

    async def init(self) -> None:
        """Initialize the underlying redis connection. Must be awaited."""
        if self._client is not None:
            return
        self._client = redis.from_url(self.url, decode_responses=self.decode_responses)
        # verify connectivity
        await self._client.ping()

    async def close(self) -> None:
        """Close the connection cleanly."""
        if self._client is None:
            return
        await self._client.close()
        self._client = None

    def get(self) -> redis.Redis:
        """Return the underlying `redis.Redis` client. Raises if not initialized."""
        if self._client is None:
            raise RuntimeError("Redis client not initialized; call init() first")
        return self._client

    # ------ simple distributed lock helpers ------

    async def acquire_lock(self, key: str, timeout_ms: int = 10_000) -> str:
        """
        Acquire a lock on `key`. Returns a token string when acquired.
        Raises RuntimeError if the client isn't initialized.
        """
        token = str(uuid.uuid4())
        client = self.get()
        # SET key token NX PX timeout_ms
        acquired = await client.set(key, token, nx=True, px=timeout_ms)
        if acquired:
            return token
        raise RuntimeError("Lock not acquired")

    async def release_lock(self, key: str, token: str) -> bool:
        """
        Release a lock only if `token` matches the stored value.
        Uses a Lua script to ensure atomicity. Returns True if released.
        """
        client = self.get()
        script = (
            "if redis.call('GET', KEYS[1]) == ARGV[1] then"
            " return redis.call('DEL', KEYS[1])"
            " else return 0 end"
        )
        res = await client.eval(script, 1, key, token)
        return res == 1


# Module-level convenience: a single default client factory
_default_client: Optional[RedisClient] = None


def create_redis_client(url: str, *, decode_responses: bool = True) -> RedisClient:
    """Create (but do not init) a RedisClient. Use `init()` to open.

    This returns a new client instance. To get a shared module-level client
    call `get_default_redis()` after calling `init_default_redis()`.
    """
    return RedisClient(url, decode_responses=decode_responses)


async def init_default_redis(url: str, *, decode_responses: bool = True) -> RedisClient:
    """Initialize and register a module-level default RedisClient.

    Returns the initialized client.
    """
    global _default_client
    if _default_client is None:
        _default_client = RedisClient(url, decode_responses=decode_responses)
    await _default_client.init()
    return _default_client


def get_default_redis() -> RedisClient:
    if _default_client is None:
        raise RuntimeError("Default Redis client not initialized; call init_default_redis()")
    return _default_client


async def close_default_redis() -> None:
    global _default_client
    if _default_client is not None:
        await _default_client.close()
        _default_client = None
