// The original instance-tag sanitizer is adapted and included by the tested source.
#include <cstring>
extern "C" void port_asset_root_refuse(const char*);
extern "C" void port_asset_mismatch_refuse(const char*);
int main(int argc,char**argv){if(argc>1&&!std::strcmp(argv[1],"mismatch"))port_asset_mismatch_refuse("different revision");port_asset_root_refuse("build/assets/nitrofs.tsv");}
