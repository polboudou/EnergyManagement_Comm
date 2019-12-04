

import pandas as pd
import random
import numpy as np
from scipy import interpolate
import paho.mqtt.client as mqtt # import the client
import time


TIME_SLOT = 1  # in minutes
CONTROL_SLOT = 10   # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours
HORIZON = 60  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius
BOILER1_TEMP_DELTA = 42
BOILER1_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = -7600  # in Watts
BOILER1_VOLUME = 800  # in litres
BOILER1_INITIAL_TEMP = 42  # in degree celsius
C =  60 / (4.186 * 997 * BOILER1_VOLUME)    # in [C/(Watt*min)]

broker_address = "mqtt.teserakt.io"  # use external broker

class Boiler():
    def __init__(self, description, TIME_SLOT, max_power, min_temp, max_temp, current_temp):
        self.description = description
        self.dt = TIME_SLOT
        self.max_power = max_power
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.current_temp = current_temp
        self.power = 0
        self.hot_water_usage = get_hot_water_usage_simu()
        self.client = self.setup_client()
        self.time_step = 0
        self.control_received = False

    def model(self):
        # T[h+1] = A * T[h] + C * P[h] + D * T_inlet[h]
        A = 1 - self.hot_water_usage[self.time_step] / BOILER1_VOLUME
        D = self.hot_water_usage[self.time_step] / BOILER1_VOLUME
        self.current_temp = A * self.current_temp - C * self.dt * self.power + D * BOILER1_TEMP_INCOMING_WATER

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

def new_resolution(y, step):
    time_steps = np.arange(0, len(y))

    f = interpolate.interp1d(time_steps, y, fill_value="extrapolate")

    new_timesteps = HORIZON / step
    new_time = np.arange(0, len(y), len(y) / new_timesteps)
    new_y = f(new_time)
    return new_y

def get_hot_water_usage_simu():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,1])
    #hot_water_usage_list = df.values/3 #for test purposes, otherwise too big.
    hot_water_usage = df['Hot water usage (litres)'].to_numpy() /2 * (TIME_SLOT/10) # data is in [litres*10min]
    hot_water_usage = new_resolution(hot_water_usage, TIME_SLOT)

    return hot_water_usage


# callback functions for communication

def on_log(client, userdata, level, buf):
     print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('boiler1 connected')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('boiler1 disconnected')

def on_message_boiler(client, userdata, msg):
    m_decode = str(msg.payload.decode("utf-8", "ignore"))
    if m_decode == 'Request measurement':
        client.publish('boiler1_sensor/temp', boiler1.current_temp)
        client.publish('boiler1_sensor/power', boiler1.power)

    if m_decode == 'End':
        print("this is the end of boiler2")
        client.disconnect(broker_address)
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler1_actuator':
        #print("msg.payload ", msg.payload)
        boiler1.power = float(msg.payload)
        boiler1.control_received = True


if __name__ == '__main__':

    print('Instantiating boiler 1 entity!')
    r = random.randrange(1, 10000)
    cname = "Boiler1-" + str(r)     # broker doesn't like when two clients with same name connect
    boiler1 = Boiler(cname, TIME_SLOT, BOILER1_RATED_P, BOILER1_TEMP_MIN, BOILER1_TEMP_MAX, BOILER1_INITIAL_TEMP)
    boiler1.client.subscribe('boiler1_actuator')

    print('boiler1.current_temp ', boiler1.current_temp)

    for t in range(int(HORIZON/TIME_SLOT)):
        if not (boiler1.time_step % CONTROL_SLOT):
            print("Boiler 1 period ", t, "min")
            while not boiler1.control_received:
                pass
        boiler1.client.publish('boiler1_sensor/temp', boiler1.current_temp)
        time.sleep(0.0001)
        boiler1.client.publish('boiler1_sensor/power', boiler1.power)
        time.sleep(0.0001)
        boiler1.model()
        boiler1.control_received = False

    print("SALIMOS DEL BOILER1")

    print('FIN DE BOILER1 CONNECTION\n \n \n \n')
    boiler1.client.loop_stop()
    boiler1.client.disconnect(broker_address)
