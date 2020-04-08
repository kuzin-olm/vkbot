from os import listdir
from os.path import basename

__f_dir = 'command'
__all__ = [basename(x)[:-3] for x in listdir(__f_dir) if x.endswith('.py') and not x.startswith('__')]

list_cmd = dict()
for x in __all__:
    x = __import__(f'{__f_dir}.{x}', globals(), locals(), x)
    list_cmd.update({x.cmd: x.main})
