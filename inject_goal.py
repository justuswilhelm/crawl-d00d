"""Inject a new goal."""
from os import getenv

from redis import Redis


if __name__ == "__main__":
    redis = Redis.from_url(getenv('REDIS_URL', 'redis://localhost:6379/'))
    redis.sadd('goals', 'https://en.wikipedia.org')
