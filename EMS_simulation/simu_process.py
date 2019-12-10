
import subprocess
import sys

# define constants
HORIZON = 1440  # in minutes, corresponds to 24 hours
#HORIZON = 60  # for testing purposes
MPC_START_TIME = '05.01.2018 00:00:00'  # pandas format mm.dd.yyyy hh:mm:ss
SIMU_TIMESTEP = 1
CONTROL_TIMESTEP = 10    # in minutes

scenario = 'Scenario3'

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = -7600  # in Watts
BOILER2_RATED_P = -7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

#BOILER1_INITIAL_TEMP = 45  # in degree celsius
#BOILER2_INITIAL_TEMP = 45  # in degree celsius

BOILER1_INITIAL_TEMP = 45  # in degree celsius
BOILER2_INITIAL_TEMP = 45  # in degree celsius

BATTERY_SOC_MAX = 5000 * 60                 # in Watts min
BATTERY_SOC_MIN = 100 * 60                  # in Watts min
BATTERY_CHARGE_POWER_LIMIT = 5000           # in Watts
BATTERY_DISCHARGE_POWER_LIMIT = -5000       # in Watts

BATTERY_INITIAL_SOC = 200                   # in Watts


no_slots = int(HORIZON / SIMU_TIMESTEP)

if __name__ == '__main__':

    print('Starting simulation!')
    subprocess.run("python3 boiler1_model.py & python3 boiler2_model.py & python3 battery_model.py & python3 controller.py", shell=True)



