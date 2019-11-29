
from EMS_simulation import boiler1_model
from EMS_simulation import controller

import subprocess

# define constants
TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius

BOILER1_RATED_P = 7600  # in Watts
BOILER2_RATED_P = 7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BOILER1_INITIAL_TEMP = 45  # in degree celsius
BOILER2_INITIAL_TEMP = 45  # in degree celsius

BATTERY_SOC_MAX = 5000 * 60                 # in Watts min
BATTERY_SOC_MIN = 100 * 60                  # in Watts min
BATTERY_CHARGE_POWER_LIMIT = 5000           # in Watts
BATTERY_DISCHARGE_POWER_LIMIT = -5000       # in Watts

BATTERY_INITIAL_SOC = 200                   # in Watts


no_slots = int(HORIZON / TIME_SLOT)

if __name__ == '__main__':

    print('Starting simulation!')
    subprocess.run("python3 boiler1_model.py & python3 boiler2_model.py & python3 controller.py", shell=True)
    #subprocess.run("python3 boiler1_model.py & python3 controller.py", shell=True)



