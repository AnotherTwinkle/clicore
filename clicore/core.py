import os
import sys
import inspect

from . import utils
from .errors import *

class Parser:
    def __init__(self):
        self._commands = {}
        self.alias_table = {}

    def _retrive_subcommand(self, command, arguments):
        while True:
            s = command._subcommand_alias_table.get(utils.safeget(arguments, 0))
            if s is not None:
                command = command._subcommands[s]
                arguments = arguments[1:]
            else:
                break

        return (command, arguments)

    def parse(self, name, arguments):
        name = self.alias_table.get(name, None)
        if name is None:
            raise CommandNotFound(f"{command} is not a reigstered command or alias.")

        command = self._commands.get(name, None)
        command, arguments = self._retrive_subcommand(command, arguments)

        flags, args = self.parse_flags(arguments)
        ctx = Context(command= command, directory= os.getcwd())

        return command.invoke(ctx, *args, **flags)

    def run(self):
        """A high level method that handles much of the pre-parsing work for you."""

        target = utils.safeget(sys.argv, 1,  None)
        args = sys.argv[2:]

        if target is None:
            raise CommandNotProvided("No command was provided.")

        return self.parse(target, args)

    def add_command(self, command):
        if (' ') in command.name:
            raise CommandError("Command name cannot have spaces.")

        if command.name in self._commands:
            raise CommandAlreadyRegistered("This command has already been reigstered.")

        if not isinstance(command.aliases, (list, tuple)):
            raise CommandError("Command aliases must be a list or tuple.")

        for alias in command.aliases:
            if (' ') in alias:
                raise CommandError("Command aliases cannot have spaces.")
            if alias in self.alias_table:
                raise CommandAlreadyRegistered(f"The alias '{alias}' has already been registered.")

        self._commands[command.name] = command
        for alias in command.aliases:
            self.alias_table[alias] = command.name
        self.alias_table[command.name] = command.name
        return command

    def command(self, **kwargs):
        def decorator(func):
            command = Command(func, **kwargs)
            return self.add_command(command)
        return decorator

    def add_flag(self, name, **kwargs):
        def decorator(command):
            flag = Flag(name= name, **kwargs)

            if (' ') in flag.name:
                raise FlagError("Flag name cannot have spaces.")

            if not isinstance(flag.aliases, (list, tuple)):
                raise FlagError("Flag aliases must be a list or tuple.")

            for alias in flag.aliases:
                if (' ') in alias:
                    raise FlagError("Flag aliases cannot have spaces.")

            command.flags[flag.name] = flag

            for alias in flag.aliases:
                command._flag_alias_lookup_table[alias] = flag.name
            command._flag_alias_lookup_table[flag.name] = flag.name

            return command
        return decorator

    def parse_flags(self, args):
        flags, notflags = ({}, [])
        x = 0
        while x < len(args):
            arg = args[x]
            if arg.startswith('--') and len(arg) > 2: # Boolean flags.
                flags[arg[2:]] = True
            elif arg.startswith('-') and len(arg) > 1: # Store flags.
                try:
                    if args[x+1].startswith('-'):
                        raise FlagError(f'No value was provided for flag {arg}')
                    flags[arg[1:]] = args[x+1] # The next argument should be the value

                except IndexError:
                    raise FlagError(f'Unexpected end of input after flag declaration.')
                x += 1 # We will skip the next index
            else:
                notflags.append(arg)
            x += 1
        return flags, notflags

    def remove_command(self, command):
        try:
            del self._commands[command]
        except KeyError:
            return

        # Delete the alias table entries for the command
        for k, v in list(self.alias_table.items()):
            if v == command:
                del self.alias_table[k]

    def get_command(self, command):
        return self._commands.get(command, None)

    @property
    def commands(self):
        return [command for command in self._commands.values()]

class Command:
    def __init__(self, func, **kwargs):
        self.name = kwargs.get('name') or func.__name__
        self.aliases = kwargs.get('aliases') or []
        self.usage = kwargs.get('usage', None)
        self.help = func.__doc__ or None

        self.callback = func
        self.params = self.callback.__code__.co_varnames[:self.callback.__code__.co_argcount]
        self.flags = FlagDict()
        self._flag_alias_lookup_table = {}

        self.parent = kwargs.get('parent', None)
        self._subcommands = {}
        self._subcommand_alias_table = {}

    def command(self, **kwargs):
        def decorator(func):
            command = Command(func, parent = self, **kwargs)
            return self.add_subcommand(command)
        return decorator

    def add_subcommand(self, command):
        if (' ') in command.name:
            raise CommandError("Command name cannot have spaces.")

        if command.name in self._subcommands:
            raise CommandAlreadyRegistered("This command has already been reigstered.")

        if not isinstance(command.aliases, (list, tuple)):
            raise CommandError("Command aliases must be a list or tuple.")

        for alias in command.aliases:
            if (' ') in alias:
                raise CommandError("Command aliases cannot have spaces.")
            if alias in self._subcommand_alias_table:
                raise CommandAlreadyRegistered(f"The alias '{alias}' has already been registered.")

        self._subcommands[command.name] = command
        for alias in command.aliases:
            self._subcommand_alias_table[alias] = command.name
        self._subcommand_alias_table[command.name] = command.name
        return command

    def remove_subcommand(self, command):
        try:
            del self._subcommands[command]
        except KeyError:
            return None

        # Delete the alias table entries for the command
        for k, v in list(self._subcommand_alias_table.items()):
            if v == command:
                del self._subcommand_alias_table[k]

    def get_subcommand(self, name):
        return self._subcommands.get(command, None)

    @property
    def subcommands(self):
        return [scmd for scmd in self._subcommands.values()]

    def convert(self, arg, converter):
        if inspect.isclass(converter) and issubclass(converter, Converter):
            if inspect.ismethod(converter.convert):
                return converter.convert(arg)
            else:
                return converter().convert(arg)
        elif isinstance(converter, Converter):
            return converter.convert(arg)

        try:
            return converter(arg)
        except KeyError:
            raise

    def invoke(self, ctx, *args, **kwargs):
        args = dict(zip(self.params[1:], args))

        defaults = utils.get_default_args(self.callback)
        annotations = utils.get_annotated_args(self.callback)
        notpassed = [param 
                    for param in self.params 
                    if param not in args 
                    and param in defaults]

        for arg in annotations:
            try:
                args[arg] = self.convert(args[arg], annotations[arg])
            except KeyError:
                pass

        for arg in notpassed:
            args[arg] = defaults[arg]

        flags = {}
        for flag in kwargs:
            f = self._flag_alias_lookup_table.get(flag, flag)  # Retrieve the original name for the flag
            flags[f] = kwargs[flag]

        requiredflags = [flag for flag in flags if flag in self.flags]
        for flag in flags:
            if flag not in requiredflags:
                print(f'Ignoring unexpected flag: "{flag}"')

        for flag in self.flags:
            if flag not in requiredflags:
                ctx.add_flag(flag, self.flags[flag].default)
                # All flags required by the command are passed to it.
                # To see if a flag was truly passed or not by the user, check 
                # `command.flags.FLAGNAME.passed`

        for flag in requiredflags:
            type = self.flags[flag].type
            if type is not utils.MISSING:
                try:
                    flags[flag] = self.convert(flags[flag], type)
                except KeyError:
                    pass

            ctx.add_flag(flag, flags[flag])
            self.flags[flag].passed = True

        args[self.params[0]] = ctx # Context
        return self(**args)

    def __call__(self, *args, **kwargs):
        return self.callback(*args, **kwargs)

class Context:
    """An object constructed from this is passed as the first argument of all commands.
    This argument can then be used to get 'context' of the command execution, and is the only way to
    access the flags passed to the command.

    The context object also allows you to access the registered Command object of the command execution."""

    def __init__(self, command, directory, **kwargs):
        self.directory = directory
        self.command = command
        self.flags = FlagDict()

    def add_flag(self, name, value):
        self.flags[name] = value

class Converter:
    """Argument converters should subclass this."""

    def convert(self, target):
        raise NotImplementedError('Derived classes need to implement this method.')

class Flag:
    """A flag class. This does not contain the value."""

    def __init__(self, name, **kwargs):
        self.name = name
        self.default = kwargs.get('default', None)
        self.aliases = kwargs.get('aliases', [])
        self.type = kwargs.get('type', utils.MISSING)
        self.description = kwargs.get('description', None)
        self.passed = False

class FlagDict(dict):
    """This dictionary allows us to treat its items like member attirbutes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        return self[item]
