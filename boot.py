import network
import esp ; esp.osdebug(None)
import gc; gc.collect()

station = network.WLAN(network.AP_IF)

print('Connection successful')
print(station.ifconfig())

ap = network.WLAN(network.AP_IF)
#ap.active(True)
#ap.config(essid='uriego', password='')
#ap.active(True)
print('Connection successful')
print(ap.ifconfig())


#station = network.WLAN(network.STA_IF)
#station.active(False)

#ssid = 'motojoa'
#password = ''
#station.active(True)
#station.connect(ssid, password)
#print(station.ifconfig())
