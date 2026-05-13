# ERTS-Pr-TrainControlSystem

SETUP INSTRUCTIONS AT THE BOTTOM

The setup is that a trains run freely on set tracks. 
They stop at stations only if there is someone at the station, detected by a camera on board, or if there was anyone pressing the stop request button beforehand. 
Before departure the doors close, and if anyone gets stuck there, it gets interrupted, delaying the train. 

A database collects all information about the trains, possibly adjusting the schedule.


## Local setup

Data collection between a controller and multiple RT devices (doors) is handled with an MQTT broker. 

Additional data (button, camera) is handled in the main process
<!-- TODO: mqtt for these as well? -->

Then the decision is made on board about the stop. 


All data is then pushed to the global server

### movement

Trains while moving to 1/100th of the track they are on every tick, unless they are stopped.
A stop is `20` ticks, with possible delay of ????


## Server setup

Listens to data from all clients (train), aggregates is, and visualizes the system information. 


## Database structure

### Entries

```
/tracks/{track_id}/
  route               [str]   — list of station ID's for the given route
  trains/{train_id}/
    stop_requested    bool    — someone pressed the button
    camera_detected   bool    — onboard camera sees a person at next station
    current_delay     int     — relative seconds offset from schedule (+/-)
    progress_on_track float   — 0.0–1.0 along current track segment
    current_status    str     — "stopped", "moving"
    next_station      str     — next station station_id 
  stations/{station_id}/
    total_delay_sum   int     — Σ delay seconds from trains that stopped here
    stop_count        int     — total train stops
    no_stop_count     int     — total pass-throughs (no stop needed)
```

## Setup for running the app

Generate firebase token for the databse to be used:
1. go to Firebase Console -> Project to use
2. go to Project Settings -> Service accounts
3. Generate new key and download the .json file

Set the .env variables:
```
FIREBASE_SERVICE_ACCOUNT=<.json token>
FIREBASE_URL=<database url>
```

These two files should be in project root

Python package management is handled via astral UV
(To run the GUI app you need to either run from linux, or comment out Local from the project root level pyproject.toml, from the workspace members)

launching is done via `uv run`
```shell
# to run the trains - raspberry local code
uv run --package local local <options>

# to run the GUI - server code
uv run --package server server
```




---------
#####
Project for Embedded and Real Time Systems - ELTE
* Márton Homoki
* Ágoston Czobor







