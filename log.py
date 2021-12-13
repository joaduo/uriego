import gc


MEM_FREE_THRESHOLD=20000


def debug(msg, *args, **kwargs):
    info(msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    if args:
        msg = msg % args
    if kwargs:
        msg = msg.format(**kwargs)
    print(msg)


def garbage_collect():
    orig_free = gc.mem_free()
    if orig_free < MEM_FREE_THRESHOLD:
        print('Collecting garbage ori_free={}'.format(orig_free))
        gc.collect()
        info('Memory it was {orig_free} and now {now_free}',
                     orig_free=orig_free, now_free=gc.mem_free())
