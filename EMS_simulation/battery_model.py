#!/usr/bin/env python3

import random
import paho.mqtt.client as mqtt
import time

## =========================    SIMULATION PARAMETERS    =============================== ##
SIMU_TIMESTEP = 30                                  # in seconds
CONTROL_TIMESTEP = 5*60                             # in seconds
HORIZON = 1440*60                                   # in seconds, corresponds to 24 hours
## ==================================================================================== ##

SIMU_STEPS = range(int(HORIZON/SIMU_TIMESTEP))

SOC_MAX = 5000                                      # Max State-of-Charge battery (Wh)
SOC_MIN = 200                                       # Min State-of-Charge battery (Wh)
PMAX_CH = -5000                                     # Max battery charging power (W)
PMAX_DISCH = 5000                                   # Max battery discharging power (W)

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
        self.model()
        self.time_step = 0
        self.control_received = False

    def model(self):
        self.current_soc = self.current_soc - (self.dt/3600) * self.current_power
        self.time_step += self.dt


    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        # client.on_log = on_log     # uncomment to see messages received and sent by battery
        client.on_disconnect = on_disconnect
        client.on_message = on_message_battery
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions don't get processed
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

def on_message_battery(client, userdata, msg):
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

    # instantiating battery and connecting to controller
    time.sleep(2)
    r = random.randrange(1, 100000)
    cname = "Battery_" + str(r)     # add randomness to name to avoid having two clients with same name
    battery = Battery(cname, SIMU_TIMESTEP, PMAX_CH, PMAX_DISCH, SOC_MIN, SOC_MAX, current_soc=SOC_MIN)
    battery.client.subscribe('batteryMS')
    time.sleep(2)   # wait to ensure that controller has subscribed to battery
    # publish first message which simulates measurements prior to t=0:
    battery.client.publish('battery/power', battery.current_power)
    battery.client.publish('battery/soc', battery.current_soc)

    # with the simulation frequency, update model and send state to controller
    for t in SIMU_STEPS:
        if not (battery.time_step % CONTROL_TIMESTEP): # only true when model timestep is a multiple of control period
            while not battery.control_received:        # in that case, model waits for control period
                time.sleep(0.001)
        battery.client.publish('battery/soc', battery.current_soc)
        time.sleep(0.0001)
        battery.client.publish('battery/power', battery.current_power)
        time.sleep(0.0001)
        battery.model()
        battery.control_received = False

    # close connection with controller
    battery.client.loop_stop()
    battery.client.disconnect(broker_address)