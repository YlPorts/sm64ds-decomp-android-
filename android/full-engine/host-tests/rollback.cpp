// Includes the complete adapted original implementation. Only services outside
// hw_collect/hw_restore_to are test fixtures; no fixture is linked to the game.
#include "native_rollback.inc"
#include <cassert>
#include <vector>
static int invalidations = 0, fallbacks = 0;
namespace ntr {void gx_invalidate_textures(){++invalidations;}}
extern "C" unsigned port_hw_regions_size(){return 0;}
extern "C" void port_hw_regions_copy_out(void*){++fallbacks;}
extern "C" void port_hw_regions_copy_in(const void*){++fallbacks;}
int main(){
    g_ww = true; g_hw_n = 2; g_ww_pages = 3;
    void *hits[4]{}; g_ww_buf = hits;
    std::vector<char> live[2], shadow[2], undo[12];
    std::vector<UndoEntry> entries[12];
    for(int r=0;r<2;++r){live[r].resize(kPage*2+17);shadow[r].resize(live[r].size());
        g_hw[r] = {live[r].data(),unsigned(live[r].size()),3,shadow[r].data()};}
    for(int i=0;i<kSlots;++i){undo[i].resize(kUndoPages*kPage);entries[i].resize(kUndoPages);
        g_ring[i].undo=entries[i].data();g_ring[i].undo_data=undo[i].data();}
    auto take=[](unsigned t){auto &s=g_ring[t%kSlots];s.valid=true;s.tag=t;s.undo_n=0;assert(hw_collect(s)==0);};
    take(1); assert(g_ring[1].undo_n == 0);
    live[0][4]=10;live[1][kPage+10]=20;take(2);assert(g_ring[2].undo_n==2);
    live[1].back()=30;take(3);assert(g_ring[3].undo_n==1);
    live[0][4]=40;take(4);assert(g_ring[4].undo_n==1);
    hw_restore_to(2,g_ring[2]);
    assert(live[0][4]==10 && live[1][kPage+10]==20 && live[1].back()==0);
    assert(live[0]==shadow[0] && live[1]==shadow[1]);assert(invalidations==1);
    // Actual function's no-change branch must not add undo entries.
    g_ring[5].undo_n=0;assert(hw_collect(g_ring[5])==0 && g_ring[5].undo_n==0);
    g_ring[3].valid=g_ring[4].valid=false;
    hw_restore_to(1,g_ring[1]);assert(live[0][4]==0 && live[1][kPage+10]==0);
    assert(invalidations==2 && fallbacks==0);
    // Overflow invalidates the partial log and refreshes every shadow.
    g_ring[6].undo_n=kUndoPages;live[0][9]=2;
    assert(hw_collect(g_ring[6])==1 && g_ring[6].undo_n==0);
    assert(live[0]==shadow[0]);
    std::puts("PASS: original undo collection, two-region reverse restore, short final block, overflow and texture invalidation; synthetic memory only");
}
