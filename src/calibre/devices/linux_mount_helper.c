#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>

#define MARKER ".created_by_calibre_mount_helper"
#define DEV "/dev/"
#define MEDIA "/media/"
#define False 0
#define True 1

int exists(const char *path) {
    struct stat file_info;
    if (stat(path, &file_info) == 0) return True;
    return False;
}

int get_root() {
    int res;
    res = setreuid(0, 0);
    if (res != 0) return False;
    if (setregid(0, 0) != 0) return False;
    return True;
}

void ensure_root() {
    if (!get_root()) {
        fprintf(stderr, "Failed to get root.\n");
        exit(EXIT_FAILURE);
    }
}

void check_mount_point(const char *mp) {
    char buffer[PATH_MAX+1];

    if (mp == NULL || strlen(mp) < strlen(MEDIA)) {
        fprintf(stderr, "Invalid arguments\n");
        exit(EXIT_FAILURE);
    }

    if (exists(mp)) {
        if (realpath(mp, buffer) == NULL) {
            fprintf(stderr, "Unable to resolve mount path\n");
            exit(EXIT_FAILURE);
        }
        if (strncmp(MEDIA, buffer, strlen(MEDIA)) != 0)  {
            fprintf(stderr, "Trying to operate on a mount point not under /media is not allowed\n");
            exit(EXIT_FAILURE);
        }
    }

    if (strncmp(MEDIA, mp, strlen(MEDIA)) != 0)  {
        fprintf(stderr, "Trying to operate on a mount point not under /media is not allowed\n");
        exit(EXIT_FAILURE);
    }

}

int do_mount(const char *dev, const char *mp) {
    char options[1000], marker[2000];
#ifdef __NetBSD__
    char uids[100], gids[100];
#endif
    int errsv;

    if (!exists(dev)) {
        fprintf(stderr, "Specified device node does not exist\n");
        return EXIT_FAILURE;
    }

    if (!exists(mp)) {
        if (mkdir(mp, S_IRUSR|S_IWUSR|S_IXUSR|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH) != 0) {
            errsv = errno;
            fprintf(stderr, "Failed to create mount point with error: %s\n", strerror(errsv));
        }
    }
    /* only mount if mp is under /media */
    mp = realpath(mp, NULL);
    if (mp == NULL) {
        fprintf(stderr, "realpath on mp failed.\n");
        exit(EXIT_FAILURE);
    }
    if (strncmp(MEDIA, mp, strlen(MEDIA)) != 0) {
        fprintf(stderr, "mount point is not under /media\n");
        exit(EXIT_FAILURE);
    }

    snprintf(marker, 2000, "%s/%s", mp, MARKER);
    if (!exists(marker)) {
        int fd = creat(marker, S_IRUSR|S_IWUSR);
        if (fd == -1) {
            int errsv = errno;
            fprintf(stderr, "Failed to create marker with error: %s\n", strerror(errsv));
            return EXIT_FAILURE;
        }
        close(fd);
    }
#ifdef __NetBSD__
    snprintf(options, 1000, "rw,noexec,nosuid,sync,nodev");
    snprintf(uids, 100, "%d", getuid());
    snprintf(gids, 100, "%d", getgid());
#else
#ifdef __FreeBSD__
    snprintf(options, 1000, "rw,noexec,nosuid,sync,-u=%d,-g=%d",getuid(),getgid());
#else
    snprintf(options, 1000, "rw,noexec,nosuid,sync,nodev,quiet,shortname=mixed,uid=%d,gid=%d,umask=077,fmask=0177,dmask=0077,utf8,iocharset=iso8859-1", getuid(), getgid());
#endif
#endif

    ensure_root();

#ifdef __NetBSD__
    execlp("mount_msdos", "mount_msdos", "-u", uids, "-g", gids, "-o", options, dev, mp, NULL);
#else
#ifdef __FreeBSD__
    execlp("mount", "mount", "-t", "msdosfs", "-o", options, dev, mp, NULL);
#else
    execlp("mount", "mount", "-t", "auto", "-o", options, dev, mp, NULL);
#endif
#endif
    errsv = errno;
    fprintf(stderr, "Failed to mount with error: %s\n", strerror(errsv));
    return EXIT_FAILURE;
}

int call_eject(const char *dev, const char *mp) {
    int ret, pid, errsv, i, status = EXIT_FAILURE;

    pid = fork();
    if (pid == -1) {
        fprintf(stderr, "Failed to fork\n");
        exit(EXIT_FAILURE);
    }

    if (pid == 0) { /* Child process */
        ensure_root();
#ifdef __NetBSD__
        execlp("eject", "eject", dev, NULL);
#else
#ifdef __FreeBSD__
	execlp("umount", "umount", dev, NULL);
#else
        execlp("eject", "eject", "-s", dev, NULL);
#endif
#endif
        /* execlp failed */
        errsv = errno;
        fprintf(stderr, "Failed to eject with error: %s\n", strerror(errsv));
        exit(EXIT_FAILURE);
    } else { /* Parent */
        for (i = 0; i < 7; i++) {
            sleep(1);
            ret = waitpid(pid, &status, WNOHANG);
            if (ret == -1) return False;
            if (ret > 0) break;
        }
        return WIFEXITED(status) && WEXITSTATUS(status) == 0;
    }
    return False;
}

int call_umount(const char *dev, const char *mp) {
    int ret, pid, errsv, i, status = EXIT_FAILURE;

    pid = fork();
    if (pid == -1) {
        fprintf(stderr, "Failed to fork\n");
        exit(EXIT_FAILURE);
    }

    if (pid == 0) { /* Child process */
        ensure_root();
#ifdef __FreeBSD__
        execlp("umount", "umount", mp, NULL);
#else
        execlp("umount", "umount", "-l", mp, NULL);
#endif
        /* execlp failed */
        errsv = errno;
        fprintf(stderr, "Failed to umount with error: %s\n", strerror(errsv));
        exit(EXIT_FAILURE);
    } else { /* Parent */
        for (i = 0; i < 7; i++) {
            sleep(1);
            ret = waitpid(pid, &status, WNOHANG);
            if (ret == -1) return False;
            if (ret > 0) break;
        }
        return WIFEXITED(status) && WEXITSTATUS(status) == 0;
    }
    return False;
}

int cleanup_mount_point(const char *mp) {
    char marker[2000];
    int urt, rmd, errsv;

    snprintf(marker, 2000, "%s/%s", mp, MARKER);
    if (exists(marker)) {
        urt = unlink(marker);
        if (urt == -1) {
            errsv = errno;
            fprintf(stderr, "Failed to unlink marker: %s\n", strerror(errsv));
            return EXIT_FAILURE;
        }
    }
    rmd = rmdir(mp);
    if (rmd == -1) {
        errsv = errno;
        fprintf(stderr, "Failed to remove mount point: %s\n", strerror(errsv));
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}

int do_eject(const char *dev, const char *mp) {
    int unmounted = False;

    ensure_root();

    unmounted = call_eject(dev, mp);
    if (!unmounted) call_umount(dev, mp);
    if (unmounted) return cleanup_mount_point(mp);
    return EXIT_FAILURE;
}

int cleanup(const char *dev, const char *mp) {
    ensure_root();
    call_umount(dev, mp);
    return cleanup_mount_point(mp);
}

void check_dev(const char *dev) {
    char buffer[PATH_MAX+1];
    struct stat file_info;

    if (dev == NULL || strlen(dev) < strlen(DEV)) {
        fprintf(stderr, "Invalid arguments\n");
        exit(EXIT_FAILURE);
    }

    if (realpath(dev, buffer) == NULL) {
        fprintf(stderr, "Unable to resolve dev path\n");
        exit(EXIT_FAILURE);
    }

    if (strncmp(DEV, buffer, strlen(DEV)) != 0) {
        fprintf(stderr, "Trying to operate on a dev node not under /dev\n");
        exit(EXIT_FAILURE);
    }

    if (stat(dev, &file_info) != 0) {
        fprintf(stderr, "stat call on dev node failed\n");
        exit(EXIT_FAILURE);
    }

    if (strstr(dev, "/shm/") != NULL) {
        fprintf(stderr, "naughty, naughty!\n");
        exit(EXIT_FAILURE);
    }

    if (!S_ISBLK(file_info.st_mode)) {
        fprintf(stderr, "dev node is not a block device\n");
        exit(EXIT_FAILURE);
    }

}

int main(int argc, char** argv)
{
    char *action, *dev, *mp, *temp;
    int status = EXIT_FAILURE;

    /*printf("Real UID\t= %d\n", getuid());
    printf("Effective UID\t= %d\n", geteuid());
    printf("Real GID\t= %d\n", getgid());
    printf("Effective GID\t= %d\n", getegid());*/

    if (argc != 4) {
        fprintf(stderr, "Needs 3 arguments: action, device node and mount point\n");
        exit(EXIT_FAILURE);
    }
    action = argv[1]; dev = argv[2]; mp = argv[3];

    /* Ensure that PATH only contains system directories to prevent execution of
       arbitrary executables as root */
    if (setenv("PATH",
            "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin\0",
            1) != 0) {
        fprintf(stderr, "Failed to restrict PATH env var, aborting.\n");
        exit(EXIT_FAILURE);
    }

    if (strncmp(action, "mount", 5) == 0) {
        dev = realpath(argv[2], NULL);
        if (dev == NULL) {
            fprintf(stderr, "Failed to resolve device node.\n");
            exit(EXIT_FAILURE);
        }
        temp = realpath(mp, NULL);
        if (temp != NULL) mp = temp;
        check_dev(dev); check_mount_point(mp);
        status = do_mount(dev, mp);
    } else if (strncmp(action, "eject", 5) == 0) {
        dev = realpath(argv[2], NULL);
        if (dev == NULL) {
            fprintf(stderr, "Failed to resolve device node.\n");
            exit(EXIT_FAILURE);
        }
        temp = realpath(mp, NULL);
        if (temp == NULL) {
            fprintf(stderr, "Mount point does not exist\n");
            exit(EXIT_FAILURE);
        }
        mp = temp;
        check_dev(dev); check_mount_point(mp);
        status = do_eject(dev, mp);
    } else if (strncmp(action, "cleanup", 7) == 0) {
        temp = realpath(mp, NULL);
        if (temp == NULL) {
            fprintf(stderr, "Mount point does not exist\n");
            exit(EXIT_FAILURE);
        }
        mp = temp;
        check_mount_point(mp);
        status = cleanup(dev, mp);
    } else {
        fprintf(stderr, "Unrecognized action: must be mount, eject or cleanup\n");
    }
 
    return status;
}

