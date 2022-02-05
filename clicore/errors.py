class CommandError(Exception):
    pass

class FlagError(CommandError):
    pass

class CommandNotFound(CommandError):
    pass

class CommandAlreadyRegistered(CommandError):
    pass


