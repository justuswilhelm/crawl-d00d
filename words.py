from redis import Redis
r = Redis(db=1)

for key in r.keys():
    print(key, r[key])
