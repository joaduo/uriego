

def debug(msg, *args, **kwargs):
    info(msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    if args:
        msg = msg % args
    if kwargs:
        msg = msg.format(**kwargs)
    print(msg)

