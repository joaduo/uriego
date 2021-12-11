import requests
import json
import time


URL_BASE='http://192.168.4.1/'
AUTH_TOKEN='123456'

def get_payload():
    pl = [
        { 
          "name":"test",
          "start":"00:00:00",
          "end":"00:00:40",
          "week_days":["Mon", "Wed", "Fri", "Sun"],
          "from_day":"Dic,1", "to_day":"Jan,2",
          "gate":1,
          "pump":1
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
    print(r.text)

def test_task_list():
    endpoint = 'task_list'
    r = requests.get(URL_BASE + endpoint)
    print(r.text)
    post(endpoint, get_payload())


def test_time():
    endpoint = 'time'
    r = requests.get(URL_BASE + endpoint)
    print(r.json())


    senttime = list(time.localtime())[:8]
    print(senttime)
    #Convert (time.localtime output)
    #(year, month, mday, hour, minute, second, weekday, yearday)
    # to (RTC datetime args)
    # https://docs.micropython.org/en/latest/library/machine.RTC.html#machine.RTC.datetime
    #(year, month, day, weekday, hours, minutes, seconds, [subseconds])
    senttime = tuple(senttime[0:3] + senttime[6:7] + senttime[3:6] + [0])
    #print(senttime)
    post(endpoint, senttime)
    r = requests.get(URL_BASE + endpoint)
    print(r.json())


def test_auth_token():
    endpoint = 'auth_token'
    r = requests.get(URL_BASE + endpoint)
    print(r.text)
#     post(endpoint, '123456')


def main():
#     test_task_list()
#     test_time()
    test_auth_token()


if __name__ == '__main__':
    main()
