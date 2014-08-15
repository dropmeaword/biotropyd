#!/bin/python
import serial
import time
import os
import threading
import logging
import OSC
import optparse
import struct


def from_lil_bytes(l):
    x = 0
    for i in range(len(l)-1, -1, -1):
        x <<= 8
        x |= l[i]
    return x

def from_big_bytes(l):
    x = 0
    for i in range(len(l)):
        x <<= 8
        x |= l[i]
    return x


### logging
def setuplogging(fnnamepre, loglevel, printtostdout):
    #print "starting up with loglevel",loglevel,logging.getLevelName(loglevel)
    filename = fnnamepre + "_record_" + time.strftime("%j_%H_%M_%S", time.localtime() ) + ".log"
    print( "Writing logfile to", filename)
    logging.basicConfig(filename=filename,format='%(message)s',level=loglevel)
    if printtostdout:
        soh = logging.StreamHandler(sys.stdout)
        soh.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(soh)

def writelogentry( data ):
    global lasttime, starttime
    curtime = time.time()
    nowtime = curtime - starttime
    deltatime = curtime - lasttime
    lasttime = curtime
    data.insert( 0, deltatime )
    data.insert( 0, nowtime )  
    string = "\t".join(str(x) for x in data)
    logging.info( string )

def writeLogData( nodeid, beaconseq, packetId, timeslotPacket, frameType, data ):
    logentrydata = [ nodeid, beaconseq, packetId, timeslotPacket, frameType ]
    logentrydata.append( data )
    writelogentry( logentrydata )
### end logging


class HolstOSC( object ):
    def set_verbose( self, onoff ):
        self.verbose = onoff;


    def sendMessage( self, path, args ):
        msg = OSC.OSCMessage()
        msg.setAddress( path )
        for a in args:
            msg.append( a )
        try:
            self.host.send( msg )
            if self.verbose:
                print( "sending message", msg )
        except OSC.OSCClientError:
            if self.verbose:
                print( "error sending message", msg )

    def dataMessage( self, nodeid,  beaconseq, packetId, timeslotPacket, frameType, data ):
        alldata = [ nodeid, frameType, packetId, beaconseq, 0, timeslotPacket ]
        alldata.extend( data )
        self.sendMessage( "/holst/rawdata", alldata )
        if self.verbose:
            print( "sending osc message with data", nodeid, data )

    def eventMessage( self, nodeid, beaconseq, packetId, timeslotPacket, frameType, eventType, eventData ):
        if eventType == 0x10:
            alldata = [ nodeid, frameType, packetId, beaconseq, eventType, timeslotPacket, 0 ]
            b = ""
            for byte in eventData[0:8]:
                b = b + chr( byte )
            alldata.append( struct.unpack( '<d', b ) )
            self.sendMessage( "/holst/event", alldata )
        if self.verbose:
            print( "sending osc message with event data", nodeid, eventType, eventData )

    def __init__(self, hostip, hostport ): #, myip, myport, hive ):
        self.verbose = False
        self.hostport = hostport
        self.hostip = hostip

        self.host = OSC.OSCClient()
        send_address = ( self.hostip, self.hostport )
        self.host.connect( send_address )

    def set_serial( self, serial ):
        self.serial = serial


class HolstSerial(object):
    def __init__(self, serial_port, baudrate = 1000000 ):
        self.serial = serial.Serial()  # open first serial port
        self.serial.baudrate = baudrate
        self.serial.port = serial_port

        self.open_serial_port()

        self.preamble = 0
        self.mac = 0
        self.appl = 0
        self.logAction = None
        self.verbose = False

        self.cb_heartbeat = None # heartbeat callback
        self.cb_alldata = None # callback for ANY data

    def isOpen( self ):
        return self.serial.isOpen()

    def init_comm( self ):
        print( "initialising communication through serial port")

    def open_serial_port( self ):
        try:
            self.serial.open()
        except:
            print( "could not open serial port", self.serial.port )
            os._exit(1)

    def set_verbose( self, onoff ):
        self.verbose = onoff
        if onoff:
            print( self.serial )
            print( self.serial.portstr )       # check which port was really used

    def set_osc( self, osc ):
        self.osc = osc

    def set_log_action( self, action ):
        self.logAction = action

    def read_byte( self, nrbytes ):
        b = self.serial.read( nrbytes )
        # callback with newly read data
        if self.cb_alldata:
            self.cb_alldata(b)

        if len( b ) > 0 :
            for byt in b:
              newbyte = ord( byt )

              if self.preamble == 0 and newbyte == ord('D'):
                  self.preamble = 1
              elif self.preamble == 1 and newbyte == ord('A'):
                  self.preamble = 2
              elif self.preamble == 2 and newbyte == ord('T'):
                  self.preamble = 3
                  self.mac = 0
              elif self.preamble == 3:
                  if self.mac == 0:
                      self.nodeid = newbyte
                      self.beacon = []
                      self.mac = 1
                  elif 0 < self.mac < 5:
                      self.beacon.append( newbyte )
                      self.mac = self.mac + 1
                      if self.mac == 5:
                          self.appl = 0
                          self.application = []
                  elif self.mac == 5:
                      self.application.append( newbyte )
                      self.appl = self.appl + 1
                      if self.appl == 26:
                          self.parse_package( self.nodeid, self.beacon, self.application )
                          self.preamble = 0

    def parse_package( self, nodeid, beacon, application ):
        beaconseq = from_lil_bytes( beacon )
        timeslotPacket = application[0] + ((application[1] & 0xF8) << 5)
        frameType = application[1] & 0x07
        packetId = (application[2] + (application[3] << 8)) & 0x0000FFF
        if frameType == 3: # event
            eventType = application[4]
            eventData = application[5:]
            if self.cb_heartbeat:
                self.cb_heartbeat( "{0}".format(eventData) )
            self.osc.eventMessage( nodeid, beaconseq, packetId, timeslotPacket, frameType, eventType, eventData )
        else: # data
            payload = []
            payload.append( (application[3] & 0x000000F0) )
            payload.extend( application[4:] )
            change = False
            data = []
            payloadindex = 0
            #for byte in payload:
            for i in range(0,15):
              if change:
                      newdata = payload[ payloadindex ] + (( payload[ payloadindex + 1 ] & 0x0000000F) << 8 )
                      change = False
                      payloadindex = payloadindex + 1
              else:
                      newdata = payload[ payloadindex + 1 ] + (( payload[ payloadindex ] & 0x000000F0) << 4 )
                      change = True
                      payloadindex = payloadindex + 2
              data.append( newdata )

            self.osc.dataMessage( nodeid, beaconseq, packetId, timeslotPacket, frameType, data )
            if self.logAction != None:
                self.logAction( nodeid, beaconseq, packetId, timeslotPacket, frameType, data )

    def read_data( self ):
        bytes_toread = self.serial.inWaiting()
        self.read_byte( bytes_toread )

    def start_recording( self, mid ):
        self.send_cmd( 'N', mid, 0xA3, 0, 0 )

    def stop_recording( self, mid ):
        self.send_cmd( 'N', mid, 0xA4, 0, 0 )

    def send_cmd( self, cmdType, destination, cmd, arg1, arg2 ):
        msg = [ ord('C' ) ]
        msg.append( ord( cmdType ) )
        msg.append( destination )
        msg.append( arg1 )
        msg.append( arg2 )
        self.serial.write( msg )
        if self.verbose:
            print( "sending message", msg )

if __name__ == "__main__":

    option_parser_class = optparse.OptionParser
    parser = option_parser_class(description='Create a program that speaks OSC to communicate with the minibee network.')
    
    parser.add_option('-v','--verbose', 
                        action='store_true',
                        dest="verbose",
                        default=False, 
                        help='verbose printing [default:%i]'% False)
    
    parser.add_option('-s','--serial', 
                        action='store',
                        type="string",
                        dest="serial",
                        default="COM8",
                        help='the serial port [default:%s]'% 'COM8')

    parser.add_option('-d','--host_ip', 
                        action='store',
                        type="string", 
                        dest="host",
                        default="127.0.0.1", 
                        help='the ip address of the application that has to receive the OSC messages [default:%s]'% "127.0.0.1")
    
    parser.add_option('-t','--host_port', 
                        type=int, 
                        action='store',
                        dest="hport",
                        default=57120, 
                        help='the port on which the application that has to receive the OSC messages will listen [default:%i]'% 57120 )
    
    parser.add_option('-l','--logging',
                        action='store_true',
                        default=False,
                        help='Write log entries to file')

    parser.add_option('-f','--filename', 
                        action='store',
                        type="string", 
                        dest="filename",
                        default="",
                        help='filename prefix for the recording [default:%s]'% "")

    (options,args) = parser.parse_args()

    print( "HolstOSC - communicating data from Holst sensors via OSC" )
    print( "Created OSC sender to (%s,%i) and opened serial port at %s. Now waiting for messages."%(options.host, options.hport, options.serial ) )

    holstserial = HolstSerial( options.serial, 1000000 )
    holstosc = HolstOSC( options.host, options.hport )
    holstserial.set_verbose( options.verbose )
    holstosc.set_verbose( options.verbose )

    #holstserial = HolstSerial( "/dev/ttyUSB0", 1000000 )
    #holstosc = HolstOSC( "127.0.0.1", 57120 )
    holstserial.set_osc( holstosc )
    holstosc.set_serial( holstserial )
    if options.logging:
        starttime = time.time()
        lasttime = starttime
        setuplogging( options.filename, 0, False)
        holstserial.set_log_action( writeLogData )
    else:
        print( "INFO: not logging to file" )

    while True:
        if holstserial.isOpen():
            holstserial.read_data()
            time.sleep(0.001)
