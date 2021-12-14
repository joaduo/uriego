import machine
import log

PUMP_PIN_NUMBER=5
VALVE_PIN_NUMBER=4


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
        self.pump_out.on()
        return self.pump_out.value()
    def stop(self):
        self.pump_out.off()
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

