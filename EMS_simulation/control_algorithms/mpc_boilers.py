#!/usr/bin/env python3
import pandas as pd
from datetime import timedelta
from datetime import datetime
from scipy.optimize import linprog
import numpy as np



# define constants
#TIME_SLOT = 10  # in minutes
TIME_SLOT = 5  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours
# HORIZON = 720  # for testing purposes
#HORIZON = 20  # for testing purposes

#no_slots = int(HORIZON / TIME_SLOT)
no_slots = int(0.5*HORIZON / TIME_SLOT)

MPC_START_TIME = '05.01.2018 00:00:00'  # pandas format mm.dd.yyyy hh:mm:ss

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius
Tb1_range = range(BOILER1_TEMP_MIN, BOILER1_TEMP_MAX+1, 2)

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius
Tb2_range = range(BOILER2_TEMP_MIN, BOILER2_TEMP_MAX+1, 6)



BOILER1_TEMP_INCOMING_WATER = 20  # in degree celsius
BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

d_WATER = 997       # in [g/L]
C_WATER = 4.186     # in [W*s/k*K]

C_BOILER1 =  (C_WATER * d_WATER * BOILER1_VOLUME)    # in [(Watt*sec)/K]
C_BOILER2 =  (C_WATER * d_WATER * BOILER2_VOLUME)    # in [(Watt*sec)/K]

def get_hot_water_usage():

    measured = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx',
                             index_col=[0],
                             usecols=[0, 2])

    actual = measured['Actual'].to_numpy() / (10 / TIME_SLOT) / 2
    actual = np.repeat(actual, int(10 / TIME_SLOT))

    return actual.tolist()

def get_energy_hot_water_usage_simu():
    litres_forecast = pd.read_excel('data_input/hot_water_consumption_artificial_profile_10min_granularity.xlsx',
                                    index_col=[0],
                                    usecols=[0, 1])
    litres_forecast = litres_forecast['Hot water usage (litres)'].to_numpy() / (
            10 / TIME_SLOT) / 2  # data is in [litres/CONTROL_TIMESTEP]    # divided by 2 cause 2 boilers
    litres_forecast = np.repeat(litres_forecast, int(10 / TIME_SLOT))
    # Energy/TIMESLOT : [L * g/L * W*s/(g*K) * K]  # forecast is created considering volume forecast and T=40 degrees
    energy_forecast = litres_forecast * d_WATER * C_WATER * 40
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(TIME_SLOT) + 'min')
    energy_forecast_df = pd.DataFrame(energy_forecast, index=dates)
    #litres_forecast_df = pd.DataFrame(litres_forecast, index=dates)

    return energy_forecast_df


def get_excess_power_forecast(iteration):
    df = pd.read_excel('data_input/Energie - 00003 - Pache.xlsx', index_col=[0], usecols=[0, 1])

    start_index = df.index[df.index == (MPC_START_TIME)][0]  # df.index returns a list
    start_index += timedelta(minutes=iteration * TIME_SLOT)
    end_index = start_index + timedelta(minutes=HORIZON - TIME_SLOT)
    df = df.loc[start_index:end_index] * (
        -6000)  # Convert the energy (kWh) to power (W) and power convention (buy positive and sell negative)
    '''prod = df['Profil production (kWh)'].to_numpy()


    #plt.axes(xticks=[0,4,8,12,16,20,24])
    #plt.axes(xticklabels=[0, 1,2,3,4,8,12,16,20,24])
    plt.axes(xticklabels=[0, 0, 3, 6, 9, 12, 15, 18, 21, 24])
    plt.plot(range(len(prod)), prod, color='orange')
    plt.plot(range(len(prod+2)), [0 for i in range(len(prod+2))], color='orange')

    plt.xlabel('Time')
    plt.ylabel('Power [W]')
    plt.show()'''
    excess = df['Flux energie au point d\'injection (kWh)'].to_numpy()
    excess = np.repeat(excess, int(10 / TIME_SLOT))
    dates = pd.date_range(start=start_index, end=end_index, freq=str(TIME_SLOT) + 'min')
    df = pd.DataFrame(excess, index=dates)

    return df

def get_energy_sell_price():
    df = pd.read_excel('data_input/energy_sell_price_10min_granularity.xlsx', index_col=[0],
                       usecols=[0, 1]).to_numpy()
    df = np.repeat(df, int(10 / TIME_SLOT))
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(TIME_SLOT) + 'min')
    df = pd.DataFrame(df, index=dates)
    return df

def get_energy_buy_price():
    df = pd.read_excel('data_input/energy_buy_price_10min_granularity.xlsx', index_col=[0],
                       usecols=[0, 1]).to_numpy()
    df = np.repeat(df, int(10 / TIME_SLOT))
    dates = pd.date_range(start=MPC_START_TIME, end='05.05.2018 23:55:00', freq=str(TIME_SLOT) + 'min')
    df = pd.DataFrame(df, index=dates)
    return df

def mpc_iteration(p_x, energy_hot_water, T_B1_init, T_B2_init, iteration):

    # 1. Get excess solar power forecasts
    excess_power_forecast_df = get_excess_power_forecast(iteration)

    # 2. Get hot water consumption volume forecast
    energy_hot_water_forecast_df = get_energy_hot_water_usage_simu()

    # Get energy sell price
    energy_sell_price_df = get_energy_sell_price()
    # Get energy buy price
    energy_buy_price_df = get_energy_buy_price()

    ############ Set up the optimisation problem

    current_time = datetime.strptime(MPC_START_TIME, "%m.%d.%Y %H:%M:%S") + timedelta(minutes=iteration * TIME_SLOT)
    print(current_time)

    indices = []
    indices.append(current_time)

    NO_CTRL_VARS_PS = 10  # control (decision) variables # variables: Phi, Pg, Pb1, Pb2, Tb1, Tb2,  alpha1, alpha2, epsilon1, epsilon2  at each time slot
    no_ctrl_vars = NO_CTRL_VARS_PS * no_slots
    c = []
    bounds = []
    A_eq = []
    b_eq = []
    A_ub = []
    b_ub = []

    for x in range(no_slots):
        # 1. Setup the objective function
        c.append(1)  # variables: Phi, Pg, Pb1, Pb2, Tb1, Tb2,  alpha1, alpha2, epsilon1, epsilon2
        c.extend([0, 0, 0, 0, 0, 0, 0, 0.2, 0.2])   # lower weights on epsilon so that the maximisation of temperatures does not overtake the minimization of cost

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
        bounds_one_slot = [phi_bounds, psg_bounds, pb1_bounds, pb2_bounds, tb1_bounds, tb2_bounds, alpha1_bounds, alpha2_bounds, epsilon1_bounds, epsilon2_bounds]
        bounds.extend(bounds_one_slot)

        # 3. Setup equality constraints
        excess_power_forecast_index = \
        excess_power_forecast_df.index[excess_power_forecast_df.index == current_time][
            0]  # df.index returns a list
        excess_power_forecast = excess_power_forecast_df.loc[excess_power_forecast_index]

        # power balance constraint
        if x == 0:  # the measured excess power is considered
            row = [0] * no_ctrl_vars  # variables: (0)Phi, (1)Pg, (2)Pb1, (3)Pb2, (4)Tb1, (5)Tb2,  (6)alpha1, (7)alpha2, (8)epsilon1, (9)epsilon2

            row[x * NO_CTRL_VARS_PS + 1] = 1
            row[x * NO_CTRL_VARS_PS + 2] = 1
            row[x * NO_CTRL_VARS_PS + 3] = 1
            A_eq.append(row)
            b_eq.append(-p_x)
        else:  # the forecasted excess is considered
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 1] = 1
            row[x * NO_CTRL_VARS_PS + 2] = 1
            row[x * NO_CTRL_VARS_PS + 3] = 1
            A_eq.append(row)
            b_eq.append(-excess_power_forecast[0])

        # Boiler models constraints
        energy_water_forecast_index = \
            energy_hot_water_forecast_df.index[energy_hot_water_forecast_df.index == current_time][
                0]  # df.index returns a list
        energy_hot_water_forecast = energy_hot_water_forecast_df.loc[energy_water_forecast_index]
        # 1. alhpa constraints
        if x == 0:
            # variables: (0)Phi, (1)Pg, (2)Pb1, (3)Pb2, (4)Tb1, (5)Tb2,  (6)alpha1, (7)alpha2, (8)epsilon1, (9)epsilon2
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 6] = 1
            row[x * NO_CTRL_VARS_PS + 2] = (TIME_SLOT * 60) / C_BOILER1
            A_eq.append(row)
            b_eq.append(T_B1_init - energy_hot_water/C_BOILER1)

            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 7] = 1
            row[x * NO_CTRL_VARS_PS + 3] = (TIME_SLOT * 60) / C_BOILER2
            A_eq.append(row)
            b_eq.append(T_B2_init - energy_hot_water/C_BOILER2)
        else:
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS - 6] = -1
            row[x * NO_CTRL_VARS_PS + 6] = 1
            row[x * NO_CTRL_VARS_PS + 2] = (TIME_SLOT * 60) / C_BOILER1
            A_eq.append(row)
            b_eq.append(-energy_hot_water_forecast[0]/C_BOILER1)

            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS - 5] = -1
            row[x * NO_CTRL_VARS_PS + 7] = 1
            row[x * NO_CTRL_VARS_PS + 3] = (TIME_SLOT * 60) / C_BOILER2
            A_eq.append(row)
            b_eq.append(-energy_hot_water_forecast[0]/C_BOILER2)

        # 2. Tb constraints
        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS + 4] = 1
        row[x * NO_CTRL_VARS_PS + 6] = -1
        row[x * NO_CTRL_VARS_PS + 8] = -1
        A_eq.append(row)
        b_eq.append(0)

        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS + 5] = 1
        row[x * NO_CTRL_VARS_PS + 7] = -1
        row[x * NO_CTRL_VARS_PS + 9] = -1
        A_eq.append(row)
        b_eq.append(0)


        # 3. Epsilon constraints
        '''# variables: (0)Phi, (1)Pg, (2)Pb1, (3)Pb2, (4)Tb1, (5)Tb2,  (6)alpha1, (7)alpha2, (8)epsilon1, (9)epsilon2
        if x==0:  # equality constraint
            K1 = energy_hot_water * BOILER1_TEMP_INCOMING_WATER
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 8] = 1
            A_eq.append(row)
            b_eq.append(-(K1 / C_BOILER1) / T_B1_init)

            K2 = energy_hot_water * BOILER2_TEMP_INCOMING_WATER
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 9] = 1
            A_eq.append(row)
            b_eq.append(-(K2 / C_BOILER2) / T_B2_init)'''


        #else: # inequality constraint
        # variables: (0)Phi, (1)Pg, (2)Pb1, (3)Pb2, (4)Tb1, (5)Tb2,  (6)alpha1, (7)alpha2, (8)epsilon1, (9)epsilon2
        K1 = energy_hot_water_forecast[0] * BOILER1_TEMP_INCOMING_WATER
        for temp in Tb1_range:
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 8] = -1
            row[x * NO_CTRL_VARS_PS - 6] = -(K1 / C_BOILER1) / (temp**2)
            A_ub.append(row)
            b_ub.append(-(K1 / C_BOILER1) * (2 / temp))

        K2 = energy_hot_water_forecast[0] * BOILER1_TEMP_INCOMING_WATER
        for temp in Tb2_range:
            row = [0] * no_ctrl_vars
            row[x * NO_CTRL_VARS_PS + 9] = -1
            row[x * NO_CTRL_VARS_PS - 5] = -(K2 / C_BOILER2) / (temp**2)
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
        row[x * NO_CTRL_VARS_PS] = -1
        row[x * NO_CTRL_VARS_PS + 1] = current_buy_price[0] / (
                (60 / TIME_SLOT) * 1000)  # converting it to price per watt-INTERVALminutes
        A_ub.append(row)
        b_ub.append(0)

        row = [0] * no_ctrl_vars
        row[x * NO_CTRL_VARS_PS] = -1
        row[x * NO_CTRL_VARS_PS + 1] = current_sell_price[0] / (
                (60 / TIME_SLOT) * 1000)  # converting it to price per watt-second
        A_ub.append(row)
        b_ub.append(0)
        current_time = current_time + timedelta(minutes=TIME_SLOT)
        indices.append(current_time)

    bounds = tuple(bounds)

    res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=bounds,
                  options={"disp": False, "maxiter": 50000, 'tol': 1e-6})

    x = 0
    print("tb1 =", res.x[4], 'tb2=', res.x[5])
    # print("pg =", res.x[1])
    # print("epsilon =", res.x[0])
    outputs = {1: res.x[2], 2: res.x[3]}
    print("p1, p2: ", outputs)

    return outputs
