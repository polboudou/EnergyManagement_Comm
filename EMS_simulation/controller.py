#!/usr/bin/env python3


import pandas as pd
import numpy as np
from scipy import interpolate
import random
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
from datetime import timedelta
from EMS_simulation.control_algorithms import scenarios
from EMS_simulation.control_algorithms import mpc_boilers
from EMS_simulation.control_algorithms import mpc_batteries
broker_address ="mqtt.teserakt.io"   # use external broker (alternative broker address: "test.mosquitto.org")


## =========================    SIMULATION PARAMETERS    =============================== ##
# select simulation horizon, control timestep, models timestep
HORIZON = 1440*60                       # in seconds, corresponds to 24 hours
MPC_START_TIME = '05.01.2018 00:00:00'  # pandas format mm.dd.yyyy hh:mm:ss
SIMU_TIMESTEP = 30                      # in seconds
CONTROL_TIMESTEP = 5*60                 # in seconds

# choose between 'Scenario0', 'Scenario1', 'Scenario2', 'MPCboilers', 'MPCbattery'
scenario = 'Scenario2'

FORECAST_INACCURACY_COEF = 0.1  # 0 for perfect accuracy, 1 for big inaccuracy
## ==================================================================================== ##


CONTROL_STEPS = range(0, int(HORIZON/SIMU_TIMESTEP), int(CONTROL_TIMESTEP/SIMU_TIMESTEP))
SIMU_STEPS = range(int(HORIZON/SIMU_TIMESTEP)-int(CONTROL_TIMESTEP/SIMU_TIMESTEP))
SIMU_STEPS = range(int(HORIZON/SIMU_TIMESTEP)-10)

if scenario == 'Scenario2' or scenario == 'MPCbattery':
    BATTERY = True
else:
    BATTERY = False

d_WATER = 977
C_WATER = 4.186


class Controller():
    def __init__(self, description):
        self.description = description
        self.client = self.setup_client()
        self.control_iter = 0
        self.Tb1 = 0
        self.pb1 = 0
        self.sb1 = 0
        self.Tb2 = 0
        self.pb2 = 0
        self.sb2 = 0
        self.soc_bat = 0
        self.p_bat = 0
        self.Tb1_list = []
        self.pb1_list = []
        self.sb1_list = []
        self.Tb2_list = []
        self.pb2_list = []
        self.sb2_list = []
        self.soc_bat_list = []
        self.p_bat_list = []


    def run_algorithm(self, p_x, water):

        if 'Scenario0' in self.description:
            output = scenarios.algo_scenario0({1: [self.Tb1, self.pb1, self.sb1], 2: [self.Tb2, self.pb2, self.sb2]})
            self.sb1 = output['hyst_states'][1]
            self.sb1_list.append(self.sb1)
            self.sb2 = output['hyst_states'][2]
            self.sb2_list.append(self.sb2)
            return output['actions']

        if 'Scenario1' in self.description:
            output = scenarios.algo_scenario1({1:[self.Tb1, self.pb1, self.sb1], 2:[self.Tb2, self.pb2, self.sb2]}, p_x)
            self.sb1 = output['hyst_states'][1]
            self.sb1_list.append(self.sb1)
            self.sb2 = output['hyst_states'][2]
            self.sb2_list.append(self.sb2)
            return output['actions']

        if 'Scenario2' in self.description:
            output = scenarios.algo_scenario2({1: [self.Tb1, self.pb1, self.sb1], 2: [self.Tb2, self.pb2, self.sb2]},
                                              p_x, [self.soc_bat, self.p_bat] )
            self.sb1 = output['hyst_states'][1]
            self.sb1_list.append(self.sb1)
            self.sb2 = output['hyst_states'][2]
            self.sb2_list.append(self.sb2)
            return output['actions']

        if 'MPCboilers' in self.description:
            start = time.time()
            output = mpc_boilers.mpc_iteration(p_x, water, self.Tb1, self.Tb2, self.control_iter)
            print("---------MPC computing time =", time.time()-start)
            self.control_iter += 1
            return output

        if 'MPCbattery' in self.description:
            print("battery soc ", self.soc_bat)
            start = time.time()
            output = mpc_batteries.mpc_iteration(p_x, water, self.Tb1, self.Tb2, self.soc_bat, self.control_iter)
            print("---------MPC computing time =", time.time()-start)
            self.control_iter += 1
            return output

    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        #client.on_log = on_log     # remove comment to see messages with entities
        client.on_disconnect = on_disconnect
        client.on_message = on_message_controller
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

def get_excess_power_forecast():
    # Data acquisition. Simulation of daily power excess (P_PV - P_nc)
    excess_df = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
    # Convert the energy (kWh) to power (W) and power convention (buy positive and sell negative)
    excess_df['P_PV - P_nc (kW)'] = excess_df[
                                     'Flux energie au point d\'injection (kWh)'] * 6 * -1000
    del excess_df['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore
    start_index = excess_df.index[excess_df.index == MPC_START_TIME][0]  # df.index returns a list
    end_index = start_index + timedelta(seconds=HORIZON - CONTROL_TIMESTEP)
    excess_df = excess_df.loc[start_index:end_index]
    excess = excess_df['P_PV - P_nc (kW)'].to_numpy()
    excess = new_resolution(excess, SIMU_TIMESTEP, 1)

    return excess

def get_excess_power_simulation(p_x_forecast):
    # random samples from a uniform distribution around 0
    random.seed(1)
    p_x_forecast = np.array(p_x_forecast)

    p_x = [0]*len(p_x_forecast)
    for i in range(len(p_x_forecast)):
        if p_x_forecast[i] > 0:
            p_x[i] = p_x_forecast[i] + random.uniform(-FORECAST_INACCURACY_COEF*p_x_forecast[i],
                                                      FORECAST_INACCURACY_COEF*p_x_forecast[i])
        else:
            p_x[i] = p_x_forecast[i] - random.uniform(0, FORECAST_INACCURACY_COEF*p_x_forecast[i])

    return p_x

def get_energy_hot_water_usage_simu():
    measured = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx',
                             index_col=[0], usecols=[0,2])
    # hot_water_usage divided by 2 cause two boilers, with same consumption
    hot_water_usage = measured['Actual'].to_numpy()/2  /(10 / (CONTROL_TIMESTEP/60)) # data was in [litres/10min]
    hot_water_usage = np.repeat(hot_water_usage, int(10 / (CONTROL_TIMESTEP/60)))
    # Energy : [L*30s * g/L * W*s/(g*K)] # we assume 40 degrees for the conversion
    water_energy_usage = hot_water_usage * C_WATER * d_WATER * 40
    return water_energy_usage.tolist()

def get_energy_sell_price():
    df = pd.read_excel('data_input/energy_sell_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1])
    sell_price = df['Sell Price (CHF / kWh)'].to_numpy()
    sell_price = new_resolution(sell_price, SIMU_TIMESTEP, len(sell_price)*10/(60*24))
    return sell_price

def get_energy_buy_price():
    df = pd.read_excel('data_input/energy_buy_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1])
    buy_price = df['Buy Price (CHF / kWh)'].to_numpy()
    buy_price = new_resolution(buy_price, SIMU_TIMESTEP, len(buy_price)*10/(60*24))
    return buy_price

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
        controller.pb1_list.append(controller.pb1)

    if msg.topic == 'boiler1_sensor/temp':
        controller.Tb1 = float(msg.payload)
        controller.Tb1_list.append(controller.Tb1)

    if msg.topic == 'boiler2_sensor/power':
        controller.pb2 = float(msg.payload)
        controller.pb2_list.append(controller.pb2)

    if msg.topic == 'boiler2_sensor/temp':
        controller.Tb2 = float(msg.payload)
        controller.Tb2_list.append(controller.Tb2)

    if msg.topic == 'battery/soc':
        controller.soc_bat = float(msg.payload)
        controller.soc_bat_list.append(controller.soc_bat)

    if msg.topic == 'battery/power':
        controller.p_bat = float(msg.payload)
        controller.p_bat_list.append(controller.p_bat)


if __name__ == '__main__':

    # instantiate controller and connect to other entities
    r = random.randrange(1, 100000)
    cname = scenario + "-" + str(r)     # add randomness to name to avoid having two clients with same name
    controller = Controller(cname)
    controller.client.subscribe("boiler2_sensor/temp")
    controller.client.subscribe("boiler2_sensor/power")
    controller.client.subscribe("boiler1_sensor/temp")
    controller.client.subscribe("boiler1_sensor/power")
    if scenario == 'Scenario2' or scenario == 'MPCbattery':
        controller.client.subscribe("battery/soc")
        controller.client.subscribe("battery/power")

    # get non-controllable variables
    sell_price = get_energy_sell_price()
    buy_price = get_energy_buy_price()
    p_x = get_excess_power_forecast()
    p_x_measured = get_excess_power_simulation(p_x)
    energy_hot_water_use = get_energy_hot_water_usage_simu()

    # wait until other entities are instantiated
    while controller.Tb1 == 0 or controller.Tb2 == 0:
        time.sleep(0.01)
    if BATTERY:
        while controller.soc_bat == 0:
            time.sleep(0.01)

    # launch control algo each CONTROL STEP taking last measurements from entities
    for h in CONTROL_STEPS:
        print("controller control action at ", h/2,'min')
        time.sleep(0.1*(CONTROL_TIMESTEP/SIMU_TIMESTEP))
        #print("len(controller.pb1), len(controller.Tb2) ", len(controller.pb1_list), len(controller.Tb2_list))
        actions = controller.run_algorithm(p_x_measured[h], energy_hot_water_use[int(h/(CONTROL_TIMESTEP/SIMU_TIMESTEP))])
        controller.client.publish('boiler1_actuator', str(actions[1]))
        controller.client.publish('boiler2_actuator', str(actions[2]))
        if BATTERY:
            controller.client.publish('batteryMS', str(actions['bat']))

    # first measurement received was an init message. we remove it
    controller.pb1_list.pop(0)
    controller.pb2_list.pop(0)
    controller.Tb1_list.pop(0)
    controller.Tb2_list.pop(0)
    print(len(controller.pb1_list))

    if BATTERY:
        controller.p_bat_list.pop(0)
        controller.soc_bat_list.pop(0)
        print(len(controller.p_bat_list))

    # print full results to use for improved plots
    '''print("pb1_list = ", controller.pb1_list)
    print("pb2_list = ", controller.pb2_list)
    print("Tb1_list = ", controller.Tb1_list)
    print("Tb2_list = ", controller.Tb2_list)
    print("soc_bat_list = ", controller.soc_bat_list)
    print("p_bat_list = ", controller.p_bat_list)
    print("p_x_forecast = ", p_x.tolist())
    print("p_x_measured = ", p_x_measured)
    print("hot_water_use = ", energy_hot_water_use)'''

    # compute cost of the simulated power exchange with the grid
    cost = 0
    for h in SIMU_STEPS:
        p_grid_silutation = (p_x_measured[h] + controller.pb1_list[h] + controller.pb2_list[h]) \
                            / (3600/SIMU_TIMESTEP) * 0.001 # convert Watt to kWh
        if BATTERY:
            p_grid_silutation += controller.p_bat_list[h] / (3600/SIMU_TIMESTEP) * 0.001 # convert Watt to kWh

        if p_grid_silutation > 0:
            cost += p_grid_silutation * sell_price[h]
        if p_grid_silutation <= 0:
            cost += p_grid_silutation * buy_price[h]
    print("Daily electricity cost with ", scenario, 'is:', round(cost,2))

    # plotting results
    positions = [0, 120 * 3, 120 * 6, 120 * 9, 120 * 12, 120 * 15, 120 * 18, 120 * 21, 120 * 24]
    labels = [0, 3, 6, 9, 12, 15, 18, 21, 24]

    fig, ax = plt.subplots(2, 1)
    plt.setp(ax, xticks=positions, xticklabels=labels)

    ax[0].set_title('(daily cost: ' + str(round(-cost, 2)) + ' CHF)', fontsize=15)
    ax[0].plot(range(len(controller.pb1_list)), controller.pb1_list, label='Power B1', color='blue', linestyle='-.')
    ax[0].plot(range(len(controller.pb2_list)), controller.pb2_list, label='Power B2', color='cyan', alpha=0.7)
    if BATTERY:
        ax[0].plot(range(len(controller.p_bat_list)), controller.p_bat_list, label='Power battery', color='green')
    ax[0].plot(range(len(p_x_measured)), p_x_measured, label='P_pv - P_load', color='grey', alpha=0.7)
    ax[0].plot(range(len(p_x_measured)), [0 for i in range(len(p_x_measured))], color='black', alpha=0.7,
               linestyle='-.')
    ax0 = ax[0].twinx()
    ax0.plot(range(len(p_x_measured)), [40 for i in range(len(p_x_measured))], color='red', linestyle='-.',
             linewidth=0.7)
    ax0.plot(range(len(p_x_measured)), [50 for i in range(len(p_x_measured))], color='red', linestyle='-.',
             linewidth=0.7)
    ax0.plot(range(len(p_x_measured)), [30 for i in range(len(p_x_measured))], color='orange', linestyle='-.',
             linewidth=0.7)
    ax0.plot(range(len(p_x_measured)), [60 for i in range(len(p_x_measured))], color='orange', linestyle='-.',
             linewidth=0.7)
    ax0.plot(range(len(controller.Tb1_list)), controller.Tb1_list, label='Temperature B1', color='red', linestyle='-.')
    ax0.plot(range(len(controller.Tb2_list)), controller.Tb2_list, label='Temperature B2', color='orange')
    if BATTERY:
        ax[1].plot(range(len(controller.soc_bat_list)), controller.soc_bat_list, label='Battery SoC', color='orange')

    ax[1].set_xlabel("Time [h]", fontsize=15)
    if BATTERY:
        ax[1].set_ylabel('Battery SoC [Wh]', fontsize=15)
    ax0.set_ylim(28, 61)
    ax[0].set_xlabel("Time [h]", fontsize=15)
    ax0.set_ylabel('Temperature [C]', fontsize=15)
    ax[0].set_ylabel('Power [W]', fontsize=15)
    ax0.legend(loc=1, fontsize=15)
    ax[0].legend(loc=2, fontsize=15)
    if BATTERY:
        ax[1].legend(loc=2, fontsize=15)
    plt.savefig('simu_output/results_'+scenario+'.pdf')

    time.sleep(1)
    controller.client.publish('boilers', 'End')
    controller.client.loop_stop()
    controller.client.disconnect(broker_address)



