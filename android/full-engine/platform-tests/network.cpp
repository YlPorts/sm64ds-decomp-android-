/* Includes the generated, reviewed COMPLETE transport. Fixtures are limited
 * to the game conductor's activity/close boundaries; datagrams use real UDP. */
#include "native_comms_under_test.cpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <chrono>
namespace port {void comms_note_wire_activity() {}}
extern "C" void func_02040724(){port::lb_close();}
static int checks=0;
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"FAIL network line %d: %s errno=%d\n",__LINE__,#x,errno);std::exit(1);}++checks;}while(0)
static void unit_tests() {
    using namespace sm64ds_net;
    int a=open_udp(AF_INET,SOCK_DGRAM,0),b=open_udp(AF_INET,SOCK_DGRAM,0);CHECK(a>=0&&b>=0);
    CHECK((fcntl(a,F_GETFD)&FD_CLOEXEC)!=0 && nonblocking(a)==0 && nonblocking(b)==0);
    sockaddr_in to{};to.sin_family=AF_INET;to.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    CHECK(::bind(b,reinterpret_cast<sockaddr*>(&to),sizeof(to))==0);
    socklen_t len=sizeof(to);CHECK(getsockname(b,reinterpret_cast<sockaddr*>(&to),&len)==0);
    int conflict=open_udp(AF_INET,SOCK_DGRAM,0);
    CHECK(::bind(conflict,reinterpret_cast<sockaddr*>(&to),sizeof(to))<0&&errno==EADDRINUSE);::close(conflict);
    char src[128],dst[128];std::memset(src,0x57,sizeof(src));
    CHECK(sm64ds_net::send(a,src,128,0,reinterpret_cast<sockaddr*>(&to),sizeof(to))==128);
    sockaddr_in from{};int naddr=sizeof(from);
    CHECK(receive(b,dst,8,0,reinterpret_cast<sockaddr*>(&from),&naddr)==-1 && errno==EMSGSIZE);
    CHECK(receive(b,dst,128,0,nullptr,nullptr)==-1&&(errno==EAGAIN||errno==EWOULDBLOCK));
    CHECK(sm64ds_net::send(a,src,128,0,reinterpret_cast<sockaddr*>(&to),sizeof(to))==128);
    CHECK(receive(b,dst,128,0,nullptr,nullptr)==128 && !std::memcmp(src,dst,128));
    CHECK(sm64ds_net::send(a,src,0,0,reinterpret_cast<sockaddr*>(&to),sizeof(to))==0);
    CHECK(receive(b,dst,128,0,nullptr,nullptr)==0);
    CHECK(receive(b,dst,-1,0,nullptr,nullptr)==-1&&errno==EINVAL);
    CHECK(port::parse_host_port("127.0.0.1:32123",1234,&to) && ntohs(to.sin_port)==32123);
    CHECK(port::parse_host_port("localhost",2345,&to)&&ntohs(to.sin_port)==2345);
    CHECK(!port::parse_host_port("",2345,&to));
    ::close(a);::close(b);
    std::printf("native UDP boundary: %d checks PASS\n",checks);
}
int main(int argc,char **argv) {
    if(argc==1){unit_tests();return 0;}
    CHECK(argc==3);
    const bool parent=!std::strcmp(argv[1],"parent");
    port::g_port_base=std::atoi(argv[2]);
    port::g_role=parent?port::kRoleParent:port::kRoleChild;
    port::g_want_players=2;
    port::lb_open(2);CHECK(port::g_open);
    if(parent)port::lb_become_parent();else port::lb_become_child();
    unsigned start=port::now_ms();
    while(port::lb_state()!=(parent?port::kCommsParentConnected:port::kCommsChildConnected)) {
        CHECK(port::now_ms()-start<5000);std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    unsigned char block[port::kCommsBlockBytes],expected[port::kCommsBlockBytes];
    std::memset(block,parent?0x11:0x22,sizeof(block));std::memset(expected,parent?0x22:0x11,sizeof(expected));
    uint16_t status=0xffff;start=port::now_ms();
    while(!port::lb_exchange(block,&status)) {
        if(port::now_ms()-start>=5000){std::fprintf(stderr,"exchange timeout\n");return 2;}
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    const void *peer=port::lb_peer_block(parent?1:0);
    CHECK(status==0 && peer && !std::memcmp(peer,expected,sizeof(expected)));
    // Keep answering re-transmits until the other endpoint has consumed its round.
    start=port::now_ms();while(port::now_ms()-start<100){port::lb_poll();std::this_thread::sleep_for(std::chrono::milliseconds(1));}
    port::lb_close();port::lb_close();CHECK(!port::g_open);
    std::printf("upstream UDP transport %s: handshake + 32-byte exchange PASS\n",argv[1]);
}
