

import pandas as pd
import random
import numpy as np
from scipy import interpolate
import paho.mqtt.client as mqtt # import the client
import time


TIME_SLOT = 1                   # in minutes
CONTROL_SLOT = 10                # in minutes
HORIZON = 1440                  # in minutes, corresponds to 24 hours
HORIZON = 60  # in minutes, corresponds to 24 hours

BOILER2_TEMP_MIN = 30           # in degree celsius
BOILER2_TEMP_MAX = 60           # in degree celsius
BOILER2_TEMP_DELTA = 32         # in degrees celsius
BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER2_RATED_P = -7600         # in Watts
BOILER2_VOLUME = 800            # in litres
BOILER2_INITIAL_TEMP = 32       # in degree celsius
C_BOILER = 60 / (4.186 * 997 * BOILER2_VOLUME)     # in [C/(Watt*min)]

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
        A = 1 - self.hot_water_usage[self.time_step] / BOILER2_VOLUME
        D = self.hot_water_usage[self.time_step] / BOILER2_VOLUME
        self.current_temp = A * self.current_temp - C_BOILER * self.dt * self.power + D * BOILER2_TEMP_INCOMING_WATER

        self.time_step += 1


    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        #client.on_log = on_log         # remove comment if curious about communication logs.
        client.on_disconnect = on_disconnect
        client.on_message = on_message_boiler
        client.connect(broker_address)
        client.loop_start()  # without the loop, the MQTT call back functions dont get processed
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
    hot_water_usage = df['Hot water usage (litres)'].to_numpy() /3 * (TIME_SLOT/10)  # data is in [litres*10min]    # divided by 3 for test purposes
    hot_water_usage = new_resolution(hot_water_usage, TIME_SLOT)
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
    if m_decode == 'Request measurement':
        client.publish('boiler2_sensor/temp', boiler2.current_temp)
        client.publish('boiler2_sensor/power', boiler2.power)

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

    print('Instantiating boiler 2 entity!')
    r = random.randrange(1, 10000)
    cname = "Boiler2-" + str(r)     # broker doesn't like when two clients with same name connect
    boiler2 = Boiler(cname, TIME_SLOT, BOILER2_RATED_P, BOILER2_TEMP_MIN, BOILER2_TEMP_MAX, BOILER2_INITIAL_TEMP)
    boiler2.client.subscribe('boiler2_actuator')


    for t in range(int(HORIZON/TIME_SLOT)):
        if not (boiler2.time_step % CONTROL_SLOT):
            print("Boiler 2 period ", t, "min")
            while not boiler2.control_received:
                pass
        boiler2.client.publish('boiler2_sensor/temp', boiler2.current_temp)
        time.sleep(0.0001)
        boiler2.client.publish('boiler2_sensor/power', boiler2.power)
        time.sleep(0.0001)
        boiler2.model()
        boiler2.control_received = False

    print("SALIMOS DEL BOILER2 LOOP")

    print('FIN DE BOILER2 CONNECTION\n \n \n \n')
    boiler2.client.loop_stop()
    boiler2.client.disconnect(broker_address)
