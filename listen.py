from OSC import *

listen_address = ('127.0.0.1', 2222)

def cb_entropy(addr, tags, stuff, source):
	msg_string = "%s [%s] %s" % (addr, tags, str(stuff))
	sys.stdout.write("OSCServer Got: '%s' from %s\n" % (msg_string, getUrlStr(source)))

def cb_ignore(addr, tags, stuff, source):
	pass

def cb_heartbeat(addr, tags, stuff, source):
	msg_string = "%s [%s] %s" % (addr, tags, str(stuff))
	sys.stdout.write("heartbeat: '%s' from %s\n" % (msg_string, getUrlStr(source)))

def main():
	s = OSCServer(listen_address)
	s.addDefaultHandlers()
	s.addMsgHandler("/entropy", cb_entropy)
	s.addMsgHandler("/holst/rawdata", cb_ignore)
	s.addMsgHandler("/holst/event", cb_heartbeat)

	print "Registered Callback-functions:"
	for addr in s.getOSCAddressSpace():
		print addr
		
	print "\nStarting OSCServer. Use ctrl-C to quit."
	st = threading.Thread(target=s.serve_forever)
	st.start()


if __name__ == '__main__':
	main()