

import pandas as pd
import paho.mqtt.client as mqtt # import the client
import time

BOILER1_VOLUME = 800    # in litres
BOILER_TEMP_INCOMING_WATER = 20     #(degrees celsius)
TIME_SLOT = 10
broker_address = "test.mosquitto.org"  # use external broker


class Boiler():
    def __init__(self, description, TIME_SLOT, max_power, min_temp, max_temp, current_temp):
        self.description = description
        self.dt = TIME_SLOT
        self.max_power = max_power
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.current_temp = current_temp
        self.power = 0
        self.hysteresis = 0
        self.hot_water_usage = get_hot_water_usage_simu()
        self.client = self.setup_client()
        self.time_step = 0

    def model(self):
        # T[h+1] = A * T[h] + C * P[h] + D * T_inlet[h]
        C = (self.dt * 60) / (4.186 * 997 * BOILER1_VOLUME)  # boiler thermal capacity (K/Watt)  #(C_water = 4.186 watt-second per gram per degree celsius, water density is 997 grams / litre)

        A = 1 - self.hot_water_usage[self.time_step][0] / BOILER1_VOLUME
        D = self.hot_water_usage[self.time_step][0] / BOILER1_VOLUME
        print("temp ", self.current_temp)
        print("CCCCCCCCCCC ", C*self.power)
        print("AAAAAAAAAA ", A*self.current_temp)
        print("DDDDD ", D*BOILER_TEMP_INCOMING_WATER)
        self.current_temp = A * self.current_temp - C * self.power + D * BOILER_TEMP_INCOMING_WATER

        if self.current_temp >= BOILER1_TEMP_DELTA:
            self.hysteresis = 0
        elif self.current_temp <= BOILER1_TEMP_MIN:
            self.hysteresis = 1
        else:
            self.hysteresis = self.hysteresis

        self.time_step += 1


    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        client.on_log = on_log
        client.on_disconnect = on_disconnect
        client.on_message = on_message_boiler
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions dont get processed
        return client


def get_hot_water_usage_simu():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,1])
	#df.plot.line(y='Hot water usage (litres)')
	#plt.savefig('../../figs_output/hot_water_usage_profile_24hrs.pdf')
    hot_water_usage_list = df.values/10 #for test purposes, otherwise too big.
    return hot_water_usage_list


# callback functions for communication

def on_log(client, userdata, level, buf):
    print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('connected OK')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('boiler disconnected')

def on_message_boiler(client, userdata, msg):
    m_decode = str(msg.payload.decode("utf-8", "ignore"))
    if m_decode == 'Request measurement':
        client.publish('boiler_sensor/temp', boiler1.current_temp)
        client.publish('boiler_sensor/power', boiler1.power)
        client.publish('boiler_sensor/hysteresis', boiler1.hysteresis)

        #client.publish('boiler_sensor', str([boiler1.current_temp, boiler1.power]).strip('[]'))
    if m_decode == 'End':
        print("this is the end")
        client.disconnect(broker_address)
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler_actuator':
        boiler1.power = float(msg.payload)
        boiler1.model()



TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius
BOILER1_TEMP_DELTA = 42

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BOILER1_INITIAL_TEMP = 45  # in degree celsius
BOILER2_INITIAL_TEMP = 45  # in degree celsius

if __name__ == '__main__':

    print('Instantiating boiler 1 entity!')
    boiler1 = Boiler('Boiler1', TIME_SLOT, BOILER1_RATED_P, BOILER1_TEMP_MIN, BOILER1_TEMP_MAX, BOILER1_INITIAL_TEMP)
    print('boiler1.current_temp', boiler1.current_temp)

    boiler1.power = -7600
    boiler1.model()

    boiler1.client.subscribe("boiler")
    boiler1.client.subscribe('boiler_actuator')
    #while True:
        #pass
    time.sleep(60)
    print('FIN DE BOILER CONNECTION\n \n \n \n')
    boiler1.client.loop_stop()
    boiler1.client.disconnect(broker_address)