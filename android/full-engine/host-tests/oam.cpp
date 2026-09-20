#include "native_oam.inc"
#include <cassert>
#include <unistd.h>
extern "C" {
void *_ZN3OAM15MM_PLAYER_ICONSE[16]; void *_ZN3OAM18MM_VS_PLAYER_ICONSE[16];
void *_ZN3OAM20MM_VS_PLAYER_ICONS_SE[16]; void *_ZN3OAM15MM_STAR_MARKERSE[8];
void *_ZN3OAM12MM_STAR_KEYSE[2]; void *data_ov002_0210c748[3];
void *data_ov002_0210cac8[3]; void *data_ov002_0210c230[9];
void *_ZN3OAM17VS_YELLOW_NUMBERSE[10];void *_ZN3OAM7NUMBERSE[10];
}
int main(){
    const size_t page=size_t(sysconf(_SC_PAGESIZE));
    auto *p=static_cast<unsigned char*>(mmap(nullptr,page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));
    assert(p!=MAP_FAILED);assert(mprotect(p+page,page,PROT_NONE)==0);
    unsigned short term[4]={0,0,0,0xffff};
    for(const auto &table:kTables)for(int i=0;i<table.count;++i)table.tbl[i]=term;
    // A valid terminator immediately before a protected page is allowed.
    memcpy(p+page-8,term,8);assert(terminated(p+page-8)==1);
    // Missing terminator cannot make this validator read the protected page.
    memset(p+page-8,0,8);assert(terminated(p+page-8)==0);
    _ZN3OAM15MM_PLAYER_ICONSE[0]=nullptr;
    _ZN3OAM15MM_PLAYER_ICONSE[1]=reinterpret_cast<void*>(uintptr_t(0x0210c648));
    _ZN3OAM15MM_PLAYER_ICONSE[2]=p+page-8;
    assert(hal_oam_templates_check()==3);assert(hal_oam_templates_check()==3);
    assert(hal_oam_walk_probe()==2); // unsupported destructive probe must not claim success
    munmap(p,page*2);puts("PASS: original OAM tables, invalid/null/DS pointers and guarded-page terminators");
}
