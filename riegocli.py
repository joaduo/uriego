import requests
import json
import time
from pprint import pprint


URL_BASE='http://192.168.220.100/'
URL_BASE='http://192.168.4.1/'
AUTH_TOKEN='1234'


def weekday_to_int(d):
    try:
        d = int(d)
        assert 0 <= d <= 6
        return d
    except ValueError:
        return ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'
                ].index(d.lower()[:3])

def month_to_int(d):
    try:
        d = int(d)
        assert 0 < d <= 12
        return d
    except ValueError:
        return ['jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dic'
                ].index(d.lower()[:3]) + 1

def to_md_tuple(md_str):
    from_m, from_d = md_str.split(',')
    return month_to_int(from_m), int(from_d)

def to_int_weekdays(dlist):
    return list(sorted(weekday_to_int(d)
                       for d in dlist))

def to_hms(hms_str):
    return tuple(int(s) for s in hms_str.split(':'))


def build_task_list():
    pl = [
        {
          "name":"abajo",
          "start": to_hms("00:00:00"),
          "end": to_hms("00:20:00"),
          #"week_days":to_int_weekdays(["Mon", "Wed", "Fri", "Sun"]),
          "week_days":to_int_weekdays([]),
          "from_day":to_md_tuple("Jan,1"),
          "to_day":to_md_tuple("Jan,2"), #Inclusive
          "gate":0,
          "pump":0, #ignored by now
        },
        {
          "name":"arriba",
          "start": to_hms("00:00:00"),
          "end": to_hms("00:10:00"),
          #"week_days":to_int_weekdays(["Mon", "Wed", "Fri", "Sun"]),
          "week_days":to_int_weekdays([]),
          "from_day":to_md_tuple("Jan,1"),
          "to_day":to_md_tuple("Jan,2"), #Inclusive
          "gate":1,
          "pump":0, #ignored by now
        },
        ]
    return pl


def post(endpoint, payload):
    data = {'auth_token':AUTH_TOKEN,
            'payload':payload}
    headers = {'content-type': 'application/json'}
    r = requests.post(URL_BASE + endpoint,
                      data=json.dumps(data),
                      headers=headers)
    return r

def get(endpoint, params=''):
    return requests.get(URL_BASE + endpoint + params)


def test_task_list():
    endpoint = 'tasks'
    r = requests.get(URL_BASE + endpoint)
    print(r.text)
    post(endpoint, build_task_list())


def send_task_list(task_list):
    endpoint = 'tasks'
    r1 = requests.get(URL_BASE + endpoint)
    r2 = post(endpoint, task_list)
    print(r1.text, r2.text)
#     print(r1.json(), r2.json())


def verify_time(threshold=10):
    endpoint = 'time'
    get_remote_t = lambda: tuple(get(endpoint).json())
    mktime = lambda t: time.mktime(t + (0,)) #add missing tm_isdst=0
    localtime = lambda: time.localtime()[:8] # remove tm_isdst=0
    remote_t = get_remote_t()
    local_t = localtime()
    if abs(mktime(local_t) - mktime(remote_t)) > threshold:
        post(endpoint, local_t)
        remote_t = get_remote_t()
        assert abs(mktime(local_t) - mktime(remote_t)) < threshold, f'local={local_t}, device={remote_t}'
        print(f'Device time updated to {remote_t}')
    else:
        print(f'Device time is correct {remote_t}')


def trigger_tasks(*names):
    endpoint = 'manual'
    r1 = get(endpoint)
    r2 = post(endpoint, names)
#     print(r1.json(), r2.json())
    print(r1.text)
    print(r2.text)
    return r2


def test_auth_token():
    endpoint = 'auth'
    r = get(endpoint)
    print(r.text)
#     post(endpoint, '123456')


def stop_tasks(*names):
    endpoint = 'stop'
    if not names:
        payload = {'stop_all':True}
    else:
        payload = {'stop_all':False, 'names':names}
    r = post(endpoint, payload)
    print(r.text)


def main():
    pass
#     pprint(build_task_list())
#     test_task_list()
#     test_auth_token()
#     verify_time()
#     send_task_list(build_task_list())
#     send_task_list([])
#     trigger_tasks(('abajo', dict(duration=2*60)))
#     time.sleep(12)
#     stop_tasks('arriba')
# 
#     time.sleep(12)
    stop_tasks('abajo')


#     stop_tasks()


if __name__ == '__main__':
    main()
