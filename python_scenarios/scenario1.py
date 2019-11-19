#!/usr/bin/env python3

import numpy as np
import operator
import pandas as pd

POWER = 1                # code clarity variable
TEMP = 0                 # code clarity variable
Dt = 1                   # control period (min)

B_TMIN = 40             # Min boiler temperature (degrees celcius)
B_TMAX = 42             # Max boiler temperature (degree celcius)
B_PMAX = -7.6           # Max boiler power (kW)
C_W = 0.00113           # specific heat of water  (kWh/(kg*K))
B_VOLUME = 300          # boiler's volume (l)
C_B = B_VOLUME * C_W    # boiler thermal capacity (kWh/K)
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
                u_B[boiler] = max(-C_B * error_Temp / (Dt / 60), B_PMAX, -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + u_B[boiler]
    print('u_B = ', u_B)
    return u_B

#START:

# Initialization:
boiler_states = []
boiler_control = []
T_B1 = 41
T_B2 = 39.5
p_B1 = 0
p_B2 = 0
init_boiler_states = {1: [T_B1, p_B1], 2: [T_B2, p_B2]}

boiler_states.append(init_boiler_states)


# Data acquisition. Simulation of daily power excess (P_PV - P_nc)
excess = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
excess['P_PV - P_nc (kW)'] = excess['Flux energie au point d\'injection (kWh)'] * 6  # Convert the energy (kWh) to power (kW) and power convention (buy positive and sell negative)
del excess['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore


# Simulation of day
for h, p_x in enumerate(excess['P_PV - P_nc (kW)']):
    print('p_x=', p_x)
    boiler_control.append(algo_scenario1(boiler_states[h], p_x))

    # In order to test the algorithm, I set boilers power close to the desired action u
    p_B1 = boiler_control[h][1] - 0.1 * boiler_control[h][1]
    p_B2 = boiler_control[h][2] - 0.1 * boiler_control[h][2]

    # temperature evolves as a function of boiler's input power according to the simple model below
    T_B1 = boiler_states[h][1][TEMP] - p_B1 * (Dt/60) / C_B - (boiler_states[h][1][TEMP] - T_AMB) * (Dt/t_HL)
    T_B2 = boiler_states[h][2][TEMP] - p_B2 * (Dt/60) / C_B - (boiler_states[h][1][TEMP] - T_AMB) * (Dt/t_HL)

    print('T_B1, T_B2:', T_B1, T_B2, "p_B1, p_B2:", p_B1, p_B2)
    boiler_states.append({1: [T_B1, p_B1], 2: [T_B2, p_B2]})
    #print(boiler_states)

# END