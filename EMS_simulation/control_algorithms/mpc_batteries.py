

import pandas as pd
from datetime import timedelta
from datetime import datetime
from scipy.optimize import linprog
import numpy as np



# define constants
TIME_SLOT = 10  # in minutes
TIME_SLOT = 5  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours
# HORIZON = 720  # for testing purposes
#HORIZON = 20  # for testing purposes

no_slots = int(HORIZON / TIME_SLOT)
no_slots = int(0.5*HORIZON / TIME_SLOT)

MPC_START_TIME = '05.01.2018 00:00:00'  # pandas format mm.dd.yyyy hh:mm:ss

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER1_TEMP_INCOMING_WATER = 20  # in degree celsius
BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BATTERY_SOC_MAX = 5000                 # in Watts h
BATTERY_SOC_MIN = 200                  # in Watts h
BATTERY_CHARGE_POWER_LIMIT = -5000           # in Watts
BATTERY_DISCHARGE_POWER_LIMIT = 5000       # in Watts


def get_hot_water_usage_forecast():
	df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx', index_col=[0], usecols=[0,1])
	hot_water_usage = df['Hot water usage (litres)'].to_numpy() / (10/TIME_SLOT)  /2# data is in [litres*10min]    # divided by 2 for [litres*5min]

	hot_water_usage = np.repeat(hot_water_usage, int(10/TIME_SLOT))
	dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(TIME_SLOT)+'min')
	df = pd.DataFrame(hot_water_usage, index=dates)
	return df

def get_excess_power_forecast(iteration):
	df = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0,1])

	start_index = df.index[df.index == (MPC_START_TIME)][0] # df.index returns a list
	start_index += timedelta(minutes=iteration*TIME_SLOT)
	end_index = start_index + timedelta(minutes = HORIZON - TIME_SLOT)
	df = df.loc[start_index:end_index] * (-6000) # Convert the energy (kWh) to power (W) and power convention (buy positive and sell negative)
	excess = df['Flux energie au point d\'injection (kWh)'].to_numpy()
	excess = np.repeat(excess, int(10/TIME_SLOT))
	dates = pd.date_range(start=start_index, end=end_index, freq=str(TIME_SLOT) + 'min')
	df = pd.DataFrame(excess, index=dates)

	return df

def get_energy_sell_price():
	df = pd.read_excel('data_input/energy_sell_price_10min_granularity.xlsx', index_col=[0], usecols=[0,1]).to_numpy()
	df = np.repeat(df, int(10 / TIME_SLOT))
	dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(TIME_SLOT) + 'min')
	df = pd.DataFrame(df, index=dates)
	return df


def get_energy_buy_price():
    df = pd.read_excel('data_input/energy_buy_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1]).to_numpy()
    df = np.repeat(df, int(10 / TIME_SLOT))
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(TIME_SLOT) + 'min')
    df = pd.DataFrame(df, index=dates)
    return df


def mpc_iteration(p_x, hot_water, T_B1_init, T_B2_init, soc_bat_init, iteration):
    # Get disturbance forecasts
    # 1. Get excess solar power forecasts
    excess_power_forecast_df = get_excess_power_forecast(iteration)

    # 2. Get hot water consumption volume forecast
    hot_water_usage_forecast_df = get_hot_water_usage_forecast()

    # Get energy sell price
    energy_sell_price_df = get_energy_sell_price()
    # Get energy buy price
    energy_buy_price_df = get_energy_buy_price()

    ############ Set up the optimisation problem

    current_time = datetime.strptime(MPC_START_TIME, "%m.%d.%Y %H:%M:%S") + timedelta(minutes=iteration * TIME_SLOT)
    print(current_time)
    indices = []
    indices.append(current_time)

    NO_CTRL_VARS_PS = 8  # control (decision) variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
    no_ctrl_vars = NO_CTRL_VARS_PS * no_slots
    c = []
    bounds = []  # before passing to the OP, we'll convert it to a tuple (currently list because of frequent append operations)
    A_eq = []
    b_eq = []
    A_ub = []
    b_ub = []


    for x in range(no_slots):
        # 1. Setup the objective function
        c.append(1)  # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
        c.extend([0, 0, 0, 0, 0, 0, 0])
        # print (c)

        # 2. Setup the bounds for the control variables
        epsilon_bounds = (None, None)
        psg_bounds = (None, None)
        pb1_bounds = (BOILER1_RATED_P, 0)
        pb2_bounds = (BOILER2_RATED_P, 0)
        tb1_bounds = (BOILER1_TEMP_MIN, BOILER1_TEMP_MAX)
        tb2_bounds = (BOILER2_TEMP_MIN, BOILER2_TEMP_MAX)
        pbat_bounds = (BATTERY_CHARGE_POWER_LIMIT, BATTERY_DISCHARGE_POWER_LIMIT)
        ebat_bounds = (BATTERY_SOC_MIN, BATTERY_SOC_MAX)
        bounds_one_slot = [epsilon_bounds, psg_bounds, pb1_bounds, pb2_bounds, tb1_bounds, tb2_bounds, pbat_bounds, ebat_bounds]
        bounds.extend(bounds_one_slot)

        # 3. Setup equality constraints
        excess_power_forecast_index = excess_power_forecast_df.index[excess_power_forecast_df.index == current_time][
            0]  # df.index returns a list
        excess_power_forecast = excess_power_forecast_df.loc[excess_power_forecast_index]
        if x == 0:
            # power balance constraint
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 1] = 1  # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
            row[x * NO_CTRL_VARS_PS + 2] = 1
            row[x * NO_CTRL_VARS_PS + 3] = 1
            row[x * NO_CTRL_VARS_PS + 6] = 1
            A_eq.append(row)
            b_eq.append(-p_x)   # we use the measurement for t=0, else the forecast.
        else:
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 1] = 1  # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
            row[x * NO_CTRL_VARS_PS + 2] = 1
            row[x * NO_CTRL_VARS_PS + 3] = 1
            row[x * NO_CTRL_VARS_PS + 6] = 1
            A_eq.append(row)
            b_eq.append(-excess_power_forecast[0])


        # Battery model constraints
        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS + 7] = 1
        row[x * NO_CTRL_VARS_PS + 6] = TIME_SLOT/60
        A_eq.append(row)
        if x == 0:
            b_eq.append(soc_bat_init)
        else:
            row[x * NO_CTRL_VARS_PS -1] = -1
            b_eq.append(0)

        # Boiler model constraints
        hot_water_usage_forecast_index = \
        hot_water_usage_forecast_df.index[hot_water_usage_forecast_df.index == current_time][
            0]  # df.index returns a list
        hot_water_usage_forecast = hot_water_usage_forecast_df.loc[hot_water_usage_forecast_index]
        if x == 0:
            newV = hot_water
        else:
            newV = hot_water_usage_forecast[0]
        Ab1 = 1 - newV / BOILER1_VOLUME
        Ab2 = 1 - newV / BOILER2_VOLUME
        Cb1 = newV / BOILER1_VOLUME
        Cb2 = newV / BOILER2_VOLUME
        # the specific heat capacity of water (C) is 4.186 joule or watt-second per gram per degree celsius
        # the density of water is 997 grams / litre
        Bb1 = (TIME_SLOT * 60) / (4.186 * 997 * BOILER1_VOLUME)  # time slots are converted to seconds.
        Bb2 = (TIME_SLOT * 60) / (4.186 * 997 * BOILER2_VOLUME)  # time slots are converted to seconds.
        # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
        if x == 0:
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 4] = 1
            row[x * NO_CTRL_VARS_PS + 2] = Bb1
            A_eq.append(row)
            b_eq.append(Ab1 * T_B1_init + Cb1 * BOILER1_TEMP_INCOMING_WATER)

            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 5] = 1
            row[x * NO_CTRL_VARS_PS + 3] = Bb2
            A_eq.append(row)
            b_eq.append(Ab2 * T_B2_init + Cb2 * BOILER2_TEMP_INCOMING_WATER)
        else:  # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 4] = 1
            row[x * NO_CTRL_VARS_PS + 2] = Bb1
            row[x * NO_CTRL_VARS_PS - 4] = -Ab1
            A_eq.append(row)
            b_eq.append(Cb1 * BOILER1_TEMP_INCOMING_WATER)

            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 5] = 1
            row[x * NO_CTRL_VARS_PS + 3] = Bb2
            row[x * NO_CTRL_VARS_PS - 3] = -Ab2
            A_eq.append(row)
            b_eq.append(Cb2 * BOILER2_TEMP_INCOMING_WATER)

        # 4. Setup inequality constraints
        sell_index = energy_sell_price_df.index[energy_sell_price_df.index == current_time][0] # dataframe.index returns a list
        buy_index = energy_buy_price_df.index[energy_buy_price_df.index == current_time][0] # df.index returns a list
        current_sell_price = energy_sell_price_df.loc[sell_index] # per unit energy price
        current_buy_price = energy_buy_price_df.loc[buy_index] # per unit (kWh) energy price

        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS] = -1
        row[x * NO_CTRL_VARS_PS + 1] = current_buy_price[0] / ((60/TIME_SLOT) * 1000) # converting it to price per watt-INTERVALminutes
        A_ub.append(row)
        b_ub.append(0)

        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS] = -1
        row[x * NO_CTRL_VARS_PS + 1] = current_sell_price[0] / ((60/TIME_SLOT) * 1000) # converting it to price per watt-second
        A_ub.append(row)
        b_ub.append(0)
        current_time = current_time + timedelta(minutes=TIME_SLOT)
        indices.append(current_time)

    bounds = tuple(bounds)

    res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds,
                  options={"disp": False, "maxiter": 50000, 'tol': 1e-6})
    #print(res)

    # outputs = {1: pb1[0], 2: pb2[0]], 'bat': p_bat}
    x = 0
    #print("tb1 =", res.x[4], 'tb2=', res.x[5])
    #print("pg =", res.x[1])
    #print("epsilon =", res.x[0])
    outputs = {1: res.x[2], 2: res.x[3], 'bat': res.x[6]}
    print("p1, p2, pbat ", outputs)

    return outputs







