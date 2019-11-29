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

DT = 10  # in minutes
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40   # in degree celsius
BOILER1_TEMP_MAX = 50   # in degree celsius
BOILER1_TEMP_DELTA = 42 # in degree celsius

BOILER2_TEMP_MIN = 30   # in degree celsius
BOILER2_TEMP_MAX = 60   # in degree celsius
BOILER2_TEMP_DELTA = 35 # in degree celsius


BOILERS_TEMP_MAX={1: BOILER1_TEMP_MAX, 2: BOILER2_TEMP_MAX}
BOILERS_TEMP_MIN={1: BOILER1_TEMP_MIN, 2: BOILER2_TEMP_MIN}
BOILERS_TEMP_DELTA = {1: BOILER1_TEMP_DELTA, 2: BOILER2_TEMP_DELTA}

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius (TODO to be verified!) Question: is it variable?

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts
BOILERS_RATED_P = {1: BOILER1_RATED_P, 2: BOILER2_RATED_P}

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

#(C_water = 4.186 watt-second per gram per degree celsius, water density is 997 grams / litre)
C_BOILER = (DT * 60) / (4.186 * 997 * BOILER1_VOLUME)   # boiler thermal capacity (C/Watt)





BOILER1_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements!)
BOILER2_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements)

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