#dump GPS log data out of Henwood TH-D72 radio
#pip3 install pyserial gpxpy progressbar
import time
import serial
import struct
import sys
from datetime import datetime
import gpxpy
import gpxpy.gpx
import progressbar 

gps_data_header = b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xEF\xE9\x03\x00\x00\x41\x42\x0F\x00"


def readall():
    out = bytes()
    time.sleep(0.1)
    while ser.inWaiting() > 0:
        out += ser.read(1)
    return out


def get_next_chunk():
    global data_idx, chunk_no
    chunk = gps_data[data_idx:data_idx+23]
    chunk_no += 1
    data_idx += 23
    #if chunk_no % 512 == 0: #at first it appeared that there's extra data every 512 blocks, but it now looks like some blocks are just bigger
    #    data_idx += 14
    #    print(chunk.hex())
    return chunk

if len(sys.argv) != 3:
    print("python3 d72_gps_dump.py <serial_port> <gpx_file>")
    sys.exit(0)

ser = serial.Serial(port=sys.argv[1],baudrate=9600)
ser.isOpen()


print("\033[92mPutting radio into programming mode...\033[0m")
#tries to mimic what mcp-4a 
ser.write(b'TC 1\r')
print(readall().decode("ascii") )
ser.write(b'ID\r')    
print(readall().decode("ascii") )

ser.write(b'TY\r')    
print(readall().decode("ascii") )

ser.write(b'FV 0\r')    
print(readall().decode("ascii") )

ser.write(b'FV 1\r')    
print(readall().decode("ascii") )

ser.write(b'0M PROGRAM\r')    
print(readall())
time.sleep(0.5)
print("\033[92mShould be in program mode now,switching to 57600 baud\033[0m")
#programming mode is at 57600 baud
ser.baudrate = 57600
ser.write(b'R\x00\x02U\x08')    
readall() #57000255081700000000000100


ser.write(b'\x06')    # \x06 is ack ?
readall()

#ok , let's read it all
gps_data = bytes()
start_addr = 0x00000001
print("\033[92mReading data...\033[0m")
bar=progressbar.ProgressBar()
for i in bar(range(255)):
    ser.write(b"R"+struct.pack('i',start_addr+i*256))
    gps_data += readall()[5:] # reply is W<ADDRESS><256bytes of data>, skip over W and <address>
    ser.write(b'\x06')    #ack
    readall()
print("\033[92mExiting programming mode.\033[0m")    
ser.write(b'E') # get out of programming mode
ser.close()

data_idx = 0
chunk_no = 0
gpx = gpxpy.gpx.GPX()
gpx_track = gpxpy.gpx.GPXTrack()
gpx.tracks.append(gpx_track)
gpx_segment = gpxpy.gpx.GPXTrackSegment()
gpx_track.segments.append(gpx_segment)

print("\033[92mParsing binary data into gpx.\033[0m")    

#each distinct GPS log begins with this header 
if gps_data.startswith(gps_data_header):
    #looks ok, let's try to parse it in 23 byte chunks
    while True:
        chunk = get_next_chunk()
        if chunk == gps_data_header:
            print("gps data header, new track")
            gpx_track = gpxpy.gpx.GPXTrack()
            gpx.tracks.append(gpx_track)
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)            
            continue
        if chunk == b"\xFF"*23:
            print("empty chunk, probably end of the log")
            break
        (yy,MM,dd,hh,mm,sec,ndeg,nmin,nsec,wdeg,wmin,wsec,status,speed,heading,alt) = struct.unpack("=BBBBB B BBhBBhBhhi",chunk)
        #print("20%d-%d-%d %d:%d:%d : N %d %d %f W %d %d %f at %d m %d kmh %d deg heading"%(yy,MM,dd,hh,mm,sec,ndeg,nmin,nsec/167,wdeg,wmin,wsec/167,alt,speed*1.852,heading))
        point_time = datetime(yy,MM,dd,hh,mm)
        east_west = 1 if (status & 0x4) > 0 else -1
        north_south = -1 if (status & 0x2) > 0 else 1
        dlatitude = north_south*(ndeg + nmin/60. + (nsec/167.)/3600.)
        dlongitude = east_west*(wdeg + wmin/60. + (wsec/167.)/3600.)
        point = gpxpy.gpx.GPXTrackPoint(dlatitude, dlongitude,time=point_time,speed=speed*1.852,elevation=alt)
        point.course=heading
        gpx_segment.points.append(point)


f = open(sys.argv[2],"w")
f.write(gpx.to_xml(version="1.0"))
f.close()
print("\033[92mAll done.\033[0m")    



