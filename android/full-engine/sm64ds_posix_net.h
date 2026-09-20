/* Native POSIX UDP boundary. No Winsock imports and no transport simulation.
 * The game/relay protocol remains in upstream comms_loopback.cpp.
 */
#ifndef SM64DS_POSIX_NET_H
#define SM64DS_POSIX_NET_H
#include <arpa/inet.h>
#include <cerrno>
#include <climits>
#include <cstddef>
#include <cstring>
#include <fcntl.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
namespace sm64ds_net {
inline int open_udp(int family, int type, int protocol) {
    int fd = ::socket(family, type, protocol);
    if (fd < 0) return -1;
    const int flags = ::fcntl(fd, F_GETFD, 0);
    if (flags < 0 || ::fcntl(fd, F_SETFD, flags | FD_CLOEXEC) < 0) {
        const int saved = errno; ::close(fd); errno = saved; return -1;
    }
    return fd;
}
inline int nonblocking(int fd) {
    const int flags = ::fcntl(fd, F_GETFL, 0);
    return flags < 0 ? -1 : ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}
inline int send(int fd, const char *data, int len, int flags,
                const sockaddr *to, int addrlen) {
    if (len < 0 || addrlen < 0) { errno = EINVAL; return -1; }
    ssize_t n;
    do { n = ::sendto(fd, data, static_cast<size_t>(len), flags | MSG_NOSIGNAL,
                     to, static_cast<socklen_t>(addrlen)); } while (n < 0 && errno == EINTR);
    return static_cast<int>(n);
}
inline int receive(int fd, char *data, int len, int flags,
                   sockaddr *from, int *addrlen) {
    if (len < 0 || (from && (!addrlen || *addrlen < 0))) { errno = EINVAL; return -1; }
    socklen_t naddr = addrlen ? static_cast<socklen_t>(*addrlen) : 0;
    ssize_t n;
    // MSG_TRUNC gives the complete datagram's length. Never accept a valid
    // prefix cut from an oversized packet (Winsock rejected that packet).
    do { n = ::recvfrom(fd, data, static_cast<size_t>(len), flags | MSG_TRUNC,
                       from, from ? &naddr : nullptr); } while (n < 0 && errno == EINTR);
    if (addrlen) *addrlen = static_cast<int>(naddr);
    if (n > len) { errno = EMSGSIZE; return -1; }
    return static_cast<int>(n);
}
inline bool resolve_ipv4(const char *host, in_addr *address) {
    if (!host || !address) return false;
    if (::inet_pton(AF_INET, host, address) == 1) return true;
    addrinfo hints{}, *answer = nullptr;
    hints.ai_family = AF_INET; hints.ai_socktype = SOCK_DGRAM;
    if (::getaddrinfo(host, nullptr, &hints, &answer) != 0) return false;
    bool found = false;
    for (auto *p = answer; p; p = p->ai_next) {
        if (p->ai_family == AF_INET && p->ai_addrlen >= sizeof(sockaddr_in)) {
            *address = reinterpret_cast<const sockaddr_in *>(p->ai_addr)->sin_addr;
            found = true; break;
        }
    }
    ::freeaddrinfo(answer);
    return found;
}
} // namespace sm64ds_net
#endif
