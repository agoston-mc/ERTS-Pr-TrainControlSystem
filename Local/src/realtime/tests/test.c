#include <sys/ipc.h>
#include <sys/msg.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>

#define QUEUE_KEY 0x12345

struct message {
    long mtype;
    char text[128];
};

int main() {
    int msqid = msgget((key_t)QUEUE_KEY, 0666);
    if (msqid == -1) {
        perror("msgget");
        return 1;
    }

    struct message msg;
    msg.mtype = 1;  // Assuming id=0, type=1

    // Test 1: Open for 1000 ms
    strcpy(msg.text, "open 1000");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd open");
        return 1;
    }
    printf("Sent: open 1000\n");

    sleep(2);  // Wait for it to close

    // Check status
    strcpy(msg.text, "status");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd status");
        return 1;
    }
    printf("Sent: status\n");

    sleep(1);

    // Test 2: Open for 2000 ms, then obstruct after 1 second
    strcpy(msg.text, "open 2000");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd open 2000");
        return 1;
    }
    printf("Sent: open 2000\n");

    sleep(1);  // Wait 1 second

    strcpy(msg.text, "obstructed");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd obstructed");
        return 1;
    }
    printf("Sent: obstructed\n");

    sleep(3);  // Wait for resume (2000ms) + some time

    // Check status
    strcpy(msg.text, "status");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd status");
        return 1;
    }
    printf("Sent: status\n");

    sleep(1);

    // Test 3: Close command
    strcpy(msg.text, "open 3000");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd open 3000");
        return 1;
    }
    printf("Sent: open 3000\n");

    sleep(1);

    strcpy(msg.text, "close");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd close");
        return 1;
    }
    printf("Sent: close\n");

    sleep(1);

    // Final status
    strcpy(msg.text, "status");
    if (msgsnd(msqid, &msg, strlen(msg.text) + 1, 0) == -1) {
        perror("msgsnd status");
        return 1;
    }
    printf("Sent: status\n");

    return 0;
}