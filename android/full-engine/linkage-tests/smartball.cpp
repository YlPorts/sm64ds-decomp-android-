#include <cassert>
#include <typeinfo>
#include "cMgSmartball_object_c.h"
int main() {
    cMgSmartball_object_c object{};
    object.mCurrent0=13;object.mCurrent1=-27;
    object.mInitial0=333;object.mInitial1=-444;
    object.SaveSnapshot();
    assert(object.mSnapshot0==13 && object.mSnapshot1==-27);
    object.RestoreInitial();
    assert(object.mCurrent0==333 && object.mCurrent1==-444);
    object.Update();
    assert(object.mCurrent0==333 && object.mCurrent1==-444);
    // The emitted native base vtable and RTTI must be real, linkable objects.
    assert(typeid(object)==typeid(cMgSmartball_object_c));
}
