"""Main module."""
import logging
from asyncio import Semaphore, get_event_loop, sleep, wait_for
from os import getenv
from urllib.parse import urljoin, urlparse, urlunparse

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from redis import Redis

DEFAULT_URL_TIMEOUT = 60 * 60 * 24
PAGE_TIMEOUT = 10

logging.basicConfig(level=getenv('LOG_LEVEL', 'INFO'))
logging.getLogger("requests").setLevel(logging.WARNING)

redis = Redis.from_url(getenv('REDIS_URL', 'redis://localhost:6379/'))


connection_sem = Semaphore(int(getenv("CONCURRENT_WORKERS", 1)))
goal_sem = Semaphore(100)


def add_urls(base, soup):
    """Add urls to redis goals set."""
    def _clean_url(raw_url):
        """Remove fragments and path of a url."""
        scheme, netloc, *_ = urlparse(urljoin(base, raw_url), scheme='http')
        return urlunparse((scheme, netloc, '', '', '', ''))

    urls = set(map(_clean_url, map(
        lambda anchor: anchor.get('href'), soup.find_all('a'))))
    logging.debug("%s:  %d URLS.", base, len(urls))
    if not urls:
        return

    goal_key = "goal:{}".format(base)
    goal_minus_visits_key = "goal:{}:visits".format(base)
    with redis.pipeline() as pipe:
        pipe.sadd(goal_key, *urls)
        pipe.sdiffstore(goal_minus_visits_key, goal_key, "visits")
        pipe.sunionstore("goals", "goals", goal_minus_visits_key)
        pipe.delete(goal_key)
        pipe.delete(goal_minus_visits_key)
        pipe.execute()


def parse_page(base, content):
    """Parse page, add urls and return title."""
    soup = BeautifulSoup(content, "html5lib")
    add_urls(base, soup)
    return soup.title.string.strip()


async def get_page(url):
    """Get page, mark as visited and return content."""
    async def _get_page():
        async with session.get(url) as response:
            return await response.text()

    async with connection_sem:
        return await wait_for(_get_page(), PAGE_TIMEOUT)


async def process_url(url):
    """Process a url, extract its content and process hrefs."""
    return parse_page(url, await get_page(url))


def get_next_goal():
    """Retrieve the next goal from redis or None."""
    raw_url = redis.spop('goals')
    if not raw_url:
        logging.warning("No goals left.")
        return
    url = raw_url.decode()
    return url


async def handle_goal(url):
    """Retrieve and publish the goal result."""
    logging.info("Handling goal: %s", url)
    try:
        title = await process_url(url)
    except Exception as e:
        logging.exception(e)
    else:
        with redis.pipeline() as pipe:
            pipe.sadd('visits', url)
            if title:
                pipe.publish('titles', "{},{}".format(url, title))
            pipe.execute()
    finally:
        goal_sem.release()


async def main():
    """Enqueeu goals."""
    while True:
        url = get_next_goal()
        if not url:
            await sleep(1)
        else:
            logging.info("Enqueueing goal: %s", url)
            await goal_sem.acquire()
            loop.create_task(handle_goal(url))


if __name__ == "__main__":
    with ClientSession() as session:
        loop = get_event_loop()
        loop.create_task(main())
        loop.run_forever()
