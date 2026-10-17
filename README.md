# Novatek Firmware info (NTKFWinfo)
NTKFWinfo is a lightweight, Python 3-based command-line tool designed for parsing, extracting, unpacking, and repacking Novatek chipset firmware images (.bin).
Built specifically for developers and reverse engineers working with dashcams, action cameras, and automotive electronics, this utility automates the entire process of firmware modification. It maps internal partition structures, handles proprietary compression (including LZ77), extracts individual partitions and compress it back supporting changes in its size, and safely rebuilds modified binaries with automatic checksum correction to prevent device bricking.

![Безымянный](https://github.com/user-attachments/assets/d5bb4816-9775-48ab-a422-d92f0ce3761f)

## Analysis & Information Gathering

* Structure Visualization: Scans the firmware file to map and display its complete internal partition layout, names, offsets, compressed algo and checksums.
* Metadata Extraction: Displays critical headers, version tags, compilation timestamps, and block boundaries.
* Integrity Validation: Automatically calculates, verifies and fix internal checksums of partitions and whole file to identify corrupted or incorrectly modified sections before you go to firmware update process.

## Modification & Manipulation
* Section Extraction and Unpacking: Easily splits the combined firmware image into individual, modifiable raw blocks (e.g., bootloader, kernel, resource partitions).
* Section Repacking: Allows users to view and edit extracted files - insert modified resources, alter bitrates, swap boot logos, change IQ config files and linux startup config.
* Partition Management: Supports adding new or removing existing partitions from the firmware update file.
* Checksum Correction: Automatically calculates and patches the partitions and file header checksums during the rebuild process, preventing the device from bricking upon flashing.


## Important Scope & Limitations
* **Supported Formats:** Works with any official factory firmware update files (`FW*****.bin`) for Novatek processors used in dashcams/actioncams.
* **Unsupported Formats:** Does not support ROM/chip memory dumps.

## Processor Compatibility & Supported Devices
Supports a comprehensive range of Novatek SoCs from the outdated GitUp Git1 and early Viofo series up to the Viofo A229 Pro, A329, Vantrue lineups and other manufacturers modern series.

### Tested on Core Processors
* **Classic 32-bit:** NT96650, NT96655, NT96658, NT96660, NT96663, NT96672, NT96675
* **High-Performance 2K/4K:** NT96685, NT96687, NT98520, NT98525
* **Modern 64-bit SoCs:** NT98528, NT98530

### Tested on Device Generations
* **GitUp:** Git1, Git2, Git3
* **Viofo:** A119, A129/Pro, A139, A229 Plus/Pro/Ultra, A329/S/T
* **Vantrue:** Element series (E1, E2, E3), Nexus series (N4 Pro, N5), E360, F1, S1
* and some others


Novatek FW info is available under the terms of the GNU Public License version 3.

If this project helps you, you can support me by sending any amount of BTC to address ***12q5kucN1nvWq4gn5V3WJ8LFS6mtxbymdj*** or use QR code below:

![btc](https://github.com/user-attachments/assets/32b5e7a0-0f01-4a38-b062-3162e6a79543)



## Installation:
**First of all install:**
```
sudo apt-get install python3
sudo apt-get install python3-pip
sudo apt-get install mtd-utils
sudo apt-get install liblzo2-dev
sudo apt-get install pypy3
```
**Additionaly install this python modules:**
```
sudo pip3 install python-lzo
sudo pip3 install ubi_reader
```
**For FDT(DTB) partitions support install:**
```
sudo apt-get install device-tree-compiler
```
**For SPARSE partitions support install:**
```
sudo apt-get install android-sdk-libsparse-utils
```
**For SquashFS partitions support install:**
```
sudo apt-get install squashfs-tools
```
## Basic usage:

### Show firmware partitions info:
```
python3 ./NTKFWinfo.py -i FWA229A-1208.bin
```
<img width="1103" height="328" alt="image" src="https://github.com/user-attachments/assets/a578cd5f-514c-4ed2-b8df-7dd8a94dc858" />

### Uncompress partition by ID to a file(for BCL1) or folder(for UBI or SPARSE):
```
python3 ./NTKFWinfo.py -i FWA229A-1208.bin -u 6
```
<img width="1103" height="308" alt="image" src="https://github.com/user-attachments/assets/75e8de23-5fb9-4028-8004-979b24e241e0" />
<img width="1103" height="548" alt="image" src="https://github.com/user-attachments/assets/90fcf620-a9fb-49cf-b39a-3f6da7fe361b" />

### Compress partition back to firmware binary file from uncompressed file(for BCL1) or folder(for UBI or SPARSE) and fix all CRC:
```
python3 ./NTKFWinfo.py -i FWA229A-1208.bin -c 6
```
<img width="1103" height="320" alt="image" src="https://github.com/user-attachments/assets/295bf0c0-99f7-4c14-bae8-bffc92178f03" />
<img width="1103" height="334" alt="image" src="https://github.com/user-attachments/assets/94ab409d-590a-482e-b6bf-924be0310e0f" />

## Additional(expert) commands:
### Extract partition by ID number and skip n start bytes(optionally):
(as example extract data from CKSM partition and skip first 64 CKSM-header bytes)
```
python3 ./NTKFWinfo.py -i FWA229A.bin -x 6 64
```
### Add a new partition with new ID=6 using file FWA229A.bin-partitionID6 (filename is optionally, if not defined will be used input filename appended with '-partitionID6'):
```
python3 ./NTKFWinfo.py -i FWA229A.bin -add 6 ./FWA229A.bin-partitionID6
```
Take a note that partition name, memory offset and size for a new partition ID will be used from fdt partition (if it is exist in FW). If such records is not presented in fdt partition - added partition can't be flash to the memory. You need to uncompress, modify and compress back fdt partition manually in that case to add a records about the added partition.
### Delete existing partition with ID=6 from input file:
```
python3 ./NTKFWinfo.py -i FWA229A.bin -delete 6
```
### Replace partition with ID=6 and start offset = 64 (CKSM-header size) using file img-726660551.ubi:
```
python3 ./NTKFWinfo.py -i FWA229A.bin -r 6 64 ./img-726660551.ubi
```
### Fix CRC for all known partitions(uboot, MODELEXT, BCL1, CKSM) and whole firmware file:
```
python3 ./NTKFWinfo.py -i FWA229A.bin -fixCRC
```
### Use custom directory for input/output partitions files:
```
python3 ./NTKFWinfo.py -i FWA229A.bin -u 6 -o tempdir
python3 ./NTKFWinfo.py -i FWA229A.bin -c 6 -o tempdir
```

## Speed-up compress BCL1 LZ partitions:
I suggest use pypy3 VS python3 to greatly speed-up the compression time for BCL1 LZ partitions:
```
pypy3 ./NTKFWinfo.py -i GIT3FWv2.3.bin -c 0
```
![pypy3 speed-up](https://user-images.githubusercontent.com/4955678/188559054-e3ea1152-743b-4686-8a4f-b76c0dd529ba.png)

