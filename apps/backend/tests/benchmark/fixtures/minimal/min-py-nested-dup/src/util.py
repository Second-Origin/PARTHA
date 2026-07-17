def outer():
    def inner():
        return 1
    return inner


def outer():
    return 2
