#!/usr/bin/env python3

######################################################################################
###    Scenario 2 adds to scenario 1 an hysteresis type logic for boiler control   ###
######################################################################################


import numpy as np
import operator
import pandas as pd

TEMP = 0                 # boiler state variable n0
POWER = 1                # boiler state variable n1
HYST = 2                 # boiler state variable n2
SOC = 0                  # battery state variable n0


DT = 1  # in minutes
HORIZON = 1440  # in minutes, corresponds to 24 hours
HORIZON = 60

BOILER1_TEMP_MIN = 40   # in degree celsius
BOILER1_TEMP_MAX = 50   # in degree celsius
BOILER1_TEMP_DELTA = 42 # in degree celsius

BOILER2_TEMP_MIN = 30   # in degree celsius
BOILER2_TEMP_MAX = 60   # in degree celsius
BOILER2_TEMP_DELTA = 32 # in degree celsius


BOILERS_TEMP_MAX={1: BOILER1_TEMP_MAX, 2: BOILER2_TEMP_MAX}
BOILERS_TEMP_MIN={1: BOILER1_TEMP_MIN, 2: BOILER2_TEMP_MIN}
BOILERS_TEMP_DELTA = {1: BOILER1_TEMP_DELTA, 2: BOILER2_TEMP_DELTA}

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts
BOILERS_RATED_P = {1: BOILER1_RATED_P, 2: BOILER2_RATED_P}

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

SOC_MAX = 5             # Max State-of-Charge battery (kWh)
SOC_MIN = 0.2           # Min State-of-Charge battery (kWh)
PMAX_CH = -5            # Max battery charging power (kW)
PMAX_DISCH = 5          # Max battery discharging power (kW)

#(C_water = 4.186 watt-second per gram per degree celsius, water density is 997 grams / litre)
C_BOILER = (DT * 60) / (4.186 * 997 * BOILER1_VOLUME)   # boiler thermal capacity (C/Watt)



#BOILER1_INITIAL_TEMP = 45  # in degree celsius
#BOILER2_INITIAL_TEMP = 45  # in degree celsius


BOILER1_INITIAL_TEMP = 40  # in degree celsius
BOILER2_INITIAL_TEMP = 30  # in degree celsius

# Control algorithm
def algo_scenario2(boiler_states, p_x):

    u_B = {1: 0, 2: 0}
    hyst_states = {1: 0, 2:0}
    p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER]
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[HYST] == 1:
            u_B[boiler] = BOILERS_RATED_P[boiler]
            p_x = p_x - state[POWER] + u_B[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, BOILERS_TEMP_MAX[boiler] - state[TEMP])
                u_B[boiler] = max(- error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + u_B[boiler]

        if state[TEMP] >= BOILERS_TEMP_DELTA[boiler]:
            hyst_states[boiler] = 0
        elif state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            hyst_states[boiler] = 1
        else:
            hyst_states[boiler] = state[HYST]

    outputs = {'actions': u_B, 'hyst_states': hyst_states}
    return outputs


# Control algorithm
def algo_scenario3(boiler_states, p_x, battery_state):

    u = {1: 0, 2: 0, 'bat': 0}
    hyst_states = {1: 0, 2:0}
    p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER] + battery_state[POWER]
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[HYST] == 1:
            u[boiler] = BOILERS_RATED_P[boiler]
            p_x = p_x - state[POWER] + u[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, BOILERS_TEMP_MAX[boiler] - state[TEMP])
                u[boiler] = max(- error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + u[boiler]

        if state[TEMP] >= BOILERS_TEMP_DELTA[boiler]:
            hyst_states[boiler] = 0
        elif state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            hyst_states[boiler] = 1
        else:
            hyst_states[boiler] = state[HYST]

    if p_x > 0:
        u['bat'] = max((battery_state[SOC] - SOC_MAX)/DT , PMAX_CH , -(p_x - battery_state[POWER]))
    else:
        u['bat'] = min((battery_state[SOC] - SOC_MIN)/DT , PMAX_DISCH , -(p_x - battery_state[POWER]))

    outputs = {'actions': u, 'hyst_states': hyst_states}
    return outputs



def algo_scenario0(boiler_states):
    '''
    :param boiler_states:
    :return: supplies boilers when they reach their lower temperature bounds and until they reach upper bounds(thermostat type)
    '''
    u_B = {1: 0, 2: 0}
    hyst_states = {1: 0, 2:0}
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[HYST] == 1:
            u_B[boiler] = BOILERS_RATED_P[boiler]
        else:
            u_B[boiler] = 0

        if state[TEMP] >= BOILERS_TEMP_DELTA[boiler]:
            hyst_states[boiler] = 0
        elif state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            hyst_states[boiler] = 1
        else:
            hyst_states[HYST] = state[HYST]

    outputs = {'actions': u_B, 'hyst_states': hyst_states}
    return outputs


def algo_scenario1(boiler_states, p_x):

    u_B = {1: 0, 2: 0}
    p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER]
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            u_B[boiler] = BOILERS_RATED_P[boiler]
            p_x = p_x - state[POWER] + u_B[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, BOILERS_TEMP_MAX[boiler] - state[TEMP])
                u_B[boiler] = max(- error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + u_B[boiler]

    return u_B