# uriego
Micropython watering system. Webserver and Scheduler


## Some initial config cheatsheet

```
import esp ; esp.osdebug(None)
import gc; gc.collect() ; print(gc.mem_free())

## As AP (router) (sometimes it's recorded permanently, depending the hardware)
# import network
# ap = network.WLAN(network.AP_IF)
# print(ap.ifconfig())
# ap.config(essid='uriego', authmode=network.AUTH_WPA_WPA2_PSK, password='', channel=4)
# network.phy_mode(network.MODE_11B)
# ap.active(True)

## As client (sometimes it's recorded permanently)
# station = network.WLAN(network.STA_IF)
# station.active(False)
# ssid = '<SSIDNAME>'
# password = ''
# station.connect(ssid, password)
# station.active(True)
# print(station.ifconfig())

# You can do both Ap + Client, but bear in mind if the Client's network is missing
# then connections to the AP will be interrupted

## WebREPL
# import webrepl; webrepl.start()
```
