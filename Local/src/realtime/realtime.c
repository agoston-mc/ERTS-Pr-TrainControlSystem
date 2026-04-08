#include <stdio.h>
#include <sys/msg.h>
#include <stdint.h>
#include <stdbool.h>
#include <fcntl.h>           /* For O_* constants */
#include <unistd.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <stdatomic.h>
struct DoorControl {
    // Timing
    uint16_t target_ms;      // Desired close time
    uint16_t elapsed_ms;     // Current progress
    
    bool is_obstructed;      // Detection flag
    
    // Recovery
    uint16_t resume_wait_ms; // Pause before retry
};

int id;

int main(int argc, char**argv){
    
    char buffer[4];
    char dest[4];
    int shm_fd = shm_open("/id", O_CREAT | O_RDWR, 0777);
    
    if(ftruncate(shm_fd,4)==-1){
            printf("error ftruncate %s in line %d",strerror(errno),__LINE__);
            exit(-1);
    }
    void*d=mmap(dest,4,PROT_WRITE | PROT_READ,MAP_SHARED,shm_fd,0);
    id=atomic_fetch_add((int*)d,1);
    printf("%d \n",id);
    
    sleep(2);
	int msqid = 12345;
	struct message {
        long type;
        char text[20];
    } msg;

    long msgtyp = 0;
	
    msgrcv(msqid,(void *)&msg, sizeof(msg), msgtyp, 0);

	printf("Message : %s", msg.text);
    munmap(dest,sizeof(id));
    close(shm_fd);
    if(shm_unlink("id")==-1){
        if(errno == ENOENT )
            return 0;
        printf("error shm_unlink %s in line %d",strerror(errno),__LINE__);
        exit(-1);
    }

	return 0;
}
