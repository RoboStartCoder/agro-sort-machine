class ContainerExists(Exception):
    pass


class ContainerDoesntExists(Exception):
    pass


class ContainerParameterExists(Exception):
    pass


class ContainerParameterDoesntExists(Exception):
    pass


class ContainerNotRegistered(Exception):
    pass


class UploadNotRegistered(Exception):
    pass

class UploadTypeBroken(Exception):
    pass

class UnknownWebsocketTask(Exception):
    pass