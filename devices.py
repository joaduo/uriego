import machine
import utime
import log

# D1  GPIO5 OK  OK  often used as SCL (I2C)
# D2  GPIO4 OK  OK  often used as SDA (I2C)
# D3  GPIO0 pulled up OK  connected to FLASH button, boot fails if pulled LOW
# D4  GPIO2 pulled up OK  HIGH at boot connected to on-board LED, boot fails if pulled LOW
#D5  GPIO14  OK  OK  SPI (SCLK)
#D6  GPIO12  OK  OK  SPI (MISO)
#D7  GPIO13  OK  OK  SPI (MOSI)
#D8  GPIO15  pulled to GND OK  SPI (CS)
PUMP_PIN_NUMBER=14
VALVE_PIN_NUMBER=12


class InvertedPin(machine.Pin):
    def on(self):
        if super().value():
            return super().off()
    def off(self):
        if not super().value():
            return super().on()
    def value(self, v=None):
        if v is not None:
            if v:
                self.on()
            else:
                self.off()
        return not bool(super().value())


class Pump:
    def __init__(self, pump_pin_n=PUMP_PIN_NUMBER, valve_pin_n=VALVE_PIN_NUMBER):
        self.pump_out = InvertedPin(pump_pin_n, machine.Pin.OUT, value=1)
        self.valve_out = InvertedPin(valve_pin_n, machine.Pin.OUT, value=1)
        self.stop()
    def start(self, valve_value):
        if self.pump_out.value():
            self.stop()
            log.error('Pump already running')
            return False
        self.valve_out.value(valve_value)
        utime.sleep(0.5) # give time to the relay to flip
        self.pump_out.on()
        return self.pump_out.value()
    def stop(self):
        self.pump_out.off()
        utime.sleep(0.5) # give time to the relay to flip
        self.valve_out.off()
        return not self.pump_out.value()
    def monitor(self, running):
        if running:
            if not self.pump_out.value():
                log.error('Not running?')
        else:
            if self.pump_out.value():
                self.stop()
                log.error('Still running?')

