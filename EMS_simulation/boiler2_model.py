
import pandas as pd
import random
import paho.mqtt.client as mqtt # import the client
import time

TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius
BOILER2_TEMP_DELTA = 35
BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER2_RATED_P = -7600  # in Watts
BOILER2_VOLUME = 800  # in litres

BOILER2_INITIAL_TEMP = 45  # in degree celsius

broker_address = "mqtt.teserakt.io"  # use external broker (alternative: test.mosquitto.org


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
        C = (self.dt * 60) / (4.186 * 997 * BOILER2_VOLUME)
        A = 1 - self.hot_water_usage[self.time_step][0] / BOILER2_VOLUME
        D = self.hot_water_usage[self.time_step][0] / BOILER2_VOLUME
        self.current_temp = A * self.current_temp - C * self.power + D * BOILER2_TEMP_INCOMING_WATER

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
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0],
                       usecols=[0, 1])
    # df.plot.line(y='Hot water usage (litres)')
    # plt.savefig('../../figs_output/hot_water_usage_profile_24hrs.pdf')
    hot_water_usage_list = df.values / 2  # for test purposes, otherwise too big.
    return hot_water_usage_list


# callback functions for communication

def on_log(client, userdata, level, buf):
    print("log: ", buf)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
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
        print("this is the end of boiler 2")
        client.disconnect(broker_address)
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler2_actuator':
        boiler2.power = float(msg.payload)
        boiler2.model()


if __name__ == '__main__':
    print('Instantiating boiler 2 entity!')
    r = random.randrange(1, 10000)
    cname = "Boiler1-" + str(r)     # broker doesn't like when two clients with same name connect
    boiler2 = Boiler(cname, TIME_SLOT, BOILER2_RATED_P, BOILER2_TEMP_MIN, BOILER2_TEMP_MAX, BOILER2_INITIAL_TEMP)
    # print('boiler1.current_temp', boiler1.current_temp)

    boiler2.client.subscribe("boilers")
    boiler2.client.subscribe('boiler2_actuator')
    #while True:
    #    pass
    time.sleep(820)
    print('FIN DE BOILER2 CONNECTION\n \n \n \n')
    boiler2.client.loop_stop()
    boiler2.client.disconnect(broker_address)