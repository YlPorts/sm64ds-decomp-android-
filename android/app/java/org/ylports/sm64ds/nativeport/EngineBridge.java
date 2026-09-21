package org.ylports.sm64ds.nativeport;
final class EngineBridge {
    static void load(String root) {
        System.loadLibrary("sm64ds_bootstrap");
        if(!prepare(root))throw new IllegalStateException("No se pudo preparar la carpeta del motor.");
        // Static engine initializers read NitroFS. Environment must precede dlopen.
        System.loadLibrary("sm64ds_engine");
    }
    private static native boolean prepare(String root);
    static native int start();
    static native int step();
    static native boolean copyFrame(int[] pixels);
    static native void touch(int id,int action,float x,float y);
    static native void finish();
}
