package org.ylports.sm64ds.nativeport;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Cartridge extraction shared by Android and the host integration check. */
public final class RomImporter {
    public interface Progress { void update(String message); }
    private static final int LIMIT = 16 * 1024 * 1024;
    private final byte[] rom, fnt, fat;
    private final TreeMap<Integer,String> names = new TreeMap<>();
    private final Map<String,byte[]> images = new HashMap<>();
    private final Map<Integer,Integer> bases = new HashMap<>();
    private final Set<Integer> visited = new HashSet<>();

    static byte[] read(InputStream input, int limit) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] chunk = new byte[65536];
        for (int n; (n=input.read(chunk))!=-1;) {
            if ((long)out.size()+n>limit) throw new IOException("El archivo supera el tamaño admitido.");
            out.write(chunk,0,n);
        }
        return out.toByteArray();
    }
    static String hash(byte[] bytes) throws IOException {
        try {
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder text=new StringBuilder();
            for(byte b:digest) text.append(String.format(Locale.ROOT,"%02x",b&255));
            return text.toString();
        } catch(java.security.NoSuchAlgorithmException e) { throw new IOException(e); }
    }
    private static void check(boolean valid,String reason) throws IOException {
        if(!valid) throw new IOException(reason);
    }
    private static int u16(byte[] b,int p) throws IOException {
        check(p>=0&&p<=b.length-2,"Tabla truncada.");return (b[p]&255)|((b[p+1]&255)<<8);
    }
    private static int u32(byte[] b,int p) throws IOException {
        return u16(b,p)|(u16(b,p+2)<<16);
    }
    private static byte[] slice(byte[] b,int offset,int length) throws IOException {
        check(offset>=0&&length>=0&&(long)offset+length<=b.length,"Rango fuera de la ROM.");
        return Arrays.copyOfRange(b,offset,offset+length);
    }
    private byte[] span(int header) throws IOException {return slice(rom,u32(rom,header),u32(rom,header+4));}
    private byte[] file(int id) throws IOException {
        int start=u32(fat,id*8),end=u32(fat,id*8+4);return slice(rom,start,end-start);
    }
    /** Nintendo backwards LZ stream. Each reference reads bytes already decoded. */
    static byte[] decompress(byte[] in,boolean required) throws IOException {
        int end=-1,head=0,packed=0,extra=0;
        for(int tail=0;tail<32&&in.length-tail>=8;tail+=4) {
            int e=in.length-tail,word=u32(in,e-8),h=word>>>24,p=word&0xffffff;
            if(h<8||h>p||p>e) continue;
            boolean padding=true;for(int i=e-h;i<e-8;i++) if(in[i]!=(byte)255)padding=false;
            if(!padding)continue;
            end=e;head=h;packed=p;extra=u32(in,e-4);break;
        }
        if(end<0) {check(!required,"Compresión no válida.");return in;}
        if(extra==0)return in;
        check(extra>0&&(long)end+extra<=8*1024*1024,"Tamaño descomprimido no válido.");
        int stop=end-packed,src=end-head,dst=end+extra;
        byte[] out=new byte[dst+(in.length-end)];System.arraycopy(in,0,out,0,stop);
        System.arraycopy(in,end,out,dst,in.length-end);
        while(dst>stop) {
            check(src>stop,"Flujo comprimido truncado.");int flags=in[--src]&255;
            for(int mask=128;mask!=0&&dst>stop;mask>>=1) {
                if((flags&mask)==0) {check(src>stop,"Literal truncado.");out[--dst]=in[--src];}
                else {
                    check(src-stop>=2,"Referencia truncada.");int a=in[--src]&255,b=in[--src]&255;
                    int count=(a>>>4)+3,distance=((a&15)<<8|b)+3;
                    int decoded=end+extra-dst;
                    if(distance>decoded) {check(decoded>=2,"Referencia antes del inicio.");distance=2;}
                    check(count<=dst-stop,"Referencia fuera de la salida.");
                    while(count-->0) {--dst;out[dst]=out[dst+distance];}
                }
            }
        }
        return out;
    }
    private RomImporter(byte[] data) throws IOException {
        rom=data;check(rom.length==LIMIT&&new String(rom,12,4,StandardCharsets.US_ASCII).equals("ASMP")&&rom[30]==0,
            "Necesitas Super Mario 64 DS Europa, revisión 0 (.nds).");
        fnt=span(0x40);fat=span(0x48);check(fat.length%8==0,"FAT inválida.");
        directory(0xf000,"",0);
        images.put("arm9",decompress(slice(rom,u32(rom,0x20),u32(rom,0x2c)),false));
        byte[] overlays=span(0x50);check(overlays.length==103*32,"Conjunto de overlays incompatible.");
        for(int p=0;p<overlays.length;p+=32) {
            int id=u32(overlays,p),flags=u32(overlays,p+28);
            String key=String.format(Locale.ROOT,"ov%03d",id);
            byte[] image=decompress(file(u32(overlays,p+24)),(flags&0x1000000)!=0);
            check(image.length==u32(overlays,p+8)&&!images.containsKey(key),"Overlay incompatible: "+id);
            images.put(key,image);bases.put(id,u32(overlays,p+4));
        }
    }
    private void directory(int id,String path,int depth) throws IOException {
        check(depth<=32&&visited.add(id),"Árbol de archivos cíclico.");
        int entry=(id&4095)*8,p=u32(fnt,entry),file=u16(fnt,entry+4);
        for(;;) {
            check(p>=0&&p<fnt.length,"Directorio truncado.");int tag=fnt[p++]&255;
            if(tag==0)return;int len=tag&127;check(len>0&&p+len<=fnt.length,"Nombre truncado.");
            String name=new String(fnt,p,len,StandardCharsets.US_ASCII);p+=len;
            check(!name.equals(".")&&!name.equals("..")&&!name.matches(".*[\\\\/\t\r\n:].*"),"Nombre de archivo no válido.");
            if((tag&128)!=0) {int next=u16(fnt,p);p+=2;directory(next,path+name+"/",depth+1);}
            else {check(file<fat.length/8&&!names.containsKey(file),"ID de archivo inválido.");names.put(file++,path+name);}
        }
    }
    private static String kind(String path) {
        String[] ext={".bca",".bmd",".btp",".kcl",".narc",".sdat",".bin"};
        String[] kinds={"animation","model","texture-sequence","collision","archive","sound-archive","data"};
        for(int i=0;i<ext.length;i++)if(path.toLowerCase(Locale.ROOT).endsWith(ext[i]))return kinds[i];return "file";
    }
    private static void write(File root,String name,byte[] bytes) throws IOException {
        File file=new File(root,name);String prefix=root.getCanonicalPath()+File.separator;
        check(file.getCanonicalPath().startsWith(prefix),"Destino fuera de la carpeta de recursos.");
        check(file.getParentFile().isDirectory()||file.getParentFile().mkdirs(),"No se pudo crear la carpeta.");
        try(FileOutputStream stream=new FileOutputStream(file)) {stream.write(bytes);}
    }
    private static void write(File root,String name,String text) throws IOException {write(root,name,text.getBytes(StandardCharsets.UTF_8));}
    private void extract(File root,byte[] recipe,byte[] manifest,Progress progress) throws IOException {
        progress.update("Preparando archivos del juego…");
        StringBuilder files=new StringBuilder("file_id\thex_id\tpath\tkind\tsize\n");
        Map<String,Integer> ids=new HashMap<>();
        for(Map.Entry<Integer,String> e:names.entrySet()) {
            int id=e.getKey();String path=e.getValue();byte[] data=file(id);ids.put(path,id);
            write(root,"extracted/dsd/files/"+path,data);
            files.append(String.format(Locale.ROOT,"%d\t0x%04x\t%s\t%s\t%d\n",id,id,path,kind(path),data.length));
        }
        write(root,"build/assets/files.tsv",files.toString());
        StringBuilder handles=new StringBuilder("handle\thex_handle\tfile_id\thex_file_id\tpath\tkind\tsize\n");
        byte[] ov0=images.get("ov000");check(ov0!=null,"Falta overlay 0.");int base=bases.get(0);
        for(int h=0;h<2058;h++) {
            int ptr=u32(ov0,0x020bd4b8-base+4*h)-base,end=ptr;
            check(ptr>=0&&ptr<ov0.length,"Handle inválido.");
            while(end<ov0.length&&ov0[end]!=0)end++;check(end<ov0.length,"Ruta sin terminador.");
            String path=new String(ov0,ptr,end-ptr,StandardCharsets.US_ASCII);Integer id=ids.get(path);
            check(id!=null,"Handle sin archivo: "+path);
            handles.append(String.format(Locale.ROOT,"%d\t0x%04x\t%d\t0x%04x\t%s\t%s\t%d\n",h,h,id,id,path,kind(path),file(id).length));
        }
        write(root,"build/assets/handles.tsv",handles.toString());
        StringBuilder tables=new StringBuilder("key\tvalue\n");String[] tableNames={"fnt","fat","ovt9","ovt7"};
        for(int i=0;i<4;i++) {
            int p=0x40+8*i,offset=u32(rom,p),size=u32(rom,p+4);String name=tableNames[i];
            tables.append(name+"_offset\t"+offset+"\n"+name+"_size\t"+size+"\n");
            if(size>0)write(root,"build/assets/nitrofs_"+name+".bin",slice(rom,offset,size));
        }
        write(root,"build/assets/nitrofs.tsv",tables.toString());
        progress.update("Verificando los datos del motor…");
        BufferedReader reader=new BufferedReader(new StringReader(new String(recipe,StandardCharsets.US_ASCII)));
        String[] header=reader.readLine().split(" ");check(header.length==5&&header[1].equals("romdata-recipe")&&header[2].equals("v1"),"Receta incompatible.");
        int total=Integer.parseInt(header[4]);check(total>0&&total<8*1024*1024,"Receta demasiado grande.");
        byte[] blob=new byte[total];int pos=0;
        for(String line;(line=reader.readLine())!=null;) {
            String[] row=line.split("\t");check(row.length==5,"Fila de receta inválida.");
            int offset=Integer.parseInt(row[0]),size=Integer.parseInt(row[1]),start=Integer.parseInt(row[3]);
            byte[] source=images.get(row[2]);check(source!=null&&offset==pos&&size>=0&&(long)pos+size<=total&&start>=0,"Rango de receta inválido.");
            int copy=Math.min(size,Math.max(0,source.length-start));if(copy>0)System.arraycopy(source,start,blob,pos,copy);
            check(hash(Arrays.copyOfRange(blob,pos,pos+size)).equals(row[4]),"Datos incompatibles con esta versión del motor.");pos+=size;
        }
        check(pos==total&&hash(blob).equals(header[3]),"La verificación final de recursos falló.");
        write(root,"build/assets/romdata.bin",blob);write(root,"build/assets/romdata.manifest",manifest);
        // Recovered filesystem seams also read these local decompressed images.
        write(root,"extracted/arm9_dec.bin",images.get("arm9"));
        for(int id:bases.keySet())write(root,String.format(Locale.ROOT,"extracted/overlays/overlay_%04d.bin",id),images.get(String.format(Locale.ROOT,"ov%03d",id)));
    }
    private static void discard(File file) {File[] children=file.listFiles();if(children!=null)for(File child:children)discard(child);file.delete();}
    public static File install(InputStream input,InputStream recipeInput,InputStream manifestInput,
                               String expectedSha,File parent,Progress progress) throws IOException {
        progress.update("Comprobando la ROM…");
        byte[] rom=read(input,LIMIT),recipe=read(recipeInput,4*1024*1024),manifest=read(manifestInput,4*1024*1024);
        check(hash(rom).equals(expectedSha),"ROM incompatible. Usa el archivo .nds de Super Mario 64 DS Europa, revisión 0. Descomprime el .7z primero.");
        RomImporter importer=new RomImporter(rom);
        check(parent.isDirectory()||parent.mkdirs(),"No se pudo preparar el almacenamiento.");
        File staging=new File(parent,"import-"+UUID.randomUUID()),dest=new File(parent,"rom-"+hash(recipe).substring(0,16));
        check(staging.mkdir(),"No se pudo crear la carpeta temporal.");
        try {
            importer.extract(staging,recipe,manifest,progress);write(staging,"READY",expectedSha+"\n"+hash(recipe)+"\n");
            File previous=new File(parent,"previous-"+UUID.randomUUID());boolean hadPrevious=dest.exists();
            if(hadPrevious)check(dest.renameTo(previous),"No se pudo reemplazar la instalación anterior.");
            if(!staging.renameTo(dest)) {
                if(hadPrevious)previous.renameTo(dest);
                throw new IOException("No se pudo finalizar la importación.");
            }
            if(hadPrevious)discard(previous);return dest;
        } catch(IOException|RuntimeException e) {discard(staging);throw e;}
    }
}
