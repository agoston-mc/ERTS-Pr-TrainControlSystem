#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
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
#include <ctype.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SOCKET_PATH "/tmp/comms.sock" //path for UNIX domain socket
#define SHM_NAME "/id"
#define SHM_SIZE sizeof(struct shmared_count)
#define QUEUE_KEY 0x12345
#define DEFAULT_CLOSE_MS 5000
#define RESUME_WAIT_MS 2000
#define POLL_INTERVAL_MS 100

struct shmared_count {
    atomic_int count;
    atomic_uint_fast32_t flag;
};

struct DoorControl {
    uint16_t target_ms;      // Desired close time
    uint16_t elapsed_ms;     // Current progress
    bool is_obstructed;      // Detection flag
    uint16_t resume_wait_ms; // Pause before retry
    bool is_open;
};

struct message {
    long mtype;
    char text[128];
};

static void trim_newline(char *text) {
    size_t len = strlen(text);
    if (len == 0) return;
    if (text[len - 1] == '\n' || text[len - 1] == '\r')
        text[len - 1] = '\0';
}

static bool starts_with(const char *text, const char *prefix) {
    return strncmp(text, prefix, strlen(prefix)) == 0;
}

static unsigned parse_uint(const char *text) {
    while (isspace((unsigned char)*text)) text++;
    return (unsigned)strtoul(text, NULL, 10);
}

static void print_status(const struct DoorControl *door) {
    printf("door status: %s, elapsed=%u/%u ms, obstructed=%s, resume_wait=%u ms\n",
           door->is_open ? "opening" : "closed",
           door->elapsed_ms,
           door->target_ms,
           door->is_obstructed ? "yes" : "no",
           door->resume_wait_ms);
}

static void process_open(struct DoorControl *door, const char *arg) {
    unsigned close_ms = DEFAULT_CLOSE_MS;
    if (arg && *arg) {
        close_ms = parse_uint(arg);
        if (close_ms == 0) {
            close_ms = DEFAULT_CLOSE_MS;
        }
    }
    door->target_ms = (uint16_t)close_ms;
    door->elapsed_ms = 0;
    door->is_open = true;
    door->is_obstructed = false;
    printf("received open command, will close after %u ms\n", close_ms);
}

static void process_close(struct DoorControl *door) {
    if (door->is_open) {
        door->is_open = false;
        door->elapsed_ms = 0;
        door->target_ms = 0;
        printf("received close command, door is closing now\n");
    } else {
        printf("received close command, door already closed\n");
    }
}

static void process_obstructed(struct DoorControl *door) {
    if (!door->is_open) {
        printf("received obstructed event, but door is not open\n");
        return;
    }
    door->is_obstructed = true;
    printf("received obstructed event, pausing door movement\n");
}

static void process_resume_wait(struct DoorControl *door, const char *arg) {
    unsigned wait_ms = parse_uint(arg);
    if (wait_ms == 0) {
        wait_ms = RESUME_WAIT_MS;
    }
    door->resume_wait_ms = (uint16_t)wait_ms;
    printf("resume wait set to %u ms\n", wait_ms);
}

static void sleep_ms(unsigned ms) {
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000UL;
    nanosleep(&ts, NULL);
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;

    // 2. Create the socket
    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock == -1) {
        perror("socket error");
        exit(1);
    }

    // 3. Define the address (the .sock file)
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(struct sockaddr_un));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);

    // 4. Connect to the Python server
    if (connect(sock, (struct sockaddr *)&addr, sizeof(struct sockaddr_un)) == -1) {
        perror("connect error - is the Python server running?");
        close(sock);
        exit(1);
    }




    int shm_fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0666);
    if (shm_fd == -1) {
        perror("shm_open");
        return 1;
    }

    if (ftruncate(shm_fd, sizeof(struct shmared_count)) == -1) {
        perror("ftruncate");
        close(shm_fd);
        return 1;
    }

    struct shmared_count *shared_count = mmap(NULL,  sizeof(struct shmared_count), PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
    if (shared_count == MAP_FAILED) {
        perror("mmap");
        close(shm_fd);
        return 1;
    }

    int id = atomic_fetch_add(&shared_count->count, 1);
    int total_ids = atomic_load(&shared_count->count);

    int msqid = msgget((key_t)QUEUE_KEY, IPC_CREAT | 0666);
    if (msqid == -1) {
        perror("msgget");
        munmap(shared_count, sizeof(struct shmared_count));
        close(shm_fd);
        return 1;
    }

    printf("realtime id=%d total_ids=%d listening on type=%d\n", id, total_ids, id + 1);

    struct DoorControl door = {
        .target_ms = 0,
        .elapsed_ms = 0,
        .is_obstructed = false,
        .resume_wait_ms = RESUME_WAIT_MS,
        .is_open = false,
    };

    while (true) {
        struct message msg;
        char message[64];
        ssize_t received = msgrcv(msqid, &msg, sizeof(msg.text), (long)(id + 1), IPC_NOWAIT);
        if (received >= 0) {
            msg.text[received] = '\0';
            trim_newline(msg.text);
            printf("received message: '%s'\n", msg.text);

            if (starts_with(msg.text, "open")) {
                atomic_fetch_or(&shared_count->flag, (atomic_uint_fast32_t)1u << id);
                const char *arg = msg.text + strlen("open");
                process_open(&door, arg);
                snprintf(message, sizeof(message), "%d:OPEN\n",id);
                if (send(sock, message, strlen(message), 0) == -1) {
                    perror("send error");
                }
            } else if (starts_with(msg.text, "close")) {
                process_close(&door);
                atomic_fetch_and(&shared_count->flag, ~((atomic_uint_fast32_t)1u << id));
            } else if (starts_with(msg.text, "obstructed")) {
                snprintf(message, sizeof(message), "%d:OBSTRUCTED\n",id);
                if (send(sock, message, strlen(message), 0) == -1) {
                    perror("send error");
                }
                process_obstructed(&door);
            } else if (starts_with(msg.text, "resume_wait")) {
                snprintf(message, sizeof(message), "%d:RESUME_WAIT\n",id);
                if (send(sock, message, strlen(message), 0) == -1) {
                    perror("send error");
                }
                const char *arg = msg.text + strlen("resume_wait");
                process_resume_wait(&door, arg);
            } else if (starts_with(msg.text, "status")) {
                snprintf(message, sizeof(message), "%d:STATUS\n",id);
                if (send(sock, message, strlen(message), 0) == -1) {
                    perror("send error");
                }

                print_status(&door);
            } else {
                snprintf(message, sizeof(message), "%d:UNKNOWN_COMMAND\n",id);
                if (send(sock, message, strlen(message), 0) == -1) {
                    perror("send error");
                }
                printf("unknown command: '%s'\n", msg.text);
            }
        } else if (errno != ENOMSG) {
            perror("msgrcv");
        }

        if (door.is_obstructed) {
            sleep_ms(door.resume_wait_ms);
            door.is_obstructed = false;
            printf("resume wait complete, continuing door action\n %d",id);
        }

        if (door.is_open) {
            if (door.elapsed_ms < door.target_ms) {
                sleep_ms(POLL_INTERVAL_MS);
                door.elapsed_ms += POLL_INTERVAL_MS;
                if (door.elapsed_ms >= door.target_ms) {
                    door.elapsed_ms = door.target_ms;
                    door.is_open = false;
                    atomic_fetch_and(&shared_count->flag, ~((atomic_uint_fast32_t)1u << id));
                    snprintf(message, sizeof(message), "%d:CLOSED\n",id);

                    if (send(sock, message, strlen(message), 0) == -1) {
                        printf("door has reached target close time and is now closed, but failed to send status update\n");
                        perror("send error");
                    }
                    printf("door has reached target close time and is now closed\n %d",id);
                }
            }
        } else {
            usleep(POLL_INTERVAL_MS * 1000);
        }
    }
    close(sock);
    munmap(shared_count, SHM_SIZE);
    close(shm_fd);
    return 0;
}
