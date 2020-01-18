

import pandas as pd
import random
import numpy as np
from scipy import interpolate
import paho.mqtt.client as mqtt
import time

## =========================    SIMULATION PARAMETERS    =============================== ##
SIMU_TIMESTEP = 30                                  # in seconds
CONTROL_TIMESTEP = 5*60                             # in seconds
HORIZON = 1440*60                                   # in seconds, corresponds to 24 hours
## ==================================================================================== ##

SIMU_STEPS = range(int(HORIZON/SIMU_TIMESTEP))

BOILER1_TEMP_MIN = 40                               # in degree celsius
BOILER1_TEMP_MAX = 50                               # in degree celsius
BOILER1_TEMP_INCOMING_WATER = 20                    # in degree celsius
BOILER1_RATED_P = -7600                             # in Watts
BOILER1_VOLUME = 800                                # in litres
BOILER1_INITIAL_TEMP = 40                           # in degree celsius
d_WATER = 977                                       # in grams/liter
C_WATER = 4.186                                     # in degree/(gram*Watt)
C_BOILER1 =  C_WATER * d_WATER * BOILER1_VOLUME     # in degree/(Watt*sec)

broker_address ="mqtt.teserakt.io"   # use external broker (alternative broker address: "test.mosquitto.org")


class Boiler():
    def __init__(self, description, simu_timestep, max_power, min_temp, max_temp, current_temp):
        self.description = description
        self.dt = simu_timestep
        self.max_power = max_power
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.current_temp = current_temp
        self.power = 0
        self.energy_hot_water = get_energy_hot_water_usage_simu()
        self.client = self.setup_client()
        self.time_step = 0
        self.time = 0
        self.control_received = False
        self.model()    # launch model simulation
        self.time_step = 0
        self.time = 0

    def model(self):
        volume_required = self.energy_hot_water[self.time_step] / (C_WATER*d_WATER * self.current_temp)
        D = volume_required / BOILER1_VOLUME
        A = 1 - D
        self.current_temp = A * self.current_temp - (1/C_BOILER1) * self.dt*self.power + D*BOILER1_TEMP_INCOMING_WATER
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

def new_resolution(y, step, days):      # creates new data points in between original data points to enhance resolution
    time_steps = np.arange(0, len(y))
    f = interpolate.interp1d(time_steps, y, fill_value="extrapolate")
    new_timesteps = days*HORIZON / step
    new_time = np.arange(0, len(y), len(y) / new_timesteps)
    new_y = f(new_time)
    return new_y

def get_energy_hot_water_usage_simu():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0],
                       usecols=[0,2])
    # hot_water_usage divided by 2 cause two boilers.
    hot_water_usage = df['Actual'].to_numpy()/2  /(10*60/SIMU_TIMESTEP) # data was in [litres*10min]
    hot_water_usage = new_resolution(hot_water_usage, SIMU_TIMESTEP, len(hot_water_usage)*10/(60*24))
    # Energy : [L*30s * g/L * W*s/(g*K)]
    water_energy_usage = hot_water_usage * C_WATER * d_WATER * 40
    return water_energy_usage

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
    cname = "Boiler1-" + str(r)     # add randomness to name to avoid having two clients with same name
    boiler1 = Boiler(cname, SIMU_TIMESTEP, BOILER1_RATED_P, BOILER1_TEMP_MIN, BOILER1_TEMP_MAX, BOILER1_INITIAL_TEMP)
    boiler1.client.subscribe('boiler1_actuator')
    # publish first message which simulates measurements prior to t=0:
    boiler1.client.publish('boiler1_sensor/power', boiler1.power)
    boiler1.client.publish('boiler1_sensor/temp', boiler1.current_temp)

    # with the simulation frequency, update model and send state to controller
    for t in SIMU_STEPS:
        if not (boiler1.time % CONTROL_TIMESTEP):   # only true when model timestep is a multiple of control period
            while not boiler1.control_received:     # in that case, model waits for control period
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
