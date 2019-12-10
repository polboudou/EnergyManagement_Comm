#!/usr/bin/env python3

import random
import numpy as np
from scipy import interpolate
import paho.mqtt.client as mqtt # import the client
import time

SIMU_TIMESTEP = 1  # in minutes
CONTROL_TIMESTEP = 10   # in minutes
HORIZON = 1440  # in minutes, corresponds to 24 hours
#HORIZON = 60

SOC_MAX = 5000             # Max State-of-Charge battery (Wh)
SOC_MIN = 200           # Min State-of-Charge battery (Wh)
PMAX_CH = -5000            # Max battery charging power (W)
PMAX_DISCH = 5000          # Max battery discharging power (W)

broker_address ="mqtt.teserakt.io"   # use external broker (alternative broker address: "test.mosquitto.org")

class Battery():
    def __init__(self, description, time_slot, max_charge_power, max_discharge_power, min_soc, max_soc, current_soc):
        self.description = description
        self.dt = time_slot
        self.max_charge_power = max_charge_power
        self.max_discharge_power = max_discharge_power
        self.min_soc = min_soc
        self.max_soc = max_soc
        self.current_soc = current_soc
        self.current_power = 0
        self.client = self.setup_client()
        self.time_step = 0
        self.control_received = False

    def model(self):
        self.current_soc = self.current_soc - (self.dt/60) * self.current_power

        self.time_step += 1


    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        #client.on_log = on_log
        client.on_disconnect = on_disconnect
        client.on_message = on_message_boiler
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions dont get processed
        return client

# callback functions for communication

def on_log(client, userdata, level, buf):
     print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('battery connected')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('battery disconnected')

def on_message_boiler(client, userdata, msg):
    m_decode = str(msg.payload.decode("utf-8", "ignore"))
    if m_decode == 'End':
        print("this is the end of battery")
        client.disconnect(broker_address)
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'batteryMS':
        battery.current_power = float(msg.payload)
        battery.control_received = True


if __name__ == '__main__':

    print('Instantiating battery entity!')
    r = random.randrange(1, 100000)
    cname = "Battery_" + str(r)     # broker doesn't like when two clients with same name connect
    battery = Battery(cname, SIMU_TIMESTEP, PMAX_CH, PMAX_DISCH, SOC_MIN, SOC_MAX, current_soc=SOC_MIN)
    battery.client.subscribe('batteryMS')

    for t in range(int(HORIZON/SIMU_TIMESTEP)):
        if not (battery.time_step % CONTROL_TIMESTEP):
            print("Battery period ", t, "min")
            while not battery.control_received:
                pass
        battery.client.publish('battery/soc', battery.current_soc)
        time.sleep(0.0001)
        battery.client.publish('battery/power', battery.current_power)
        time.sleep(0.0001)
        battery.model()
        battery.control_received = False

    print("SALIMOS DEL battery")

    print('FIN DE battery CONNECTION\n \n \n \n')
    battery.client.loop_stop()
    battery.client.disconnect(broker_address)