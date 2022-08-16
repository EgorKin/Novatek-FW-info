# Novatek-FW-info
Python script for work with Novatek binary firmwares - get info, modify...
![Безымянный](https://user-images.githubusercontent.com/4955678/184808463-1b5d62b6-eb76-41d9-a75a-dbd019e8f60f.png)
![Безымянный2](https://user-images.githubusercontent.com/4955678/184808917-48616d07-9d85-4656-9c44-ca424bc82cca.png)

Require install few python modules:
sudo apt-get install mtd-utils
sudo apt-get install python3
sudo apt-get install liblzo2-dev
sudo apt-get install python3-pip
sudo pip install python-lzo
sudo pip install ubi_reader


How to use:

Get firmware partitions info:
python3 ./FWinfo.py -i FWA229A-0623.bin

Extract partition by ID number and skip n start bytes:
(extract data from CKSM partition require skip 64 CKSM-header bytes.
python3 ./FWinfo.py -i FWA229A-0623.bin -x 6 64

Replace partition data with ID=6 and start offset = 64 (CKSM header size) using file img-726660551.ubi:
python3 ./FWinfo.py -i FWA229A-0623.bin -r 6 64 ./img-726660551.ubi

Fix CRC for uboot and CKSM partitions:
python3 ./FWinfo.py -i FWA229A-0623.bin -fixCRC


-------------------------------------------------------------------------------------------------------------------------


You may also extract all files from UBIFS exctracted from CKSM using ubi-reader:
ubireader_extract_files -k -i -f FWA229A-0623.bin-partitionID6

Modify something and compile back to UBI:
1) ubireader_utils_info FWA229A-0623.bin-partitionID6
2) remove line with "vol_flags = 0" in file ./ubifs-root/FWA229A-0623.bin-partitionID6/img-726660551/img-726660551.ini
3) chmod +x ./ubifs-root/FWA229A-0623.bin-partitionID6/img-726660551/create_ubi_img-726660551.sh
4) ./ubifs-root/FWA229A-0623.bin-partitionID6/img-726660551/create_ubi_img-726660551.sh ./ubifs-root/726660551/rootfs

