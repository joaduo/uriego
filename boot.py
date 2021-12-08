import network
import esp ; esp.osdebug(None)
import gc; gc.collect()

station = network.WLAN(network.AP_IF)

print('Connection successful')
print(station.ifconfig())

# ap = network.WLAN(network.AP_IF)
# 
# #ap.active(True)
# #ap.config(essid='uriego', password='TuT0t0t0TiburonPapazzz23495')
# #ap.active(True)
# 
# print('Connection successful')
# print(ap.ifconfig())
