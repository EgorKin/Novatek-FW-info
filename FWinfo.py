# Creator: Dex9999(4pda.to user) aka Dex aka EgorKin

# V2.0 - improve parsing, now support Viofo A139 and 70Mai A500S firmwares
# V2.1 - add LZ77 unpacker
# V3.0 - add get info about partition names from fdt(dtb) partition
# V3.1 - add MODELEXT INFO partition support
 

import os, struct, sys, argparse, array
from datetime import datetime
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
    0x0B : 'LZMA',  #вроде бы так
    0x0C : 'ZLIB'  #вроде бы так
}


def get_args():
    global in_file
    global is_extract
    global is_uncompress

    p = argparse.ArgumentParser(add_help=True, description='This script working with ARM-based Novatek firmware binary file. Creator: Dex9999(4pda.to user) aka Dex aka EgorKin')
    p.add_argument('-i',metavar='filename', nargs=1, help='input file')
    p.add_argument('-x',metavar=('partID', 'offset'), type=int, nargs=2, help='extract partition by ID with start offset')
    p.add_argument('-r',metavar=('partID', 'offset', 'filename'), nargs=3, help='replace partition by ID with start offset using iput file')
    p.add_argument('-u',metavar=('partID'), type=int, nargs=1, help='uncompress partition by ID')
    p.add_argument('-fixCRC', action='store_true', help='fix CRC value for all possible partitions')
    #p.add_argument('-o',metavar='output',nargs=1,help='output file')
    #print("len=%i" %(len(sys.argv)))
    if len(sys.argv) < 3:
        p.print_help(sys.stderr)
        sys.exit(1)

    args=p.parse_args(sys.argv[1:])
    in_file=args.i[0]

    if args.x:
        is_extract = args.x[0]
        is_extract_offset = args.x[1]
    else:
        is_extract = -1
        is_extract_offset = -1

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
    else:
        is_uncompress = -1

    if args.fixCRC:
        fixCRC_partID = 1
    else:
        fixCRC_partID = -1


    return (in_file, is_extract, is_extract_offset, is_replace, is_replace_offset, is_replace_file, is_uncompress, fixCRC_partID)



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

  
    
   

def lz_uncompress(in_offset):
    global in_file
    global out_file
    

    fin = open(in_file, 'rb')

    # check BCL1 marker at start of partition    
    fin.seek(in_offset, 0)
    FourCC = fin.read(4)
    if FourCC != b'BCL1':
        print("\033[91mBCL1 marker not found, exit\033[0m")
        sys.exit(1)
    
    # check compression algo - must be LZ (0x0009)
    fin.read(2)
    Algorithm = struct.unpack('>H', fin.read(2))[0]
    if Algorithm!=0x09:
        print("\033[91mCompression algo is not LZ, exit\033[0m")
        sys.exit(1)


    fout = open(out_file, 'w+b')
    
    outsize = struct.unpack('>I', fin.read(4))[0]
    insize = struct.unpack('>I', fin.read(4))[0]

    in_offset = in_offset + 0x10 #skip BCL1 header
    fin.seek(in_offset, 0)

	# Get marker symbol from input stream
    marker = struct.unpack('B', fin.read(1))[0]
    #print("LZ marker = 0x%0X" % marker)
    inpos = 1

    # Main decompression loop
    outpos = 0;
    while((inpos < insize) & (outpos < outsize)):
        fin.seek(in_offset + inpos, 0)
        symbol = struct.unpack('B', fin.read(1))[0]
        inpos = inpos + 1

        if symbol == marker:
            # We had a marker byte
            fin.seek(in_offset + inpos, 0)

            if struct.unpack('B', fin.read(1))[0] == 0:
                # It was a single occurrence of the marker byte
                fout.write(struct.pack('B', marker))
                outpos = outpos + 1
                inpos = inpos + 1
            else:
                # Extract true length and offset
				#inpos += lz_read_var_size( &length, &in[ inpos ] );
                #=================================================
                #print("curr file offset = 0x%0x" % (in_offset + inpos))
                y = 0
                num_bytes = 0
                
                fin.seek(in_offset + inpos, 0)
                b = struct.unpack('B', fin.read(1))[0]
                y = (y << 7) | (b & 0x0000007f)
                num_bytes = num_bytes + 1
                
                while (b & 0x00000080) != 0:
                    b = struct.unpack('B', fin.read(1))[0]
                    y = (y << 7) | (b & 0x0000007f)
                    num_bytes = num_bytes + 1

                length = y;
                inpos = inpos + num_bytes;
                #=================================================
                #print("length = 0x%0x" % (length))
                
				#inpos += lz_read_var_size( &offset, &in[ inpos ] );
                #=================================================
                y = 0
                num_bytes = 0
                
                fin.seek(in_offset + inpos, 0)
                b = struct.unpack('B', fin.read(1))[0]
                y = (y << 7) | (b & 0x0000007f)
                num_bytes = num_bytes + 1
                
                while (b & 0x00000080) != 0:
                    b = struct.unpack('B', fin.read(1))[0]
                    y = (y << 7) | (b & 0x0000007f)
                    num_bytes = num_bytes + 1

                offset = y;
                inpos = inpos + num_bytes;
                #=================================================
                #print("offset = 0x%0x" % (offset))

                # Copy corresponding data from history window
                for i in range(length):
                    #out[ outpos ] = out[ outpos - offset ];
                    fout.seek(outpos - offset, 0)
                    out = struct.unpack('B', fout.read(1))[0]
                    
                    fout.seek(outpos, 0)
                    fout.write(struct.pack('B', out))
                    
                    outpos = outpos + 1
        else:
            # No marker, plain copy
            fout.write(struct.pack('B', symbol))
            outpos = outpos + 1

    fin.close()
    fout.close()


def fillIDPartNames(startat):
    global in_file
    
    
    fin = open(in_file, 'r+b')
    fin.seek(startat+0x34, 0)

    #-----начали 1 секцию----
    starting = struct.unpack('>I', fin.read(4))[0] #00000001
    while(starting == 0x00000001):
        #вычисляем длину id
        id_lenght = 0
        t = struct.unpack('b', fin.read(1))[0]
        while(t != 0x00):
            id_lenght+=1
            t = struct.unpack('b', fin.read(1))[0]
        #print(id_lenght)
        fin.seek(-1*(id_lenght+1), 1) # вернемся на начало имени id
        # считаем idx
        idname = str(struct.unpack('%ds' % (id_lenght), fin.read(id_lenght))[0])[2:-1] #отрезает b` `
        #print(idname)
        dtbpart_ID.append(idname)
        fin.read(4 - (id_lenght%4)) #дочитываем все 00 которые нужны для выравнивания по 4 байта
        
        fin.read(4) #00000003
        lenghtname = struct.unpack('>I', fin.read(4))[0]
        fin.read(4) #00000223
        shortname = str(struct.unpack('%ds' % (lenghtname-1), fin.read(lenghtname-1))[0])[2:-1] #отрезает b` `
        #print(shortname)
        dtbpart_name.append(shortname)
        if lenghtname > 1:
            fin.read(4 - ((lenghtname-1)%4)) #дочитываем все 00 которые нужны для выравнивания по 4 байта
        else:
            fin.read(4) #если имени нет то дочитываются все 4 байта
        
        fin.read(4) #00000003
        lenghtfilename = struct.unpack('>I', fin.read(4))[0]
        fin.read(4) #00000232
        filename = str(struct.unpack('%ds' % (lenghtfilename-1), fin.read(lenghtfilename-1))[0])[2:-1] #отрезает b` `
        #print(filename)
        dtbpart_filename.append(filename)
        if lenghtfilename > 1:
            fin.read(4 - ((lenghtfilename-1)%4)) #дочитываем все 00 которые нужны для выравнивания по 4 байта
        else:
            fin.read(4) #если имени нет то дочитываются все 4 байта
        
        fin.read(4) #00000002
        #-----закончили 1 секцию----
        
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
        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(0)
            fin.close()
        return temp_parttype


    # uboot
    if partID == 3:
        temp_parttype = 'uboot'
        fin.seek(start_offset + 0x36E, 0)
        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(struct.unpack('<H', fin.read(2))[0])
            part_crcCalc.append(MemCheck_CalcCheckSum16Bit(start_offset, part_size, 0x36E))
            fin.close()
        return temp_parttype


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

        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(0)
            fin.close()
        return temp_parttype


    # Compressed ext4 file system SPARSE image format - бывает находится внутри CKSM
    if partfirst4bytes == 0x3AFF26ED:
        temp_parttype = '\033[93mSPARSE EXT4 image\033[0m'

        if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(0)
                part_crcCalc.append(0)
                fin.close()
        return temp_parttype


    # MODELEXT info header and data
    if partfirst4bytes == 0x38000000:
        fin.seek(0xC, 1)
        if(str(struct.unpack('8s', fin.read(8))[0])[2:-1] == 'MODELEXT'):
            temp_parttype = 'MODELEXT INFO'

            temp_parttype += ', Chip:\033[93m' + str(struct.unpack('8s', fin.read(8))[0]).replace("\\x00","")[2:-1] + '\033[0m'
            fin.read(8)
            temp_parttype += ', Build:\033[93m' + str(struct.unpack('8s', fin.read(8))[0]).replace("\\x00","")[2:-1] + '\033[0m'
            uiLenght = struct.unpack('<I', fin.read(4))[0]
            fin.seek(2, 1)
            uiChkValue = struct.unpack('<H', fin.read(2))[0]
            
            if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(uiChkValue)
                part_crcCalc.append(MemCheck_CalcCheckSum16Bit(start_offset, uiLenght, 0x36))
                fin.close()
            return temp_parttype


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

        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(0)
            fin.close()
        return temp_parttype


    # UBI#
    if partfirst4bytes ==  0x55424923:
        temp_parttype = '\033[93mUBI\033[0m'

        # get UBI volume name
        #ubireader_display_info <<<$(tail -c+3621181 FWA229A.bin | head -c67502080)
        #os.system('tail -c+3621181 FWA229A.bin | head -c67502080 > temp6')
        #proc = subprocess.Popen(['ubireader_display_info temp6|grep Volume:'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        #os.system('rm ./temp6')
        #temp_parttype += ' \033[93m' + proc.communicate()[0] + '\033[0m'
            
        if addinfo:
            part_type.append(temp_parttype)
            part_crc.append(0)
            part_crcCalc.append(0)
            fin.close()
        return temp_parttype


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
            deeppart = GetPartitionInfo(start_offset + 0x40, 0, 0, 0)
            if deeppart != '':
                temp_parttype += '\033[94m<--\033[0m' + deeppart

            if addinfo:
                part_type.append(temp_parttype)
                part_crc.append(uiChkValue)
                part_crcCalc.append(MemCheck_CalcCheckSum16Bit(start_offset, uiDataOffset + uiDataSize + uiPaddingSize, 0xC))
                fin.close()
            return temp_parttype


    # unknown part
    if addinfo:
        part_type.append('\033[91munknown part\033[0m')
        part_crc.append(0)
        part_crcCalc.append(0)
        fin.close()
    return ''






def main():
    global in_file
    #global in_offset
    global out_file
    in_file, is_extract, is_extract_offset, is_replace, is_replace_offset, is_replace_file, is_uncompress, fixCRC_partID = get_args()


    fin = open(in_file, 'rb')

    #os.system('color')

    # NVTPACK_FW_HDR2 GUID check
    if struct.unpack('<I', fin.read(4))[0] == 0xD6012E07:
        if struct.unpack('<H', fin.read(2))[0] == 0x10BC:
            if struct.unpack('<H', fin.read(2))[0] == 0x4F91:
                if struct.unpack('>H', fin.read(2))[0] == 0xB28A:
                    if struct.unpack('>I', fin.read(4))[0] == 0x352F8226:
                        if struct.unpack('>H', fin.read(2))[0] == 0x1A50:
                            print("\033[93mNVTPACK_FW_HDR2\033[0m found")
    
    # NVTPACK_FW_HDR2_VERSION check
    if struct.unpack('<I', fin.read(4))[0] == 0x16071515:
        print("\033[93mNVTPACK_FW_HDR2_VERSION\033[0m found")
    else:
        print("\033[91mNVTPACK_FW_HDR2_VERSION\033[0m not found")
        exit(0)
    
    NVTPACK_FW_HDR2_size = struct.unpack('<I', fin.read(4))[0]
    partitions_count = struct.unpack('<I', fin.read(4))[0]
    total_file_size = struct.unpack('<I', fin.read(4))[0]
    checksum_method = struct.unpack('<I', fin.read(4))[0]
    checksum_value = struct.unpack('<I', fin.read(4))[0]
    print('Found \033[93m%i\033[0m partitions' % partitions_count)
    print('Firmware file size \033[93m{:>11,}\033[0m bytes'.format(total_file_size).replace(',', ' '))
    
    
    # если есть команда извлечь или заменить или распаковать партицию то CRC не считаем чтобы не тормозить
    if (is_extract == -1 & is_replace == -1 & is_uncompress == -1):
        CRC_FW = MemCheck_CalcCheckSum16Bit(0, total_file_size, 0x24)
        if checksum_value == CRC_FW:
            print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[92m0x%04X\033[0m' % (checksum_value, CRC_FW))
        else:
            print('Firmware file ORIG_CRC:\033[93m0x%04X\033[0m CALC_CRC:\033[91m0x%04X\033[0m' % (checksum_value, CRC_FW))
    
    
    # read partitions table info`
    fin.seek(NVTPACK_FW_HDR2_size, 0)
    
    

    
    
    for a in range(partitions_count):
        part_startoffset.append(struct.unpack('<I', fin.read(4))[0])
        part_size.append(struct.unpack('<I', fin.read(4))[0])
        part_id.append(struct.unpack('<I', fin.read(4))[0])
        part_endoffset.append(part_startoffset[a] + part_size[a])
    
    
    # extract partition by ID to outputfile
    if is_extract != -1:
        part_nr = -1
        for a in range(partitions_count):
            if part_id[a] == is_extract:
                part_nr = a
                break
        if part_nr != -1:
            print('Extract partition ID %i from 0x%08X + 0x%08X to file \033[93m%s\033[0m' % (is_extract, part_startoffset[part_nr], is_extract_offset, in_file + '-partitionID' + str(is_extract)))
            fin.seek(part_startoffset[part_nr] + is_extract_offset, 0)
            finread = fin.read(part_size[part_nr] - is_extract_offset)
            
            fpartout = open(in_file + '-partitionID' + str(is_extract), 'w+b')
            fpartout.write(finread)
            fpartout.close()
        else:
            print('\033[91mCould not find partiton with ID %i\033[0m' % is_extract)
        fin.close()
        exit(0)


    # replace partition by ID with inputfile
    if is_replace != -1:
        part_nr = -1
        for a in range(partitions_count):
            if part_id[a] == is_replace:
                part_nr = a
                break
        if part_nr != -1:
            print('Replace partition ID %i from 0x%08X + 0x%08X using inputfile \033[93m%s\033[0m' % (is_replace, part_startoffset[part_nr], is_replace_offset, is_replace_file))
            fin.close()
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
        fin.close()
        exit(0)


    # uncompress partition by ID (if it possible, only LZ77 now)
    if is_uncompress != -1:
        part_nr = -1
        for a in range(partitions_count):
            if part_id[a] == is_uncompress:
                part_nr = a
                break
        if part_nr != -1:
            print('Uncompress partition ID %i from 0x%08X to file \033[93m%s\033[0m' % (is_uncompress, part_startoffset[part_nr], in_file + '-uncomp_partitionID' + str(is_uncompress)))
            out_file = in_file + '-uncomp_partitionID' + str(is_uncompress)
            lz_uncompress(part_startoffset[part_nr])
            
        else:
            print('\033[91mCould not find partiton with ID %i\033[0m' % is_uncompress)
        fin.close()
        exit(0)



    # read each partition info
    for a in range(partitions_count):
        GetPartitionInfo(part_startoffset[a], part_size[a], part_id[a])

    fin.close()



    # looking into dtb partition for partition id - name - filename info
    SearchPartNamesInDTB(partitions_count)


    # если что-то нашли в dtb ты выводим расширенную информацию
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
                    # fix CRC for MODELEXT
                    if part_type[a][:13] == 'MODELEXT INFO':
                        fin = open(in_file, 'r+b')
                        fin.seek(part_startoffset[a] + 0x36, 0)
                        fin.write(struct.pack('<H', part_crcCalc[a]))
                        fin.close()
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





if __name__ == "__main__":
    main()
