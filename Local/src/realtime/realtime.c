#include <stdio.h>
#include <sys/msg.h>


struct DoorControl {
    // Timing
    uint16_t target_ms;      // Desired close time
    uint16_t elapsed_ms;     // Current progress
    
    bool is_obstructed;      // Detection flag
    
    // Recovery
    uint16_t resume_wait_ms; // Pause before retry
};


int main(int argc, char**argv){
	int msqid = 12345;
	struct message {
        long type;
        char text[20];
    } msg;

    long msgtyp = 0;
	
    ssize_t msgrcv(msqid, (void*)&msg, sizeof(msg), msgtyp, 0);
	
	printf("Message : %s", msg.text);
	return 0;
}
