from laspy.file import File
from laspy.header import *
import sys

print(sys.path)
my_file = File("C:/Data/USGS_LPC_IL_4County_Cook_2017_LAS_15008550_LAS_2019.laz", mode='r')

h = my_file.header

extent = [*h.min, *h.max]

print(extent)