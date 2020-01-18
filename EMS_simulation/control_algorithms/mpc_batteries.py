#!/usr/bin/env python3

import pandas as pd
from datetime import timedelta
from datetime import datetime
from scipy.optimize import linprog
import numpy as np

## =========================    SIMULATION PARAMETERS    =============================== ##
CONTROL_TIMESTEP = 5                                       # in minutes
HORIZON = 1440                                      # in minutes, corresponds to 24 hours
MPC_START_TIME = '05.01.2018 00:00:00'              # pandas format mm.dd.yyyy hh:mm:ss
## ==================================================================================== ##

no_slots = int(0.5 * HORIZON / CONTROL_TIMESTEP)

BOILER1_TEMP_MIN = 40                               # in degree celsius
BOILER1_TEMP_MAX = 50                               # in degree celsius
TB1_RANGE = range(BOILER1_TEMP_MIN, BOILER1_TEMP_MAX + 1, 2)

BOILER2_TEMP_MIN = 30                               # in degree celsius
BOILER2_TEMP_MAX = 60                               # in degree celsius
TB2_RANGE = range(BOILER2_TEMP_MIN, BOILER2_TEMP_MAX + 1, 6)


BOILER1_TEMP_INCOMING_WATER = 20                    # in degree celsius
BOILER2_TEMP_INCOMING_WATER = 20                    # in degree celsius

BOILER1_RATED_P = -7600                             # in Watts
BOILER2_RATED_P = -7600                             # in Watts

BOILER1_VOLUME = 800                                # in litres
BOILER2_VOLUME = 800                                # in litres

d_WATER = 997                                       # in [g/L]
C_WATER = 4.186                                     # in [W*s/k*K]

C_BOILER1 =  (C_WATER * d_WATER * BOILER1_VOLUME)   # in [(Watt*sec)/K]
C_BOILER2 =  (C_WATER * d_WATER * BOILER2_VOLUME)   # in [(Watt*sec)/K]

BATTERY_SOC_MAX = 5000                              # in Watts-h
BATTERY_SOC_MIN = 200                               # in Watts-h
BATTERY_CHARGE_POWER_LIMIT = -5000                  # in Watts
BATTERY_DISCHARGE_POWER_LIMIT = 5000                # in Watts
BATTERY_POWER_EFFICIENCY = 1


def get_hot_water_energy_usage_forecast():
    litres_forecast = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx',
                                    index_col=[0],
                                    usecols=[0, 1])
    litres_forecast = litres_forecast['Hot water usage (litres)'].to_numpy() / (
            10 / CONTROL_TIMESTEP) / 2  # data is in [litres/CONTROL_TIMESTEP]    # divided by 2 cause 2 boilers
    litres_forecast = np.repeat(litres_forecast, int(10 / CONTROL_TIMESTEP))
    # Energy/TIMESLOT : [L * g/L * W*s/(g*K) * K]  # forecast is created considering volume forecast and T=40 degrees
    energy_forecast = litres_forecast * d_WATER * C_WATER * 40
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(CONTROL_TIMESTEP) + 'min')
    energy_forecast_df = pd.DataFrame(energy_forecast, index=dates)
    return energy_forecast_df

def get_excess_power_forecast(iteration):
    df = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0,1])

    start_index = df.index[df.index == (MPC_START_TIME)][0] # df.index returns a list
    start_index += timedelta(minutes=iteration * CONTROL_TIMESTEP)
    end_index = start_index + timedelta(minutes =HORIZON - CONTROL_TIMESTEP)
    df = df.loc[start_index:end_index] * (-6000) # Convert energy (kWh) to power (W) (buy positive and sell negative)
    excess = df['Flux energie au point d\'injection (kWh)'].to_numpy()
    excess = np.repeat(excess, int(10 / CONTROL_TIMESTEP))
    dates = pd.date_range(start=start_index, end=end_index, freq=str(CONTROL_TIMESTEP) + 'min')
    df = pd.DataFrame(excess, index=dates)
    return df

def get_energy_sell_price():
    df = pd.read_excel('data_input/energy_sell_price_10min_granularity.xlsx', index_col=[0], usecols=[0,1]).to_numpy()
    df = np.repeat(df, int(10 / CONTROL_TIMESTEP))
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(CONTROL_TIMESTEP) + 'min')
    df = pd.DataFrame(df, index=dates)
    return df


def get_energy_buy_price():
    df = pd.read_excel('data_input/energy_buy_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1]).to_numpy()
    df = np.repeat(df, int(10 / CONTROL_TIMESTEP))
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(CONTROL_TIMESTEP) + 'min')
    df = pd.DataFrame(df, index=dates)
    return df


def mpc_iteration(p_x, soc_bat_init, hot_water_energy, T_B1_init, T_B2_init, iteration):
    # 1. Get excess solar power forecasts
    excess_power_forecast_df = get_excess_power_forecast(iteration)

    # 2. Get hot water consumption volume forecast
    hot_water_energy_usage_forecast_df = get_hot_water_energy_usage_forecast()

    # Get energy sell price
    energy_sell_price_df = get_energy_sell_price()
    # Get energy buy price
    energy_buy_price_df = get_energy_buy_price()

    ############ Set up the optimisation problem

    current_time = datetime.strptime(MPC_START_TIME, "%m.%d.%Y %H:%M:%S") + timedelta(minutes=iteration * CONTROL_TIMESTEP)
    print(current_time)

    indices = []
    indices.append(current_time)

    # decision variables: Phi, Pg, Pb1, Pb2, Tb1, Tb2,  alpha1, alpha2, epsilon1, epsilon2, Pbat, Ebat
    NO_VARS_PS = 12
    no_ctrl_vars = NO_VARS_PS * no_slots
    c = []
    bounds = []
    A_eq = []
    b_eq = []
    A_ub = []
    b_ub = []

    for x in range(no_slots):
        # 1. Setup the objective function
        c.append(1)  # variables: Phi, Pg, Pb1, Pb2, Tb1, Tb2,  alpha1, alpha2, epsilon1, epsilon2, Pbat, Ebat
        c.extend([0, 0, 0, 0, 0, 0, 0, 0.2, 0.2, 0, 0])   # 0.2 weights on epsilon give good results

        # 2. Setup the bounds for the control variables
        phi_bounds = (None, None)
        psg_bounds = (None, None)
        pb1_bounds = (BOILER1_RATED_P, 0)
        pb2_bounds = (BOILER2_RATED_P, 0)
        tb1_bounds = (BOILER1_TEMP_MIN, BOILER1_TEMP_MAX)
        tb2_bounds = (BOILER2_TEMP_MIN, BOILER2_TEMP_MAX)
        alpha1_bounds = (0, BOILER1_TEMP_MAX)   # for T in temp_bounds, alpha cannot be negative
        alpha2_bounds = (0, BOILER2_TEMP_MAX)
        epsilon1_bounds = (0, BOILER1_TEMP_MAX) # for T in temp_bounds, alpha cannot be negative
        epsilon2_bounds = (0, BOILER2_TEMP_MAX)
        pbat_bounds = (BATTERY_CHARGE_POWER_LIMIT, BATTERY_DISCHARGE_POWER_LIMIT)
        ebat_bounds = (BATTERY_SOC_MIN, BATTERY_SOC_MAX)
        bounds_one_slot = [phi_bounds, psg_bounds, pb1_bounds, pb2_bounds, tb1_bounds, tb2_bounds, alpha1_bounds,
                           alpha2_bounds, epsilon1_bounds, epsilon2_bounds, pbat_bounds, ebat_bounds]
        bounds.extend(bounds_one_slot)

        # 3. Setup equality constraints
        excess_power_forecast_index = \
        excess_power_forecast_df.index[excess_power_forecast_df.index == current_time][
            0]  # df.index returns a list
        excess_power_forecast = excess_power_forecast_df.loc[excess_power_forecast_index]

        # power balance constraint
        if x == 0:  # the measured excess power is considered
            # var: (0)Phi,(1)Pg,(2)Pb1,(3)Pb2,(4)Tb1,(5)Tb2,(6)alpha1,(7)alpha2,(8)epsi1,(9)epsi2,(10)Pbat,(11)Ebat
            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS + 1] = 1
            row[x * NO_VARS_PS + 2] = 1
            row[x * NO_VARS_PS + 3] = 1
            row[x * NO_VARS_PS + 10] = 1
            A_eq.append(row)
            b_eq.append(-p_x)
        else:  # the forecasted excess is considered
            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS + 1] = 1
            row[x * NO_VARS_PS + 2] = 1
            row[x * NO_VARS_PS + 3] = 1
            row[x * NO_VARS_PS + 10] = 1
            A_eq.append(row)
            b_eq.append(-excess_power_forecast[0])

        # Battery model constraints
        row = [0] * no_ctrl_vars
        row[x * NO_VARS_PS + 11] = 1
        row[x * NO_VARS_PS + 10] = BATTERY_POWER_EFFICIENCY * CONTROL_TIMESTEP / 60
        A_eq.append(row)
        if x == 0:
            b_eq.append(soc_bat_init)
        else:
            row[x * NO_VARS_PS -1] = -1
            b_eq.append(0)

        # Boiler models constraints
        hot_water_usage_forecast_index = \
            hot_water_energy_usage_forecast_df.index[hot_water_energy_usage_forecast_df.index == current_time][
                0]  # df.index returns a list
        hot_water_energy_usage_forecast = hot_water_energy_usage_forecast_df.loc[hot_water_usage_forecast_index]

        # 1. alhpa constraints
        if x == 0:
            # variables:(0)Phi,(1)Pg,(2)Pb1,(3)Pb2,(4)Tb1,(5)Tb2,(6)alpha1,(7)alpha2,(8)epsi1,(9)epsi2,(10)Pbat,(11)Ebat
            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS + 6] = 1
            row[x * NO_VARS_PS + 2] = (CONTROL_TIMESTEP * 60) / C_BOILER1
            A_eq.append(row)
            b_eq.append(T_B1_init - hot_water_energy/C_BOILER1)

            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS + 7] = 1
            row[x * NO_VARS_PS + 3] = (CONTROL_TIMESTEP * 60) / C_BOILER2
            A_eq.append(row)
            b_eq.append(T_B2_init - hot_water_energy/C_BOILER2)
        else:
            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS - 8] = -1
            row[x * NO_VARS_PS + 6] = 1
            row[x * NO_VARS_PS + 2] = (CONTROL_TIMESTEP * 60) / C_BOILER1
            A_eq.append(row)
            b_eq.append(-hot_water_energy_usage_forecast[0]/C_BOILER1)

            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS - 7] = -1
            row[x * NO_VARS_PS + 7] = 1
            row[x * NO_VARS_PS + 3] = (CONTROL_TIMESTEP * 60) / C_BOILER2
            A_eq.append(row)
            b_eq.append(-hot_water_energy_usage_forecast[0]/C_BOILER2)

        # 2. Tb constraints
        row = [0] * no_ctrl_vars
        row[x * NO_VARS_PS + 4] = 1
        row[x * NO_VARS_PS + 6] = -1
        row[x * NO_VARS_PS + 8] = -1
        A_eq.append(row)
        b_eq.append(0)

        row = [0] * no_ctrl_vars
        row[x * NO_VARS_PS + 5] = 1
        row[x * NO_VARS_PS + 7] = -1
        row[x * NO_VARS_PS + 9] = -1
        A_eq.append(row)
        b_eq.append(0)

        # 3. Epsilon inequality constraints
        # variables: (0)Phi,(1)Pg,(2)Pb1,(3)Pb2,(4)Tb1,(5)Tb2,(6)alpha1,(7)alpha2,(8)epsi1,(9)epsi2,(10)Pbat,(11)Ebat
        K1 = hot_water_energy_usage_forecast[0] * BOILER1_TEMP_INCOMING_WATER
        for temp in TB1_RANGE:
            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS + 8] = -1
            row[x * NO_VARS_PS - 8] = -(K1 / C_BOILER1) / (temp**2)
            A_ub.append(row)
            b_ub.append(-(K1 / C_BOILER1) * (2 / temp))

        K2 = hot_water_energy_usage_forecast[0] * BOILER1_TEMP_INCOMING_WATER
        for temp in TB2_RANGE:
            row = [0] * no_ctrl_vars
            row[x * NO_VARS_PS + 9] = -1
            row[x * NO_VARS_PS - 7] = -(K2 / C_BOILER2) / (temp**2)
            A_ub.append(row)
            b_ub.append(-(K2 / C_BOILER2) * (2 / temp))

        # Grid inequality constraints
        sell_index = energy_sell_price_df.index[energy_sell_price_df.index == current_time][
            0]  # dataframe.index returns a list
        buy_index = energy_buy_price_df.index[energy_buy_price_df.index == current_time][
            0]  # df.index returns a list
        current_sell_price = energy_sell_price_df.loc[sell_index]  # per unit energy price
        current_buy_price = energy_buy_price_df.loc[buy_index]  # per unit (kWh) energy price

        row = [0] * no_ctrl_vars
        row[x * NO_VARS_PS] = -1
        row[x * NO_VARS_PS + 1] = current_buy_price[0] / (
                (60 / CONTROL_TIMESTEP) * 1000)  # converting it to price per watt-INTERVALminutes
        A_ub.append(row)
        b_ub.append(0)

        row = [0] * no_ctrl_vars
        row[x * NO_VARS_PS] = -1
        row[x * NO_VARS_PS + 1] = current_sell_price[0] / (
                (60 / CONTROL_TIMESTEP) * 1000)  # converting it to price per watt-second
        A_ub.append(row)
        b_ub.append(0)
        current_time = current_time + timedelta(minutes=CONTROL_TIMESTEP)
        indices.append(current_time)

    bounds = tuple(bounds)

    res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds,
                  options={"disp": False, "maxiter": 50000, 'tol': 1e-6})
    x = 0
    outputs = {1: res.x[2], 2: res.x[3], 'bat': res.x[6]}   # outputs = {1: pb1[0], 2: pb2[0]], 'bat': p_bat[0]}

    return outputs







