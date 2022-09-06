import machine
import utime
import log

PUMP_PIN_NUMBER=19
VALVE_1_PIN_NUMBER=18
VALVE_2_PIN_NUMBER=5


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
    def __init__(self, pump_pin_n=PUMP_PIN_NUMBER,
                 valve_1_pin=VALVE_1_PIN_NUMBER,
                 valve_2_pin=VALVE_2_PIN_NUMBER):
        self.pump_out = InvertedPin(pump_pin_n, machine.Pin.OUT, value=1)
        self.valve_1 = InvertedPin(valve_1_pin, machine.Pin.OUT, value=1)
        self.valve_2 = InvertedPin(valve_2_pin, machine.Pin.OUT, value=1)
        self.valve_map = {0:self.valve_1, 1:self.valve_2}
        self.stop()
    def start(self, valve_value):
        if self.pump_out.value():
            self.stop()
            log.error('Pump already running')
            return False
        valve = self.valve_map[valve_value]
        for v in self.valve_map.values():
            if v != valve:
                v.off()
        valve.on()
        self.pump_out.on()
        return self.pump_out.value()
    def stop(self):
        for v in self.valve_map.values():
            v.off()
        self.pump_out.off()
        return not self.pump_out.value()
    def monitor(self, running):
        if running:
            if not self.pump_out.value():
                log.error('Not running?')
        else:
            if self.pump_out.value():
                self.stop()
                log.error('Still running?')

