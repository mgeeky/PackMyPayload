#!/usr/bin/python3

import os, sys, re
import argparse
import string
import random
import glob
import textwrap

import lib.packager
import lib.logger

globalOpts = {
    'verbose': True, 
    'debug': True,
    'nocolor' : False,
}


logger = lib.logger.Logger(globalOpts)

def banner():
    return '''
+      o     +              o   +      o     +              o
    +             o     +           +             o     +         +
    o  +           +        +           o  +           +          o
-_-^-^-^-^-^-^-^-^-^-^-^-^-^-^-^-^-_-_-_-_-_-_-_,------,      o
   :: PACK MY PAYLOAD (1.3.0)       -_-_-_-_-_-_-|   /\\_/\\
   for all your container cravings   -_-_-_-_-_-~|__( ^ .^)  +    +
-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-__-_-_-_-_-_-_-''  ''
+      o         o   +       o       +      o         o   +       o
+      o            +      o    ~   Mariusz Banach / mgeeky    o
o      ~     +           ~          <mb [at] binary-offensive.com>
    o           +                         o           +           +
'''

def getoptions():
    global logger
    global evasions

    formats = ''

    for a, b in lib.packager.Packager.formatsMap.items():
        formats += f'\t- {a}\n'

    epilog = f'''

=====================================================

Supported container/archive formats:

{formats}

=====================================================

'''

    usage = banner() + '\nUsage: PackMyPayload.py [options] <infile> <outfile>\n'
    opts = argparse.ArgumentParser(
        usage = usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog = textwrap.dedent(epilog)
    )

    req = opts.add_argument_group('Required arguments')
    req.add_argument('infile', help = 'Input file/directory to be packaged into output archive/container')
    req.add_argument('outfile', help = 'Output file with extension pointing at output format')

    opt = opts.add_argument_group('Options')
    opt.add_argument('-v', '--verbose', default=False, action='store_true', help='Verbose mode.')
    opt.add_argument('-d', '--debug', default=False, action='store_true', help='Debug mode.')
    opt.add_argument('-N', '--nocolor', default=False, action='store_true', help='Dont use colors in text output.')
    opt.add_argument('-i', '--backdoor', default='', type=str, help = 'Instead of generating blank new output container/archive, will backdoor existing input one.')
    opt.add_argument('-n', '--filename', default='', metavar='NAME', help='Package input file into archive/container under this filename (may contain relative path).')
    opt.add_argument('-p', '--password', default='', metavar='PASSWORD', help='If output archive/container format supports password protection, use this password to protect output file.')
    opt.add_argument('--out-format', default='', choices=lib.packager.Packager.formatsMap.keys(), help = 'Explicitely define output format disregarding output file\'s extension. Can be one of following: ' + ', '.join(lib.packager.Packager.formatsMap.keys()))
    opt.add_argument('-H', '--hide', default='', type=str, help='(Supported in ISO/IMG, ZIP) Set hidden attribute on file(s). Cannot be repeated, only comma-separated. Example: --hide icon.ico,evil.exe . Supports wildcards: --hide icon?.*')

    zipo = opts.add_argument_group('ZIP specific options')
    zipo.add_argument('--zip-noreadonly', action='store_true', help='DISABLE ZIP MOTW bypass that is used by default. By default, PackMyPayload marks Office files as Read-Only making ZIP software unable to set MOTW flag on them when extracted. This option disables that behavior.')

    vhdopts = opts.add_argument_group('VHD specific options')
    vhdopts.add_argument('--vhd-size', default=1024, type=int, metavar='SIZE', help='VHD dynamic size in MB. Default: 1024')
    vhdopts.add_argument('--vhd-letter', default='', metavar='LETTER', help='Drive letter where to mount VHD drive. Default: will pick unused one at random.')
    vhdopts.add_argument('--vhd-filesystem', default='fat32', choices=['fat','fat32','ntfs'], metavar='FS', help='Filesystem to be used while formatting VHD. Default: FAT32. Supported: fat, fat32, ntfs')
    
    args = opts.parse_args()
    globalOpts.update(vars(args))

    logger = lib.logger.Logger(globalOpts)

    if len(args.backdoor) > 0 and not os.path.isfile(args.backdoor):
        logger.fatal(f'File specifed to backdoor does not exist: {args.backdoor}')

    return args

def main(argv):
    args = getoptions()
    if not args:
        return False

    logger.text(banner())

    if not os.path.isfile(args.infile) and not os.path.isdir(args.infile):
        logger.fatal('Specified input file does not exist.')

    packager = lib.packager.Packager(logger, globalOpts)

    outputFormat = ''
    if args.out_format != '':
        outputFormat = packager.getFormat('foo.' + args.out_format)

    else:
        outputFormat = packager.getFormat(args.outfile)

    filepath, fileext = os.path.splitext(args.outfile)

    if outputFormat == '':
        logger.err(f'The expected output format {fileext} is not supported.')
        logger.err('Please use on of the following output file\'s extensions: ' + ', '.join(lib.packager.Packager.formatsMap.keys()))
        return False

    logger.text(f'[.] Packaging input file to output {fileext} ({outputFormat})...')

    if not packager.package(args.infile, args.outfile, outputFormat):
        logger.fatal('Packaging failed.')

    logger.info('Successfully packed input file.')

    logger.text(f'\n[+] Generated file written to (size: {os.path.getsize(args.outfile)}): {args.outfile}\n', color='green')

if __name__ == '__main__':
    main(sys.argv)
