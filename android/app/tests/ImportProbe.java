package org.ylports.sm64ds.nativeport;
import java.io.*;
public final class ImportProbe {
    public static void main(String[] args) throws Exception {
        try(InputStream rom=new FileInputStream(args[0]);InputStream recipe=new FileInputStream(args[1]);InputStream manifest=new FileInputStream(args[2])) {
            System.out.println(RomImporter.install(rom,recipe,manifest,args[3],new File(args[4]),System.out::println));
        }
    }
}
