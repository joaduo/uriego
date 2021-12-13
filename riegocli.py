import requests
import json
import time


URL_BASE='http://192.168.4.1/'
AUTH_TOKEN='1234'

def build_task_list():
    pl = [
        { 
          "name":"test",
          "start":"00:00:00",
          "end":"00:00:40",
          "week_days":["Mon", "Wed", "Fri", "Sun"],
          "from_day":"Dic,1", "to_day":"Jan,2",
          "gate":1,
          "pump":0 #ignored by now
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
    endpoint = 'task_list'
    r = requests.get(URL_BASE + endpoint)
    print(r.text)
    post(endpoint, build_task_list())


def send_task_list(task_list):
    endpoint = 'task_list'
    r1 = requests.get(URL_BASE + endpoint)
    r2 = post(endpoint, task_list)
#     print(r1.text, r2.text)
    print(r1.json(), r2.json())


def verify_time():
    endpoint = 'time'
    get_remote_t = lambda: tuple(get(endpoint).json())
    mktime = lambda t: time.mktime(t + (0,)) #add missing tm_isdst=0
    localtime = lambda: time.localtime()[:8] # remove tm_isdst=0
    remote_t = get_remote_t()
    local_t = localtime()
    if abs(mktime(local_t) - mktime(remote_t)) > 2:
        post(endpoint, local_t)
        new_dev_time = get_remote_t()
        assert local_t == new_dev_time, f'local={local_t}, device={new_dev_time}'
    else:
        print(f'Device time is correct {remote_t}')


def trigger_task(name):
    endpoint = 'manual_task'
    r1 = get(endpoint)
    r2 = post(endpoint, [name])
    print(r1.json(), r2.json())
    return r2


def test_auth_token():
    endpoint = 'auth_token'
    r = requests.get(URL_BASE + endpoint)
    print(r.text)
#     post(endpoint, '123456')


def main():
#     test_task_list()
#     test_auth_token()
    verify_time()
    send_task_list(build_task_list())
    trigger_task('test')


if __name__ == '__main__':
    main()
