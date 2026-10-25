from django.core.cache import cache, caches  # noqa
from django.conf import settings  # noqa

from django_redis.cache import RedisCache
from django_redis.client.default import DefaultClient


class MyRedisClient(DefaultClient):
    def __getattr__(self, item):
        client = self.get_client(write=True)
        return getattr(client, item)

    def redis_incr(self, key, count=1):
        """
        django 默认的 incr 在 key 不存在时候会抛异常
        """
        client = self.get_client(write=True)
        return client.incr(key, count)


class MyRedisCache(RedisCache):
    def __init__(self, server, params):
        super().__init__(server, params)
        self._client_cls = MyRedisClient

    # El limitador histórico guarda números Redis, no objetos serializados de
    # Django. django-redis 7 añadió hset con serialización: conservar explícitamente
    # ambos extremos del protocolo anterior y sus claves sin prefijo nuevo.
    def hset(self, key, field, value):
        return self.client.get_client(write=True).hset(key, field, value)

    def hget(self, key, field):
        return self.client.get_client(write=True).hget(key, field)

    def __getattr__(self, item):
        return getattr(self.client, item)
