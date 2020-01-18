#!/usr/bin/env python3

import operator

## =========================    SIMULATION PARAMETERS    =============================== ##
SIMU_TIMESTEP = 30                                  # in seconds
CONTROL_TIMESTEP = 5*60                             # in seconds
HORIZON = 1440*60                                   # in seconds, corresponds to 24 hours
## ==================================================================================== ##

BOILER1_TEMP_MIN = 40                               # in degree celsius
BOILER1_TEMP_MAX = 50                               # in degree celsius
BOILER1_TEMP_DELTA = 40.2                           # in degree celsius

BOILER2_TEMP_MIN = 30                               # in degree celsius
BOILER2_TEMP_MAX = 60                               # in degree celsius
BOILER2_TEMP_DELTA = 30.6                           # in degree celsius

BOILERS_TEMP_MAX={1: BOILER1_TEMP_MAX, 2: BOILER2_TEMP_MAX}
BOILERS_TEMP_MIN={1: BOILER1_TEMP_MIN, 2: BOILER2_TEMP_MIN}
BOILERS_TEMP_DELTA = {1: BOILER1_TEMP_DELTA, 2: BOILER2_TEMP_DELTA}

BOILER1_RATED_P = -7600                             # in Watts
BOILER2_RATED_P = -7600                             # in Watts
BOILERS_RATED_P = {1: BOILER1_RATED_P, 2: BOILER2_RATED_P}

BOILER1_VOLUME = 800                                # in litres
BOILER2_VOLUME = 800                                # in litres

SOC_MAX = 5000                                      # Max State-of-Charge battery (Wh)
SOC_MIN = 200                                       # Min State-of-Charge battery (Wh)
PMAX_CH = -5000                                     # Max battery charging power (W)
PMAX_DISCH = 5000                                   # Max battery discharging power (W)

d_WATER = 997                                       # in [g/L]
C_WATER = 4.186                                     # in [W*s/k*K]

C_BOILER =  (C_WATER * d_WATER * BOILER1_VOLUME)    # in [(Watt*sec)/K]

TEMP = 0                 # boiler state variable n0
POWER = 1                # boiler state variable n1
HYST = 2                 # boiler state variable n2
SOC = 0                  # battery state variable n0

def algo_scenario0(boiler_states):
    '''
    :param boiler_states:
    :return: supplies boilers when they reach their lower temperature bounds and until they reach upper bounds(thermostat type)
    '''
    u_B = {1: 0, 2: 0}
    hyst_states = {1: 0, 2: 0}
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))

    for (boiler, state) in boiler_states_sorted:
        # determining hysteresis state variables
        if state[TEMP] >= BOILERS_TEMP_DELTA[boiler]:
            hyst_states[boiler] = 0
        elif state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            hyst_states[boiler] = 1
        else:
            hyst_states[boiler] = state[HYST]
        # setting control actions
        if hyst_states[boiler] == 1:
            u_B[boiler] = BOILERS_RATED_P[boiler]
        else:
            u_B[boiler] = 0

    outputs = {'actions': u_B, 'hyst_states': hyst_states}
    return outputs


def algo_scenario1(boiler_states, p_x):

    u_B = {1: 0, 2: 0}
    hyst_states = {1: 0, 2: 0}
    #p_x = p_x + boiler_states[1][POWER] + boiler_states[2][POWER]
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:

        #print("boiler", boiler, 'state temp ', state[TEMP])
        if state[TEMP] >= BOILERS_TEMP_DELTA[boiler]:
            hyst_states[boiler] = 0
        elif state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            hyst_states[boiler] = 1
        else:
            hyst_states[boiler] = state[HYST]

        if hyst_states[boiler] == 1:
            u_B[boiler] = BOILERS_RATED_P[boiler]
            p_x += u_B[boiler]
        else:
            #print('px ', p_x)
            if p_x > 0:
                error_Temp = max(0, BOILERS_TEMP_MAX[boiler] - state[TEMP])
                #print('boiler', boiler, "- error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -(p_x - state[POWER])", - error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -p_x)
                u_B[boiler] = max(- error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -p_x)
                p_x += u_B[boiler]

    outputs = {'actions': u_B, 'hyst_states': hyst_states}
    return outputs

def algo_scenario2(boiler_states, p_x, battery_state):

    u = {1: 0, 2: 0, 'bat': 0}

    hyst_states = {1: 0, 2: 0}
    boiler_states_sorted = sorted(boiler_states.items(), key=operator.itemgetter(1))
    for (boiler, state) in boiler_states_sorted:
        # setting hysteresis state variable
        if state[TEMP] >= BOILERS_TEMP_DELTA[boiler]:
            hyst_states[boiler] = 0
        elif state[TEMP] <= BOILERS_TEMP_MIN[boiler]:
            hyst_states[boiler] = 1
        else:
            hyst_states[boiler] = state[HYST]

        # determining control action
        if hyst_states[boiler] == 1:
            u[boiler] = BOILERS_RATED_P[boiler]
            p_x += u[boiler]
        else:
            if p_x > 0:
                error_Temp = max(0, BOILERS_TEMP_MAX[boiler] - state[TEMP])
                u[boiler] = max(- error_Temp / C_BOILER, BOILERS_RATED_P[boiler], -p_x)
                p_x += u[boiler]
    if p_x > 0:
        u['bat'] = max((battery_state[SOC] - SOC_MAX)/(CONTROL_TIMESTEP/3600), PMAX_CH , -p_x)
    else:
        u['bat'] = min((battery_state[SOC] - SOC_MIN)/(CONTROL_TIMESTEP/3600) , PMAX_DISCH , -p_x)

    outputs = {'actions': u, 'hyst_states': hyst_states}
    return outputs


