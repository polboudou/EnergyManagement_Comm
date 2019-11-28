#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import timedelta
from datetime import datetime
from scipy.optimize import linprog
import random

# import scipy as scipy
# print (scipy.version.version)
# exit()

# # test a small OP
# c = [1, 2]
# # xbounds = (-1, 10)
# # ybounds = (-10, 3)
# xbounds = (-1, None)
# ybounds = (-10, 3)
# bounds = (xbounds, ybounds)
# A_ub = [[-4, -3], [1, 0]]
# b_ub = [30, 10]
# res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, options={"disp": True})
# print (res)
# exit()


# define constants
TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours
MPC_START_TIME = '05.01.2018 00:00:00'  # pandas format mm.dd.yyyy hh:mm:ss

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

BATTERY_SOC_MAX = 5000 * 60                 # in Watts min
BATTERY_SOC_MIN = 100 * 60                  # in Watts min
BATTERY_CHARGE_POWER_LIMIT = 5000           # in Watts
BATTERY_DISCHARGE_POWER_LIMIT = -5000       # in Watts

BATTERY_INITIAL_SOC = 200                   # in Watts


no_slots = int(HORIZON / TIME_SLOT)


def get_excess_power_forecast():
    df = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])
    df['excess_power (kW) (Psolar - Pload)'] = df[
                                                   'Flux energie au point d\'injection (kWh)'] * -6  # Convert the energy (kWh) to power (kW) and power convention (buy positive and sell negative)
    del df['Flux energie au point d\'injection (kWh)']  # we do not need the energy column anymore

    start_index = df.index[df.index == MPC_START_TIME][0]  # df.index returns a list
    end_index = start_index + timedelta(minutes=HORIZON - TIME_SLOT)
    excess_power_forecast_df = df.loc[start_index:end_index]
    excess_power_forecast_df.plot.line(y='excess_power (kW) (Psolar - Pload)')
    plt.savefig('data_output/figs_mpc_battery/power_profile_at_connection_point.pdf')
    return excess_power_forecast_df


def get_hot_water_usage_forecast():
    df = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx',
                       index_col=[0], usecols=[0, 1])
    df.plot.line(y='Hot water usage (litres)')
    plt.savefig('data_output/figs_mpc_battery/hot_water_usage_profile_24hrs.pdf')
    return df


def get_energy_sell_price():
    df = pd.read_excel('data_input/energy_sell_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1])
    df.plot.line(y='Sell Price (CHF / kWh)')
    plt.savefig('data_output/figs_mpc_battery/energy_sell_price_24hrs.pdf')
    return df


def get_energy_buy_price():
    df = pd.read_excel('data_input/energy_buy_price_10min_granularity.xlsx', index_col=[0], usecols=[0, 1])
    df.plot.line(y='Buy Price (CHF / kWh)')
    plt.savefig('data_output/figs_mpc_battery/energy_buy_price_24hrs.pdf')
    return df


def main():
    # Get disturbance forecasts
    # 1. Get excess solar power forecasts
    excess_power_forecast_df = get_excess_power_forecast()

    # 2. Get hot water consumption volume forecast
    hot_water_usage_forecast_df = get_hot_water_usage_forecast()

    # Get energy sell price
    energy_sell_price_df = get_energy_sell_price()
    # Get energy buy price
    energy_buy_price_df = get_energy_buy_price()

    concated_df = pd.concat(
        [excess_power_forecast_df, hot_water_usage_forecast_df, energy_sell_price_df, energy_buy_price_df], axis=1)
    # concated_df.plot.line(y=['power_pcc (kW) (+ import)', 'Hot water usage (litres)'], secondary_y=['Sell Price (CHF / kWh)', 'Buy Price (CHF / kWh)'])
    concated_df.plot.line(secondary_y=['Sell Price (CHF / kWh)', 'Buy Price (CHF / kWh)'])
    plt.savefig('data_output/figs_mpc_battery/disturbances_and_energy_prices.pdf')
    # plt.show()
    # exit()

    ############ Set up the optimisation problem
    current_time = datetime.strptime(MPC_START_TIME, "%m.%d.%Y %H:%M:%S")
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
        pb1_bounds = (0, BOILER1_RATED_P)
        pb2_bounds = (0, BOILER2_RATED_P)
        tb1_bounds = (BOILER1_TEMP_MIN, BOILER1_TEMP_MAX)
        tb2_bounds = (BOILER2_TEMP_MIN, BOILER2_TEMP_MAX)
        pbat_bounds = (BATTERY_DISCHARGE_POWER_LIMIT, BATTERY_CHARGE_POWER_LIMIT)
        ebat_bounds = (BATTERY_SOC_MIN, BATTERY_SOC_MAX)
        bounds_one_slot = [epsilon_bounds, psg_bounds, pb1_bounds, pb2_bounds, tb1_bounds, tb2_bounds, pbat_bounds, ebat_bounds]
        bounds.extend(bounds_one_slot)

        # 3. Setup equality constraints
        excess_power_forecast_index = excess_power_forecast_df.index[excess_power_forecast_df.index == current_time][
            0]  # df.index returns a list
        excess_power_forecast = excess_power_forecast_df.loc[excess_power_forecast_index]
        # excess_power_forecast[0] = 1 # for testing purposes
        # if random.uniform(0,1) <= 0.5:
        # 	excess_power_forecast[0] = -random.uniform(0,1) * 50000
        # else:
        # 	excess_power_forecast[0] = random.uniform(0,1) * 50000
        # print (excess_power_forecast[0])
        # power balance constraint
        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS + 1] = -1  # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
        row[x * NO_CTRL_VARS_PS + 2] = 1
        row[x * NO_CTRL_VARS_PS + 3] = 1
        row[x * NO_CTRL_VARS_PS + 6] = 1
        #print (row)
        A_eq.append(row)
        # print (A_eq)
        b_eq.append(excess_power_forecast[
                        0] * 1000)  # converting kW to Watts and excess power is defined as Psolar - Pload (both positive values)
        # print (b_eq)

        #######################     Battery model     ##########################
        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS + 7] = 1
        row[x * NO_CTRL_VARS_PS + 6] = -TIME_SLOT
        A_eq.append(row)
        if x == 0:
            b_eq.append(BATTERY_INITIAL_SOC)
        else:
            row[x * NO_CTRL_VARS_PS -1] = -1
            b_eq.append(0)
        ########################################################################

        # Boiler 1 and 2 are connected in series. The newV is the same for both boilers in this case.
        hot_water_usage_forecast_index = \
        hot_water_usage_forecast_df.index[hot_water_usage_forecast_df.index == current_time][
            0]  # df.index returns a list
        hot_water_usage_forecast = hot_water_usage_forecast_df.loc[hot_water_usage_forecast_index]
        # newV = 0 # for testing purposes
        # print (hot_water_usage_forecast[0])
        newV = hot_water_usage_forecast[0]
        Ab1 = 1 - newV / BOILER1_VOLUME
        Ab2 = 1 - newV / BOILER2_VOLUME
        Cb1 = newV / BOILER1_VOLUME
        Db2 = Cb1 * BOILER2_TEMP_INCOMING_WATER
        # the specific heat capacity of water (C) is 4.186 joule or watt-second per gram per degree celsius
        # the density of water is 997 grams / litre
        Bb1 = (TIME_SLOT * 60) / (4.186 * 997 * BOILER1_VOLUME)  # time slots are converted to seconds.
        Bb2 = (TIME_SLOT * 60) / (4.186 * 997 * BOILER2_VOLUME)  # time slots are converted to seconds.

        # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat for each time slot
        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS + 4] = 1
        row[x * NO_CTRL_VARS_PS + 2] = -Bb1

        if x == 0:
            # print (row)
            A_eq.append(row)
            # print (A_eq)
            b_eq.append(Ab1 * BOILER1_INITIAL_TEMP + Cb1 * BOILER2_INITIAL_TEMP)

            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 5] = 1
            row[x * NO_CTRL_VARS_PS + 3] = -Bb2
            print("PERONOOOOOOO ", -Bb2)
            # print (row)
            A_eq.append(row)
            # print (A_ub)
            b_eq.append(Ab2 * BOILER2_INITIAL_TEMP + Db2)
        else:  # variables are Epsilon, Pg, Pb1, Pb2, Tb1, Tb2, Pbat, Ebat
            row[x * NO_CTRL_VARS_PS - 4] = -Ab1
            row[x * NO_CTRL_VARS_PS - 3] = -Cb1
            A_eq.append(row)
            b_eq.append(0)

            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 5] = 1
            row[x * NO_CTRL_VARS_PS + 3] = -Bb2
            row[x * NO_CTRL_VARS_PS - 3] = -Ab2
            A_eq.append(row)
            b_eq.append(Db2)

        # 4. Setup inequality constraints
        sell_index = energy_sell_price_df.index[energy_sell_price_df.index == current_time][
            0]  # dataframe.index returns a list
        buy_index = energy_buy_price_df.index[energy_buy_price_df.index == current_time][0]  # df.index returns a list
        current_sell_price = energy_sell_price_df.loc[sell_index]  # per unit energy price
        current_buy_price = energy_buy_price_df.loc[buy_index]  # per unit (kWh) energy price
        # print (current_buy_price[0])
        # print (current_sell_price[0])
        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS] = -1
        row[x * NO_CTRL_VARS_PS + 1] = current_buy_price[0] / (6 * 1000)  # converting it to price per watt-10minutes
        A_ub.append(row)
        b_ub.append(0)

        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS] = -1
        row[x * NO_CTRL_VARS_PS + 1] = current_sell_price[0] / (6 * 1000)  # converting it to price per watt-second
        A_ub.append(row)
        b_ub.append(0)
        current_time = current_time + timedelta(minutes=TIME_SLOT)
        indices.append(current_time)


    # if x == 1:
    # 	print ("c is")
    # 	print (c)
    # 	print ("bounds are")
    # 	print (bounds)
    # 	print ("A_eq is")
    # 	print (A_eq)
    # 	print ("b_eq is")
    # 	print (b_eq)
    # 	exit()
    bounds = tuple(bounds)

    '''print ("c is")
    print (c)
    print ("bounds are")
    print (bounds)
    print ("A_eq is")
    print (A_eq)
    print ("b_eq is")
    print (b_eq)
    print ("A_ub is")
    print (A_ub)
    print ("b_ub is")
    print (b_ub)'''

    # res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='interior-point', options={"disp": True, "maxiter": 50000, 'tol': 1e-6})
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds,
                  options={"disp": True, "maxiter": 50000, 'tol': 1e-6})
    #print(res)

    power_pcc = []
    power_boiler1 = []
    power_boiler2 = []
    temp_boiler1 = []
    temp_boiler2 = []
    power_battery = []
    soc_battery = []

    # for the first time slot, the temperature values are the intial ones
    temp_boiler1.append(BOILER1_INITIAL_TEMP)
    temp_boiler2.append(BOILER2_INITIAL_TEMP)
    soc_battery.append(BATTERY_INITIAL_SOC / (60*1000)) #converting (Watts min) to kWh)

    for x in range(no_slots):
        power_pcc.append(res.x[x * NO_CTRL_VARS_PS + 1])
        power_boiler1.append(res.x[x * NO_CTRL_VARS_PS + 2])
        power_boiler2.append(res.x[x * NO_CTRL_VARS_PS + 3])
        temp_boiler1.append(res.x[x * NO_CTRL_VARS_PS + 4])
        temp_boiler2.append(res.x[x * NO_CTRL_VARS_PS + 5])
        power_battery.append(res.x[x * NO_CTRL_VARS_PS + 6])
        soc_battery.append(res.x[x * NO_CTRL_VARS_PS + 7] / (60*1000)) #converting (Watts min) to kWh

    # for the last time slot, we do not have these values
    power_pcc.append(None)
    power_boiler1.append(None)
    power_boiler2.append(None)
    power_battery.append(None)


    results = {'power_pcc (Watts) (+ import)': power_pcc, 'power_boiler1 (Watts)': power_boiler1,
               'power_boiler2 (Watts)': power_boiler2, 'power_battery (Watts)': power_battery, 'temp_boiler1 (°C)': temp_boiler1,
               'temp_boiler2 (°C)': temp_boiler2}
    results_df = pd.DataFrame(data=results, index=indices)
    soc_result_df = pd.DataFrame(data=soc_battery, index=indices, columns =['soc_battery (kWh)'])

    fig, axes = plt.subplots(2, 1)
    results_df.plot.line(secondary_y=['temp_boiler1 (°C)', 'temp_boiler2 (°C)'], ax=axes[0], figsize=(10,15))
    soc_result_df.plot.line(ax=axes[1])
    energy_buy_price_df.plot.line(ax=axes[1], secondary_y=True)
    plt.savefig('data_output/figs_mpc_battery/results_mpc_battery.pdf')

# plt.show()


if __name__ == "__main__":
    main()



