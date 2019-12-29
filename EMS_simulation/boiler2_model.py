#!/usr/bin/env python3

import pandas as pd
import random
import numpy as np
from scipy import interpolate
import paho.mqtt.client as mqtt # import the client
import time


SIMU_TIMESTEP = 30                   # in minutes
CONTROL_TIMESTEP = 10*60                # in minutes
CONTROL_TIMESTEP = 5*60   # in minutes
HORIZON = 1440*60                  # in minutes, corresponds to 24 hours
#HORIZON = 720*60  # for testing purposes
#HORIZON = 20*60  # for testing purposes

SIMU_STEPS = range(int(HORIZON/SIMU_TIMESTEP))

BOILER2_TEMP_MIN = 30           # in degree celsius
BOILER2_TEMP_MAX = 60           # in degree celsius
BOILER2_TEMP_DELTA = 36         # in degrees celsius
BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER2_RATED_P = -7600         # in Watts
BOILER2_VOLUME = 800            # in litres
BOILER2_INITIAL_TEMP = 36       # in degree celsius
C_BOILER = 1 / (4.186 * 997 * BOILER2_VOLUME)     # in [C/(Watt*sec)]

broker_address ="mqtt.teserakt.io"   # use external broker (alternative broker address: "test.mosquitto.org")
#broker_address ="test.mosquitto.org"   # use external broker (alternative broker address: "mqtt.teserakt.io")
#broker_address = 'mqtt.eclipse.org'
#broker_address="broker.hivemq.com"

class Boiler():
    def __init__(self, description, simu_timestep, max_power, min_temp, max_temp, current_temp):
        self.description = description
        self.dt = simu_timestep
        self.max_power = max_power
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.current_temp = current_temp
        self.power = 0
        self.hot_water_usage = get_hot_water_usage_simu()
        self.client = self.setup_client()
        self.time_step = 0
        self.time = 0
        self.control_received = False
        self.model()    # launch model simulation
        self.time_step = 0
        self.time = 0

    def model(self):
        # T[h+1] = A * T[h] + C * P[h] + D * T_inlet[h]
        A = 1 - self.hot_water_usage[self.time_step] / BOILER2_VOLUME
        D = self.hot_water_usage[self.time_step] / BOILER2_VOLUME
        self.current_temp = A * self.current_temp - C_BOILER * self.dt * self.power + D * BOILER2_TEMP_INCOMING_WATER
        #print('current temp boiler2 ', self.current_temp)
        #print('current power boiler2 ', self.power)

        self.time_step += 1
        self.time += self.dt


    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        #client.on_log = on_log         # remove comment if curious about communication logs.
        client.on_disconnect = on_disconnect
        client.on_message = on_message_boiler
        client.connect(broker_address)
        client.loop_start()  # without the loop, the MQTT call back functions dont get processed
        return client

def new_resolution(y, step, days):
    time_steps = np.arange(0, len(y))

    f = interpolate.interp1d(time_steps, y, fill_value="extrapolate")

    new_timesteps = days*HORIZON / step
    new_time = np.arange(0, len(y), len(y) / new_timesteps)
    new_y = f(new_time)
    return new_y


def get_hot_water_usage_simu():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,1])
    hot_water_usage = df['Hot water usage (litres)'].to_numpy()/2  /(10*60/SIMU_TIMESTEP) # data is in [litres*10min]    # divided by 3 for test purposes
    hot_water_usage = new_resolution(hot_water_usage, SIMU_TIMESTEP, len(hot_water_usage)*10/(60*24))
    return hot_water_usage


# callback functions for communication
def on_log(client, userdata, level, buf):
    print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('boiler2 connected')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('boiler2 disconnected')

def on_message_boiler(client, userdata, msg):
    m_decode = str(msg.payload.decode("utf-8", "ignore"))
    if m_decode == 'End':
        print("this is the end of boiler2")
        client.disconnect(broker_address)
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler2_actuator':
        #print("msg.payload ", msg.payload)
        boiler2.power = float(msg.payload)
        boiler2.control_received = True

if __name__ == '__main__':

    time.sleep(2)
    print('Instantiating boiler 2 entity!')
    r = random.randrange(1, 100000)
    cname = "Boiler2-" + str(r)     # broker doesn't like when two clients with same name connect
    boiler2 = Boiler(cname, SIMU_TIMESTEP, BOILER2_RATED_P, BOILER2_TEMP_MIN, BOILER2_TEMP_MAX, BOILER2_INITIAL_TEMP)
    boiler2.client.subscribe('boiler2_actuator')
    boiler2.client.publish('boiler2_sensor/power', boiler2.power)
    boiler2.client.publish('boiler2_sensor/temp', boiler2.current_temp)

    for t in SIMU_STEPS:
        if not (boiler2.time % CONTROL_TIMESTEP): #only true when model timestep is a multiple of control period (model has to wait for control period)
            #print('waiting for boiler 2 to receive control. boiler2 time:', boiler2.time_step)
            while not boiler2.control_received:
                time.sleep(0.001)
        boiler2.client.publish('boiler2_sensor/temp', boiler2.current_temp)
        time.sleep(0.0001)
        boiler2.client.publish('boiler2_sensor/power', boiler2.power)
        time.sleep(0.0001)
        boiler2.model()
        boiler2.control_received = False

    time.sleep(5)
    boiler2.client.loop_stop()
    boiler2.client.disconnect(broker_address)
