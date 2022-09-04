import log
import ujson

_config_storage = {}
def get(*a, **kw):
    """
    Get the value of a setting
    Call get('name') to avoid setting default value
    Call get(name=default_value) to set default value 
    """
    if not((a and len(a) == 1) or (kw and len(kw) == 1, '')):
        log.error('a={} kw={}, incorrect lookup arguments', a, kw)
        raise LookupError('Bad arguments')
    if a:
        return _config_storage[a[0]]
    if kw:
        name, default_value = next(iter(kw.items()))
        return _config_storage.get(name, default_value)

def set_(**kw):
    for name, value in kw.items():
        if name in _config_storage:
            log.debug('Replacing {} = {}', name, value)
        _config_storage[name] = value

def pop(name):
    return _config_storage.pop(name)

def load(path='./config.json'):
    global _config_storage
    if file_exists(path):
        with open(path) as fp:
            log.debug('loading storage from {}', path)
            _config_storage = ujson.load(fp)
    return _config_storage

def dump(path='./config.json'):
    with open(path, 'w') as fp:
        log.debug('dumping storage to {}', path)
        ujson.dump(_config_storage, fp)

def file_exists(path):
    try:
        with open(path):
            pass
        return True
    except:
        return False
