#!/usr/bin/env python3

import numpy as np
import operator
import pandas as pd

TEMP = 0                 # boiler state variable n0
POWER = 1                # boiler state variable n1
HYST = 2                 # boiler state variable n2

Dt = 1                   # control period (min)

B_TMIN = 40             # Min boiler temperature (degrees celcius)
B_TMAX = 42             # Max boiler temperature (degree celcius)
T_DELTA = 40.5          # Min boiler temperature for hysteresis control (degrees celcius)
B_PMAX = -7.6           # Max boiler power (kW)
C_W = 0.00113           # specific heat of water  (kWh/(kg*K))
B_VOLUME = 300          # boiler's volume (l)
C_B = B_VOLUME * C_W    # boiler thermal capacity (kWh/K)
T_AMB = 22              # ambient temperature (degrees celsius)
t_HL = 400              # time constant for heat loss (min)



def algo_scenario1(boiler_states, p_x):


    u_B = {1: 0, 2: 0}
    p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER]
    print("px considering boilers:", p_x)
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[HYST] == 1:
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
s_B1 = 0    # previous boiler 1 charge/discharge state
s_B2 = 1    # previous boiler 2 charge/discharge state
init_boiler_states = {1: [T_B1, p_B1, s_B1], 2: [T_B2, p_B2, s_B2]}

boiler_states.append(init_boiler_states)


# In order to test the algorithm, we simulate the power excess (P_PV - P_nc)
excess = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
excess['P_PV - P_nc (kW)'] = excess['Flux energie au point d\'injection (kWh)'] * 6  # Convert the energy (kWh) to power (kW)
del excess['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore

def boiler_model(boiler_previous_state, boiler_control):

    boiler_new_state = boiler_previous_state

    for (boiler, state) in boiler_new_state.items():
        # In this model, actual boiler power cannot get to target in Dt (fake model to test control algorithm)
        state[POWER] = boiler_control[boiler] - 0.1 * boiler_control[boiler]

        # temperature evolves as a function of boiler's input power according to the simple model below
        state[TEMP] = state[TEMP] - state[POWER] * (Dt / 60) / C_B - (state[TEMP] - T_AMB) * (Dt / t_HL)

        if state[TEMP] >= T_DELTA:
            state[HYST] = 0
        elif state[TEMP] <= B_TMIN:
            state[HYST] = 1
        else:
            state[HYST] = state[HYST]

    print(boiler_new_state)

    return boiler_new_state


# Simulation of day
for h, p_x in enumerate(excess['P_PV - P_nc (kW)']):
    print('p_x=', p_x)
    boiler_control.append(algo_scenario1(boiler_states[h], p_x))

    boiler_new_state = boiler_model(boiler_states[h], boiler_control[h])

    boiler_states.append(boiler_new_state)

# END