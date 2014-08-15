#!/usr/bin/env python
# -*- coding: utf8 -*-
import sys, os
import fcntl
import struct
import argparse
import time
from OSC import *
from holst import *

__author__ = "Luis Rodil-Fernandez <root@derfunke.net>"
__mad_props__ = "Ash"
__copyright__ = "(cc) 2014 Luis Rodil-Fernandez"
__version__ = "0.9b"

default_host_address = ("127.0.0.1", 2222)  # host, port tuple

# kernel entropy pool running stats
ENTROPY_READING = '/proc/sys/kernel/random/entropy_avail'
ENTROPY_POOL_SIZE = '/proc/sys/kernel/random/poolsize'

entropy_ratio = 3  # bits of entropy per byte of data
RNDADDENTROPY = 1074287107 # from /usr/include/linux/random.h

def get_kernel_proc_reading(procfile):
	""" Linux only, get the number of bits of entropy in the pool """
	if os.path.isfile(procfile):
		with open(procfile) as f:
			reading = f.read()
			return reading.strip()

def get_entropy_measurement():
	return int(get_kernel_proc_reading(ENTROPY_READING))

def get_entropy_pool_size():
	return int(get_kernel_proc_reading(ENTROPY_POOL_SIZE))

def feed_entropy(somenoise, ratio = entropy_ratio):
	"""
	"Only entropy comes easy" -- Anton Chekhov
	"""
	fd = os.open("/dev/random", os.O_WRONLY)
	fmt = 'ii%is' % (len(somenoise)) # define format for bitstream
	rand_pool = struct.pack(fmt, ratio * len(somenoise), len(somenoise), somenoise)
	fcntl.ioctl(fd, RNDADDENTROPY, rand_pool)
	os.close(fd)

def print_info(host):
	print "Biotro.py (cc) 2014 Luis Rodil-Fernandez"
	print "Sending stuff to ", host
	print
	print "Press Ctrl+C for teletransportation."

def osc_send_biotropy(host, verbose=False):
	tx = OSCClient()
	tx.connect( host )
	msg = OSCMessage("/entropy")
	measurement = get_entropy_measurement()
	poolsize = get_entropy_pool_size() 
	msg.append( measurement )
	percentage = float(measurement * 1.0 / poolsize * 1.0)
	msg.append( percentage )
	msg.append( poolsize )

	if verbose:
		print "sending {0} {1} {2} {3}".format("/entropy", measurement, percentage, poolsize)

	tx.send( msg )
	tx.close()

def main():
	option_parser_class = optparse.OptionParser

	parser = option_parser_class(description='Create a broadcasting node that speaks OSC to communicate with the heart sensor network.')

	parser.add_option('-v','--verbose', 
		action='store_true',
		dest="verbose",
		default=False, 
		help='verbose printing [default:%i]'% False)

	parser.add_option('-a','--alldata', 
		action='store_true',
		dest="alldata",
		default=False, 
		help='use any data to feed random pool [default:%i]'% False)

	parser.add_option('-s','--serial', 
		action='store',
		type="string",
		dest="serial",
		default="/dev/ttyUSB0",
		help='the serial port [default:%s]'% '/dev/ttyUSB0')

	parser.add_option('-d','--desthost', 
		action='store',
		type="string", 
		dest="host",
		default="127.0.0.1", 
		help='the ip address of the application that has to receive the OSC messages [default:%s]'% "127.0.0.1")

	parser.add_option('-t','--hostport', 
		type=int, 
		action='store',
		dest="port",
		default=2222, 
		help='the port on which the application that has to receive the OSC messages will listen [default:%i]'% 2222 )

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

	holstserial = HolstSerial( options.serial, 1000000 )
	holstosc = HolstOSC( options.host, options.port )

	holstserial.set_verbose( options.verbose )
	holstserial.set_osc( holstosc )

	holstosc.set_verbose( options.verbose )
	holstosc.set_serial( holstserial )

	# set callbacks for feeding the pool
	holstserial.cb_heartbeat = feed_entropy
	if options.alldata:
		holstserial.cb_alldata   = feed_entropy

	if options.logging:
		starttime = time.time()
		lasttime = starttime
		setuplogging( options.filename, 0, False)
		holstserial.set_log_action( writeLogData )
	else:
		print( "INFO: not logging to file" )

	host = (options.host, options.port)
	print_info(host)

	skip_counter = 0
	try:
		while True:
			if holstserial.isOpen():
				holstserial.read_data()
				if not skip_counter % 1000:
					osc_send_biotropy(host, options.verbose)
				time.sleep(0.001)
				skip_counter += 1
	except KeyboardInterrupt, e:
		print
		print "Seems that you want to exit. Goodbye!"
		pass

if __name__ == '__main__':
	main()
