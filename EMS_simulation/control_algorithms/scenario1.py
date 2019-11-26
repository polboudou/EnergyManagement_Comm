#!/usr/bin/env python3

import numpy as np
import operator
import pandas as pd
import matplotlib.pyplot as plt

POWER = 1                # code clarity variable
TEMP = 0                 # code clarity variable
DT = 1                   # control period (min)

B_TMIN = 40             # Min boiler temperature (degrees celsius)
B_TMAX = 42             # Max boiler temperature (degree celsius)
B_PMAX = -7.6           # Max boiler power (kW)
BOILER1_VOLUME = 800    # in litres
BOILER2_VOLUME = 800    # in litres

BOILER_TEMP_INCOMING_WATER = 20     #(degrees celsius)

# (C_water = 4.186 watt-second per gram per degree celsius, water density is 997 grams / litre)
C_BOILER1 = (DT * 60) / (4.186 * 997 * BOILER1_VOLUME)  # boiler thermal capacity (kWh/K)
C_BOILER2 = (DT * 60) / (4.186 * 997 * BOILER2_VOLUME)  # boiler thermal capacity (kWh/K)
C_BOILERS = {1: C_BOILER1, 2: C_BOILER2}

print(C_BOILER2)
T_AMB = 22              # ambient temperature (degrees celsius)
t_HL = 400              # time constant for heat loss (min)


# Control algorithm
def algo_scenario1(boiler_states, p_x):

    u_B = {1: 0, 2: 0}
    p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER]
    print("px en considérant les boilers:", p_x)
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))

    for (boiler, state) in boiler_states_sorted:
        if state[TEMP] <= B_TMIN:
            u_B[boiler] = B_PMAX
            p_x = p_x - state[POWER] + u_B[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, B_TMAX - state[TEMP])
                u_B[boiler] = max(-C_BOILERS[boiler] * error_Temp, B_PMAX, -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + u_B[boiler]
    print('u_B = ', u_B)
    return u_B

#START:

# Initialization:
boiler_states = []
boiler_control = []
T_B1_0 = 41
T_B2_0 = 39.5
p_B1_0 = 0
p_B2_0 = 0
init_boiler_states = {1: [T_B1_0, p_B1_0], 2: [T_B2_0, p_B2_0]}

T_B1 = []
T_B2 = []
p_B1 = []
p_B2 = []
u_B1 = []
u_B2 = []

boiler_states.append(init_boiler_states)


# Data acquisition. Simulation of daily power excess (P_PV - P_nc)
excess = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
excess['P_PV - P_nc (kW)'] = excess['Flux energie au point d\'injection (kWh)'] * 6  # Convert the energy (kWh) to power (kW) and power convention (buy positive and sell negative)
del excess['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore

# Simulation of how water consumption
hot_water_usage = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,1])
hot_water_usage_list = hot_water_usage.values

# Simulation of day
for h, p_x in enumerate(excess['P_PV - P_nc (kW)']):
    print('p_x=', p_x)
    boiler_control.append(algo_scenario1(boiler_states[h], p_x))

    u_B1.append(boiler_control[h][1])
    u_B2.append(boiler_control[h][2])

    # In order to test the algorithm, I set boilers power close to the desired action u
    p_B1.append(u_B1[h] - 0.1 * u_B1[h])
    p_B2.append(u_B2[h] - 0.1 * u_B2[h])

    # temperature evolution
    A_B1_h = 1 - hot_water_usage_list[h]/BOILER1_VOLUME /2 # for tests purposes. otherwise to much consumption
    T_B1.append(A_B1_h * boiler_states[h][1][TEMP] + C_BOILER1 * p_B1[h] - (hot_water_usage_list[h]//BOILER1_VOLUME) * BOILER_TEMP_INCOMING_WATER)

    A_B2_h = 1 - hot_water_usage_list[h]/BOILER2_VOLUME /3 # for tests purposes. otherwise to much consumption
    T_B2.append(A_B2_h * boiler_states[h][2][TEMP] - C_BOILER1 * p_B2[h] - (hot_water_usage_list[h]//BOILER2_VOLUME) * BOILER_TEMP_INCOMING_WATER)

    #T_B1 = boiler_states[h][1][TEMP] - p_B1 * (DT/60) / C_B - (boiler_states[h][1][TEMP] - T_AMB) * (DT/t_HL)
    #T_B2 = boiler_states[h][2][TEMP] - p_B2 * (DT/60) / C_B - (boiler_states[h][1][TEMP] - T_AMB) * (DT/t_HL)

    #print('T_B1, T_B2:', T_B1_h, T_B2_h, "p_B1, p_B2:", p_B1_h, p_B2_h)
    boiler_states.append({1: [T_B1[h], p_B1[h]], 2: [T_B2[h], p_B2[h]]})
    #print(boiler_states)

    if h == 140:
        break

fig, axes = plt.subplots(2, 1)
axes[0].plot(T_B1, label='boiler 1 temp')
axes[0].plot(T_B2, label='boiler 1 temp')
axes[1].plot(p_B1, label='boiler 1 power')
axes[1].plot(p_B2, label='boiler 2 power')
axes[1].plot(u_B1, label='boiler 1 action (power)')
axes[1].plot(u_B2, label='boiler 2 action (power)')
axes[0].plot(hot_water_usage_list, label='hot_water_usage')
axes[0].legend()
axes[1].legend()

plt.show()
# END