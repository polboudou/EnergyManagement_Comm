

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt # import the client
import time
#from EMS_simulation.control_algorithms import scenario1, scenario2, scenario3
from EMS_simulation.control_algorithms import scenario2
broker_address = "test.mosquitto.org"  # use external broker

FORECAST_INACCURACY_COEF = 0.1  # 0 for perfect accuracy, 1 for big inaccuracy

class Controller():
    def __init__(self, description):
        self.description = description
        self.client = self.setup_client()

        if self.description == 'SC1':
            self.Tb1 = 0
            self.pb1 = 0
            self.sb1 = 0
            self.Tb1_list = []
            self.pb1_list = []
            self.sb1_list = []
            #self.states = [0]*2     # [T_B1, p_B1]
            #self.states[1] = 0
            self.algorithm = 'scenario1'

    def run_algorithm(self, p_x):
        self.Tb1_list.append(self.Tb1)
        self.pb1_list.append(self.pb1)
        self.sb1_list.append(self.sb1)
        action = scenario2.algo_scenario2({1: [self.Tb1, self.pb1, self.sb1]}, p_x)
        return action

    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        client.on_log = on_log
        client.on_disconnect = on_disconnect
        client.on_message = on_message_controller
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions dont get processed
        return client

def Initialise_client_object():
    mqtt.Client.last_pub_time = time.time()
    mqtt.Client.topic_ack = []
    mqtt.Client.run_control_flag = False

def get_excess_power_forecast():
    # Data acquisition. Simulation of daily power excess (P_PV - P_nc)
    excess = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
    excess['P_PV - P_nc (kW)'] = excess[
                                     'Flux energie au point d\'injection (kWh)'] * 6 * 1000  # Convert the energy (kWh) to power (W) and power convention (buy positive and sell negative)
    del excess['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore
    return excess['P_PV - P_nc (kW)']


def get_excess_power_simulation(p_x_forecast):
    # random samples from a uniform distribution around 0
    p_x_forecast = np.array(p_x_forecast)
    mean_px = np.nanmean(np.array(p_x_forecast))
    p_x = p_x_forecast + FORECAST_INACCURACY_COEF*mean_px*np.random.normal(size=len(p_x_forecast))
    return(p_x)


# callback functions for communication
def on_log(client, userdata, level, buf):
    print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('connected OK')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('controller disconnected')

def on_message_controller(client, userdata, msg):
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler_sensor/power':
        controller.pb1 = float(msg.payload)

    if msg.topic == 'boiler_sensor/temp':
        controller.Tb1 = float(msg.payload)

    if msg.topic == 'boiler_sensor/hysteresis':
        controller.sb1 = float(msg.payload)


TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius (TODO to be verified!) Question: is it variable?

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BOILER1_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements!)
BOILER2_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements)

SIMU_STEPS = 6*24

if __name__ == '__main__':

    print('Instantiating controller!')
    controller = Controller('SC1')
    p_x_forecast = get_excess_power_forecast()
    p_x = get_excess_power_simulation(p_x_forecast)
    controller.client.subscribe("boiler_sensor")
    controller.client.subscribe("boiler_sensor/temp")
    controller.client.subscribe("boiler_sensor/power")
    controller.client.subscribe("boiler_sensor/hysteresis")
    for h in range(SIMU_STEPS):
        controller.client.publish('boiler', 'Request measurement')
        time.sleep(0.1) # to ensure that all units are instantiated
        print('controller.pb1', controller.pb1)
        print('controller.Tb1', controller.Tb1)
        print('controller.Tb1', controller.sb1)
        #if controller.client.flag == 1:
        actions = controller.run_algorithm(p_x_forecast[h])
        controller.client.publish('boiler_actuator', str(actions[1]))

    controller.client.publish('boiler', 'End')
    controller.client.loop_stop()
    controller.client.disconnect(broker_address)

    fig, axes = plt.subplots(2, 1)
    axes[0].plot(range(SIMU_STEPS), controller.pb1_list, label = 'Power')
    ax2 = axes[0].twinx()
    ax2.plot(range(SIMU_STEPS), controller.Tb1_list, label = 'Temperature', color='red')
    axes[1].plot(range(SIMU_STEPS), controller.sb1_list, label = 'Hysteresis state')
    plt.legend()
    ax2.legend(loc=2)
    axes[0].legend(loc=1)
    axes[1].legend()
    plt.savefig('simu_output/results_simu_'+controller.description+'.pdf')

