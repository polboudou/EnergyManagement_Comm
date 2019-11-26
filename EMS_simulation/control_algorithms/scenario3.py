#!/usr/bin/env python3

######################################################################################
#####               Scenario 3 incorporates a battery system                      #####
######################################################################################

import numpy as np
import operator
import pandas as pd

TEMP = 0                 # boiler state variable n0
POWER = 1                # boiler state variable n1
HYST = 2                 # boiler state variable n2
SOC = 0                  # battery state variable n0

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

SOC_MAX = 5             # Max State-of-Charge battery (kWh)
SOC_MIN = 0.2           # Min State-of-Charge battery (kWh)
PMAX_CH = -5            # Max battery charging power (kW)
PMAX_DISCH = 5          # Max battery discharging power (kW)


# Control algorithm
def algo_scenario3(boiler_states, p_x, battery_state):

    action = {1: 0, 2: 0, 'bat': 0}
    p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER] + battery_state[POWER]
    print("px considering flexible loads:", p_x)
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[HYST] == 1:
            action[boiler] = B_PMAX
            p_x = p_x - state[POWER] + action[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, B_TMAX - state[TEMP])
                action[boiler] = max(-C_B * error_Temp / (Dt / 60), B_PMAX, -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + action[boiler]

    print("action after boiler priority:", action)
    print("px after boiler priority control", p_x)
    if p_x > 0:
        action['bat'] = max((battery_state[SOC] - SOC_MAX)/Dt , PMAX_CH , -(p_x - battery_state[POWER]))
    else:
        action['bat'] = min((battery_state[SOC] - SOC_MIN)/Dt , PMAX_DISCH , -(p_x - battery_state[POWER]))

    print("final actions :", action)

    return action

#START:

# Initialization:
boiler_states = []
controller_actions = []
T_B1 = 41
T_B2 = 39.5
p_B1 = 0
p_B2 = 0
s_B1 = 0    # previous boiler 1 charge/discharge state
s_B2 = 1    # previous boiler 2 charge/discharge state
init_boiler_states = {1: [T_B1, p_B1, s_B1], 2: [T_B2, p_B2, s_B2]}
boiler_states.append(init_boiler_states)
print(boiler_states[0])

battery_state = []
x_bat = 0
p_bat = 0
battery_state.append([x_bat, p_bat])
print(battery_state[0])



# Data acquisition. Simulation of daily power excess (P_PV - P_nc)
excess = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
excess['P_PV - P_nc (kW)'] = excess['Flux energie au point d\'injection (kWh)'] * 6  # Convert the energy (kWh) to power (kW)
del excess['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore


def battery_model(previous_state, control_action):
    new_state = previous_state
    new_state[POWER] = control_action * 0.95   # 0.95 randomly set to somehow model the slow response of the BMS
    new_state[SOC] = previous_state[SOC] - new_state[POWER] * (Dt/60)
    return new_state


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

    return boiler_new_state


# Simulation of day
for h, p_x in enumerate(excess['P_PV - P_nc (kW)']):
    print('p_pv - p_nc =', p_x)
    controller_actions.append(algo_scenario3(boiler_states[h], p_x, battery_state[h]))
    boiler_new_state = boiler_model(boiler_states[h], controller_actions[h])
    battery_new_state = battery_model(battery_state[h], controller_actions[h]['bat'])
    print('boiler_new_state', boiler_new_state)
    print('battery_new_state', battery_new_state)

    boiler_states.append(boiler_new_state)
    battery_state.append(battery_new_state)
    if h ==100:
        break

# END