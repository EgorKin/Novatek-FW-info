# Creator: Dex9999(4pda.to user) aka Dex aka EgorKin

# V2.0 - improve parsing, now support Viofo A139 and 70Mai A500S firmwares
# V2.1 - add LZ77 unpacker
# V3.0 - add get info about partition names from fdt(dtb) partition
# V3.1 - add MODELEXT INFO partition support
# V3.2 - initial support old firmware format (BCL1 starting partition + NVTPACK_FW_HDR)
# V3.3 - add optional start offset for -u command (uncompress partition); add -x ALL option, also start offset for -x and -u now optional (do not need set it to 0)
# V3.4 - add ZLIB uncompress support
# V3.5 - add LZMA uncompress support
# V3.6 - for -u command: if start offset not defined of 0 - auto skip CKSM header size (0x40 bytes) for CKSM partition
# V3.7 - parse UBI volume names
# V3.8 - for -u command: if start offset not defined - auto skip CKSM header size (0x40 bytes) for CKSM partition; if offset set to 0 - force use 0 (does not use auto skip)
# V3.9 - extract files from UBI via -u command using ubireader
# V4.0 - add -c command: compress partition by ID and merge to firmware file (only CKSM<--UBI support now, WIP)


import os, struct, sys, argparse, array
from datetime import datetime
import zlib
import lzma
import subprocess


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


def get_args():
    global in_file
    global is_extract
    global is_uncompress
    global is_compress
    global is_silent

    p = argparse.ArgumentParser(add_help=True, description='This script working with ARM-based Novatek firmware binary file. Creator: Dex9999(4pda.to user) aka Dex aka EgorKin')
    p.add_argument('-i',metavar='filename', nargs=1, help='input file')
    p.add_argument('-x',metavar=('partID', 'offset'), nargs='+', help='extract partition by ID with optional start offset. Or all partitions if partID = ALL')
    p.add_argument('-r',metavar=('partID', 'offset', 'filename'), nargs=3, help='replace partition by ID with start offset using iput file')
    p.add_argument('-u',metavar=('partID', 'offset'), type=int, nargs='+', help='uncompress partition by ID with optional start offset')
    p.add_argument('-c',metavar=('partID', 'offset'), type=int, nargs='+', help='compress partition by ID and merge to firmware file with optional start offset')
    p.add_argument('-fixCRC', action='store_true', help='fix CRC value for all possible partitions')
    p.add_argument('-silent', action='store_true', help='do not print messages')
    #p.add_argument('-o',metavar='output',nargs=1,help='output file')
    #print("len=%i" %(len(sys.argv)))
    if len(sys.argv) < 3:
        p.print_help(sys.stderr)
        sys.exit(1)

    args=p.parse_args(sys.argv[1:])
    in_file=args.i[0]

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

    if args.c:
        is_compress = args.c[0]
        # если задан 2ой аргумент - offset
        if len(args.c) == 2:
            is_compress_offset = int(args.c[1])
        else:
            # если offset не задан - то будет -1 для того чтобы дальше присвоить либо 0x40 (для CKSM) либо 0 (в остальных случаях)
            is_compress_offset = -1
    else:
        is_compress = -1
        is_compress_offset = -1

    if args.fixCRC:
        fixCRC_partID = 1
    else:
        fixCRC_partID = -1

    if args.silent:
        is_silent = 1
    else:
        is_silent = -1


    return (in_file, is_extract, is_extract_offset, is_extract_all, is_replace, is_replace_offset, is_replace_file, is_uncompress, is_uncompress_offset, is_compress, is_compress_offset, fixCRC_partID)



def MemCheck_CalcCheckSum16Bit(in_offset, uiLen, ignoreCRCoffset):
    global in_file
    uiSum = 0
    pos = 0
    num_words = uiLen // 2
    
    fin = open(in_file, 'rb')
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



def compress(part_nr, offset, in2_file):
    global in_file

    fin = open(in_file, 'rb')
    fin.seek(part_startoffset[part_nr], 0)
    FourCC = fin.read(4)

    if FourCC != b'CKSM':
        print('\033[91mNot CKSM partition, exit\033[0m')
        exit(0)

    # skip CKSM
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
    fpartout = open('./' + in2_file + '/' + 'tempfile', 'w+b')
    fpartout.write(finread)
    fpartout.close()

    # delete temp dir for info - ubireader require clear folder
    subprocess.run('rm -rf ' + in2_file + '/tempdir', shell=True)

    # get info about UBI to compressing script
    subprocess.check_output('ubireader_utils_info ' + '-o ' + in2_file + '/tempdir ./' + in2_file + '/' + 'tempfile', shell=True)

    # delete tempfile
    subprocess.run('rm ' + in2_file + '/tempfile', shell=True)

    # получим имя папки в которую была распакована партиция (пока я видел чисто цифровые имена, тоже что и image_seq -Q в выводе ubireader_utils_info)
    d = os.popen('(cd ' + in2_file + '&& find -maxdepth 1 -wholename "./*" -not -wholename "./temp*" -type d)').read()

    # проверим что нашли
    if not os.path.exists(in2_file + d[1:-1]):
        print('\033[91mNo input valid folder in %s found, exit\033[0m' % in2_file)
        exit(0)

    # d[2:-1] уберем ./ в начале и новую строку в конце имени папки
    d = d[2:-1]
    
    # fix ini-file: delete line "vol_flags=0" it cause error "unknown flags"
    subprocess.run('(cd ' + in2_file + '/tempdir/tempfile/img-' + d + ' && sed -i "/vol_flags = 0/d" img-' + d + '.ini)', shell=True)

    # run compilation dir to ubi script    
    subprocess.run('(cd ' + in2_file + '/tempdir/tempfile/img-' + d + ' && ./create_ubi_img-' + d + '.sh ../../../' + d + '/*)', shell=True)

    # hide output print
    global is_silent
    is_silent = 1
    
    # replace partition
    if offset == -1:
        partition_replace(part_id[part_nr], 0x40, in2_file + '/tempdir/tempfile/img-' + d + '/img-' + d + '.ubi')
    else:
        partition_replace(part_id[part_nr], offset, in2_file + '/tempdir/tempfile/img-' + d + '/img-' + d + '.ubi')

    # delete temp dir for info
    subprocess.run('rm -rf ' + in2_file + '/tempdir', shell=True)

    # fix CRC
    is_silent = 0
    fixCRC(part_id[part_nr])



def uncompress(in_offset, out_filename, size):
    global in_file

    fin = open(in_file, 'rb')
    # check BCL1 marker at start of partition    
    fin.seek(in_offset, 0)
    FourCC = fin.read(4)


    if FourCC == b'BCL1':
        fin.close()
        BCL1_uncompress(in_offset)
        return

    if FourCC == b'UBI#':
        #create dir with similar name as for other parttition types
        os.system('rm -rf ' + out_filename)
        os.system('mkdir ' + out_filename)

        #extract UBI partition to tempfile
        fin.seek(in_offset, 0)
        finread = fin.read(size)
        fin.close()
        fpartout = open('./' + out_filename + '/' + 'tempfile', 'w+b')
        fpartout.write(finread)
        fpartout.close()

        #unpack UBIFS to created dir
        os.system('ubireader_extract_files -k -i -f ' + '-o ' + out_filename + ' ./' + out_filename + '/' + 'tempfile')

        # delete tempfile
        os.system('rm -rf ' + './' + out_filename + '/' + 'tempfile')
        return

    print("\033[91mBCL1 or UBI# markers not found, exit\033[0m")
    fin.close()


def BCL1_uncompress(in_offset):
    global in_file
    global out_file


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


    fout = open(out_file, 'w+b')

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
    
        # Main decompression loop
        outpos = 0;
        while((inpos < insize) & (outpos < outsize)):
            symbol = struct.unpack('B', fin.read(1))[0]
            inpos += 1
    
            if symbol == marker:
                # We had a marker byte
                readbyte = struct.unpack('B', fin.read(1))[0]
                if readbyte == 0:
                    # It was a single occurrence of the marker byte
                    fout.write(struct.pack('B', marker))
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
    
                    length = y;
                    inpos += num_bytes;
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
    
                    offset = y;
                    inpos += num_bytes;
                    #print("offset = 0x%0x" % (offset))
                    #=================================================
    
                    # Copy corresponding data from history window
                    #out[ outpos ] = out[ outpos - offset ];
                    for i in range(length):
                        fout.seek(outpos - offset, 0)
                        out = struct.unpack('B', fout.read(1))[0]
                        fout.seek(outpos, 0)
                        fout.write(struct.pack('B', out))
                        outpos += 1
            else:
                # No marker, plain copy
                fout.write(struct.pack('B', symbol))
                outpos += 1

        fin.close()
        fout.close()
    
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
        t = struct.unpack('b', fin.read(1))[0]
        while(t != 0x00):
            id_length+=1
            t = struct.unpack('b', fin.read(1))[0]
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
                    alreadyfound = 1 # чтобы снова не добавлять инфу из партиции fdt.restore





def GetPartitionInfo(start_offset, part_size, partID, addinfo = 1):
    global in_file
    
    
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
            fin.close()
        return temp_parttype, CRC


    # uboot
    if partID == 3:
        temp_parttype = 'uboot'
        fin.seek(start_offset + 0x36E, 0)
        CRC = MemCheck_CalcCheckSum16Bit(start_offset, part_size, 0x36E)
        if addinfo:
            part_type.append(temp_parttype)
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
    if partfirst4bytes == 0x27051956:
        temp_parttype = 'uImage'

        # Operating System
        fin.seek(start_offset + 28, 0)
        temp = struct.unpack('b', fin.read(1))[0]
        if temp in uImage_os:
            temp_parttype += ', OS: ' + '\"\033[93m' + uImage_os[temp] + '\033[0m\"'
        else:
            temp_parttype += ''

        # CPU architecture
        #fin.seek(part_offset[2] + 29, 0)
        temp = struct.unpack('b', fin.read(1))[0]
        if temp in uImage_arch:
            temp_parttype += ', CPU: ' + '\"\033[93m' + uImage_arch[temp] + '\033[0m\"'
        else:
            temp_parttype += ''

        # Image Type
        #fin.seek(part_offset[2] + 30, 0)
        temp = struct.unpack('b', fin.read(1))[0]
        if temp in uImage_imagetype:
            temp_parttype += ', Image type: ' + '\"\033[93m' + uImage_imagetype[temp] + '\033[0m\"'
        else:
            temp_parttype += ''

        # Compression Type
        #fin.seek(part_offset[2] + 31, 0)
        temp = struct.unpack('b', fin.read(1))[0]
        if temp in uImage_compressiontype:
            temp_parttype += ', Compression type: ' + '\"\033[93m' + uImage_compressiontype[temp] + '\033[0m\"'
        else:
            temp_parttype += ''

        # Image Name
        #fin.seek(part_offset[2] + 32, 0)
        temp_parttype += ', Image name: ' + '\"\033[93m' + str(fin.read(32)).replace("\\x00","")[2:-1] + '\033[0m\"' #[2:-1] for remove b' at start and ' at end and \x00 after name

        # Image Creation Timestamp
        fin.seek(start_offset + 8, 0)
        ts = struct.unpack('>I', fin.read(4))[0]
        temp_parttype += ', created: ' + '\"\033[93m' + datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') + '\033[0m\"'

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
            
            CRC = MemCheck_CalcCheckSum16Bit(start_offset, uilength, 0x36)
            
            if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(uiChkValue)
                part_crcCalc.append(CRC)
                fin.close()
            return temp_parttype, CRC


    # BCL1
    if partfirst4bytes == 0x42434C31:
        temp_parttype = '\033[93mBCL1\033[0m'

        fin.seek(start_offset + 6, 0)        
        # compression algo
        compressAlgo = struct.unpack('>H', fin.read(2))[0]
        if compressAlgo in compressAlgoTypes:
            temp_parttype += ', \033[93m' + compressAlgoTypes[compressAlgo] + '\033[0m'
        else:
            temp_parttype += ', \033[91mcomp.algo:0x%0X\033[0m' % compressAlgo

        unpackedSize = struct.unpack('>I', fin.read(4))[0]
        packedSize = struct.unpack('>I', fin.read(4))[0]
        temp_parttype += ' \033[93m' + str(unpackedSize) + '\033[0m packed to \033[93m' + str(packedSize) + '\033[0m bytes'
        CRC = 0
        
        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
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
        t = struct.unpack('b', fin.read(1))[0]
        while(t != 0x00):
            id_length += 1
            t = struct.unpack('b', fin.read(1))[0]
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

            CRC = MemCheck_CalcCheckSum16Bit(start_offset, uiDataOffset + uiDataSize + uiPaddingSize, 0xC)

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




def partition_replace(is_replace, is_replace_offset, is_replace_file):
    global partitions_count

    part_nr = -1
    for a in range(partitions_count):
        if part_id[a] == is_replace:
            part_nr = a
            break
    if part_nr != -1:
        if is_silent != 1:
            print('Replace partition ID %i from 0x%08X + 0x%08X using inputfile \033[93m%s\033[0m' % (is_replace, part_startoffset[part_nr], is_replace_offset, is_replace_file))
        freplace = open(is_replace_file, 'rb')
        freplacedata = freplace.read()
        freplace.close()
        
        if (len(freplacedata) + is_replace_offset) == part_size[part_nr]:
            fin = open(in_file, 'r+b')
            fin.seek(part_startoffset[part_nr] + is_replace_offset, 0)
            fin.write(freplacedata)
            fin.close()
        else:
            print('\033[91mError: Input data size and partition size is not same! Cancelled.\033[0m')
    else:
        print('\033[91mCould not find partiton with ID %i\033[0m' % is_replace)



def fixCRC(partID):
    global partitions_count
    
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
                    return
                # fix CRC for MODELEXT
                if part_type[a][:13] == 'MODELEXT INFO':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0x36, 0)
                    fin.write(struct.pack('<H', calcCRC))
                    fin.close()
                    if is_silent != 1:
                        print('Partition ID ' + str(part_id[a]) + ' - \033[94mCRC fixed\033[0m')
                    return
                # fix CRC for CKSM
                if part_type[a][:13] == '\033[93mCKSM\033[0m':
                    fin = open(in_file, 'r+b')
                    fin.seek(part_startoffset[a] + 0xC, 0)
                    fin.write(struct.pack('<I', calcCRC))
                    fin.close()
                    if is_silent != 1:
                        print('Partition ID ' + str(part_id[a]) + ' - \033[94mCRC fixed\033[0m')
                    return
            else:
                if is_silent != 1:
                    print('Partition ID ' + str(part_id[a]) + ' - fix CRC not required')


def main():
    global in_file
    #global in_offset
    global out_file
    in_file, is_extract, is_extract_offset, is_extract_all, is_replace, is_replace_offset, is_replace_file, is_uncompress, is_uncompress_offset, is_compress, is_compress_offset, fixCRC_partID = get_args()
    global partitions_count

    partitions_count = 0
    fin = open(in_file, 'rb')

    #os.system('color')

    # NVTPACK_FW_HDR2 GUID check
    FW_HDR2 = 0
    
    if struct.unpack('<I', fin.read(4))[0] == 0xD6012E07:
        if struct.unpack('<H', fin.read(2))[0] == 0x10BC:
            if struct.unpack('<H', fin.read(2))[0] == 0x4F91:
                if struct.unpack('>H', fin.read(2))[0] == 0xB28A:
                    if struct.unpack('>I', fin.read(4))[0] == 0x352F8226:
                        if struct.unpack('>H', fin.read(2))[0] == 0x1A50:
                            FW_HDR2 = 1
    
    if FW_HDR2 == 1:
        if is_silent != 1:
            print("\033[93mNVTPACK_FW_HDR2\033[0m found")
    else:
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
                checksum = struct.unpack('<I', fin.read(4))[0]
                partitions_count = struct.unpack('<I', fin.read(4))[0] + 1  # + 1 так как есть еще нулевая BCL1 партиция
                print('Found \033[93m%i\033[0m partitions' % (partitions_count))

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

        fin.close()

    
    if FW_HDR2 == 1:
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
        checksum_method = struct.unpack('<I', fin.read(4))[0]
        checksum_value = struct.unpack('<I', fin.read(4))[0]
        if is_silent != 1:
            print('Found \033[93m%i\033[0m partitions' % partitions_count)
            print('Firmware file size \033[93m{:>11,}\033[0m bytes'.format(total_file_size).replace(',', ' '))
    
    
        # если есть команда извлечь или заменить или распаковать или запаковать партицию то CRC не считаем чтобы не тормозить
        if (is_extract == -1 & is_replace == -1 & is_uncompress == -1 & is_compress == -1):
            CRC_FW = MemCheck_CalcCheckSum16Bit(0, total_file_size, 0x24)
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

        # looking into dtb partition for partition id - name - filename info
        SearchPartNamesInDTB(partitions_count)
        
        
        
    
    # для всех - и для FW_HDR и для FW_HDR2
    
    # extract partition by ID to outputfile
    if is_extract != -1:
        part_nr = -1
        if is_extract_all != 1:
            for a in range(partitions_count):
                if part_id[a] == is_extract:
                    part_nr = a
                    break
            if part_nr != -1:
                out_file = in_file + '-partitionID' + str(part_id[part_nr])
                
                if is_extract_offset != -1:
                    if is_silent != 1:
                        print('Extract partition ID %i from 0x%08X + 0x%08X to file \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], is_extract_offset, out_file))
                else:
                    if is_silent != 1:
                        print('Extract partition ID %i from 0x%08X to file \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], out_file))
                    is_extract_offset = 0

                fin.seek(part_startoffset[part_nr] + is_extract_offset, 0)
                finread = fin.read(part_size[part_nr] - is_extract_offset)
                
                fpartout = open(out_file, 'w+b')
                fpartout.write(finread)
                fpartout.close()
            else:
                print('\033[91mCould not find partiton with ID %i\033[0m' % is_extract)
        else:
            # extract all partitions
            for part_nr in range(partitions_count):
                if part_nr != -1:
                    out_file = in_file + '-partitionID' + str(part_id[part_nr])
                    
                    if is_silent != 1:
                        print('Extract partition ID %i from 0x%08X to file \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], out_file))
                    fin.seek(part_startoffset[part_nr], 0)
                    finread = fin.read(part_size[part_nr])
                    
                    fpartout = open(out_file, 'w+b')
                    fpartout.write(finread)
                    fpartout.close()
                else:
                    print('\033[91mCould not find partiton with ID %i\033[0m' % part_id[part_nr])
                    
        fin.close()
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
            out_file = in_file + '-uncomp_partitionID' + str(part_id[part_nr])
            
            if is_uncompress_offset != -1:
                if is_silent != 1:
                    print('Uncompress partition ID %i from 0x%08X + 0x%08X to \033[93m%s\033[0m' % (part_id[part_nr], part_startoffset[part_nr], is_uncompress_offset, out_file))
            else:
                if is_silent != 1:
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
            in2_file = in_file + '-uncomp_partitionID' + str(part_id[part_nr])

            if is_compress_offset != -1:
                if is_silent != 1:
                    print('Compress \033[93m%s\033[0m to partition ID %i at 0x%08X + 0x%08X' % (in2_file, part_id[part_nr], part_startoffset[part_nr], is_compress_offset))
            else:
                if is_silent != 1:
                    print('Compress \033[93m%s\033[0m to partition ID %i at 0x%08X' % (in2_file, part_id[part_nr], part_startoffset[part_nr]))

            compress(part_nr, is_compress_offset, in2_file)

        else:
            print('\033[91mCould not find partiton with ID %i\033[0m' % is_compress)
        fin.close()
        exit(0)


    fin.close()



    # если вообще что-то нашли
    if partitions_count > 0:
        # если что-то нашли в dtb то выводим расширенную информацию
        if len(dtbpart_ID) != 0:
            print(" -------------------------------------------------- PARTITIONS INFO ---------------------------------------------------")
            print("|  ID   Name            start_offset  end_offset         size       ORIG_CRC   CALC_CRC              type              |")
            print(" ----------------------------------------------------------------------------------------------------------------------")
        
            for a in range(partitions_count):
                if part_crc[a] != part_crcCalc[a]:
                    if fixCRC_partID != -1:
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
        
                if part_crc[a] == part_crcCalc[a]:
                    print("  %2i    %-15s  0x%08X - 0x%08X     %9i       0x%04X     \033[92m0x%04X\033[0m       %s" % (part_id[a], dtbpart_name[part_id[a]], part_startoffset[a], part_endoffset[a], part_size[a], part_crc[a], part_crcCalc[a], part_type[a]))
                else:
                    print("  %2i    %-15s  0x%08X - 0x%08X     %9i       0x%04X     \033[91m0x%04X\033[0m       %s" % (part_id[a], dtbpart_name[part_id[a]], part_startoffset[a], part_endoffset[a], part_size[a], part_crc[a], part_crcCalc[a], part_type[a]))
            print(" ----------------------------------------------------------------------------------------------------------------------")
        else:
            print(" -------------------------------------------------- PARTITIONS INFO ---------------------------------------------------")
            print("|  ID   start_offset  end_offset         size       ORIG_CRC   CALC_CRC                        type                    |")
            print(" ----------------------------------------------------------------------------------------------------------------------")
        
            for a in range(partitions_count):
                if part_crc[a] != part_crcCalc[a]:
                    if fixCRC_partID != -1:
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
        
                if part_crc[a] == part_crcCalc[a]:
                    print("  %2i     0x%08X - 0x%08X     %9i       0x%04X     \033[92m0x%04X\033[0m       %s" % (part_id[a], part_startoffset[a], part_endoffset[a], part_size[a], part_crc[a], part_crcCalc[a], part_type[a]))
                else:
                    print("  %2i     0x%08X - 0x%08X     %9i       0x%04X     \033[91m0x%04X\033[0m       %s" % (part_id[a], part_startoffset[a], part_endoffset[a], part_size[a], part_crc[a], part_crcCalc[a], part_type[a]))
            print(" ----------------------------------------------------------------------------------------------------------------------")

        if fixCRC_partID != -1:
            CRC_FW = MemCheck_CalcCheckSum16Bit(0, total_file_size, 0x24)
            if checksum_value == CRC_FW:
                print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
            else:
                print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m' % (checksum_value, CRC_FW))




if __name__ == "__main__":
    main()
