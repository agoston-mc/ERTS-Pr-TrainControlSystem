#include <stdio.h>

struct DoorControl {
    // Timing
    uint16_t target_ms;      // Desired close time
    uint16_t elapsed_ms;     // Current progress
    
    bool is_obstructed;      // Detection flag
    
    // Recovery
    uint16_t resume_wait_ms; // Pause before retry
};


int main(int argc, char**argv){
	printf("Hello world");
	return 0;
}
