import network
import esp ; esp.osdebug(None)
import gc; gc.collect() ; print(gc.mem_free())

ap = network.WLAN(network.AP_IF)
print('AP config:')
print(ap.ifconfig())