#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <sys/ipc.h>
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
#include <time.h>

#define SHM_NAME "/id"
#define SHM_SIZE sizeof(atomic_int)
#define QUEUE_KEY 0x12345
#define OPEN_INTERVAL_MS 3000
#define OBSTRUCT_PROBABILITY_PERCENT 30

struct message {
    long mtype;
    char text[128];
};

static void sleep_ms(unsigned ms) {
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000UL;
    nanosleep(&ts, NULL);
}

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;
    int shm_fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0666);
    if (shm_fd == -1) {
        perror("shm_open");
        return 1;
    }

    if (ftruncate(shm_fd, SHM_SIZE) == -1) {
        perror("ftruncate");
        close(shm_fd);
        return 1;
    }

    atomic_int *shared_count = mmap(NULL, SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
    if (shared_count == MAP_FAILED) {
        perror("mmap");
        close(shm_fd);
        return 1;
    }

    int id = atomic_fetch_add(shared_count, 1);
    int total_ids = atomic_load(shared_count);

    srand((unsigned)time(NULL) ^ getpid());

    int msqid = msgget((key_t)QUEUE_KEY, IPC_CREAT | 0666);
    if (msqid == -1) {
        perror("msgget");
        munmap(shared_count, SHM_SIZE);
        close(shm_fd);
        return 1;
    }

    printf("sensor id=%d total_ids=%d running open/obstruct sender\n", id, total_ids);

    while (true) {
        total_ids = atomic_load(shared_count);
        if (total_ids <= 0) {
            total_ids = 1;
        }

        int target_id = rand() % total_ids;
        struct message msg;
        msg.mtype = (long)(target_id + 1);
        snprintf(msg.text, sizeof(msg.text), "open");

        if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
            perror("msgsnd open");
        } else {
            printf("sent open to target_id=%d (mtype=%ld)\n", target_id, msg.mtype);
        }

        if ((rand() % 100) < OBSTRUCT_PROBABILITY_PERCENT) {
            struct message obst;
            obst.mtype = (long)(target_id + 1);
            snprintf(obst.text, sizeof(obst.text), "obstructed");
            if (msgsnd(msqid, &obst, strlen(obst.text) + 1, 0) == -1) {
                perror("msgsnd obstructed");
            } else {
                printf("sent obstructed to target_id=%d (mtype=%ld)\n", target_id, obst.mtype);
            }
        }

        sleep_ms(OPEN_INTERVAL_MS);
    }

    munmap(shared_count, SHM_SIZE);
    close(shm_fd);

    return 0;
}
