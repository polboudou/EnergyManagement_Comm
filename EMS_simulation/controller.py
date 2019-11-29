

import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt # import the client
import time
from EMS_simulation.control_algorithms import scenarios
broker_address = "mqtt.teserakt.io"  # use external broker (alternative broker address: test.mosquitto.org)

FORECAST_INACCURACY_COEF = 0.1  # 0 for perfect accuracy, 1 for big inaccuracy
TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

scenario = 'Scenario2'


BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius
BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BOILER1_INITIAL_TEMP = 45  # in degree celsius
BOILER2_INITIAL_TEMP = 45  # in degree celsius

SIMU_STEPS = 6*24
no_entities = 2


class Controller():
    def __init__(self, description):
        self.description = description
        self.client = self.setup_client()
        self.Tb1 = 0
        self.pb1 = 0
        self.sb1 = 0
        self.Tb2 = 0
        self.pb2 = 0
        self.sb2 = 0
        self.Tb1_list = []
        self.pb1_list = []
        self.sb1_list = []
        self.Tb2_list = []
        self.pb2_list = []
        self.sb2_list = []

    def run_algorithm(self, p_x):

        if 'Scenario1' in self.description:
            '''self.Tb1_list.append(self.Tb1)
            self.pb1_list.append(self.pb1)
            self.sb1_list.append(self.sb1)
            self.Tb2_list.append(self.Tb2)
            self.pb2_list.append(self.pb2)
            self.sb2_list.append(self.sb2)
            output = scenarios.algo_scenario2({1: [self.Tb1, self.pb1, self.sb1], 2: [self.Tb2, self.pb2, self.sb2]}, p_x)
            self.sb1 = output['hyst_states'][1]
            self.sb2 = output['hyst_states'][2]
            self.client.run_control_flag = 0
            print('scenario2 output : ', output)
            return output['actions']'''
            self.Tb1_list.append(self.Tb1)
            self.pb1_list.append(self.pb1)
            self.Tb2_list.append(self.Tb2)
            self.pb2_list.append(self.pb2)
            target_power = scenarios.algo_scenario1({1: [self.Tb1, self.pb1], 2: [self.Tb2, self.pb2]}, p_x)
            self.client.run_control_flag = 0
            return target_power

        if 'Scenario2' in self.description:
            self.Tb1_list.append(self.Tb1)
            self.pb1_list.append(self.pb1)
            self.sb1_list.append(self.sb1)
            self.Tb2_list.append(self.Tb2)
            self.pb2_list.append(self.pb2)
            self.sb2_list.append(self.sb2)
            output = scenarios.algo_scenario2({1: [self.Tb1, self.pb1, self.sb1], 2: [self.Tb2, self.pb2, self.sb2]}, p_x)
            self.sb1 = output['hyst_states'][1]
            self.sb2 = output['hyst_states'][2]
            self.client.run_control_flag = 0
            print('scenario2 output : ', output)
            return output['actions']

    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        client.on_log = on_log
        client.on_disconnect = on_disconnect
        client.on_message = on_message_controller
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions dont get processed
        return client


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


def Initialise_client_object():
    mqtt.Client.last_pub_time = time.time()
    mqtt.Client.run_control_flag = 0  # when control_flag equals number of connected entities, then controller runs.

# callback functions for communication
def on_log(client, userdata, level, buf):
    print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('controller connected')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('controller disconnected')

def on_message_controller(client, userdata, msg):
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler1_sensor/power':
        controller.pb1 = float(msg.payload)
        controller.client.run_control_flag += 1

    if msg.topic == 'boiler1_sensor/temp':
        controller.Tb1 = float(msg.payload)

    if msg.topic == 'boiler2_sensor/power':
        controller.pb2 = float(msg.payload)

    if msg.topic == 'boiler2_sensor/temp':
        controller.Tb2 = float(msg.payload)
        controller.client.run_control_flag += 1


if __name__ == '__main__':

    print('Instantiating controller!')
    Initialise_client_object()      # add extra flags

    r = random.randrange(1, 1000)
    cname = scenario + "-" + str(r)     # broker doesn't like when two clients with same name connect
    controller = Controller(cname)

    p_x_forecast = get_excess_power_forecast()
    p_x = get_excess_power_simulation(p_x_forecast)
    controller.client.subscribe("boiler1_sensor/temp")
    controller.client.subscribe("boiler1_sensor/power")
    controller.client.subscribe("boiler2_sensor/temp")
    controller.client.subscribe("boiler2_sensor/power")

    for h in range(SIMU_STEPS):
    #for h in range(2):
        time.sleep(0.1)
        controller.client.publish('boilers', 'Request measurement')
        time.sleep(0.1) # to ensure that all units are instantiated
        print('controller.pb1', controller.pb1)
        print('controller.Tb1', controller.Tb1)
        print('controller.pb2', controller.pb2)
        print('controller.Tb2', controller.Tb2)
        while not controller.client.run_control_flag == no_entities:
            pass
        actions = controller.run_algorithm(p_x_forecast[h])
        controller.client.publish('boiler1_actuator', str(actions[1]))
        controller.client.publish('boiler2_actuator', str(actions[2]))
        #print("controller.client.run_control_flag", controller.client.run_control_flag)

    controller.client.publish('boilers', 'End')
    controller.client.loop_stop()
    controller.client.disconnect(broker_address)


    ############################       PLOTTING FOR SCENARIO 1     ###########################
    fig, ax = plt.subplots(1, 1)
    ax.plot(range(SIMU_STEPS), controller.pb1_list, label = 'Power B1', color='blue', linestyle='-.')
    ax.plot(range(SIMU_STEPS), controller.pb2_list, label = 'Power B2', color='cyan',  alpha=0.7)
    ax2 = ax.twinx()
    ax2.plot(range(SIMU_STEPS), controller.Tb1_list, label = 'Temperature B1', color='red', linestyle='-.')
    ax2.plot(range(SIMU_STEPS), controller.Tb2_list, label = 'Temperature B2', color='red')
    plt.xlabel("Time [min]")
    plt.ylabel('Temperature [C]')
    plt.legend()
    ax2.legend(loc=1)
    ax.legend(loc=2)
    plt.savefig('simu_output/boilers_evolution_'+scenario+'.pdf')
    ###########################################################################################







'''    ############################       PLOTTING FOR SCENARIO 2     ###########################
    fig, axes = plt.subplots(2, 1)
    axes[0].plot(range(SIMU_STEPS), controller.pb1_list, label = 'Power B1', color='blue', linestyle='-.')
    axes[0].plot(range(SIMU_STEPS), controller.pb2_list, label = 'Power B2', color='blue')
    ax2 = axes[0].twinx()
    ax2.plot(range(SIMU_STEPS), controller.Tb1_list, label = 'Temperature B1', color='red', linestyle='-.')
    ax2.plot(range(SIMU_STEPS), controller.Tb2_list, label = 'Temperature B2', color='red')
    axes[1].plot(range(SIMU_STEPS), controller.sb1_list, label = 'Hysteresis state B1')
    axes[1].plot(range(SIMU_STEPS), controller.sb2_list, label = 'Hysteresis state B2')
    plt.legend()
    ax2.legend(loc=1)
    axes[0].legend(loc=2)
    axes[1].legend()
    plt.savefig('simu_output/boilers_evolution_'+scenario+'.pdf')
    ###########################################################################################'''
