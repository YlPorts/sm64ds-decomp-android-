package org.ylports.sm64ds.controls;
/** JNI binding to the existing native pad backend, not a reimplementation in Java. */
public final class NativeBridge {
    static { System.loadLibrary("sm64ds_controls"); }
    private NativeBridge(){}
    public static native void init();
    public static native void focus(boolean focused);
    public static native void submit(int buttons,float x,float y,int rightTrigger);
    public static native void cancel();
    public static native void pointer(int id,int action,float x,float y);
    public static native boolean key(int device,int source,int code,int action,boolean canceled);
    public static native void axes(int device,float[] values);
    public static native void removeDevice(int device);
    public static native int[] poll();
}
