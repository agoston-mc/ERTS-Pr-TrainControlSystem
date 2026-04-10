# ERTS-Pr-TrainControlSystem

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





---------
#####
Project for Embedded and Real Time Systems - ELTE
* Márton Homoki
* Ágoston Czobor







