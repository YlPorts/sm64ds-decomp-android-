package org.ylports.sm64ds.nativeport;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Integration checks using the owner's local ROM; no game data is bundled. */
public final class RomImporterChecks {
    interface Operation {void run() throws Exception;}
    static void reject(Operation action) throws Exception {
        try {action.run();} catch(IOException expected) {return;}
        throw new AssertionError("Invalid input was accepted");
    }
    static File install(byte[] rom,byte[] recipe,byte[] manifest,String sha,File parent) throws IOException {
        return RomImporter.install(new ByteArrayInputStream(rom),new ByteArrayInputStream(recipe),
                new ByteArrayInputStream(manifest),sha,parent,message->{});
    }
    public static void main(String[] args) throws Exception {
        byte[] rom=Files.readAllBytes(Paths.get(args[0])),recipe=Files.readAllBytes(Paths.get(args[1])),manifest=Files.readAllBytes(Paths.get(args[2]));
        String sha=args[3];File parent=new File(args[4]);
        File installed=install(rom,recipe,manifest,sha,parent);
        Path blob=installed.toPath().resolve("build/assets/romdata.bin");
        byte[] good=Files.readAllBytes(blob);
        Files.write(blob,new byte[]{1,2,3});
        if(!install(rom,recipe,manifest,sha,parent).equals(installed)||!Arrays.equals(good,Files.readAllBytes(blob)))throw new AssertionError("Reimport did not repair data");
        byte[] wrong=rom.clone();wrong[0]^=1;
        reject(()->install(wrong,recipe,manifest,sha,parent));
        byte[] badRecipe=recipe.clone();int headerEnd=0;while(badRecipe[headerEnd]!='\n')headerEnd++;
        badRecipe[headerEnd-1]=(byte)'1'; // Wrong total length; stage must be removed.
        reject(()->install(rom,badRecipe,manifest,sha,parent));
        if(!Arrays.equals(good,Files.readAllBytes(blob)))throw new AssertionError("Failed import damaged installed resources");
        String[] remaining=parent.list();
        if(remaining==null||remaining.length!=1||!remaining[0].equals(installed.getName()))throw new AssertionError("Staging or backup was left behind");
        reject(()->RomImporter.decompress(new byte[8],true));
        reject(()->RomImporter.read(new ByteArrayInputStream(new byte[9]),8));
        System.out.println("PASS: verified import, repair, wrong ROM, failed-stage cleanup, invalid compression, bounded input");
    }
}
