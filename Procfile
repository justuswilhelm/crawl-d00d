web: gunicorn -b "0.0.0.0:$PORT" -w 3 frontend --log-config gunicorn_logging.ini --worker-class aiohttp.worker.GunicornWebWorker
spider: python run.py
# only relevant when running locally
local-redis: redis-server
