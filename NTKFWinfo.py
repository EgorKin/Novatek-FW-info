#!/usr/bin/env python3

# ==================================================================================
# NTKFWinfo - python script for work with Novatek firmware binary files
# Show full FW info, allow extract/replace/uncompress/compress partitions, fix CRC
#
# Copyright © 2025 Dex9999(4pda.to) aka Dex aka EgorKin(GitHub, etc.)
# ==================================================================================


# I suggest use pypy3 (apt install pypy3) for speed-up LZ77 compression, not python3


# V2.0 - improve parsing, now support Viofo A139 and 70Mai A500S firmwares
# V2.1 - add LZ77 unpacker
# V3.0 - add get info about partition names from fdt(dtb) partition
# V3.1 - add MODELEXT INFO partition support
# V3.2 - initial support old firmware format (BCL1 starting partition + NVTPACK_FW_HDR)
# V3.3 - add optional start offset for -u command (uncompress partition); add -x ALL option, also start offset for -x and -u now optional (do not need set it to 0)
# V3.4 - add ZLIB uncompress support
# V3.5 - add LZMA uncompress support
# V3.6 - for -u command: if start offset not defined or 0 - auto skip CKSM header size (0x40 bytes) for CKSM partition
# V3.7 - parse UBI volume names
# V3.8 - for -u command: if start offset not defined - auto skip CKSM header size (0x40 bytes) for CKSM partition; if offset set to 0 - force use 0 (does not use auto skip)
# V3.9 - extract files from UBI via -u command using ubireader
# V4.0 - add -c command: compress partition by ID and merge to firmware file
# V4.1 - support change partition size for -c command
# V4.2 - add support CKSM<--BCL1 and BCL1 partitions for -c command
# V4.3 - add support SPARSE partitions for -u and -c command
# V4.4 - speed up LZ77 uncompress
# V4.5 - add LZ compression for -c command; now support -u & -c for old firmware format; another temp folders struct for SPARSE partitions
# V4.6 - show progress bar and elapsed time for LZ77 compression process
# V4.7 - BCL1 partitions CRC support
# V4.8 - add -o option for define working dir for output partitions
# V4.9 - add banner; pre-release version
# V5.0 - private release
# V5.1 - add FDT(DTB) partition uncompress/compress support
# V5.2 - BCL1 LZ77 compatibility improvements, BCL1 LZMA DictionarySize support WIP
# V5.3 - fix -x ALL (all partitions extraction)
# V5.4 - fix additional characters in filenames support
# V5.5 - add -udtb and -cdtb for convert DTB file to DTS file for easy view/edit application.dtb file with sensor settings and vice versa
# V5.6 - print some additional info while unpack BCL1 partitions
# V5.7 - make_ext4 is not need anymore and deprecated in modern distributives, move to img2simg
# V5.8 - Fix CRC for uncompressed data partition before compress it to BCL1 partition if it is required
# V5.9 - fix datetime.fromtimestamp() calls in actual Python versions
# V6.0 - unassign uboot partition findings from partID=3. Add 'ARM Trusted Firmware-A' partition support
# V6.1 - initial support of 'Multi-File Images' type for uImage partitions
# V6.2 - for ARM64 rootfs partition only (part name "rootfs" is hardcoded now): change compressior algo from "lzo" to "favor_lzo" to be more closer to original partition size than with "lzo". Add "sudo" to exec cmds for UBI partitions to be sure in right file permissions.
# V6.3 - output filename is optional now for -udtb/-cdtb commands (replace extension to .dts/.dtb in input filename if output filename is not defined)

CURRENT_VERSION = '6.3'

import os, struct, sys, argparse, array
from datetime import datetime, timezone
import zlib
import lzma
import subprocess
import platform


in_file = ''
in_offset = 0
out_file = ''

part_startoffset = array.array('I')
part_endoffset = array.array('I')
part_size = array.array('I')
part_id = array.array('I')
part_type = []
part_crc = array.array('I')
part_crcCalc = array.array('I')


# для данных из dbt партиции о соответствии idx - имени_партиции - имени_файла_партиции
dtbpart_ID = []
dtbpart_name = []
dtbpart_filename = []

is_ARM64 = 0 # unknown by default, flag for apply favor_lzo compression algo in UBI rootfs partition

# defines from uboot source code
uImage_os = {
    0 : 'Invalid OS',
    1 : 'OpenBSD',
    2 : 'NetBSD',
    3 : 'FreeBSD',
    4 : '4.4BSD',
    5 : 'LINUX',
    6 : 'SVR4',
    7 : 'Esix',
    8 : 'Solaris',
    9 : 'Irix',
    10: 'SCO',
    11: 'Dell',
    12: 'NCR',
    13: 'LynxOS',
    14: 'VxWorks',
    15: 'pSOS',
    16: 'QNX',
    17: 'Firmware',
    18: 'RTEMS',
    19: 'ARTOS',
    20: 'Unity OS',
    21: 'INTEGRITY',
    22: 'OSE',
    23: 'Plan 9',
    24: 'OpenRTOS',
    25: 'ARM Trusted Firmware',
    26: 'Trusted Execution Environment',
    27: 'RISC-V OpenSBI',
    28: 'EFI Firmware (e.g. GRUB2)'
}

uImage_arch = {
    0 : 'Invalid CPU',
    1 : 'Alpha',
    2 : 'ARM',
    3 : 'Intel x86',
    4 : 'IA64',
    5 : 'MIPS',
    6 : 'MIPS 64 Bit',
    7 : 'PowerPC',
    8 : 'IBM S390',
    9 : 'SuperH',
    10: 'Sparc',
    11: 'Sparc 64 Bit',
    12: 'M68K',
    13: 'Nios-32',
    14: 'MicroBlaze',
    15: 'Nios-II',
    16: 'Blackfin',
    17: 'AVR32',
    18: 'STMicroelectronics ST200',
    19: 'Sandbox architecture (test only)',
    20: 'ANDES Technology - NDS32',
    21: 'OpenRISC 1000',
    22: 'ARM64',
    23: 'Synopsys DesignWare ARC',
    24: 'AMD x86_64, Intel and Via',
    25: 'Xtensa',
    26: 'RISC-V'
}

uImage_imagetype = {
    0 : 'Invalid Image',
    1 : 'Standalone Program',
    2 : 'OS Kernel Image',
    3 : 'RAMDisk Image',
    4 : 'Multi-File Image',
    5 : 'Firmware Image',
    6 : 'Script file',
    7 : 'Filesystem Image (any type)',
    8 : 'Binary Flat Device Tree Blob',
    9 : 'Kirkwood Boot Image',
    10: 'Freescale IMXBoot Image'
}

uImage_compressiontype = {
    0 : 'No',
    1 : 'gzip',
    2 : 'bzip2',
    3 : 'lzma',
    4 : 'lzo',
    5 : 'lz4',
    6 : 'zstd'
}


# defines from PartitionInfo.h Novatek SDK source code
embtypes = {
    0x00 : 'UNKNOWN',
    0x01 : 'UITRON',
    0x02 : 'ECOS',
    0x03 : 'UBOOT',
    0x04 : 'LINUX',
    0x05 : 'DSP',
    0x06 : 'PSTORE',
    0x07 : 'FAT',
    0x08 : 'EXFAT',
    0x09 : 'UBIFS',
    0x0A : 'RAMFS',
    0x0B : 'UENV'     # u-boot environment data
}

# Basic Compression Library compress algos
compressAlgoTypes = {
    0x01 : 'RLE',
    0x02 : 'HUFFMAN',
    0x03 : 'RICE8',
    0x04 : 'RICE16',
    0x05 : 'RICE32',
    0x06 : 'RICE8S',
    0x07 : 'RICE16S',
    0x08 : 'RICE32S',
    0x09 : 'LZ',
    0x0A : 'SF',
    0x0B : 'LZMA',
    0x0C : 'ZLIB'
}


def ShowInfoBanner():
    print("===================================================================================")
    print("  \033[92mNTKFWinfo\033[0m - python script for work with Novatek firmware binary files. Ver. %s" % (CURRENT_VERSION))
    print("  Show full FW \033[93mi\033[0mnfo, allow e\033[93mx\033[0mtract/\033[93mr\033[0meplace/\033[93mu\033[0mncompress/\033[93mc\033[0mompress partitions, \033[93mfixCRC\033[0m")
    print("")
    print("  Copyright © 2025 \033[93mDex9999\033[0m(4pda.to) aka \033[93mDex\033[0m aka \033[93mEgorKin\033[0m(GitHub, etc.)")
    print("  If you like this project or use it with commercial purposes please donate some")
    print("  \033[93mBTC\033[0m to: \033[92m12q5kucN1nvWq4gn5V3WJ8LFS6mtxbymdj\033[0m")
    print("===================================================================================")


def get_args():
    global in_file
    global is_extract
    global is_uncompress
    global is_compress
    global is_silent
    global workdir

    p = argparse.ArgumentParser(add_help=True, description='')
    p.add_argument('-i',metavar='filename', nargs=1, help='input file')
    p.add_argument('-x',metavar=('partID', 'offset'), nargs='+', help='extract partition by ID with optional start offset or all partitions if partID set to \"ALL\"')
    p.add_argument('-r',metavar=('partID', 'offset', 'filename'), nargs=3, help='replace partition by ID with start offset using input file')
    p.add_argument('-u',metavar=('partID', 'offset'), type=int, nargs='+', help='uncompress partition by ID with optional start offset')
    p.add_argument('-c',metavar=('partID'), type=int, nargs=1, help='compress partition by ID to firmware input file and fixCRC')
    p.add_argument('-udtb',metavar=('DTB_filename', 'DTS_filename'), nargs='+', help='convert DTB to DTS file')
    p.add_argument('-cdtb',metavar=('DTS_filename', 'DTB_filename'), nargs='+', help='convert DTS to DTB file')
    p.add_argument('-fixCRC', action='store_true', help='fix CRC values for all possible partitions and whole FW file')
    p.add_argument('-silent', action='store_true', help='do not print messages, except errors')
    p.add_argument('-o',metavar='outputdir', nargs=1, help='set working dir')

    if len(sys.argv) < 3:
        ShowInfoBanner()
        p.print_help(sys.stderr)
        sys.exit(1)

    args=p.parse_args(sys.argv[1:])

    if args.o:
        workdir = args.o[0]
        if not os.path.exists(workdir):
            os.system('mkdir ' + '\"' + workdir + '\"')
    else:
        workdir = ''
    
    if args.x:
        #если offset = ALL - извлекаем все партиции
        if (args.x[0] == 'all') | (args.x[0] == 'ALL'):
            is_extract_all = 1
            is_extract_offset = 0
            is_extract = 0xFF
        else:
            is_extract_all = 0
            is_extract = int(args.x[0])
            # если задан 2ой аргумент - offset
            if len(args.x) == 2:
                is_extract_offset = int(args.x[1])
            else:
                # если offset не задан - далее исправим на 0
                is_extract_offset = -1
    else:
        is_extract = -1
        is_extract_offset = -1
        is_extract_all = 0

    if args.r:
        is_replace = int(args.r[0])
        is_replace_offset = int(args.r[1])
        is_replace_file = str(args.r[2])
    else:
        is_replace = -1
        is_replace_offset = -1
        is_replace_file = ''

    if args.u:
        is_uncompress = args.u[0]
        # если задан 2ой аргумент - offset
        if len(args.u) == 2:
            is_uncompress_offset = int(args.u[1])
        else:
            # если offset не задан - то будет -1 для того чтобы дальше присвоить либо 0x40 (для CKSM) либо 0 (в остальных случаях)
            is_uncompress_offset = -1
    else:
        is_uncompress = -1
        is_uncompress_offset = -1

    if args.udtb:
        if len(args.udtb) == 2:
            uncompressDTB(args.udtb[0], args.udtb[1])
        else:
            uncompressDTB(args.udtb[0])
        exit(0)

    if args.cdtb:
        if len(args.cdtb) == 2:
            compressToDTB(args.cdtb[0], args.cdtb[1])
        else:
            compressToDTB(args.cdtb[0])
        exit(0)

    if args.c:
        is_compress = args.c[0]
    else:
        is_compress = -1

    if args.fixCRC:
        fixCRC_partID = 1
    else:
        fixCRC_partID = -1

    if args.silent:
        is_silent = 1
    else:
        is_silent = -1

    in_file=args.i[0]

    return (in_file, is_extract, is_extract_offset, is_extract_all, is_replace, is_replace_offset, is_replace_file, is_uncompress, is_uncompress_offset, is_compress, fixCRC_partID)



def MemCheck_CalcCheckSum16Bit(input_file, in_offset, uiLen, ignoreCRCoffset):
    uiSum = 0
    pos = 0
    num_words = uiLen // 2
    
    fin = open(input_file, 'rb')
    fin.seek(in_offset, 0)
    fread = fin.read(uiLen)
    fin.close()
    
    #читаем по 2 байта в little endian
    for chunk in struct.unpack("<%sH" % num_words, fread[0:num_words*2]):
        if pos*2 != ignoreCRCoffset:
            uiSum += chunk + pos
        else:
            uiSum += pos
        pos+=1
        #print('read=0x%04X' % chunk)
        #print('pos=%i' % pos)
        #print('or 0x%08X' % struct.unpack('>H', read)[0])
        #print('CRC=0x%08X' % uiSum)
        

    #print('CRC=0x%08X' % uiSum)
    uiSum = uiSum & 0xFFFF
    uiSum = (~uiSum & 0xFFFF) + 1
    #print('Final CRC=0x%08X' % uiSum)

    return uiSum



def compress_CKSM_UBI(part_nr, in2_file):
    global in_file, is_ARM64

    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)
    FourCC = fin.read(4)

    if FourCC != b'CKSM':
        print('\033[91mNot CKSM partition, exit\033[0m')
        exit(0)

    # skip CKSM header
    fin.seek(part_startoffset[part_nr] + 0x40, 0)

    FourCC = fin.read(4)
    if FourCC != b'UBI#':
        print('\033[91mNot UBI# into CKSM partition, exit\033[0m')
        exit(0)

    # для UBI на вход должна подаваться папка партиции, а не файл
    if not os.path.exists(in2_file):
        print('\033[91m%s folder does not found, exit\033[0m' % in2_file)
        exit(0)

    # extract UBI partition to tempfile
    fin.seek(part_startoffset[part_nr] + 0x40, 0)
    finread = fin.read(part_size[part_nr] - 0x40)
    fin.close()
    fpartout = open(in2_file + '/tempfile', 'w+b')
    fpartout.write(finread)
    fpartout.close()

    # delete temp dir for info - ubireader require clear folder
    subprocess.run('rm -rf ' + '\"' + in2_file + '/tempdir' + '\"', shell=True)

    # get info about UBI to compressing script
    subprocess.check_output('ubireader_utils_info ' + '-o ' + '\"' + in2_file + '/tempdir' + '\"' + ' ./' + '\"' + in2_file + '/tempfile' + '\"', shell=True)

    # delete tempfile
    subprocess.run('rm ' + '\"' + in2_file + '/tempfile' + '\"', shell=True)
    
    # получим имя папки в которую была распакована партиция (пока я видел чисто цифровые имена, тоже что и image_seq -Q в выводе ubireader_utils_info)
    d = os.popen('(cd ' + '\"' + in2_file + '\"' + '&& find -maxdepth 1 -wholename "./*" -not -wholename "./temp*" -type d)').read()

    # проверим что нашли
    if not os.path.exists(in2_file + d[1:-1]):
        print('\033[91mNo input valid folder in %s found, exit\033[0m' % in2_file)
        exit(0)

    # d[2:-1] уберем ./ в начале и новую строку в конце имени папки
    d = d[2:-1]

    # fix ini-file: delete line "vol_flags=0" it cause error "unknown flags"
    subprocess.run('(cd ' + '\"' + in2_file + '/tempdir/tempfile/img-' + d + '\"' + ' && sed -i "/vol_flags = 0/d" img-' + d + '.ini)', shell=True)

    # fix .sh file for ARM64 rootfs partition only: change compressior algo from "lzo" to "favor_lzo" to be more closer to original partition size than with "lzo"
    if (is_ARM64 == 1):
        # Т.к. UBIname я нигде не храню, сделал проверку по pratition type
        if dtbpart_name[part_id[part_nr]][:6] == 'rootfs':
            #print('Use favor_lzo instead lzo')
            subprocess.run('(cd ' + '\"' + in2_file + '/tempdir/tempfile/img-' + d + '\"' + ' && sed -i "s/-x lzo/-x favor_lzo/" create_ubi_img-' + d + '.sh)', shell=True)

    # run compilation dir to ubi script
    subprocess.run('(cd ' + '\"' + in2_file + '/tempdir/tempfile/img-' + d + '\"' + ' && sudo ./create_ubi_img-' + d + '.sh ../../../' + d + '/*)', shell=True)

    # hide output print
    global is_silent
    is_silent = 1

    # replace partition
    partition_replace(part_id[part_nr], 0x40, in2_file + '/tempdir/tempfile/img-' + d + '/img-' + d + '.ubi')

    # delete temp dir for info
    subprocess.run('rm -rf ' + '\"' + in2_file + '/tempdir' + '\"', shell=True)

    # fix CRC
    is_silent = 0
    fixCRC(part_id[part_nr])



def compress_CKSM_BCL(part_nr, in2_file):
    global in_file

    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)
    FourCC = fin.read(4)

    if FourCC != b'CKSM':
        print('\033[91mNot CKSM partition, exit\033[0m')
        exit(0)

    # skip CKSM header
    fin.seek(part_startoffset[part_nr] + 0x40, 0)

    FourCC = fin.read(4)
    if FourCC != b'BCL1':
        print('\033[91mNot BCL1 into CKSM partition, exit\033[0m')
        exit(0)

    # для BCL1 на вход должен подаваться файл
    if not os.path.isfile(in2_file):
        print('\033[91m%s file does not found, exit\033[0m' % in2_file)
        exit(0)

    # compress uncomp_partitionID to comp_partitionID
    BCL1_compress(part_nr, 0x40, in2_file)

    comp_filename = in2_file.replace('uncomp_partitionID', 'comp_partitionID')
    # проверим прошла ли упаковка успешно
    if not os.path.isfile(comp_filename):
        print('\033[91m%s compressed partition file does not found, exit\033[0m' % comp_filename)
        exit(0)

    # hide output print
    global is_silent
    is_silent = 1

    # replace partition
    partition_replace(part_id[part_nr], 0x40, comp_filename)

    # delete comp_partitionID file
    subprocess.run('rm -rf ' + '\"' + comp_filename + '\"', shell=True)
    
    # fix CRC for CKSM
    is_silent = 0
    fixCRC(part_id[part_nr])



def compress_CKSM_SPARSE(part_nr, in2_file):
    global in_file

    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)
    FourCC = fin.read(4)

    if FourCC != b'CKSM':
        print('\033[91mNot CKSM partition, exit\033[0m')
        exit(0)

    # skip CKSM header
    fin.seek(part_startoffset[part_nr] + 0x40, 0)

    FourCC = fin.read(4)
    if struct.unpack('>I', FourCC)[0] != 0x3AFF26ED:
        print('\033[91mNot SPARSE into CKSM partition, exit\033[0m')
        exit(0)

    # для SPARSE на вход должна подаваться папка партиции, а не файл
    if not os.path.exists(in2_file):
        print('\033[91m%s folder does not found, exit\033[0m' % in2_file + '/mount')
        exit(0)

    # для сборки SPARSE нужно знать размер tempfile.ext4
    if not os.path.isfile(in2_file + '/tempfile.ext4'):
        print('\033[91m%s file does not found, exit\033[0m' % in2_file + '/tempfile.ext4')
        exit(0)

    # run compilation dir to SPARSE EXT4 cmd
    # "make_ext4fs" is deprecated now
    #os.popen('make_ext4fs -s -l ' + str(os.path.getsize(in2_file + '/tempfile.ext4')) + ' ' + '\"' + in2_file + '/tempSPARSEfile' + '\"' + ' ' + '\"' + in2_file + '/mount' + '\"').read()

    # umount - it is mean that we updates tempfile.ext4 file depend on current /mount folder
    subprocess.run('umount -d -f ' + '\"' + in2_file + '/mount' + '\"', shell=True)

    # convert ext4 to SPARSE
    subprocess.run('img2simg ' + '\"' + in2_file + '/tempfile.ext4' + '\"' + ' ' + '\"' + in2_file + '/tempSPARSEfile' + '\"', shell=True)

    # hide output print
    global is_silent
    is_silent = 1

    # replace partition
    partition_replace(part_id[part_nr], 0x40, in2_file + '/tempSPARSEfile')

    # удалим всю директорию
    # delete tempfile & tempfile.ext4 & tempSPARSEfile
    os.system('rm -rf ' + '\"' + in2_file + '\"')

    # fix CRC
    is_silent = 0
    fixCRC(part_id[part_nr])



def compress_BCL(part_nr, in2_file):
    global in_file

    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)

    FourCC = fin.read(4)
    if FourCC != b'BCL1':
        print('\033[91mNot BCL1 partition, exit\033[0m')
        exit(0)

    # для BCL1 на вход должен подаваться файл
    if not os.path.isfile(in2_file):
        print('\033[91m%s file does not found, exit\033[0m' % in2_file)
        exit(0)

    # compress uncomp_partitionID to comp_partitionID
    BCL1_compress(part_nr, 0, in2_file)

    comp_filename = in2_file.replace('uncomp_partitionID', 'comp_partitionID')
    # проверим прошла ли упаковка успешно
    if not os.path.isfile(comp_filename):
        print('\033[91m%s compressed partition file does not found, exit\033[0m' % comp_filename)
        exit(0)

    # hide output print
    global is_silent
    is_silent = 1

    # replace partition
    partition_replace(part_id[part_nr], 0, comp_filename)

    # delete comp_partitionID file
    subprocess.run('rm -rf ' + '\"' + comp_filename + '\"', shell=True)
    
    # fix CRC
    is_silent = 0
    fixCRC(part_id[part_nr])



def compress_FDT(part_nr, in2_file):
    global in_file
    
    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)

    FourCC = fin.read(4)
    if struct.unpack('>I', FourCC)[0] != 0xD00DFEED:
        print('\033[91mNot FDT(DTB) partition, exit\033[0m')
        exit(0)

    # для FDT(DTB) на вход должен подаваться файл
    if not os.path.isfile(in2_file):
        print('\033[91m%s file does not found, exit\033[0m' % in2_file)
        exit(0)

    # compress uncomp_partitionID to comp_partitionID
    comp_filename = in2_file.replace('uncomp_partitionID', 'comp_partitionID')
    os.system('dtc -qq -I dts -O dtb ' + '\"' + in2_file + '\"' + ' -o ' + '\"' + comp_filename + '\"')

    # проверим прошла ли упаковка успешно
    if not os.path.isfile(comp_filename):
        print('\033[91m%s compressed partition file does not found, exit\033[0m' % comp_filename)
        exit(0)

    # hide output print
    global is_silent
    is_silent = 1

    # replace partition
    partition_replace(part_id[part_nr], 0, comp_filename)
    
    # delete comp_partitionID file
    subprocess.run('rm -rf ' + '\"' + comp_filename + '\"', shell=True)

    # fix CRC
    is_silent = 0
    fixCRC(part_id[part_nr])



def compress(part_nr, in2_file):
    global in_file

    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)
    FourCC = fin.read(4)

    if FourCC == b'CKSM':
        # skip CKSM header
        fin.seek(part_startoffset[part_nr] + 0x40, 0)
        FourCC = fin.read(4)

        # CKSM<--UBI#
        if FourCC == b'UBI#':
            fin.close()
            compress_CKSM_UBI(part_nr, in2_file)
            return

        # CKSM<--BCL1
        if FourCC == b'BCL1':
            fin.close()
            compress_CKSM_BCL(part_nr, in2_file)
            return

        # CKSM<--SPARSE EXT4 image
        if struct.unpack('>I', FourCC)[0] == 0x3AFF26ED:
            fin.close()
            compress_CKSM_SPARSE(part_nr, in2_file)
            return
    else:
        # BCL1
        if FourCC == b'BCL1':
            fin.close()
            compress_BCL(part_nr, in2_file)
            return

        # FDT(DTB)
        if struct.unpack('>I', FourCC)[0] == 0xD00DFEED:
            fin.close()
            compress_FDT(part_nr, in2_file)
            return

    print("\033[91mThis partition type is not supported for compression\033[0m")
    exit(0)



def BCL1_compress(part_nr, in_offset, in2_file):
    global in_file

    fin = open(in_file, 'rb')

    # check BCL1 marker at start of partition    
    fin.seek(part_startoffset[part_nr] + in_offset, 0)
    FourCC = fin.read(4)
    if FourCC != b'BCL1':
        print("\033[91mBCL1 marker not found, exit\033[0m")
        sys.exit(1)

    # skip old CRC 2 bytes
    oldCRC = fin.read(2)

    # check compression algo
    Algorithm = struct.unpack('>H', fin.read(2))[0]

    if (Algorithm != 0x09) & (Algorithm != 0x0B) & (Algorithm != 0x0C):
        print("\033[91mCompression algo %0X is not supported\033[0m" % Algorithm)
        sys.exit(1)

    # read LZMA Dictionary size - 4 байта в заголовке LZMA
    if (Algorithm == 0x0B):
        fin.seek(part_startoffset[part_nr] + in_offset + 0x11, 0)
        LZMA_DictSize = struct.unpack('<I', fin.read(4))[0]
        LZMA_UncompSize1 = struct.unpack('<I', fin.read(4))[0]
        LZMA_UncompSize2 = struct.unpack('<I', fin.read(4))[0]
        
    out = in2_file.replace('uncomp_partitionID', 'comp_partitionID')


    fin.close()
    fin = open(in2_file, 'rb')
    dataread = bytearray(fin.read())
    fin.close()

    # с BCL1 в плане CRC всё интересно - есть CRC в заголовке BCL1 по смещению 0x4 который расчитывается в самом конце уже после сжатия данных
    # а ещё есть CRC несжатых данных:
    #   если по смещению 0x6C лежат FFFF а по 0x46C лежат 55AA то CRC_offset = 0x46E- изменил это из-за Viofo FW139, ввел доп. условие
    # а если по смещению 0x6C лежат 55AA то CRC_offset = 0x6E
    # а еще может быть в самом начале файла 0x100 байт данных из-за которых по смещению 0x16C лежат 55AA и CRC_offset = 0x16E
    #
    # иначе в файле прошивки нет CRC для несжатых данных
    # Если он есть то этот CRC нужно расчитать и записать до того как начать сжатие в BCL1
    if (dataread[0x6C] == 0xFF) & (dataread[0x6D] == 0xFF) & (dataread[0x46C] == 0x55) & (dataread[0x46D] == 0xAA):
        newCRC = MemCheck_CalcCheckSum16Bit(in2_file, 0, len(dataread), 0x46E)
        oldCRC = (dataread[0x46F]<<8)|dataread[0x46E]
        if is_silent != 1:
            if oldCRC != newCRC:
                print('Uncompressed data partitionID %i at \033[94m0x%04X\033[0m: ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (part_id[part_nr], 0x46E, oldCRC, newCRC))
            else:
                print('Uncompressed data partitionID %i at \033[94m0x%04X\033[0m: ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (part_id[part_nr], 0x46E, oldCRC, newCRC))
        dataread[0x46E] = (newCRC & 0xFF)
        dataread[0x46F] = ((newCRC >> 8) & 0xFF)
    else:
        if (dataread[0x6C] == 0x55) & (dataread[0x6D] == 0xAA):
            newCRC = MemCheck_CalcCheckSum16Bit(in2_file, 0, len(dataread), 0x6E)
            oldCRC = (dataread[0x6F]<<8)|dataread[0x6E]
            if is_silent != 1:
                if oldCRC != newCRC:
                    print('Uncompressed data partitionID %i at \033[94m0x%04X\033[0m: ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (part_id[part_nr], 0x6E, oldCRC, newCRC))
                else:
                    print('Uncompressed data partitionID %i at \033[94m0x%04X\033[0m: ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (part_id[part_nr], 0x6E, oldCRC, newCRC))
            dataread[0x6E] = (newCRC & 0xFF)
            dataread[0x6F] = ((newCRC >> 8) & 0xFF)
        else:
            # для Viofo A139 Pro появилось вот такое ещё условие
            if (dataread[0x16C] == 0x55) & (dataread[0x16D] == 0xAA):
                newCRC = MemCheck_CalcCheckSum16Bit(in2_file, 0, len(dataread), 0x16E)
                oldCRC = (dataread[0x16F]<<8)|dataread[0x16E]
                if is_silent != 1:
                    if oldCRC != newCRC:
                        print('Uncompressed data partitionID %i at \033[94m0x%04X\033[0m: ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (part_id[part_nr], 0x16E, oldCRC, newCRC))
                    else:
                        print('Uncompressed data partitionID %i at \033[94m0x%04X\033[0m: ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (part_id[part_nr], 0x16E, oldCRC, newCRC))
                dataread[0x16E] = (newCRC & 0xFF)
                dataread[0x16F] = ((newCRC >> 8) & 0xFF)

    # LZ77 compress
    if Algorithm == 0x09:
        # размер в байтах сжимаемых данных
        insize = len(dataread)

        # temporary buffer (internal working buffer), which must be able to hold (insize+65536) unsigned integers
        work = []
        for a in range(65536 + insize):
            work.append(0x00000000)

        # Build a "jump table"
        for i in range(65536):
            work[ i ] = 0xffffffff
        for i in range(insize-1):
            symbols = ((dataread[i]) << 8) | (dataread[i+1])
            index = work[ symbols ]
            work[ symbols ] = i
            work[ 65536 + i ] = index

        work[ 65536 + insize-1 ] = 0xffffffff


        # найдем наименее встречающийся байт среди сжимаемых данных
        # он будет маркером т.к. маркер кодируется 2 байтами то чем меньше таких символов тем лучше сжатие
        histogram = []
        for a in range(256):
            histogram.append(0)
        for a in range(len(dataread)):
            histogram[int(dataread[a])] += 1
        marker = histogram.index(min(histogram))
        #print("new marker byte = 0x%02X" % marker)


        fout = open(out, 'w+b')
        fout.write(struct.pack('>I', 0x42434C31)) # write BCL1
        fout.write(struct.pack('<H', 0x0000)) # write new CRC, unknown now - rewrite on step 2 after compression
        fout.write(struct.pack('>H', Algorithm)) # write Algorithm
        fout.write(struct.pack('>I', insize)) # write unpacked size
        fout.write(struct.pack('>I', 0)) # write packed size, unknown now - rewrite on step 1 after compression

        # Lower values give faster compression, while higher values gives better compression.
        # 100000 дает байт в байт такое же сжатие как у всех оригинальных прошивок
        LZ_MAX_OFFSET = 100000

        outputbuf = bytearray()

        # для замеров скорости выполнения
        startT = datetime.now()
        # для вывода прогресса работы
        oldcurrprogress = 0

        # Write marker byte as first symbol for the decoder
        outputbuf.append(marker)
        #print("new LZ marker = 0x%02X" % marker)

        # Start of compression
        inpos = 0
        outpos = 1

        # Main compression loop
        bytesleft = insize
        while bytesleft > 3:
            # Search history window for maximum length string match
            bestlength = 3
            bestoffset = 0

            j = work[ 65536 + inpos ]
            while (j != 0xffffffff) & ((inpos - j) < LZ_MAX_OFFSET):

                # защита от выхода за пределы массива dataread[]
                if (j + bestlength >= insize):
                    break
                if (inpos + bestlength >= insize):
                    break

                # Quickly determine if this is a candidate (for speed)
                if dataread[ j + bestlength ] == dataread[ inpos + bestlength ]:
                    # Determine maximum length for this offset
                    offset = inpos - j
                    if bytesleft < offset:
                        maxlength = bytesleft
                    else:
                        maxlength = offset

                    # Count maximum length match at this offset
                    #length = _LZ_StringCompare( ptr1, ptr2, 2, maxlength );
                    length = 2
                    while (length < maxlength):
                        if (dataread[ inpos + length ] == dataread[ j + length ]):
                            length += 1
                        else:
                            break

                    # Better match than any previous match?
                    if length > bestlength:
                        bestlength = length
                        bestoffset = offset

                # Get next possible index from jump table
                j = work[ 65536 + j ]


            # Was there a good enough match?
            if( (bestlength > 7) |
                ((bestlength == 4) & (bestoffset <= 0x0000007f)) |
                ((bestlength == 5) & (bestoffset <= 0x00003fff)) |
                ((bestlength == 6) & (bestoffset <= 0x001fffff)) |
                ((bestlength == 7) & (bestoffset <= 0x0fffffff)) ):
                    outputbuf.append(marker)
                    #print("0x%08X : 0x%02X" % (outpos, marker))
                    outpos += 1

                    #print("length = 0x%08X" % bestlength)
                    ##outpos += _LZ_WriteVarSize( bestlength, &out[ outpos ] )
                    buf = 0
                    y = bestlength >> 3
                    num_bytes = 5
                    while num_bytes >= 2:
                        if y & 0xfe000000 != 0:
                            break
                        y <<= 7
                        num_bytes -= 1
                    # Write all bytes, seven bits in each, with 8:th bit set for all
                    # but the last byte.
                    i = num_bytes-1
                    while i >= 0:
                        b = (bestlength >> (i*7)) & 0x0000007f
                        if i > 0:
                            b |= 0x00000080
                        buf = (buf<<8) | b
                        i -= 1
                    # Return number of bytes written
                    outpos += num_bytes
                    #print("write num_bytes = %d" % num_bytes)
                    #print("write buf:")

                    while num_bytes > 0:
                        #print("0x%02X" % ((buf>>(8*(num_bytes - 1)))&0xFF))
                        outputbuf.append((buf>>(8*(num_bytes - 1)))&0xFF)
                        num_bytes -= 1

                    #print("offset = 0x%08X" % bestoffset)
                    ##outpos += _LZ_WriteVarSize( bestoffset, &out[ outpos ] )
                    buf = 0
                    y = bestoffset >> 3
                    num_bytes = 5
                    while num_bytes >= 2:
                        if y & 0xfe000000 != 0:
                            break
                        y <<= 7
                        num_bytes -= 1
                    # Write all bytes, seven bits in each, with 8:th bit set for all
                    # but the last byte.
                    i = num_bytes-1
                    while i >= 0:
                        b = (bestoffset >> (i*7)) & 0x0000007f
                        if i > 0:
                            b |= 0x00000080
                        buf = (buf<<8) | b
                        i -= 1
                    # Return number of bytes written
                    outpos += num_bytes
                    #print("write num_bytes = %d" % num_bytes)
                    #print("write buf:")

                    while num_bytes > 0:
                        #print("0x%02X" % ((buf>>(8*(num_bytes - 1)))&0xFF))
                        outputbuf.append((buf>>(8*(num_bytes - 1)))&0xFF)
                        num_bytes -= 1

                    inpos += bestlength
                    bytesleft -= bestlength
            else:
                # Output single byte (or two bytes if marker byte)
                symbol = dataread[ inpos ]
                inpos += 1
                outputbuf.append(symbol)
                #print("0x%02X" % symbol)
                outpos += 1
                if symbol == marker:
                    outputbuf.append(0)
                    #print("0x00")
                    outpos += 1
                bytesleft -= 1

            # вывод прогресса работы упаковщика
            currprogress = round(inpos/insize*100)
            if currprogress > oldcurrprogress:
                updateProgressBar(currprogress)
                oldcurrprogress = currprogress

        # Dump remaining bytes, if any
        while inpos < insize:
            if dataread[ inpos ] == marker:
                outputbuf.append(marker)
                #print("0x%02X" % marker)
                outpos += 1
                outputbuf.append(0)
                #print("0x00")
                outpos += 1
            else:
                outputbuf.append(dataread[ inpos ])
                #print("0x%02X" % dataread[ inpos ])
                outpos += 1
            inpos += 1

        fout.write(outputbuf)

        # надо дописать к сжатым данным 00... для выравнивания по 4 байтам
        # для всех новых прошивок или более старой версии прошивок (BCL1 + NVTPACK_FW_HDR) для самой первой партиции или для просто прошивки из одного BCL1
        addsize = 0
        if (FW_HDR2 == 1) | ((FW_HDR == 1) & (part_id[part_nr] == 0)) | (FW_HDR == 0):
            addsize = (len(outputbuf) % 4)
            if addsize != 0:
                addsize = 4 - addsize

                # добавим сколько надо 00 для выравнивания до 4 байт
                for b in range(addsize):
                    fout.write(struct.pack('B', 0))
                outpos += addsize
        fout.close()
        #print("Compression to LZ BCL1 successfull")

        fout = open(out, 'r+b')
        fout.seek(12, 0)
        fout.write(struct.pack('>I', outpos)) # write compressed data size to BCL1 header
        fout.close()

        endT = datetime.now()
        print("elapsed: %s" % str(endT - startT))

        # пересчитываем CRC для BCL1-заголовка только после того как все остальное кроме CRC уже записали
        newCRC = MemCheck_CalcCheckSum16Bit(out, 0, outpos + 16, 0x4)
        fout = open(out, 'r+b')
        fout.seek(4, 0)
        fout.write(struct.pack('<H', newCRC)) # write new CRC value
        fout.close()
        return

    # LZMA compress
    if Algorithm == 0x0B:
        #print("LZMA_DictSize=0x%08X" % LZMA_DictSize)

        # lzma.exe e -a1 -d20 -mfbt4 -fb40 -mc36 -lc3 -lp0 -pb2 infile outfile
        ##fast_bytes = 40
        ##search_depth = 16 + fast_bytes//2 # depth search формула для любого из MF_BT*
        ##my_filters = [{"id":lzma.FILTER_LZMA1, "mode":lzma.MODE_NORMAL, "dict_size":LZMA_DictSize, "mf":lzma.MF_BT4, "nice_len":fast_bytes, "depth":search_depth, "lc":3, "lp":0, "pb":2}]
        
        ##compress = lzma.compress(dataread, format = lzma.FORMAT_ALONE, filters = my_filters) # но пока что filters не работает с pypy3 и это все равно не дает байт в байт сжатие как lzma.exe
        compress = lzma.compress(dataread, format = lzma.FORMAT_ALONE)

        # надо дописать к сжатым данным 00... для выравнивания по 4 байтам
        # но делаю это только если нулевая партиция (без этого NVTPACK_FW_HDR будет не выровнен)
        addsize = 0
        if part_id[part_nr] == 0:
            addsize = (len(outputbuf) % 4)
            if addsize != 0:
                addsize = 4 - addsize

        fout = open(out, 'w+b')
        fout.write(struct.pack('>I', 0x42434C31)) # write BCL1
        fout.write(struct.pack('<H', 0x0000)) # write new CRC, unknown now - rewrite after compression
        fout.write(struct.pack('>H', Algorithm)) # write Algorithm
        fout.write(struct.pack('>I', len(dataread))) # write unpacked size
        fout.write(struct.pack('>I', len(compress) + addsize)) # write packed size

        fout.write(compress) # write compressed data

        # добавим сколько надо 00 для выравнивания до 4 байт
        for b in range(addsize):
            fout.write(struct.pack('B', 0))
        fout.close()

        # исправим в LZMA заголовке данные о Unpacked size - в LZMA-библиотеке python они всегда записываются как FF FF FF FF
        # в стандарте указано что это одно 64-битное число но во всех прошивках идет дублирование 2-х 32-битных чисел
        ##fout = open(out, 'r+b')
        ##fout.seek(0x15, 0)
        ##if (LZMA_UncompSize1 == LZMA_UncompSize2):
        ##    # если дублирование
        ##    fout.write(struct.pack('<II', len(dataread), len(dataread)))
        ##else:
        ##    # если по стандарту 64 бита
        ##    fout.write(struct.pack('<II', len(dataread)&0xFFFFFFFF, (len(dataread)>>32)&0xFFFFFFFF))
        ##fout.close()

        # пересчитываем CRC для BCL1-заголовка только после того как все остальное кроме CRC уже записали
        newCRC = MemCheck_CalcCheckSum16Bit(out, 0, len(compress) + addsize + 16, 0x4)
        fout = open(out, 'r+b')
        fout.seek(4, 0)
        fout.write(struct.pack('<H', newCRC)) # write new CRC value
        fout.close()
        return

    # ZLIB compress
    if Algorithm == 0x0C:
        compress = zlib.compress(dataread)

        # надо дописать к сжатым данным 00... для выравнивания по 4 байтам
        # но делаю это только если нулевая партиция (без этого NVTPACK_FW_HDR будет не выровнен)
        addsize = 0
        if part_id[part_nr] == 0:
            addsize = (len(outputbuf) % 4)
            if addsize != 0:
                addsize = 4 - addsize

        fout = open(out, 'w+b')
        fout.write(struct.pack('>I', 0x42434C31)) # write BCL1
        fout.write(struct.pack('<H', 0x0000)) # write new CRC, unknown now - rewrite after compression
        fout.write(struct.pack('>H', Algorithm)) # write Algorithm
        fout.write(struct.pack('>I', len(dataread))) # write unpacked size
        fout.write(struct.pack('>I', len(compress) + addsize)) # write packed size
 
        fout.write(compress) # write compressed data

        # добавим сколько надо 00 для выравнивания до 4 байт
        for b in range(addsize):
            fout.write(struct.pack('B', 0))
        fout.close()
        
        # пересчитываем CRC для BCL1-заголовка только после того как все остальное кроме CRC уже записали
        newCRC = MemCheck_CalcCheckSum16Bit(out, 0, len(compress) + addsize + 0x10, 0x4)
        fout = open(out, 'r+b')
        fout.seek(4, 0)
        fout.write(struct.pack('<H', newCRC)) # write new CRC value
        fout.close()
        return



# функция для отображения прогресса выполнения операций (распаковки/запаковки партиций к примеру)
def updateProgressBar(value):
    line = '\r\033[93m%s%%\033[0m[\033[94m%s\033[0m%s]' % ( str(value).rjust(3), '#' * round((float(value)/100) * 70), '-' * round(70 -((float(value)/100) * 70))) # 70 - длина прогресс-бара
    print(line, end='')
    sys.stdout.flush()
    # чтобы сделать переход на новую строку после 100% прогресс бара
    if value == 100:
        print('')


def uncompressDTB(in_file, out_filename = ''):
    fin = open(in_file, 'rb')
    FourCC = fin.read(4)
    fin.close()

    # check DTB magic
    if struct.unpack('>I', FourCC)[0] == 0xD00DFEED:
        if out_filename == '':
            out_filename = os.path.splitext(in_file)[0] + '.dts'
        #unpack DTB to DTS
        os.system('dtc -qqq -I dtb -O dts ' + '\"' + in_file + '\"' + ' -o ' + '\"' + out_filename + '\"')
    else:
        print("\033[91mDTB marker not found, exit\033[0m")
        sys.exit(1)


def compressToDTB(in_file, out_filename = ''):
    if out_filename == '':
        out_filename = os.path.splitext(in_file)[0] + '.dtb'
    #pack to DTB
    os.system('dtc -qqq -I dts -O dtb ' + '\"' + in_file + '\"' + ' -o ' + '\"' + out_filename + '\"')


def uncompress(in_offset, out_filename, size):
    global in_file

    fin = open(in_file, 'rb')
    # check BCL1 marker at start of partition    
    fin.seek(in_offset, 0)
    FourCC = fin.read(4)


    # FDT (DTB)
    if struct.unpack('>I', FourCC)[0] == 0xD00DFEED:
        #extract FDT partition to tempfile
        fin.seek(in_offset, 0)
        finread = fin.read(size)
        fin.close()
        fpartout = open(out_filename + '_tempfile', 'w+b')
        fpartout.write(finread)
        fpartout.close()
        
        #unpack DTB to DTS
        os.system('dtc -qqq -I dtb -O dts ' + '\"' + out_filename + '_tempfile' + '\"' + ' -o ' + '\"' + out_filename + '\"')
        
        # delete tempfile
        os.system('rm -rf ' + '\"' + out_filename + '_tempfile' + '\"')
        return


    if FourCC == b'BCL1':
        fin.close()
        BCL1_uncompress(in_offset, out_filename)
        return

    if FourCC == b'UBI#':
        #create dir with similar name as for other parttition types
        os.system('sudo rm -rf ' + '\"' + out_filename + '\"')
        os.system('mkdir ' + '\"' + out_filename + '\"')

        #extract UBI partition to tempfile
        fin.seek(in_offset, 0)
        finread = fin.read(size)
        fin.close()
        fpartout = open(out_filename + '/tempfile', 'w+b')
        fpartout.write(finread)
        fpartout.close()

        #unpack UBIFS to created dir
        os.system('sudo ubireader_extract_files -k -i -f ' + '-o ' + '\"' + out_filename + '\"' + ' ' + '\"' + out_filename + '/tempfile' + '\"')

        # delete tempfile
        os.system('rm -rf ' + '\"' + out_filename + '/tempfile' + '\"')
        return

    # SPARSE EXT4
    if struct.unpack('>I', FourCC)[0] == 0x3AFF26ED:
        #create dir with similar name as for other parttition types
        os.system('rm -rf ' + '\"' + out_filename + '\"')
        os.system('mkdir ' + '\"' + out_filename + '\"')
        os.system('mkdir ' + '\"' + out_filename + '/mount' + '\"') # subdir for mounting ext4

        #extract SPARSE EXT4 partition to tempfile
        fin.seek(in_offset, 0)
        finread = fin.read(size)
        fin.close()
        fpartout = open(out_filename + '/tempfile', 'w+b')
        fpartout.write(finread)
        fpartout.close()

        # convert SPARSE to ext4
        subprocess.run('simg2img ' + '\"' + out_filename + '/tempfile' + '\"' + ' ' + '\"' + out_filename + '/tempfile.ext4' + '\"', shell=True)

        # mount ext4 to folder
        os.system('mount ' + '\"' + out_filename + '/tempfile.ext4' + '\"' + ' ' + '\"' + out_filename + '/mount' + '\"')

        # удалим tempfile, tempfile.ext4 нам еще нужен будет для сборки обратно
        os.system('rm -rf ' + '\"' + out_filename + '/tempfile' + '\"')
        return

    print("\033[91mOnly FDT(DTB), BCL1, UBI and SPARSE partitions supported now, exit\033[0m")
    fin.close()



def BCL1_uncompress(in_offset, out_filename):
    global in_file


    fin = open(in_file, 'rb')

    # check BCL1 marker at start of partition    
    fin.seek(in_offset, 0)
    FourCC = fin.read(4)
    if FourCC != b'BCL1':
        print("\033[91mBCL1 marker not found, exit\033[0m")
        sys.exit(1)

    # check compression algo
    fin.read(2)
    Algorithm = struct.unpack('>H', fin.read(2))[0]
    if (Algorithm != 0x09) & (Algorithm != 0x0B) & (Algorithm != 0x0C):
        print("\033[91mCompression algo %0X is not supported\033[0m" % Algorithm)
        sys.exit(1)


    fout = open(out_filename, 'w+b')

    outsize = struct.unpack('>I', fin.read(4))[0]
    insize = struct.unpack('>I', fin.read(4))[0]

    in_offset = in_offset + 0x10 #skip BCL1 header
    fin.seek(in_offset, 0)

    # LZ77 uncompress
    if Algorithm == 0x09:
        # Get marker symbol from input stream
        marker = struct.unpack('B', fin.read(1))[0]
        #print("LZ marker = 0x%0X" % marker)

        inpos = 1
        outputbuf = bytearray()

        # для замеров скорости выполнения
        #startT = datetime.now()
        # для вывода прогресса работы
        #oldcurrprogress = 0
        
        # Main uncompression loop
        outpos = 0
        while((inpos < insize) & (outpos < outsize)):
            symbol = struct.unpack('B', fin.read(1))[0]
            inpos += 1
    
            if symbol == marker:
                # We had a marker byte
                readbyte = struct.unpack('B', fin.read(1))[0]
                if readbyte == 0:
                    # It was a single occurrence of the marker byte
                    ##fout.write(struct.pack('B', marker))
                    outputbuf.append(marker)
                    outpos += 1
                    inpos += 1
                else:
                    # Extract true length and offset
                    #print("curr file offset = 0x%0x" % (in_offset + inpos))
                    #inpos += lz_read_var_size( &length, &in[ inpos ] );
                    #=================================================
                    y = 0
                    num_bytes = 0
                    
                    b = readbyte
                    y = (y << 7) | (b & 0x0000007f)
                    num_bytes += 1
                    
                    while (b & 0x00000080) != 0:
                        b = struct.unpack('B', fin.read(1))[0]
                        y = (y << 7) | (b & 0x0000007f)
                        num_bytes += 1
    
                    length = y
                    inpos += num_bytes
                    #print("length = 0x%0x" % (length))
                    #=================================================
                    
                    #inpos += lz_read_var_size( &offset, &in[ inpos ] );
                    #=================================================
                    y = 0
                    num_bytes = 0
                    
                    b = struct.unpack('B', fin.read(1))[0]
                    y = (y << 7) | (b & 0x0000007f)
                    num_bytes += 1
                    
                    while (b & 0x00000080) != 0:
                        b = struct.unpack('B', fin.read(1))[0]
                        y = (y << 7) | (b & 0x0000007f)
                        num_bytes += 1
    
                    offset = y
                    inpos += num_bytes
                    #print("offset = 0x%0x" % (offset))
                    #=================================================
    
                    # Copy corresponding data from history window
                    #out[ outpos ] = out[ outpos - offset ];
                    for i in range(length):
                        ##fout.seek(outpos - offset, 0)
                        ##out = struct.unpack('B', fout.read(1))[0]
                        ##fout.seek(outpos, 0)
                        ##fout.write(struct.pack('B', out))
                        outputbuf.append(outputbuf[outpos - offset])
                        outpos += 1
            else:
                # No marker, plain copy
                ##fout.write(struct.pack('B', symbol))
                outputbuf.append(symbol)
                outpos += 1

            # вывод прогресса работы упаковщика
            #currprogress = round(inpos/insize*100)
            #if currprogress > oldcurrprogress:
            #    updateProgressBar(currprogress)
            #    oldcurrprogress = currprogress

        fout.write(outputbuf)
        fin.close()
        fout.close()

        #endT = datetime.now()
        #print("elapsed: %s" % str(endT - startT))


    # LZMA uncompress
    if Algorithm == 0x0B:
        dataread = fin.read(insize)
        fin.close()
        
        decompress = decompress_lzma(dataread)[:outsize]
        fout.write(decompress)
        fout.close()


    # ZLIB uncompress
    if Algorithm == 0x0C:
        dataread = fin.read(insize)
        fin.close()
        
        decompress = zlib.decompress(dataread)
        fout.write(decompress)
        fout.close()

    # выведем немного информации о распакованной BCL1 партиции
    fin = open(out_filename, 'rb')
    dataread = bytearray(fin.read())
    fin.close()

    if (dataread[0x6C] == 0xFF) & (dataread[0x6D] == 0xFF) & (dataread[0x46C] == 0x55) & (dataread[0x46D] == 0xAA):
        print('Partition data: Name="\033[93m%s\033[0m", Date="\033[93m%s\033[0m", Size=%s, CRC Offset=\033[93m0x%04X\033[0m, CRC=\033[93m0x%04X\033[0m' % (str(struct.unpack('8s',dataread[0x450:0x458])[0])[2:-1].replace('\\x00',''), str(struct.unpack('8s',dataread[0x460:0x468])[0])[2:-1], '\033[93m{:,}\033[0m'.format(struct.unpack('<I', dataread[0x468:0x46C])[0]), 0x46E, struct.unpack('<H', dataread[0x46E:0x470])[0]))
    else:
        if (dataread[0x6C] == 0x55) & (dataread[0x6D] == 0xAA):
            print('Partition data: Name="\033[93m%s\033[0m", Date="\033[93m%s\033[0m", Size=%s, CRC Offset=\033[93m0x%04X\033[0m, CRC=\033[93m0x%04X\033[0m' % (str(struct.unpack('8s',dataread[0x50:0x58])[0])[2:-1].replace('\\x00',''), str(struct.unpack('8s',dataread[0x60:0x68])[0])[2:-1], '\033[93m{:,}\033[0m'.format(struct.unpack('<I', dataread[0x68:0x6C])[0]), 0x6E, struct.unpack('<H', dataread[0x6E:0x70])[0]))
        else:
            if (dataread[0x16C] == 0x55) & (dataread[0x16D] == 0xAA):
                print('Partition with 0x100 data at begin: Name="\033[93m%s\033[0m", Date="\033[93m%s\033[0m", Size=%s, CRC Offset=\033[93m0x%04X\033[0m, CRC=\033[93m0x%04X\033[0m' % (str(struct.unpack('8s',dataread[0x150:0x158])[0])[2:-1].replace('\\x00',''), str(struct.unpack('8s',dataread[0x160:0x168])[0])[2:-1], '\033[93m{:,}\033[0m'.format(struct.unpack('<I', dataread[0x168:0x16C])[0]), 0x16E, struct.unpack('<H', dataread[0x16E:0x170])[0]))
            else:
                print('Partition data without CRC')




# use for lzma exception workaround
# see at https://stackoverflow.com/questions/37400583/python-lzma-compressed-data-ended-before-the-end-of-stream-marker-was-reached
def decompress_lzma(data):
    results = []
    while True:
        decomp = lzma.LZMADecompressor(lzma.FORMAT_ALONE, None, None)
        try:
            res = decomp.decompress(data)
        except lzma.LZMAError:
            if results:
                break  # Leftover data is not a valid LZMA/XZ stream; ignore it.
            else:
                raise  # Error on the first iteration; bail out.
        results.append(res)
        data = decomp.unused_data
        if not data:
            break
        if not decomp.eof:
            raise lzma.LZMAError("Compressed data ended before the end-of-stream marker was reached")
    return b"".join(results)


def fillIDPartNames(startat):
    global in_file
    
    
    fin = open(in_file, 'r+b')
    fin.seek(startat+0x34, 0)

    #-----начали секцию----
    starting = struct.unpack('>I', fin.read(4))[0] #00000001
    while(starting == 0x00000001):
        #вычисляем длину id
        id_length = 0
        t = struct.unpack('B', fin.read(1))[0]
        while(t != 0x00):
            id_length+=1
            t = struct.unpack('B', fin.read(1))[0]
        #print(id_length)
        fin.seek(-1*(id_length+1), 1) # вернемся на начало имени id
        # считаем idx
        idname = str(struct.unpack('%ds' % (id_length), fin.read(id_length))[0])[2:-1] #отрезает b` `
        #print(idname)
        dtbpart_ID.append(idname)
        fin.read(4 - (id_length%4)) #дочитываем все 00 которые нужны для выравнивания по 4 байта
        
        fin.read(4) #00000003
        lengthname = struct.unpack('>I', fin.read(4))[0]
        fin.read(4) #00000223
        shortname = str(struct.unpack('%ds' % (lengthname-1), fin.read(lengthname-1))[0])[2:-1] #отрезает b` `
        #print(shortname)
        dtbpart_name.append(shortname)
        if lengthname > 1:
            fin.read(4 - ((lengthname-1)%4)) #дочитываем все 00 которые нужны для выравнивания по 4 байта
        else:
            fin.read(4) #если имени нет то дочитываются все 4 байта
        
        fin.read(4) #00000003
        lengthfilename = struct.unpack('>I', fin.read(4))[0]
        fin.read(4) #00000232
        filename = str(struct.unpack('%ds' % (lengthfilename-1), fin.read(lengthfilename-1))[0])[2:-1] #отрезает b` `
        #print(filename)
        dtbpart_filename.append(filename)
        if lengthfilename > 1:
            fin.read(4 - ((lengthfilename-1)%4)) #дочитываем все 00 которые нужны для выравнивания по 4 байта
        else:
            fin.read(4) #если имени нет то дочитываются все 4 байта
        
        fin.read(4) #00000002
        #-----закончили секцию----
        
        starting = struct.unpack('>I', fin.read(4))[0] #00000001
    
    fin.close()
    
    

def SearchPartNamesInDTB(partitions_count):
    global in_file
    alreadyfound = 0
    
    for a in range(partitions_count):
        if part_type[a] == 'device tree blob (dtb)':
            fin = open(in_file, 'r+b')
            fin.seek(part_startoffset[a], 0)
            dtbfile = fin.read(part_size[a])
            fin.close()
            startat = dtbfile.find(b'NVTPACK_FW_INI_16072017')

            if startat != -1:
                #print("0x%0X" % startat)
                if alreadyfound == 0:
                    fillIDPartNames(part_startoffset[a] + startat)
                    alreadyfound = 1 # чтобы снова не добавлять инфу из следующих партиций навроде fdt.restore





def GetPartitionInfo(start_offset, part_size, partID, addinfo = 1):
    global in_file
    global is_ARM64


    fin = open(in_file, 'rb')
    # go to partition start offset
    fin.seek(start_offset, 0)
    partfirst4bytes = struct.unpack('>I', fin.read(4))[0]

    
    #dtb
    if partfirst4bytes == 0xD00DFEED:
        temp_parttype = 'device tree blob (dtb)'
        CRC = 0
        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(CRC)

            # перенес сюда получение названий партиций
            fin.seek(start_offset, 0)
            dtbfile = fin.read(part_size)
            startat = dtbfile.find(b'NVTPACK_FW_INI_16072017')
            if startat != -1:
                fillIDPartNames(start_offset + startat)

            fin.close()
        return temp_parttype, CRC


    # atf = ARM Trusted Firmware-A
    if len(dtbpart_name) != 0 and dtbpart_name[partID] == 'atf':
        temp_parttype = 'ARM Trusted Firmware'
        CRC = 0
        if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(0)
                part_crcCalc.append(CRC)
                fin.close()
        return temp_parttype, CRC


    # uboot
    # if partID == 3: # ранее всегда 3 партиция - это uboot
    if len(dtbpart_name) != 0 and dtbpart_name[partID] == 'uboot':
        temp_parttype = 'uboot'
        CRC = MemCheck_CalcCheckSum16Bit(in_file, start_offset, part_size, 0x36E)
        if addinfo:
            part_type.append(temp_parttype)
            fin.seek(start_offset + 0x36E, 0)
            part_crc.append(struct.unpack('<H', fin.read(2))[0])
            part_crcCalc.append(CRC)
            fin.close()
        return temp_parttype, CRC


    # uImage header
        #https://github.com/EmcraftSystems/u-boot/blob/master/include/image.h
        #Legacy format image header,
        #all data in network byte order (aka natural aka bigendian).
        # 
        ##define IH_MAGIC	0x27051956	/* Image Magic Number		*/
        ##define IH_NMLEN		32		/* Image Name Length		*/
        #
        #typedef struct image_header {
        #	uint32_t	ih_magic;	/* Image Header Magic Number	*/
        #	uint32_t	ih_hcrc;	/* Image Header CRC Checksum	*/
        #	uint32_t	ih_time;	/* Image Creation Timestamp		*/
        #	uint32_t	ih_size;	/* Image Data Size				*/
        #	uint32_t	ih_load;	/* Data	 Load  Address			*/
        #	uint32_t	ih_ep;		/* Entry Point Address			*/
        #	uint32_t	ih_dcrc;	/* Image Data CRC Checksum		*/
        #	uint8_t		ih_os;		/* Operating System		*/
        #	uint8_t		ih_arch;	/* CPU architecture		*/
        #	uint8_t		ih_type;	/* Image Type			*/
        #	uint8_t		ih_comp;	/* Compression Type		*/
        #	uint8_t		ih_name[IH_NMLEN];	/* Image Name	*/
        #} image_header_t;
        #
        #       27 05 19 56		/* Image Magic Number		*/	#define IH_MAGIC	0x27051956
        #		5C 0D F3 82		/* Image Header CRC Checksum*/	header CRC: 0x5C0DF382
        #		62 B4 60 B7		/* Image Creation Timestamp	*/	created: 2022-06-23 12:46:47
        #		00 2C B0 50		/* Image Data Size			*/  размер данных в этой партиции (0x2CB050 + 0x40(header size) = 0x2CB090(partition size))
        #		00 00 80 00		/* Data	 Load  Address		*/
        #		00 00 80 00		/* Entry Point Address		*/
        #		5A 34 64 C3		/* Image Data CRC Checksum	*/	data CRC: 0x5A3464C3
        #		05				/* Operating System			*/	#define IH_OS_LINUX		5	/* Linux	*/
        #		02				/* CPU architecture			*/	#define IH_ARCH_ARM		2	/* ARM		*/
        #		02				/* Image Type				*/	#define IH_TYPE_KERNEL	2	/* OS Kernel Image		*/
        #		00				/* Compression Type			*/	#define IH_COMP_NONE	0	/* No Compression Used	*/
        #		Linux-4.19.91	/* Image Name				*/
        #
        # ONLY for ih_type = 4 ('Multi-File Image'):
        # Next goes list of Image sizes:
        #   uint32_t   sizeof_uImage1 (rounded up to a multiple of 4 bytes)
        #   ...
        #   00 00 00 00 end of sizeof list marker
        #
    if partfirst4bytes == 0x27051956:
        temp_parttype = 'uImage'
        MultiFileImage_content = ''

        # Operating System
        fin.seek(start_offset + 28, 0)
        temp = struct.unpack('B', fin.read(1))[0]
        if temp in uImage_os:
            temp_parttype += ', OS: ' + '\"\033[93m' + uImage_os[temp] + '\033[0m\"'
        else:
            temp_parttype += ''

        # CPU architecture
        #fin.seek(part_offset[2] + 29, 0)
        found_ARM64 = 0
        temp = struct.unpack('B', fin.read(1))[0]
        if temp in uImage_arch:
            temp_parttype += ', CPU: ' + '\"\033[93m' + uImage_arch[temp] + '\033[0m\"'
            # check for ARM64 architecture to use favor_lzo compr algo in UBI partitions
            if (temp == 22): # and uImage_arch[temp] == 'ARM64'
                found_ARM64 = 1
        else:
            temp_parttype += ''

        # Image Type
        #fin.seek(part_offset[2] + 30, 0)
        temp = struct.unpack('B', fin.read(1))[0]
        if temp in uImage_imagetype:
            temp_parttype += ', Image type: ' + '\"\033[93m' + uImage_imagetype[temp] + '\033[0m\"'

            # for favor_lzo in UBI
            if(temp == 2 and found_ARM64 == 1): # if uImage_os[temp] == 'OS Kernel Image':
                is_ARM64 = 1
            
            # 4 : 'Multi-File Image' For this type we need to parse all uImages data
            if temp == 4:
                currpos = fin.tell()
                fin.seek(start_offset + 64, 0)
                temp = struct.unpack('>I', fin.read(4))[0]
                MultiFileImage_amount = 0
                MultiFileImage_content = os.linesep + 'Contents:' + os.linesep
                while(temp != 0):
                    MultiFileImage_amount += 1
                    MultiFileImage_content += 'Image ' + str(MultiFileImage_amount) + ': ' + '{:,}'.format(temp) + ' bytes' + os.linesep

                fin.seek(currpos, 0) # back to previous read pos
        else:
            temp_parttype += ''

        # Compression Type
        #fin.seek(part_offset[2] + 31, 0)
        temp = struct.unpack('B', fin.read(1))[0]
        if temp in uImage_compressiontype:
            temp_parttype += ', Compression type: ' + '\"\033[93m' + uImage_compressiontype[temp] + '\033[0m\"'
        else:
            temp_parttype += ''

        # Image Name
        #fin.seek(part_offset[2] + 32, 0)
        temp_parttype += ', Image name: ' + '\"\033[93m' + str(fin.read(32)).replace("\\x00","")[2:-1] + '\033[0m\"' #[2:-1] for remove b' at start and ' at end and \x00 after name

        # Image Creation Timestamp
        fin.seek(start_offset + 8, 0)
        temp = struct.unpack('>I', fin.read(4))[0]
        temp_parttype += ', created: ' + '\"\033[93m' + datetime.fromtimestamp(temp, timezone.utc).strftime('%Y-%m-%d %H:%M:%S') + '\033[0m\"'

        # Image Data Size
        temp = struct.unpack('>I', fin.read(4))[0]
        temp_parttype += ', size: ' + '\"\033[93m{:,}\033[0m" bytes'.format(temp)

        # print contents for Multi-File Images type
        if MultiFileImage_content != '':
            temp_parttype += MultiFileImage_content

        CRC = 0
        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(CRC)
            fin.close()
        return temp_parttype, CRC


    # Compressed ext4 file system SPARSE image format - бывает находится внутри CKSM
    if partfirst4bytes == 0x3AFF26ED:
        temp_parttype = '\033[93mSPARSE EXT4 image\033[0m'
        CRC = 0

        if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(0)
                part_crcCalc.append(CRC)
                fin.close()
        return temp_parttype, CRC


    # MODELEXT info header and data
    if partfirst4bytes == 0x38000000:
        fin.seek(0xC, 1)
        if(str(struct.unpack('8s', fin.read(8))[0])[2:-1] == 'MODELEXT'):
            temp_parttype = 'MODELEXT INFO'

            temp_parttype += ', Chip:\033[93m' + str(struct.unpack('8s', fin.read(8))[0]).replace("\\x00","")[2:-1] + '\033[0m'
            fin.read(8)
            temp_parttype += ', Build:\033[93m' + str(struct.unpack('8s', fin.read(8))[0]).replace("\\x00","")[2:-1] + '\033[0m'
            uilength = struct.unpack('<I', fin.read(4))[0]
            fin.seek(2, 1)
            uiChkValue = struct.unpack('<H', fin.read(2))[0]
            
            CRC = MemCheck_CalcCheckSum16Bit(in_file, start_offset, uilength, 0x36)
            
            if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(uiChkValue)
                part_crcCalc.append(CRC)
                fin.close()
            return temp_parttype, CRC


    # BCL1
    if partfirst4bytes == 0x42434C31:
        temp_parttype = '\033[93mBCL1\033[0m'

        fin.seek(start_offset + 4, 0)
        uiChkValue = struct.unpack('<H', fin.read(2))[0] # CRC

        # compression algo
        compressAlgo = struct.unpack('>H', fin.read(2))[0]
        if compressAlgo in compressAlgoTypes:
            temp_parttype += ', \033[93m' + compressAlgoTypes[compressAlgo] + '\033[0m'
        else:
            temp_parttype += ', \033[91mcomp.algo:0x%0X\033[0m' % compressAlgo

        unpackedSize = struct.unpack('>I', fin.read(4))[0]
        packedSize = struct.unpack('>I', fin.read(4))[0]
        temp_parttype += ' \033[93m{:,}\033[0m'.format(unpackedSize) + ' packed to ' + '\033[93m{:,}\033[0m bytes'.format(packedSize)

        CRC = MemCheck_CalcCheckSum16Bit(in_file, start_offset, packedSize + 0x10, 0x4)

        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(uiChkValue)
            part_crcCalc.append(CRC)
            fin.close()
        return temp_parttype, CRC


    # UBI#
    if partfirst4bytes ==  0x55424923:
        temp_parttype = '\033[93mUBI\033[0m'

        # get UBI volume name
        # чтобы не вызывать лишних команд и не делать временные файлы (т.к. ubireader не умеет работать с данными напрямую а лишь с файлами)
        # делаем проще - от UBI# + 0x1010 и там лежит имя Volume
        fin.seek(0x100C, 1)
        # считываем имя, идя до \00
        #вычисляем длину имени
        id_length = 0
        t = struct.unpack('B', fin.read(1))[0]
        while(t != 0x00):
            id_length += 1
            t = struct.unpack('B', fin.read(1))[0]
        #print(id_length)
        fin.seek(-1*(id_length+1), 1) # вернемся на начало имени id
        # считаем имя
        UBIname = str(struct.unpack('%ds' % (id_length), fin.read(id_length))[0])[2:-1] #отрезает b` `
        # добавим считанное
        temp_parttype += ' \"\033[93m' + UBIname + '\033[0m\"'
        CRC = 0

        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(CRC)
            fin.close()
        return temp_parttype, CRC


    # CKSM - внутри могут быть UBI or BCL1 or ...
    if partfirst4bytes == 0x434B534D:
        if struct.unpack('>I', fin.read(4))[0] == 0x19070416:
            uiChkMethod = struct.unpack('<I', fin.read(4))[0]
            uiChkValue = struct.unpack('<I', fin.read(4))[0]
            uiDataOffset = struct.unpack('<I', fin.read(4))[0]
            uiDataSize = struct.unpack('<I', fin.read(4))[0]
            uiPaddingSize = struct.unpack('<I', fin.read(4))[0]
            uiEmbType = struct.unpack('<I', fin.read(4))[0]

            temp_parttype = '\033[93mCKSM\033[0m'
            # как оказалось везде проставлен один тип = UBIFS - даже если внутри CKSM лежит BCL1
            #if uiEmbType in embtypes:
            #    temp_parttype += ' ' + embtypes[uiEmbType]
            #else:
            #    temp_parttype += ' unknown EmbType'

            # смотрим что внутри CKSM
            deeppart, calcCRC = GetPartitionInfo(start_offset + 0x40, 0, 0, 0)
            if deeppart != '':
                temp_parttype += '\033[94m<--\033[0m' + deeppart

            CRC = MemCheck_CalcCheckSum16Bit(in_file, start_offset, uiDataOffset + uiDataSize + uiPaddingSize, 0xC)

            if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(uiChkValue)
                part_crcCalc.append(CRC)
                fin.close()
            return temp_parttype, CRC


    # unknown part
    if addinfo:
        part_type.append('\033[91munknown part\033[0m')
        part_crc.append(0)
        part_crcCalc.append(0)
        fin.close()
    return '', 0



def partition_extract(is_extract, is_extract_offset):
    global partitions_count
    global workdir

    part_nr = -1
    for a in range(partitions_count):
        if part_id[a] == is_extract:
            part_nr = a
            break
    if part_nr != -1:
        if workdir != '':
            out_file = workdir + '/' + in_file + '-partitionID' + str(part_id[part_nr])
        else:
            out_file = in_file + '-partitionID' + str(part_id[part_nr])

        if is_extract_offset != -1:
            if is_silent != 1:
                print('Extract partition ID %i from 0x%08X + 0x%08X to file \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], is_extract_offset, out_file))
        else:
            if is_silent != 1:
                print('Extract partition ID %i from 0x%08X to file \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], out_file))
            is_extract_offset = 0

        fin = open(in_file, 'r+b')
        fin.seek(part_startoffset[part_nr] + is_extract_offset, 0)
        finread = fin.read(part_size[part_nr] - is_extract_offset)
        fin.close()

        fpartout = open(out_file, 'w+b')
        fpartout.write(finread)
        fpartout.close()
    else:
        print('\033[91mCould not find partiton with ID %i\033[0m' % is_extract)



def partition_replace(is_replace, is_replace_offset, is_replace_file):
    global partitions_count
    global NVTPACK_FW_HDR2_size
    global total_file_size
    

    part_nr = -1
    for a in range(partitions_count):
        if part_id[a] == is_replace:
            part_nr = a
            break
    if part_nr != -1:
        if not os.path.isfile(is_replace_file):
            print('\033[91m%s file does not found, exit\033[0m' % is_replace_file)
            exit(0)
    
        if is_silent != 1:
            print('Replace partition ID %i from 0x%08X + 0x%08X using inputfile \033[93m%s\033[0m' % (is_replace, part_startoffset[part_nr], is_replace_offset, is_replace_file))
        freplace = open(is_replace_file, 'rb')
        replacedata = freplace.read()
        freplace.close()
        
        if (len(replacedata) + is_replace_offset) == part_size[part_nr]:
            fin = open(in_file, 'r+b')
            fin.seek(part_startoffset[part_nr] + is_replace_offset, 0)
            fin.write(replacedata)
            fin.close()
        else:
            # размер партиции изменился - надо всё передвигать и обновлять заголовки
            # для современной версии прошивок
            if FW_HDR2 == 1:
                fin = open(in_file, 'rb')
                # если заменяемая партиция не последняя то
                if part_nr + 1 < partitions_count:
                    fin.seek(part_startoffset[part_nr + 1], 0)
                    #print('enddata start at 0x%08X' % part_startoffset[part_nr + 1])
                    enddata = fin.read() # считали все партиции после заменяемой партиции
                fin.close()

                # заменим данные в таблице партиций: [part_startoffset, part_size, part_id]
                fin = open(in_file, 'r+b') # именно r+b для ЗАМЕНЫ данных
                fin.seek(NVTPACK_FW_HDR2_size + (part_nr * 12), 0)
                fin.seek(4, 1) # part_startoffset не поменяется
                # высчитаем сколько нужно 00 для выравнивания новой партиции до кратности 4 байт
                newalignsize = (4 - ((len(replacedata) + is_replace_offset)%4))
                if newalignsize == 4:
                    newalignsize = 0
                newsize = len(replacedata) + is_replace_offset + newalignsize
                # бывают прошивки где между part_startoffset+part_size и началом следующей партиции есть место (больше чем требуется для выравнивания по 4 байта), неиспользуемое но оно есть
                # поэтому вычитаем не part_size[part_nr] + oldalignsize
                # а (part_startoffset[part_nr + 1] - part_startoffset[part_nr]) - полный размер партиции = полезный размер + выравнивание до 4 байт + неиспользуемые данные 00 до след. партиции
                if part_nr + 1 < partitions_count:
                    sizediff = newsize - (part_startoffset[part_nr + 1] - part_startoffset[part_nr]) # разница в размерах - может быть отрицательной
                else:
                    sizediff = newsize - part_size[part_nr] # для последней партиции если только брать её размер

                #print('new alignsize %d' % newalignsize)
                #print('newsize %d' % newsize)
                #print('sizediff %d' % sizediff)
                #print('write newsize to 0x%08X' % (NVTPACK_FW_HDR2_size + (part_nr * 12) + 4))
                fin.write(struct.pack('<I', newsize - newalignsize)) # заменим part_size новым без учёта выравнивания до 4 байт
                part_size[part_nr] = newsize - newalignsize # корректируем данные в нашей переменной
                fin.seek(4, 1) #пропустим part_id

                # пересчитаем part_startoffset для партиций идущих следом за заменяемой
                a = part_nr + 1
                while(a < partitions_count):
                    fin.write(struct.pack('<I', part_startoffset[a] + sizediff))
                    part_startoffset[a] = part_startoffset[a] + sizediff # корректируем данные в нашей переменной
                    fin.seek(8, 1)
                    a += 1

                # заменим партицию
                #print('replace part at 0x%08X' % (part_startoffset[part_nr] + is_replace_offset))
                fin.seek(part_startoffset[part_nr] + is_replace_offset, 0)
                fin.write(replacedata)

                # добавим сколько надо 00 для выравнивания до 4 байт адреса начала следующей партиции
                for b in range(newalignsize):
                    fin.write(struct.pack('B', 0))

                # если заменяемая партиция не последняя то
                if part_nr + 1 < partitions_count:
                    # допишем оставшиеся партиции
                    fin.write(enddata)
                fin.truncate() # изменим размер файла
                fin.close()

                filesize = os.path.getsize(in_file)
                # пересчитаем TotalSize в NVTPACK_FW_HDR2
                fin = open(in_file, 'r+b') # именно r+b для ЗАМЕНЫ данных
                fin.seek(28, 0)
                fin.write(struct.pack('<I', filesize))
                total_file_size = filesize # корректируем данные в нашей переменной

                # если заменяем CKSM-партицию то в её заголовке нужно исправить DataSize
                if part_type[part_nr][:13] == '\033[93mCKSM\033[0m':
                    fin.seek(part_startoffset[part_nr] + 0x14, 0)
                    fin.write(struct.pack('<I', newsize - is_replace_offset))

                fin.close()
                return

            # для более старой версии прошивок (BCL1 + NVTPACK_FW_HDR) или для просто BCL1
            if (FW_HDR == 1) | ((FW_HDR == 0) & (partitions_count == 1)):
                fin = open(in_file, 'rb')
                # если заменяемая партиция не последняя то
                if part_nr + 1 < partitions_count:
                    fin.seek(part_startoffset[part_nr + 1], 0)
                    #print('enddata start at 0x%08X' % part_startoffset[part_nr + 1])
                    enddata = fin.read() # считали все партиции после заменяемой партиции
                fin.close()

                # если это не просто BCL1 партиция идущая вне таблицы партиций
                if part_id[part_nr] != 0:
                    # заменим данные в таблице партиций: [part_startoffset, part_size, part_id]
                    fin = open(in_file, 'r+b') # именно r+b для ЗАМЕНЫ данных
                    fin.seek(part_size[0] + 28 + ((part_nr - 1) * 12), 0)
                    fin.seek(4, 1) # part_startoffset не поменяется
                    # высчитаем сколько нужно 00 для выравнивания новой партиции до кратности 4 байт
                    newalignsize = (4 - ((len(replacedata) + is_replace_offset)%4))
                    if newalignsize == 4:
                        newalignsize = 0
                    newsize = len(replacedata) + is_replace_offset + newalignsize
                    # бывают прошивки где между part_startoffset+part_size и началом следующей партиции есть место (больше чем требуется для выравнивания по 4 байта), неиспользуемое но оно есть
                    # поэтому вычитаем не part_size[part_nr] + oldalignsize
                    # а (part_startoffset[part_nr + 1] - part_startoffset[part_nr]) - полный размер партиции = полезный размер + выравнивание до 4 байт + неиспользуемые данные 00 до след. партиции
                    if part_nr + 1 < partitions_count:
                        sizediff = newsize - (part_startoffset[part_nr + 1] - part_startoffset[part_nr]) # разница в размерах - может быть отрицательной
                    else:
                        sizediff = newsize - part_size[part_nr] # для последней партиции если только брать её размер

                    #print('new alignsize %d' % newalignsize)
                    #print('newsize %d' % newsize)
                    #print('sizediff %d' % sizediff)
                    #print('write newsize to 0x%08X' % (part_size[0] + 28 + ((part_nr-1) * 12) + 4))
                    fin.write(struct.pack('<I', newsize - newalignsize)) # заменим part_size новым без учёта выравнивания до 4 байт
                    part_size[part_nr] = newsize - newalignsize # корректируем данные в нашей переменной
                    fin.seek(4, 1) #пропустим part_id

                    # пересчитаем part_startoffset для партиций идущих следом за заменяемой
                    a = part_nr + 1
                    while(a < partitions_count):
                        fin.write(struct.pack('<I', part_startoffset[a] + sizediff))
                        part_startoffset[a] = part_startoffset[a] + sizediff # корректируем данные в нашей переменной
                        fin.seek(8, 1) # size и ID не поменяются
                        a += 1

                    # заменим партицию
                    #print('replace part at 0x%08X' % (part_startoffset[part_nr] + is_replace_offset))
                    fin.seek(part_startoffset[part_nr] + is_replace_offset, 0)
                    fin.write(replacedata)

                    # добавим сколько надо 00 для выравнивания до 4 байт адреса начала следующей партиции
                    for b in range(newalignsize):
                        fin.write(struct.pack('B', 0))

                    # если заменяемая партиция не последняя то
                    if part_nr + 1 < partitions_count:
                        # допишем оставшиеся партиции
                        fin.write(enddata)
                    fin.truncate() # изменим размер файла
                    fin.close()

                    filesize = os.path.getsize(in_file)
                    # TotalSize в NVTPACK_FW_HDR не меняется т.к. в нем только размеры заголовков
                    total_file_size = filesize # корректируем данные в нашей переменной

                    # если заменяем CKSM-партицию то в её заголовке нужно исправить DataSize
                    if part_type[part_nr][:13] == '\033[93mCKSM\033[0m':
                        fin.seek(part_startoffset[part_nr] + 0x14, 0)
                        fin.write(struct.pack('<I', newsize - is_replace_offset))

                    fin.close()
                    return
                else:
                    # если это просто BCL1 партиция идущая с начала файла
                    fin = open(in_file, 'r+b') # именно r+b для ЗАМЕНЫ данных
                    fin.seek(part_size[0] + 28, 0)
                    # высчитаем сколько нужно 00 для выравнивания новой партиции до кратности 4 байт
                    newalignsize = (4 - ((len(replacedata) + is_replace_offset)%4))
                    if newalignsize == 4:
                        newalignsize = 0
                    newsize = len(replacedata) + is_replace_offset + newalignsize
                    # бывают прошивки где между part_startoffset+part_size и началом следующей партиции есть место (больше чем требуется для выравнивания по 4 байта), неиспользуемое но оно есть
                    # поэтому вычитаем не part_size[part_nr] + oldalignsize
                    # а (part_startoffset[part_nr + 1] - part_startoffset[part_nr]) - полный размер партиции = полезный размер + выравнивание до 4 байт + неиспользуемые данные 00 до след. партиции
                    if part_nr + 1 < partitions_count:
                        sizediff = newsize - (part_startoffset[part_nr + 1] - part_startoffset[part_nr]) # разница в размерах - может быть отрицательной
                    else:
                        sizediff = newsize - part_size[part_nr] # для последней партиции если только брать её размер

                    #print('new alignsize %d' % newalignsize)
                    #print('newsize %d' % newsize)
                    #print('sizediff %d' % sizediff)
                    #print('write newsize to 0x%08X' % (part_size[0] + 28 + ((part_nr-1) * 12) + 4))

                    # пересчитаем part_startoffset для всех партиций в таблице (нулевой там нет)
                    a = 1
                    while(a < partitions_count):
                        fin.write(struct.pack('<I', part_startoffset[a] + sizediff + 28 + (partitions_count - 1)*12)) # коррекция на величину изменения размера 0 партиции + размер заголовка _NVTPACK_FW_HDR + n*_NVTPACK_PARTITION_HDR
                        part_startoffset[a] = part_startoffset[a] + sizediff + 28 + (partitions_count - 1)*12 # корректируем данные в нашей переменной
                        fin.seek(8, 1) # size и ID не поменяются
                        a += 1

                    # если заменяемая партиция не последняя то
                    if part_nr + 1 < partitions_count:
                        # считали всё после нулевой партиции - вместе с _NVTPACK_FW_HDR и таблицей партиций
                        fin.seek(part_size[0], 0)
                        enddata = fin.read()

                    # заменим партицию
                    #print('replace partition at 0x%08X' % (part_startoffset[part_nr] + is_replace_offset))
                    fin.seek(part_startoffset[part_nr] + is_replace_offset, 0)
                    fin.write(replacedata)

                    part_size[part_nr] = newsize - newalignsize # корректируем данные в нашей переменной

                    # добавим сколько надо 00 для выравнивания до 4 байт адреса начала следующей партиции
                    for b in range(newalignsize):
                        fin.write(struct.pack('B', 0))

                    # если заменяемая партиция не последняя то
                    if part_nr + 1 < partitions_count:
                        # допишем оставшиеся партиции
                        fin.write(enddata)
                    fin.truncate() # изменим размер файла
                    fin.close()

                    filesize = os.path.getsize(in_file)
                    # TotalSize в NVTPACK_FW_HDR не меняется т.к. в нем только размеры заголовков
                    total_file_size = filesize # корректируем данные в нашей переменной

                    # если заменяем CKSM-партицию то в её заголовке нужно исправить DataSize
                    if part_type[part_nr][:13] == '\033[93mCKSM\033[0m':
                        fin.seek(part_startoffset[part_nr] + 0x14, 0)
                        fin.write(struct.pack('<I', newsize - is_replace_offset))

                    fin.close()
                    return
            else:
                print('\033[91mError: Could not replace this partition.\033[0m')
                exit(0)
    else:
        print('\033[91mCould not find partiton with ID %i\033[0m' % is_replace)



def fixCRC(partID):
    global partitions_count
    global total_file_size, orig_file_size
    
    for a in range(partitions_count):
        if part_id[a] == partID:
            # recalculate CRC of replaced partititon
            text, calcCRC = GetPartitionInfo(part_startoffset[a], part_size[a], part_id[a], 0)
            
            if part_crc[a] != calcCRC:
                # fix CRC for uboot
                if part_type[a] == 'uboot':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x36E, 0)
                    fin.write(struct.pack('<H', calcCRC))
                    fin.close()
                    if is_silent != 1:
                        print('Partition ID ' + str(part_id[a]) + ' - \033[94mCRC fixed\033[0m')
                    break
                # fix CRC for MODELEXT
                if part_type[a][:13] == 'MODELEXT INFO':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x36, 0)
                    fin.write(struct.pack('<H', calcCRC))
                    fin.close()
                    if is_silent != 1:
                        print('Partition ID ' + str(part_id[a]) + ' - \033[94mCRC fixed\033[0m')
                    break
                # fix CRC for CKSM
                if part_type[a][:13] == '\033[93mCKSM\033[0m':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0xC, 0)
                    fin.write(struct.pack('<I', calcCRC))
                    fin.close()
                    if is_silent != 1:
                        print('Partition ID ' + str(part_id[a]) + ' - \033[94mCRC fixed\033[0m')
                    break
                # fix CRC for BCL1
                if part_type[a][:13] == '\033[93mBCL1\033[0m':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x4, 0)
                    fin.write(struct.pack('<H', calcCRC))
                    fin.close()
                    if is_silent != 1:
                        print('Partition ID ' + str(part_id[a]) + ' - \033[94mCRC fixed\033[0m')
                    break
            else:
                if is_silent != 1:
                    print('Partition ID ' + str(part_id[a]) + ' - fix CRC not required')

    # fix CRC for whole file
    if FW_HDR2 == 1:
        # Выведем новый размер файла прошивки т.к. он изменился
        if(total_file_size != orig_file_size):
            print('Firmware file size \033[94m{:,}\033[0m bytes'.format(total_file_size))
        else:
            print('Firmware file size \033[92m{:,}\033[0m bytes'.format(total_file_size))
    
        CRC_FW = MemCheck_CalcCheckSum16Bit(in_file, 0, total_file_size, 0x24)
        if checksum_value == CRC_FW:
            if is_silent != 1:
                print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
        else:
            fin = open(in_file, 'r+b')
            fin.seek(0x24, 0) # for NVTPACK_FW_HDR2
            fin.write(struct.pack('<I', CRC_FW))
            fin.close()
            if is_silent != 1:
                print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (checksum_value, CRC_FW))

    else:
        if FW_HDR == 1:
            # Выведем новый размер файла прошивки т.к. он изменился
            if(total_file_size != orig_file_size):
                print('Firmware file size \033[94m{:,}\033[0m bytes'.format(total_file_size))
            else:
                print('Firmware file size \033[92m{:,}\033[0m bytes'.format(total_file_size))

            CRC_FW = MemCheck_CalcCheckSum16Bit(in_file, part_size[0], NVTPACK_FW_HDR_AND_PARTITIONS_size, 0x14)
            if checksum_value == CRC_FW:
                if is_silent != 1:
                    print('NVTPACK_FW_HDR + Partitions table ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
            else:
                fin = open(in_file, 'r+b')
                fin.seek(part_size[0] + 0x14, 0) # for NVTPACK_FW_HDR
                fin.write(struct.pack('<I', CRC_FW))
                fin.close()
                if is_silent != 1:
                    print('NVTPACK_FW_HDR + Partitions table ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (checksum_value, CRC_FW))



def main():
    global in_file
    #global in_offset
    global out_file
    in_file, is_extract, is_extract_offset, is_extract_all, is_replace, is_replace_offset, is_replace_file, is_uncompress, is_uncompress_offset, is_compress, fixCRC_partID = get_args()
    global partitions_count
    global FW_HDR
    global FW_HDR2
    global NVTPACK_FW_HDR2_size
    global total_file_size, orig_file_size
    global checksum_value
    global NVTPACK_FW_HDR_AND_PARTITIONS_size
    global workdir


    # for color output support in Windows
    if platform.system() == 'Windows':
        os.system('color')

    # show header about this program and author copyrights
    if is_silent != 1:
        ShowInfoBanner()

    if not os.path.exists(in_file):
        print('\033[91m%s input file does not found, exit\033[0m' % in_file)
        exit(0)

    partitions_count = 0
    fin = open(in_file, 'rb')

    FW_HDR = 0
    FW_HDR2 = 0

    # NVTPACK_FW_HDR2 GUID check
    if struct.unpack('<I', fin.read(4))[0] == 0xD6012E07:
        if struct.unpack('<H', fin.read(2))[0] == 0x10BC:
            if struct.unpack('<H', fin.read(2))[0] == 0x4F91:
                if struct.unpack('>H', fin.read(2))[0] == 0xB28A:
                    if struct.unpack('>I', fin.read(4))[0] == 0x352F8226:
                        if struct.unpack('>H', fin.read(2))[0] == 0x1A50:
                            FW_HDR2 = 1

    if FW_HDR2 != 1:
        print("\033[91mNVTPACK_FW_HDR2\033[0m not found")
        fin.seek(0, 0)
        if struct.unpack('>I', fin.read(4))[0] == 0x42434C31: # == BCL1
            part_startoffset.append(0)
            fin.seek(0xC, 0)
            part_size.append(struct.unpack('>I', fin.read(4))[0] + 0x10)  # + 0x10 потому что мы будем показывать размер партиции с заголовком а не размер данных внутри BCL1
            part_id.append(0)
            part_endoffset.append(0 + part_size[0])

            fin.seek(part_size[0], 0)
            #тут должен быть NVTPACK_FW_HDR
            FW_HDR = 0
            #проверим не в конце ли мы файла уже
            if (fin.tell() + 0x10) < os.stat(in_file).st_size:
                # если не в конце то проверяем дальше
                # NVTPACK_FW_HDR GUID check
                if struct.unpack('<I', fin.read(4))[0] == 0x8827BE90:
                    if struct.unpack('<H', fin.read(2))[0] == 0x36CD:
                        if struct.unpack('<H', fin.read(2))[0] == 0x4FC2:
                            if struct.unpack('>H', fin.read(2))[0] == 0xA987:
                                if struct.unpack('>I', fin.read(4))[0] == 0x73A8484E:
                                    if struct.unpack('>H', fin.read(2))[0] == 0x84B1:
                                        FW_HDR = 1
            if FW_HDR == 0:
                print("\033[91mNVTPACK_FW_HDR\033[0m not found")
                partitions_count = 1 # раз нет NVTPACK_FW_HDR значит у нас только 1 партиция - BCL1
            else:
                if is_silent != 1:
                    print("\033[93mNVTPACK_FW_HDR\033[0m found")
                NVTPACK_FW_HDR_AND_PARTITIONS_size = struct.unpack('<I', fin.read(4))[0]
                checksum_value = struct.unpack('<I', fin.read(4))[0]
                partitions_count = struct.unpack('<I', fin.read(4))[0] + 1  # + 1 так как есть еще нулевая BCL1 партиция
                print('Found \033[93m%i\033[0m partitions' % (partitions_count))

                total_file_size = os.path.getsize(in_file)
                orig_file_size = total_file_size
                print('Firmware file size \033[93m{:,}\033[0m bytes'.format(total_file_size))

                # если есть команда извлечь или заменить или распаковать или запаковать партицию то CRC не считаем чтобы не тормозить
                if (is_extract == -1 & is_replace == -1 & is_uncompress == -1 & is_compress == -1):
                    CRC_FW = MemCheck_CalcCheckSum16Bit(in_file, part_size[0], NVTPACK_FW_HDR_AND_PARTITIONS_size, 0x14)
                    if checksum_value == CRC_FW:
                        print('NVTPACK_FW_HDR + Partitions table ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
                    else:
                        print('NVTPACK_FW_HDR + Partitions table ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m' % (checksum_value, CRC_FW))

                # read partitions table info
                fin.seek(part_size[0] + 0x1C, 0)

                for a in range(partitions_count):
                    a = 1 # так как нулевую партицию мы уже занесли в массивы
                    part_startoffset.append(struct.unpack('<I', fin.read(4))[0])
                    part_size.append(struct.unpack('<I', fin.read(4))[0])
                    part_id.append(struct.unpack('<I', fin.read(4))[0])
                    part_endoffset.append(part_startoffset[a] + part_size[a])

            # read each partition info
            for a in range(partitions_count):
                GetPartitionInfo(part_startoffset[a], part_size[a], part_id[a])
        else:
            print("\033[91mBCL1\033[0m not found")
            exit(0) # ничего не найдено



    if FW_HDR2 == 1:
        if is_silent != 1:
            print("\033[93mNVTPACK_FW_HDR2\033[0m found")

        # NVTPACK_FW_HDR2_VERSION check
        if struct.unpack('<I', fin.read(4))[0] == 0x16071515:
            if is_silent != 1:
                print("\033[93mNVTPACK_FW_HDR2_VERSION\033[0m found")
        else:
            print("\033[91mNVTPACK_FW_HDR2_VERSION\033[0m not found")
            exit(0)
        
        NVTPACK_FW_HDR2_size = struct.unpack('<I', fin.read(4))[0]
        partitions_count = struct.unpack('<I', fin.read(4))[0]
        total_file_size = struct.unpack('<I', fin.read(4))[0]
        orig_file_size = total_file_size                                
        checksum_method = struct.unpack('<I', fin.read(4))[0]
        checksum_value = struct.unpack('<I', fin.read(4))[0]
        print('Found \033[93m%i\033[0m partitions' % partitions_count)
        print('Firmware file size \033[93m{:,}\033[0m bytes'.format(total_file_size))
    
    
        # если есть команда извлечь или заменить или распаковать или запаковать партицию то CRC не считаем чтобы не тормозить
        if (is_extract == -1 & is_replace == -1 & is_uncompress == -1 & is_compress == -1):
            CRC_FW = MemCheck_CalcCheckSum16Bit(in_file, 0, total_file_size, 0x24)
            if checksum_value == CRC_FW:
                print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
            else:
                print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m' % (checksum_value, CRC_FW))


        # read partitions table info
        fin.seek(NVTPACK_FW_HDR2_size, 0)


        for a in range(partitions_count):
            part_startoffset.append(struct.unpack('<I', fin.read(4))[0])
            part_size.append(struct.unpack('<I', fin.read(4))[0])
            part_id.append(struct.unpack('<I', fin.read(4))[0])
            part_endoffset.append(part_startoffset[a] + part_size[a])

        # read each partition info
        for a in range(partitions_count):
            GetPartitionInfo(part_startoffset[a], part_size[a], part_id[a])

        # если есть команда извлечь или заменить или распаковать или запаковать партицию то CRC не считаем чтобы не тормозить
        #if (is_extract == -1 & is_replace == -1 & is_uncompress == -1 & is_compress == -1):
        #    # looking into dtb partition for partition id - name - filename info
        #    SearchPartNamesInDTB(partitions_count)
        
        
        
    
    # для всех - и для FW_HDR и для FW_HDR2
    
    # extract partition by ID to outputfile
    if is_extract != -1:
        fin.close()
        if is_extract_all != 1:
            # extract partition by ID
            partition_extract(is_extract, is_extract_offset)
        else:
            # extract all partitions
            for part_nr in range(partitions_count):
                partition_extract(part_id[part_nr], -1) # -1 в функции преобразуется в 0, нужен чтобы не писать "from 0x%08X + 0x%08X to file"
        exit(0)


    # replace partition by ID with inputfile
    if is_replace != -1:
        fin.close()
        partition_replace(is_replace, is_replace_offset, is_replace_file)
        exit(0)


    # uncompress partition by ID
    if is_uncompress != -1:
        part_nr = -1
        for a in range(partitions_count):
            if part_id[a] == is_uncompress:
                part_nr = a
                break
        if part_nr != -1:
            if workdir != '':
                out_file = workdir + '/' + in_file + '-uncomp_partitionID' + str(part_id[part_nr])
            else:
                out_file = in_file + '-uncomp_partitionID' + str(part_id[part_nr])
            
            if is_silent != 1:
                if is_uncompress_offset != -1:
                    print('Uncompress partition ID %i from 0x%08X + 0x%08X to \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], is_uncompress_offset, out_file))
                else:
                    print('Uncompress partition ID %i from 0x%08X to \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], out_file))

            # if offset not defined - auto skip CKSM header size (0x40 bytes)
            if is_uncompress_offset == -1:
                fin.seek(part_startoffset[part_nr], 0)
                FourCC = fin.read(4)
                # skip CKSM header
                if FourCC == b'CKSM':
                    is_uncompress_offset = 0x40 # CKSM header size
                    if is_silent != 1:
                        print('Auto skip CKSM header: 64 bytes')
                else:
                    is_uncompress_offset = 0 # if start offset not defined set it to 0

            uncompress(part_startoffset[part_nr] + is_uncompress_offset, out_file, part_size[part_nr] - is_uncompress_offset)

        else:
            print('\033[91mCould not find partiton with ID %i\033[0m' % is_uncompress)
        fin.close()
        exit(0)


    # compress partition by ID and merge to FW file
    if is_compress != -1:
        part_nr = -1
        for a in range(partitions_count):
            if part_id[a] == is_compress:
                part_nr = a
                break
        if part_nr != -1:
            if workdir != '':
                in2_file = workdir + '/' + in_file + '-uncomp_partitionID' + str(part_id[part_nr])
            else:
                in2_file = in_file + '-uncomp_partitionID' + str(part_id[part_nr])

            if is_silent != 1:
                print('Compress \033[93m%s\033[0m to partition ID %i at 0x%08X' % (in2_file, part_id[part_nr], part_startoffset[part_nr]))

            compress(part_nr, in2_file)

        else:
            print('\033[91mCould not find partiton with ID %i\033[0m' % is_compress)
        fin.close()
        exit(0)


    # fix CRC values for partitions and whole firmware file
    if fixCRC_partID != -1:
        # fix partitions CRC
        for a in range(partitions_count):
            if part_crc[a] != part_crcCalc[a]:
                # fix CRC for uboot
                if part_type[a] == 'uboot':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x36E, 0)
                    fin.write(struct.pack('<H', part_crcCalc[a]))
                    fin.close()
                    part_type[a] += ', \033[94mCRC fixed\033[0m'
                # fix CRC for MODELEXT
                if part_type[a][:13] == 'MODELEXT INFO':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x36, 0)
                    fin.write(struct.pack('<H', part_crcCalc[a]))
                    fin.close()
                    part_type[a] += ', \033[94mCRC fixed\033[0m'
                # fix CRC for CKSM
                if part_type[a][:13] == '\033[93mCKSM\033[0m':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0xC, 0)
                    fin.write(struct.pack('<I', part_crcCalc[a]))
                    fin.close()
                    part_type[a] += ', \033[94mCRC fixed\033[0m'
                # fix CRC for BCL1
                if part_type[a][:13] == '\033[93mBCL1\033[0m':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x4, 0)
                    fin.write(struct.pack('<H', part_crcCalc[a]))
                    fin.close()
                    part_type[a] += ', \033[94mCRC fixed\033[0m'
        # fix firmware file CRC
        if fixCRC_partID != -1:
            if FW_HDR2 == 1:
                CRC_FW = MemCheck_CalcCheckSum16Bit(in_file, 0, total_file_size, 0x24)
                if checksum_value == CRC_FW:
                    print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
                else:
                    fin = open(in_file, 'r+b')
                    fin.seek(0x24, 0) # for NVTPACK_FW_HDR2
                    fin.write(struct.pack('<I', CRC_FW))
                    fin.close()
                    print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (checksum_value, CRC_FW))
            else:
                if FW_HDR == 1:
                    CRC_FW = MemCheck_CalcCheckSum16Bit(in_file, part_size[0], NVTPACK_FW_HDR_AND_PARTITIONS_size, 0x14)
                    if checksum_value == CRC_FW:
                        print('NVTPACK_FW_HDR + Partitions table ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
                    else:
                        fin = open(in_file, 'r+b')
                        fin.seek(part_size[0] + 0x14, 0) # for NVTPACK_FW_HDR
                        fin.write(struct.pack('<I', CRC_FW))
                        fin.close()
                        print('NVTPACK_FW_HDR + Partitions table ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m, \033[94mCRC fixed\033[0m' % (checksum_value, CRC_FW))
    # exit не делаем чтобы показать информацию по партициям и где CRC были исправлены


    fin.close()



    # показываем информацию о прошивке
    # если вообще что-то нашли
    if partitions_count > 0:
        # если что-то нашли в dtb то выводим расширенную информацию
        if len(dtbpart_ID) != 0:
            print(' -------------------------------------------------- PARTITIONS INFO ---------------------------------------------------')
            print('|  ID   NAME            START_OFFSET  END_OFFSET         SIZE       ORIG_CRC   CALC_CRC              TYPE              |')
            print(' ----------------------------------------------------------------------------------------------------------------------')
            for a in range(partitions_count):
                if part_crc[a] == part_crcCalc[a]:
                    print("  %2i    %-15s  0x%08X - 0x%08X     %+11s     0x%04X     \033[92m0x%04X\033[0m     %s" % (part_id[a], dtbpart_name[part_id[a]], part_startoffset[a], part_endoffset[a], '{:,}'.format(part_size[a]), part_crc[a], part_crcCalc[a], part_type[a]))
                else:
                    print("  %2i    %-15s  0x%08X - 0x%08X     %+11s     0x%04X     \033[91m0x%04X\033[0m     %s" % (part_id[a], dtbpart_name[part_id[a]], part_startoffset[a], part_endoffset[a], '{:,}'.format(part_size[a]), part_crc[a], part_crcCalc[a], part_type[a]))
            print(" ----------------------------------------------------------------------------------------------------------------------")
        # если dtb нет - то информацию без имен партиций
        else:
            print(" -------------------------------------------------- PARTITIONS INFO ---------------------------------------------------")
            print("|  ID   START_OFFSET  END_OFFSET         SIZE       ORIG_CRC   CALC_CRC                        TYPE                    |")
            print(" ----------------------------------------------------------------------------------------------------------------------")
            for a in range(partitions_count):
                if part_crc[a] == part_crcCalc[a]:
                    print("  %2i     0x%08X - 0x%08X     %+11s     0x%04X     \033[92m0x%04X\033[0m     %s" % (part_id[a], part_startoffset[a], part_endoffset[a], '{:,}'.format(part_size[a]), part_crc[a], part_crcCalc[a], part_type[a]))
                else:
                    print("  %2i     0x%08X - 0x%08X     %+11s     0x%04X     \033[91m0x%04X\033[0m     %s" % (part_id[a], part_startoffset[a], part_endoffset[a], '{:,}'.format(part_size[a]), part_crc[a], part_crcCalc[a], part_type[a]))
            print(" ----------------------------------------------------------------------------------------------------------------------")



if __name__ == "__main__":
    main()
