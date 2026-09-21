package org.ylports.sm64ds.nativeport;
import android.app.Activity;
import android.content.*;
import android.graphics.*;
import android.hardware.input.InputManager;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.ylports.sm64ds.controls.*;

/** The engine belongs to one worker and one disposable :engine process. */
public final class GameActivity extends Activity implements InputManager.InputDeviceListener {
    private final Object stateLock=new Object();
    private volatile boolean resumed,loaded,stop;
    private volatile long heartbeat=SystemClock.uptimeMillis();
    private TouchOverlay overlay;private DsLayout layout;private Screen screen;private TextView message;
    private InputManager input;private android.content.SharedPreferences preferences;
    private final Handler handler=new Handler(Looper.getMainLooper());
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        preferences=getSharedPreferences("controls-v2-portrait",MODE_PRIVATE);
        input=(InputManager)getSystemService(INPUT_SERVICE);
        LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setBackgroundColor(0xff111820);
        root.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        LinearLayout toolbar=new LinearLayout(this);message=new TextView(this);message.setTextColor(0xffdce7f1);message.setText("Preparando motor…");
        toolbar.addView(message,new LinearLayout.LayoutParams(0,dp(48),1));
        Button adjust=new Button(this);adjust.setText("Ajustar");adjust.setOnClickListener(v->settings());toolbar.addView(adjust);
        Button exit=new Button(this);exit.setText("Salir");exit.setOnClickListener(v->leave());toolbar.addView(exit);root.addView(toolbar);
        FrameLayout stage=new FrameLayout(this);screen=new Screen(this);stage.addView(screen);
        overlay=new TouchOverlay(this,new TouchControls.Sink(){
            public void pad(int b,float x,float y,int rt){if(loaded)NativeBridge.submit(b,x,y,rt);}
            public void cancel(){if(loaded){NativeBridge.cancel();EngineBridge.touch(0,3,0,0);}}
            public void stylus(int id,int action,float x,float y){DsLayout p=layout;if(loaded&&p!=null)EngineBridge.touch(id,action,(x-p.x)*256/p.width,(y-p.bottom)*192/p.height);}
        });stage.addView(overlay);
        stage.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
            layout=DsLayout.fit(r-l,b-t,getResources().getDisplayMetrics().density);DsLayout p=layout;
            overlay.controls.compact(true);overlay.controls.viewport(dp(8),p.dockY,r-l-dp(16),p.dockHeight-dp(4),getResources().getDisplayMetrics().density);
            overlay.controls.stylusRect(p.x,p.bottom,p.width,p.height);
        });
        overlay.opacity(preferences.getFloat("opacity",.38f));overlay.controls.scale(preferences.getFloat("scale",1));overlay.haptics(preferences.getBoolean("haptics",true));
        float[] positions=new float[18];for(int i=0;i<18;i++)positions[i]=preferences.getFloat("position"+i,-1);overlay.controls.positions(positions);
        root.addView(stage,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
        String path=getIntent().getStringExtra("root");if(path==null){leave();return;}
        new Thread(()->runEngine(path),"SM64DS engine").start();
        handler.postDelayed(new Runnable(){public void run(){
            if(stop)return;
            if(resumed&&SystemClock.uptimeMillis()-heartbeat>60000){message.setText("El arranque se ha detenido. Revisa el registro desde el lanzador.");leave();}
            else handler.postDelayed(this,1000);
        }},1000);
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private void runEngine(String root) {
        try {
            EngineBridge.load(root);NativeBridge.init();loaded=true;NativeBridge.focus(resumed);
            int result=EngineBridge.start();if(result!=0)throw new IllegalStateException("El motor no arrancó (código "+result+"). Revisa el registro.");
            runOnUiThread(()->message.setText("SM64DS · motor activo"));
            long next=System.nanoTime();
            while(!stop) {
                synchronized(stateLock){while(!resumed&&!stop){heartbeat=SystemClock.uptimeMillis();stateLock.wait(500);} }
                if(stop)break;
                heartbeat=SystemClock.uptimeMillis();int frame=EngineBridge.step();
                if(frame<0)throw new IllegalStateException("No se pudo producir la imagen del juego ("+frame+").");
                screen.postInvalidateOnAnimation();next+=16666667;
                long delay=next-System.nanoTime();if(delay>0)java.util.concurrent.locks.LockSupport.parkNanos(delay);else next=System.nanoTime();
            }
            EngineBridge.finish();
        } catch(Throwable error){
            stop=true;
            try(java.io.PrintWriter log=new java.io.PrintWriter(new java.io.FileWriter(new java.io.File(root,"engine.log"),true))){error.printStackTrace(log);}
            catch(java.io.IOException ignored){}
            runOnUiThread(()->message.setText(error.toString()));
        }
    }
    private void saveControls(){
        SharedPreferences.Editor edit=preferences.edit().putFloat("scale",overlay.controls.scale()).putFloat("opacity",overlay.opacity()).putBoolean("haptics",overlay.haptics());
        float[] positions=overlay.controls.positions();for(int i=0;i<positions.length;i++)edit.putFloat("position"+i,positions[i]);edit.apply();
    }
    private void settings(){
        if(overlay.controls.editing()){overlay.controls.editing(false);saveControls();return;}
        overlay.release();
        LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(dp(20),dp(8),dp(20),0);
        TextView label=new TextView(this);label.setText("Opacidad");box.addView(label);SeekBar opacity=new SeekBar(this);opacity.setMax(70);opacity.setProgress(Math.round(overlay.opacity()*100)-15);box.addView(opacity);
        TextView sizeLabel=new TextView(this);sizeLabel.setText("Tamaño");box.addView(sizeLabel);SeekBar size=new SeekBar(this);size.setMax(60);size.setProgress(Math.round(overlay.controls.scale()*100)-80);box.addView(size);
        new android.app.AlertDialog.Builder(this).setTitle("Controles táctiles").setView(box)
            .setPositiveButton("Guardar",(d,w)->{overlay.opacity((opacity.getProgress()+15)/100f);overlay.controls.scale((size.getProgress()+80)/100f);saveControls();})
            .setNeutralButton("Mover",(d,w)->{overlay.controls.editing(true);message.setText("Mueve los controles y pulsa Ajustar para guardar.");})
            .setNegativeButton("Cerrar",null).show();
    }
    private void leave(){stop=true;saveControls();synchronized(stateLock){stateLock.notifyAll();}finish();handler.postDelayed(()->android.os.Process.killProcess(android.os.Process.myPid()),200);}
    @Override public void onBackPressed(){leave();}
    @Override protected void onResume(){super.onResume();resumed=true;heartbeat=SystemClock.uptimeMillis();if(loaded)NativeBridge.focus(true);if(overlay!=null)overlay.controls.focus(true);input.registerInputDeviceListener(this,null);synchronized(stateLock){stateLock.notifyAll();}}
    @Override protected void onPause(){resumed=false;if(overlay!=null){overlay.release();overlay.controls.focus(false);}if(loaded)NativeBridge.focus(false);input.unregisterInputDeviceListener(this);super.onPause();}
    @Override protected void onDestroy(){
        stop=true;resumed=false;synchronized(stateLock){stateLock.notifyAll();}
        handler.removeCallbacksAndMessages(null);
        // The engine's static state belongs to this disposable process. A new
        // Activity must load it fresh, even if Android destroyed this one.
        handler.postDelayed(()->android.os.Process.killProcess(android.os.Process.myPid()),250);
        super.onDestroy();
    }
    @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(loaded)NativeBridge.focus(focus&&resumed);if(overlay!=null)overlay.controls.focus(focus&&resumed);}
    public void onInputDeviceAdded(int id){}public void onInputDeviceChanged(int id){if(loaded)NativeBridge.removeDevice(id);}public void onInputDeviceRemoved(int id){if(loaded)NativeBridge.removeDevice(id);}
    @Override public boolean dispatchKeyEvent(KeyEvent e){if(loaded&&resumed&&NativeBridge.key(e.getDeviceId(),e.getSource(),e.getKeyCode(),e.getAction(),e.isCanceled()))return true;return super.dispatchKeyEvent(e);}
    @Override public boolean onGenericMotionEvent(MotionEvent e){if(loaded&&resumed&&(e.getSource()&InputDevice.SOURCE_JOYSTICK)==InputDevice.SOURCE_JOYSTICK){NativeBridge.axes(e.getDeviceId(),new float[]{e.getAxisValue(0),e.getAxisValue(1),e.getAxisValue(11),e.getAxisValue(14),e.getAxisValue(17),e.getAxisValue(18),e.getAxisValue(15),e.getAxisValue(16)});return true;}return super.onGenericMotionEvent(e);}
    private final class Screen extends View {
        final int[] pixels=new int[256*384];final Bitmap bitmap=Bitmap.createBitmap(256,384,Bitmap.Config.ARGB_8888);final Paint paint=new Paint();
        Screen(Context context){super(context);setContentDescription("Pantalla superior y pantalla táctil de Nintendo DS");}
        @Override protected void onDraw(Canvas canvas){
            if(layout==null)return;
            if(loaded&&EngineBridge.copyFrame(pixels))bitmap.setPixels(pixels,0,256,0,0,256,384);
            DsLayout p=layout;canvas.drawBitmap(bitmap,new Rect(0,0,256,192),new RectF(p.x,p.top,p.x+p.width,p.top+p.height),paint);
            canvas.drawBitmap(bitmap,new Rect(0,192,256,384),new RectF(p.x,p.bottom,p.x+p.width,p.bottom+p.height),paint);
        }
    }
}
