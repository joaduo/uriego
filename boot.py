import network
import esp ; esp.osdebug(None)
import gc; gc.collect()

station = network.WLAN(network.AP_IF)

print('Connection successful')
print(station.ifconfig())


