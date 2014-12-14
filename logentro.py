import csv
from entro import *

def main():
	skip_counter = 0
	csvfile = open('measurements.csv', 'wb')
	csvw = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
	try:
		while True:
			measurement = get_entropy_measurement()
			poolsize = get_entropy_pool_size() 
			percentage = float(measurement) / float(poolsize)
			csvw.writerow([measurement, poolsize, percentage])
			time.sleep(0.01)
			
			if not skip_counter % 100:
				print("{0} | {1} | {2}".format(measurement, poolsize, percentage))
			
			skip_counter += 1
	
	except KeyboardInterrupt, e:
		csvfile.close()
		print
		print "Seems that you want to exit. Goodbye!"
		pass

if __name__ == '__main__':
	main()
