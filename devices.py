import machine

PUMP_PIN_NUMBER=12
GATE_PIN_NUMBER=14


class Pump:
    def __init__(self, pump_pin_n=PUMP_PIN_NUMBER, valve_pin_n=GATE_PIN_NUMBER):
        self.pump_out = machine.Pin(pump_pin_n, machine.Pin.OUT)
        self.valve_out = machine.Pin(valve_pin_n, machine.Pin.OUT)
        self.preventive_stop()
    def value(self):
        return self.pump_out.value()
    def start(self, valve_value):
        if self.pump_out.value():
            self.preventive_stop()
            raise RuntimeError('Pump already running')
        self.valve_out.value(valve_value)
        self.pump_out.on()
    def preventive_stop(self):
        if self.pump_out.value():
            
            self.pump_out.off()
    def stop(self):
        self.pump_out.off()
        # pump off means gates off (no power)
        self.valve_out.off() # we only save relay power
    def monitor(self, running):
        if running:
            if not self.pump_out.value():
                raise RuntimeError('Not running?')
        else:
            if self.pump_out.value():
                self.preventive_stop()
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


