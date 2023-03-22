#!/usr/bin/python3
#
# Written by Mariusz Banach <mb@binary-offensive.com>, @mariuszbit / mgeeky
#

import sys
import os
import colorama
import atexit

try:
    colorama.init()
except:
    pass

class Logger:
    options = {
        'debug': False,
        'verbose': False,
        'nocolor' : False,
        'force_stdout' : False,
        'log': sys.stderr,
        'colorPlaceholders' : False,
    }

    DefaultColor = 'white'

    colors_map = {
        'red':      colorama.Fore.RED, 
        'green':    colorama.Fore.GREEN, 
        'yellow':   colorama.Fore.YELLOW,
        'blue':     colorama.Fore.BLUE, 
        'magenta':  colorama.Fore.MAGENTA, 
        'cyan':     colorama.Fore.CYAN,
        'white':    colorama.Fore.WHITE, 
        'grey':     colorama.Fore.WHITE,
        'reset':    colorama.Style.RESET_ALL,
    }

    colors_dict = {
        'error': 'red',
        'fatal': 'red',
        'info' : DefaultColor,
        'debug': 'magenta',
        'other': 'grey',
        'normal' : DefaultColor
    }

    def __init__(self, opts = None):
        self.options.update(Logger.options)

        if opts is not None and len(opts) > 0:
            self.options.update(opts)

    @staticmethod
    def with_color(c, s):
        return c + s + Logger.colors_map['reset']

    @staticmethod
    def colorize(txt, col):
        if Logger.options['nocolor'] or len(col) == 0:
            return txt
            
        if not col in Logger.colors_map.keys():
            col = Logger.DefaultColor

        if os.environ.get('RMF_COLORS_TO_PLACEHOLDERS', '') == '1':
            return f'__COLOR_{col}__|{txt}|__END_COLOR__'

        return Logger.with_color(Logger.colors_map[col], txt)

    @staticmethod
    def replaceColors(s0):
        pos = 0
        s = s0

        while pos < len(s):
            if s[pos:].startswith('__COLOR_'):
                pos += len('__COLOR_')
                pos1 = s[pos:].find('__|')

                assert pos1 != -1, "Output colors mismatch - could not find pos of end of color number!"

                col = s[pos:pos+pos1]
                pos += pos1 + len('__|')

                patt = f'__COLOR_{col}__|'
                colored = Logger.colors_map[col]

                s = s.replace(patt, colored)
                pos = 0
                continue

            pos += 1

        s = s.replace('|__END_COLOR__', Logger.colors_map['reset'])

        return s

    @staticmethod
    def colorize_prefix(txt, **kwargs):
        n = 0
        ls = txt[:len(txt) - len(txt.lstrip())]
        txt = txt.lstrip()

        if len(txt) > n+4 and txt[n+0] == '[' and txt[n+2] == ']' and txt[n+3] == ' ':
            if 'color' not in kwargs.keys() or kwargs['color'] == '' or kwargs['color'] == 'none':
                if 'nocolor' not in kwargs.keys() or not kwargs['nocolor']:
                    aux = Logger.DefaultColor

                    if   txt[n+1] == '.': aux = 'cyan'
                    elif txt[n+1] == '+': aux = 'green'
                    elif txt[n+1] == '-': aux = 'red'
                    elif txt[n+1] == '!': aux = 'red'
                    elif txt[n+1] == '?': aux = 'yellow'
                    elif txt[n+1] == '>': aux = 'blue'
                    elif txt[n+1] == '#': aux = 'magenta'

                    txt = Logger.colors_map[aux] + txt[:n+3] + Logger.colors_map['reset'] + txt[n+3:]
        
        return ls + txt

    @staticmethod
    def mode_translate(mode):
        mode = mode.lower().strip()
        if mode == 'info':
            return '.'
        elif mode == 'debug':
            return '#'
        elif mode == 'error':
            return '-'
        elif mode == 'fatal':
            return 'fatal'
        
        return mode

    @staticmethod
    def out(txt, fd, mode='info', **kwargs):
        output = ''

        if type(txt) is not str:
            txt = str(txt)

        txt = txt.replace('\r\n', '\n')

        if txt == '\n':
            txt = ''

        lines = txt.split('\n')

        for i in range(len(lines)):
            kwargs['noPrefix'] = kwargs.get('noPrefix', False) or i > 0
            Logger._out(lines[i], fd, mode, **kwargs)

    @staticmethod
    def _out(txt, fd, mode='info', **kwargs):
        if txt is None or fd == 'none':
            return 
        elif fd is None:
            raise Exception('[ERROR] Logging descriptor has not been specified!')

        args = {
            'color': None, 
            'noprefix': False, 
            'newline': True,
            'nocolor' : False,
            'force_stdout' : False,
            'colorPlaceholders' : False,
        }
        args.update(kwargs)
            
        txt = txt.replace('\t', ' ' * 4)

        if args['colorPlaceholders']:
            txt = Logger.replaceColors(txt)

        col = ''

        if args['nocolor']:
            col = ''

        elif args['color']:
            col = args['color']

        elif mode in Logger.colors_map.keys():
            col = mode

        elif mode in Logger.colors_dict.keys():
            col = Logger.colors_dict[mode]

        prefix = ''
        if mode and mode != 'normal':
            m = Logger.mode_translate(mode)
            mode = f'[{m}] '
            prefix = mode
        
        nl = ''
        if 'newline' in args:
            if args['newline']:
                nl = '\n'

        if 'force_stdout' in args:
            fd = sys.stdout

        if 'noPrefix' in kwargs.keys() and kwargs['noPrefix']:
            prefix = ''

        line = ''

        if type(fd) == str:
            if len(txt) == 0:
                line = nl
            else:
                line = prefix + txt + nl
        else:
            if len(txt) == 0:
                line = nl
            else:
                line = prefix + txt
                
                if not args['nocolor'] and len(col) > 0:
                    if col == Logger.DefaultColor or col == '':
                        line = Logger.colorize_prefix(line)
                    else:
                        line = Logger.colorize(line, col)
                
                line += nl

        Logger.rawWrite(fd, line)

    @staticmethod
    def rawWrite(fd, line):
        if type(fd) == str:
            with open(fd, 'a', encoding='utf8') as f:
                f.write(line)
                try:
                    f.flush()
                except:
                    pass
        else:
            fd.write(line)
            try:
                fd.flush()
            except:
                pass

    # Info shall be used as an ordinary logging facility, for every desired output.
    def info(self, txt, forced = False, **kwargs):
        kwargs['nocolor'] = self.options['nocolor']
        kwargs['force_stdout'] = self.options['force_stdout']
        kwargs['colorPlaceholders'] = self.options['colorPlaceholders']

        if forced or (self.options['verbose'] or \
            self.options.get('debug',False) ) \
            or (type(self.options['log']) == str and self.options['log'] != 'none'):
            Logger.out(txt, self.options['log'], 'info', **kwargs)

    def text(self, txt, **kwargs):
        kwargs['noPrefix'] = True
        kwargs['nocolor'] = self.options['nocolor']
        kwargs['force_stdout'] = self.options['force_stdout']
        kwargs['colorPlaceholders'] = self.options['colorPlaceholders']

        #txt = Logger.colorize_prefix(txt)

        Logger.out(txt, self.options['log'], 'normal', **kwargs)

    def dbg(self, txt, **kwargs):
        if self.options.get('debug',False):
            kwargs['nocolor'] = self.options['nocolor']
            kwargs['force_stdout'] = self.options['force_stdout']
            kwargs['colorPlaceholders'] = self.options['colorPlaceholders']
            
            Logger.out(txt, self.options['log'], 'debug', **kwargs)

    def err(self, txt, **kwargs):
        kwargs['nocolor'] = self.options['nocolor']
        kwargs['force_stdout'] = self.options['force_stdout']
        kwargs['colorPlaceholders'] = self.options['colorPlaceholders']

        Logger.out(txt, self.options['log'], 'error', **kwargs)

    def fatal(self, txt, **kwargs):
        kwargs['nocolor'] = self.options['nocolor']
        kwargs['force_stdout'] = self.options['force_stdout']
        kwargs['colorPlaceholders'] = self.options['colorPlaceholders']

        Logger.out(txt, self.options['log'], 'fatal', **kwargs)
        os._exit(1)

@atexit.register
def goodbye():
    try:
        colorama.deinit()
    except:
        pass
