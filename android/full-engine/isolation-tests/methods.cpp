#include "api.h"
int Mixer::Apply(int32_t x) { state+=x;return state; }
Triple Mixer::Vector(int32_t n) { return {state+n,n*2,-n}; }
Record::Record() { _ZN6RecordC1Ev(this); }
Cleanup::~Cleanup() { _ZN7CleanupD1Ev(this); }
int Face::Value() {return 81;}
Face::~Face() = default;
