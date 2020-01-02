

import pandas as pd
import random
import numpy as np
from scipy import interpolate
import paho.mqtt.client as mqtt # import the client
import time


SIMU_TIMESTEP = 30  # in minutes
CONTROL_TIMESTEP = 10*60   # in minutes
CONTROL_TIMESTEP = 5*60   # in minutes
HORIZON = 1440*60  # in minutes, corresponds to 24 hours
#HORIZON = 720*60  # for testing purposes
#HORIZON = 20*60  # for testing purposes

SIMU_STEPS = range(int(HORIZON/SIMU_TIMESTEP))

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius
BOILER1_TEMP_INCOMING_WATER = 20  # in degree celsius
BOILER1_RATED_P = -7600  # in Watts
BOILER1_VOLUME = 800  # in litres
BOILER1_INITIAL_TEMP = 40  # in degree celsius
C_BOILER1 =  1 / (4.186 * 997 * BOILER1_VOLUME)    # in [C/(Watt*sec)]

broker_address ="mqtt.teserakt.io"   # use external broker (alternative broker address: "test.mosquitto.org")
#broker_address ="test.mosquitto.org"   # use external broker (alternative broker address: "mqtt.teserakt.io")


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
        A = 1 - self.hot_water_usage[self.time_step] / BOILER1_VOLUME
        D = self.hot_water_usage[self.time_step] / BOILER1_VOLUME
        self.current_temp = A * self.current_temp - C_BOILER1 * self.dt * self.power + D * BOILER1_TEMP_INCOMING_WATER
        self.time_step += 1
        self.time += self.dt


    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        #client.on_log = on_log
        client.on_disconnect = on_disconnect
        client.on_message = on_message_boiler
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions dont get processed
        return client

def new_resolution(y, step, days):
    time_steps = np.arange(0, len(y))

    f = interpolate.interp1d(time_steps, y, fill_value="extrapolate")

    new_timesteps = days*HORIZON / step
    new_time = np.arange(0, len(y), len(y) / new_timesteps)
    new_y = f(new_time)
    return new_y


'''def get_hot_water_usage_simu():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,1])
    hot_water_usage = df['Hot water usage (litres)'].to_numpy()/2  /(10*60/SIMU_TIMESTEP) # data is in [litres*10min]    # divided by 3 for test purposes
    hot_water_usage = new_resolution(hot_water_usage, SIMU_TIMESTEP, len(hot_water_usage)*10/(60*24))
    return hot_water_usage'''

def get_hot_water_usage_simu():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,2])
    hot_water_usage = df['Actual'].to_numpy()/2  /(10*60/SIMU_TIMESTEP) # data is in [litres*10min]    # divided by 3 for test purposes
    hot_water_usage = new_resolution(hot_water_usage, SIMU_TIMESTEP, len(hot_water_usage)*10/(60*24))
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
    if m_decode == 'End':
        print("this is the end of boiler1")
        client.disconnect(broker_address)
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler1_actuator':
        boiler1.power = float(msg.payload)
        boiler1.control_received = True


if __name__ == '__main__':

    # instatiating boiler and connecting to controller
    time.sleep(2)
    r = random.randrange(1, 100000)
    cname = "Boiler1-" + str(r)     # broker doesn't like when two clients with same name connect
    boiler1 = Boiler(cname, SIMU_TIMESTEP, BOILER1_RATED_P, BOILER1_TEMP_MIN, BOILER1_TEMP_MAX, BOILER1_INITIAL_TEMP)

    boiler1.client.subscribe('boiler1_actuator')
    boiler1.client.publish('boiler1_sensor/power', boiler1.power)
    boiler1.client.publish('boiler1_sensor/temp', boiler1.current_temp)

    # with the simulation frequency, update model and send state to controller
    for t in SIMU_STEPS:
        if not (boiler1.time % CONTROL_TIMESTEP):
            while not boiler1.control_received:
                time.sleep(0.001)
        boiler1.client.publish('boiler1_sensor/temp', boiler1.current_temp)
        time.sleep(0.0001)
        boiler1.client.publish('boiler1_sensor/power', boiler1.power)
        time.sleep(0.0001)
        boiler1.model()
        boiler1.control_received = False

    # close connection with controller
    time.sleep(5)
    boiler1.client.loop_stop()
    boiler1.client.disconnect(broker_address)
