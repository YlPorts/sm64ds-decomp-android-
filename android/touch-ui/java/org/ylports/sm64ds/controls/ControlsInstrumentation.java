package org.ylports.sm64ds.controls;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.MotionEvent;
import java.io.File;
import java.io.FileOutputStream;

/** Framework MotionEvent -> actual overlay -> JNI -> production native pad.
 * Injected events and an Android emulator are not a physical-touchscreen test.
 */
public final class ControlsInstrumentation extends Instrumentation {
    private int checks;
    private void check(boolean value,String name){checks++;if(!value)throw new AssertionError(name);}
    private void event(TouchOverlay v,int action,int[] ids,float[] xy){
        MotionEvent.PointerProperties[] props=new MotionEvent.PointerProperties[ids.length];
        MotionEvent.PointerCoords[] coords=new MotionEvent.PointerCoords[ids.length];
        for(int i=0;i<ids.length;i++){
            props[i]=new MotionEvent.PointerProperties();props[i].id=ids[i];props[i].toolType=MotionEvent.TOOL_TYPE_FINGER;
            coords[i]=new MotionEvent.PointerCoords();coords[i].x=xy[i*2];coords[i].y=xy[i*2+1];coords[i].pressure=1;coords[i].size=1;
        }
        long now=SystemClock.uptimeMillis();MotionEvent e=MotionEvent.obtain(now,now,action,ids.length,props,coords,0,0,1,1,0,0,0x1002,0);
        try{check(v.dispatchTouchEvent(e),"MotionEvent consumed");}finally{e.recycle();}
    }
    @Override public void onCreate(Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){
        Bundle result=new Bundle();
        try{
            Intent intent=new Intent(getTargetContext(),ControlsActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ControlsActivity a=(ControlsActivity)startActivitySync(intent);waitForIdleSync();
            runOnMainSync(()->{
                TouchOverlay v=a.overlay;TouchControls c=v.controls;c.defaults();c.focus(true);NativeBridge.focus(true);v.haptics(false);
                check(v.getWidth()>0&&v.getHeight()>0,"real View laid out");
                TouchControls.Control joy=c.controls[0],jump=c.controls[1];float[] panel=c.stylusRect();
                float jx=joy.x+joy.rx*.7f,jy=joy.y,ax=jump.x,ay=jump.y,tx=panel[0]+panel[2]/2,ty=panel[1]+panel[3]/2;
                event(v,0,new int[]{3},new float[]{jx,jy});check(NativeBridge.poll()[1]>20000,"native stick");
                event(v,5|(1<<8),new int[]{3,9},new float[]{jx,jy,ax,ay});check(NativeBridge.poll()[0]==0x1000,"native jump while moving");
                event(v,2,new int[]{9,3},new float[]{ax,ay,jx,jy});check(NativeBridge.poll()[0]==0x1000,"pointer reordering preserves ownership");
                event(v,5|(2<<8),new int[]{9,3,17},new float[]{ax,ay,jx,jy,tx,ty});check(NativeBridge.poll()[4]==1,"independent stylus");
                event(v,6,new int[]{9,3,17},new float[]{ax,ay,jx,jy,tx,ty});int[] p=NativeBridge.poll();check(p[0]==0&&p[1]>20000&&p[4]==1,"one finger releases only its button");
                event(v,3,new int[]{3,17},new float[]{jx,jy,tx,ty});p=NativeBridge.poll();check(p[0]==0&&p[1]==0&&p[4]==0,"cancel clears everything");
                event(v,0,new int[]{9},new float[]{ax,ay});event(v,1,new int[]{9},new float[]{ax,ay});
                check(NativeBridge.poll()[0]==0x1000,"quick tap latched");check(NativeBridge.poll()[0]==0,"quick tap release");
                TouchControls.Control attack=c.controls[2];
                event(v,0,new int[]{9},new float[]{ax,ay});event(v,1,new int[]{9},new float[]{ax,ay});
                event(v,0,new int[]{2},new float[]{attack.x,attack.y});event(v,1,new int[]{2},new float[]{attack.x,attack.y});
                check(NativeBridge.poll()[0]==0x3000,"two completed gestures retain both pending buttons");
                check(NativeBridge.poll()[0]==0,"combined pulses do not stick");
                c.editing(true);event(v,0,new int[]{9},new float[]{ax,ay});check(NativeBridge.poll()[0]==0,"editing not gameplay");
                event(v,1,new int[]{9},new float[]{ax,ay});c.editing(false);
                c.focus(false);NativeBridge.focus(false);event(v,0,new int[]{9},new float[]{ax,ay});check(NativeBridge.poll()[0]==0,"unfocused input ignored");
                c.focus(true);NativeBridge.focus(true);v.release();v.invalidate();
            });
            waitForIdleSync();SystemClock.sleep(120);
            // Render the actual laid-out Android decor View. A device-screen
            // screenshot may instead capture first-boot/keyguard overlays.
            final Bitmap[] capture=new Bitmap[1];
            runOnMainSync(()->{
                android.view.View decor=a.getWindow().getDecorView();
                check(decor.getHeight()>decor.getWidth(),"portrait Android layout");
                DsLayout layout=a.panels;
                check(layout!=null && layout.bottom>layout.top+layout.height,"stacked separated panels");
                check(Math.abs(layout.width/layout.height-4f/3f)<.001f,"native ratio, not stretched");
                for(TouchControls.Control control:a.overlay.controls.controls)
                    check(control.y-control.ry>=layout.bottom+layout.height,"controls below both panels");
                capture[0]=Bitmap.createBitmap(decor.getWidth(),decor.getHeight(),Bitmap.Config.ARGB_8888);
                decor.draw(new android.graphics.Canvas(capture[0]));
            });
            Bitmap image=capture[0];check(image!=null,"actual Android View rendered");
            try(FileOutputStream out=new FileOutputStream(new File(getTargetContext().getFilesDir(),"controls.png"))){check(image.compress(Bitmap.CompressFormat.PNG,100,out),"screenshot saved");}image.recycle();
            result.putString("stream","PASS "+checks+" framework/JNI input checks. Controls diagnostic only; no game or physical device.\n");finish(Activity.RESULT_OK,result);
        }catch(Throwable t){result.putString("stream","FAIL "+t+"\n"+android.util.Log.getStackTraceString(t));finish(Activity.RESULT_CANCELED,result);}
    }
}
