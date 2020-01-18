#!/usr/bin/env python3

import subprocess

## =========================    SIMULATION PARAMETERS    =============================== ##
BATTERY = False
#BATTERY = True
## ===================================================================================== ##

if __name__ == '__main__':

    print('Starting simulation!')
    if BATTERY:
        subprocess.run("python3 controller.py & python3 boiler1_model.py & python3 boiler2_model.py "
                       "& python3 battery_model.py", shell=True)
    else:
        subprocess.run("python3 controller.py & python3 boiler1_model.py & python3 boiler2_model.py", shell=True)
