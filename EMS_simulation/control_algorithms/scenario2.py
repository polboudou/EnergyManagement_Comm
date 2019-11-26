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


B_TMIN = 40             # Min boiler temperature (degrees celcius)
B_TMAX = 42             # Max boiler temperature (degree celcius)
T_DELTA = 40.5          # Min boiler temperature for hysteresis control (degrees celcius)
B_PMAX = -7.6           # Max boiler power (kW)
C_W = 0.00113           # specific heat of water  (kWh/(kg*K))
B_VOLUME = 300          # boiler's volume (l)
C_B = B_VOLUME * C_W    # boiler thermal capacity (kWh/K)
T_AMB = 22              # ambient temperature (degrees celsius)
t_HL = 400              # time constant for heat loss (min)

DT = 1  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius (TODO to be verified!) Question: is it variable?

BOILER1_RATED_P = 7600  # in Watts
BOILER2_RATED_P = 7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BOILER1_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements!)
BOILER2_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements)

# Control algorithm
def algo_scenario2(boiler_states, p_x):

    #u_B = {1: 0, 2: 0}
    u_B = {1: 0}
    p_x = p_x + boiler_states[1][POWER] #+ boiler_states[2][POWER]
    print("px considering boilers:", p_x)
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        if state[HYST] == 1:
            u_B[boiler] = B_PMAX
            p_x = p_x - state[POWER] + u_B[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, BOILER1_TEMP_MAX - state[TEMP])
                u_B[boiler] = max(-C_B * error_Temp / (DT / 60), BOILER1_RATED_P, -(p_x - state[POWER]))
                p_x = p_x - state[POWER] + u_B[boiler]
    return u_B

