/* Native fatal configuration reporting. Keeps the upstream non-returning exit(2)
 * contract, including calls from static initializers. No Win32 UI or guessed
 * repository path. A future launcher must set SM64DS_ERROR_DIR before loading
 * the engine and read the report after a failed engine-process launch.
 */
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <limits.h>
#include <unistd.h>
#include "instance_tag.h"
namespace {
void report(const char *text){
    std::fprintf(stderr,"[startup] %s\n",text);std::fflush(stderr);
    const char *dir=std::getenv("SM64DS_ERROR_DIR");
    if(!dir||dir[0]!='/')return; // Never write next to a system executable or in an unknown cwd.
    const char *tag=port_instance_tag();if(!tag)tag="";
    for(const char *c=tag+(*tag=='.'?1:0);*c;++c)if(!((*c>='a'&&*c<='z')||(*c>='A'&&*c<='Z')||(*c>='0'&&*c<='9')||*c=='_'||*c=='-'))return;
    char path[PATH_MAX];int n=std::snprintf(path,sizeof path,"%s/startup_error%s.txt",dir,tag);
    if(n<0||static_cast<size_t>(n)>=sizeof path)return;
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC|O_NOFOLLOW,0600);
    if(fd<0){std::fprintf(stderr,"[startup] Cannot write report: errno=%d\n",errno);return;}
    const char *p=text;size_t left=std::strlen(text);
    while(left){ssize_t wrote=write(fd,p,left);if(wrote<0&&errno==EINTR)continue;if(wrote<=0)break;p+=wrote;left-=static_cast<size_t>(wrote);}
    if(left)std::fprintf(stderr,"[startup] Report write was incomplete\n");
    int rc;do{rc=fsync(fd);}while(rc<0&&errno==EINTR);
    if(rc<0)std::fprintf(stderr,"[startup] Report could not be synced\n");
    close(fd);
}
}
extern "C" void port_asset_root_refuse(const char *wanted){
    char text[1400];std::snprintf(text,sizeof text,
        "No se ha indicado la carpeta de recursos de Super Mario 64 DS.\n"
        "Abre el juego desde su lanzador y selecciona tu ROM para preparar los recursos.\n"
        "No se utilizará una carpeta de desarrollo como alternativa.\nArchivo solicitado: %s\n",wanted?wanted:"(sin detalle)");
    report(text);std::exit(2);
}
extern "C" void port_asset_mismatch_refuse(const char *detail){
    char text[1800];std::snprintf(text,sizeof text,
        "Los recursos seleccionados no corresponden a esta compilación de Super Mario 64 DS.\n"
        "Vuelve a preparar los recursos desde tu ROM con esta versión del lanzador.\n"
        "No se cargarán datos incompatibles. No se han borrado tus archivos.\nDetalle: %s\n",detail?detail:"(sin detalle)");
    report(text);std::exit(2);
}
