extern "C" void *_ZTV9FaderWipe[];
int main() {
    HalFaderWipe object;
    auto **vt=*(void***)&object;
    assert(vt==_ZTV9FaderWipe);
    using Dtor=void(*)(void*);using Query=int(*)(void*);
    using Speed=int(*)(void*,int,int);
    ((Dtor)vt[0])(&object);assert(destroyed==&object && !deleted);
    ((Dtor)vt[1])(&object);assert(deleted==&object);
    assert(((Query)vt[5])(&object)==1 && ((Query)vt[6])(&object)==0);
    assert(((Speed)vt[4])(&object,4,0)==0 && object.speed==0x400);
    assert(((Query)vt[2])(&object)==1 && object.currInterp==0x1000);
    assert(((Query)vt[6])(&object)==1 && ((Query)vt[5])(&object)==0);
    assert(((Speed)vt[3])(&object,8,0)==0 && object.speed==-0x200);
    assert(((Query)vt[2])(&object)==1 && object.currInterp==0);
    object.currInterp=0x800;assert(((Query)vt[7])(&object)==1);
    ((Dtor)vt[8])(&object);assert(object.currInterp==0x1000);
    ((Dtor)vt[9])(&object);assert(object.currInterp==0);
}
