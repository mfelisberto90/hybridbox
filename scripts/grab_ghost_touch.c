/*
 * Bloqueador Kernel evdev (EVIOCGRAB) para o digitizer físico quebrado
 * NVTCapacitiveTouchScreen (/dev/input/event2) no Xiaomi Redmi Note 8 Pro.
 *
 * 1. Abre /dev/input/event2 com O_RDWR (permitido para uid=2000 shell / gid=1004 input).
 * 2. Injeta eventos de liberação (ABS_MT_SLOT 0..9 -> ABS_MT_TRACKING_ID = -1, BTN_TOUCH = 0, SYN_REPORT)
 *    para limpar imediatamente quaisquer dedos fantasmas presos (TouchStatesByDisplay down=true)
 *    no InputReader/InputDispatcher do Android.
 * 3. Executa ioctl(fd, EVIOCGRAB, 1) para capturar exclusivamente /dev/input/event2 no kernel,
 *    impedindo que novos toques fantasmas de 60Hz cheguem ao Android TV, MIUI ou Termux:X11,
 *    enquanto preserva 100% de `input tap`, `input swipe`, `input keyevent`, Bluetooth e XTEST.
 */

#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static void emit_ev(int fd, unsigned short type, unsigned short code, int val) {
    struct input_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.type = type;
    ev.code = code;
    ev.value = val;
    (void)write(fd, &ev, sizeof(ev));
}

static void release_stuck_mt_slots(int fd) {
    for (int slot = 0; slot < 10; slot++) {
        emit_ev(fd, EV_ABS, ABS_MT_SLOT, slot);
        emit_ev(fd, EV_ABS, ABS_MT_TRACKING_ID, -1);
    }
    emit_ev(fd, EV_KEY, BTN_TOUCH, 0);
    emit_ev(fd, EV_KEY, BTN_TOOL_FINGER, 0);
    emit_ev(fd, EV_SYN, SYN_REPORT, 0);
}

static int find_broken_touch_device(char *out_path, size_t max_len) {
    char path[64];
    char name[128];
    for (int i = 0; i < 16; i++) {
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDWR | O_NONBLOCK);
        if (fd < 0) {
            fd = open(path, O_RDONLY | O_NONBLOCK);
        }
        if (fd < 0) {
            continue;
        }
        memset(name, 0, sizeof(name));
        if (ioctl(fd, EVIOCGNAME(sizeof(name) - 1), name) >= 0) {
            if (strstr(name, "NVTCapacitiveTouchScreen") != NULL ||
                strstr(name, "TouchScreen") != NULL ||
                strstr(name, "fts_ts") != NULL ||
                strstr(name, "goodix_ts") != NULL) {
                snprintf(out_path, max_len, "%s", path);
                return fd;
            }
        }
        close(fd);
    }
    int fallback_fd = open("/dev/input/event2", O_RDWR | O_NONBLOCK);
    if (fallback_fd < 0) {
        fallback_fd = open("/dev/input/event2", O_RDONLY | O_NONBLOCK);
    }
    if (fallback_fd >= 0) {
        snprintf(out_path, max_len, "/dev/input/event2");
        return fallback_fd;
    }
    return -1;
}

int main(int argc, char **argv) {
    int check_only = (argc > 1 && strcmp(argv[1], "--test") == 0);
    int daemon_mode = (argc > 1 && strcmp(argv[1], "--daemon") == 0);

    char dev_path[64] = {0};
    int fd = find_broken_touch_device(dev_path, sizeof(dev_path));
    if (fd < 0) {
        fprintf(stderr, "GRAB_ERR: cannot open touchscreen device (%s)\n", strerror(errno));
        return 1;
    }

    /* Limpa slots multitouch presos antes de travar o dispositivo */
    release_stuck_mt_slots(fd);
    usleep(25000);
    release_stuck_mt_slots(fd);

    if (ioctl(fd, EVIOCGRAB, 1) < 0) {
        /* Se já estiver com EVIOCGRAB ativo por outra instância de grab_ghost_touch, ok */
        if (errno == EBUSY) {
            printf("GRAB_ALREADY_ACTIVE device=%s\n", dev_path);
            close(fd);
            return 0;
        }
        fprintf(stderr, "GRAB_ERR: ioctl EVIOCGRAB failed on %s (%s)\n", dev_path, strerror(errno));
        close(fd);
        return 2;
    }

    printf("GRAB_OK device=%s\n", dev_path);
    fflush(stdout);

    if (check_only) {
        sleep(1);
        ioctl(fd, EVIOCGRAB, 0);
        close(fd);
        return 0;
    }

    if (daemon_mode) {
        pid_t pid = fork();
        if (pid < 0) {
            close(fd);
            return 3;
        }
        if (pid > 0) {
            /* Processo pai encerra imediatamente mantendo o fd aberto no filho */
            _exit(0);
        }
        setsid();
        int null_fd = open("/dev/null", O_RDWR);
        if (null_fd >= 0) {
            dup2(null_fd, STDIN_FILENO);
            dup2(null_fd, STDOUT_FILENO);
            dup2(null_fd, STDERR_FILENO);
            if (null_fd > 2 && null_fd != fd) {
                close(null_fd);
            }
        }
    }

    signal(SIGHUP, SIG_IGN);
    struct input_event ev[64];
    for (;;) {
        ssize_t n = read(fd, ev, sizeof(ev));
        if (n < 0) {
            if (errno == EAGAIN || errno == EINTR) {
                usleep(250000);
                continue;
            }
            break;
        }
        usleep(100000);
    }

    close(fd);
    return 0;
}
