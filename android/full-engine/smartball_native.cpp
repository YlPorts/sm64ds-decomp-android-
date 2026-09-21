// Native class faces for bodies already present in the matching inventory.
// Slot addresses: port/hal/scene_mg.cpp's ROM vtable census, ov006:0213ed10
// (root) and ov006:0213ed60 (board). The class definitions also supply the
// compiler's real RTTI. No synthetic typeinfo or replacement game logic.
#include "cMgSmartball_board_c.h"

extern "C" {
void func_ov006_02114724(void *);
void func_ov006_02114720();
void func_ov006_02114738(void *);
void func_ov006_0210e4f4(void *);
void func_ov006_0210f914(void *);
}

void cMgSmartball_object_c::SaveSnapshot() { func_ov006_02114724(this); }
void cMgSmartball_object_c::Update() { func_ov006_02114720(); }
void cMgSmartball_object_c::RestoreInitial() { func_ov006_02114738(this); }
void cMgSmartball_board_c::Update() { func_ov006_0210e4f4(this); }
void cMgSmartball_board_c::RestoreInitial() { func_ov006_0210f914(this); }
