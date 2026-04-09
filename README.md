# ERTS-Pr-TrainControlSystem

The setup is that a trains run freely on set tracks. 
They stop at stations only if there is someone at the station, detected by a camera on board, or if there was anyone pressing the stop request button beforehand. 
Before departure the doors close, and if anyone gets stuck there, it gets interrupted, delaying the train. 

A database collects all information about the trains, possibly adjusting the schedule.


## Local setup


## Server setup


## Database structure

### Entries


tracks_{id}
    trains_{id}
        will_stop
        current_delay
        progress_on_track
    stations{id}
        sum delays



---------
#####
Project for Embedded and Real Time Systems
Márton Homoki
Ágoston Czobor







