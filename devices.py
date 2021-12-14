import machine

PUMP_PIN_NUMBER=5
VALVE_PIN_NUMBER=4


class InvertedPin(machine.Pin):
    def on(self):
        if super().value():
            super().off()
    def off(self):
        if not super().value():
            super().on()
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
    def value(self):
        return self.pump_out.value()
    def start(self, valve_value):
        if self.pump_out.value():
            self.stop()
            raise RuntimeError('Pump already running')
        self.valve_out.value(valve_value)
        self.pump_out.on()
    def stop(self):
        self.pump_out.off()
        self.valve_out.off()
    def monitor(self, running):
        if running:
            if not self.pump_out.value():
                raise RuntimeError('Not running?')
        else:
            if self.pump_out.value():
                self.stop()
                raise RuntimeError('Still running?')


def test():
    import log
    import utime
    pump = Pump()
    FIRST_GATE ,SECOND_GATE = 0,1
    pump.start(SECOND_GATE)
    for i in range(2):
        log.info('Waiting...')
        pump.monitor(running=True)
        utime.sleep(1)
    pump.stop()
    pump.monitor(running=False)
    utime.sleep(1)
    pump.start(FIRST_GATE)
    for i in range(2):
        log.info('Waiting...')
        pump.monitor(running=True)
        utime.sleep(1)
    pump.stop()
    pump.monitor(running=False)



if __name__ == '__main__':
    test()

