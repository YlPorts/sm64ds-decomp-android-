package org.ylports.sm64ds.controls;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.hardware.input.InputManager;
import android.os.Bundle;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/** Separate controls-only application. It does not load a ROM or pretend to run the game.
 * The native backend is the same one used by the port's compilation inventory.
 */
public final class ControlsActivity extends Activity implements InputManager.InputDeviceListener {
    TouchOverlay overlay;
    private SharedPreferences prefs;
    private InputManager input;
    private FrameLayout stage;
    private Button settings;
    private boolean resumed;
    @Override public void onCreate(Bundle state){
        super.onCreate(state);NativeBridge.init();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        prefs=getSharedPreferences("controls-v1",MODE_PRIVATE);
        input=(InputManager)getSystemService(INPUT_SERVICE);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(0xff111820);
        root.setOnApplyWindowInsetsListener((v,insets)->{
            int l=insets.getSystemWindowInsetLeft(),r=insets.getSystemWindowInsetRight();
            int t=insets.getSystemWindowInsetTop(),b=insets.getSystemWindowInsetBottom();
            if(android.os.Build.VERSION.SDK_INT>=28&&insets.getDisplayCutout()!=null){
                l=Math.max(l,insets.getDisplayCutout().getSafeInsetLeft());r=Math.max(r,insets.getDisplayCutout().getSafeInsetRight());
                t=Math.max(t,insets.getDisplayCutout().getSafeInsetTop());b=Math.max(b,insets.getDisplayCutout().getSafeInsetBottom());}
            v.setPadding(l,t,r,b);return insets;
        });
        LinearLayout toolbar=new LinearLayout(this);toolbar.setGravity(android.view.Gravity.CENTER_VERTICAL);toolbar.setPadding(dp(20),0,dp(12),0);
        TextView title=new TextView(this);title.setText("SM64DS  /  CONTROLES · PRUEBA");title.setTextColor(0xffdce7f1);title.setTextSize(14);
        toolbar.addView(title,new LinearLayout.LayoutParams(0,dp(52),1));title.setGravity(android.view.Gravity.CENTER_VERTICAL);
        settings=new Button(this);settings.setText("Ajustar");settings.setAllCaps(false);settings.setContentDescription("Ajustar tamaño, transparencia y posición de los controles");
        settings.setOnClickListener(v->{if(overlay.controls.editing()){overlay.controls.editing(false);save();settings.setText("Ajustar");overlay.invalidate();}else showSettings();});
        toolbar.addView(settings,new LinearLayout.LayoutParams(dp(116),dp(48)));root.addView(toolbar);
        stage=new FrameLayout(this);
        overlay=new TouchOverlay(this,new TouchControls.Sink(){
            public void pad(int b,float x,float y,int rt){NativeBridge.submit(b,x,y,rt);}
            public void stylus(int id,int action,float x,float y){NativeBridge.pointer(id,action,x,y);}
            public void cancel(){NativeBridge.cancel();}
        });
        stage.addView(new Monitor(this),new FrameLayout.LayoutParams(-1,-1));stage.addView(overlay,new FrameLayout.LayoutParams(-1,-1));
        stage.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
            if(r-l==or-ol && b-t==ob-ot)return;float d=getResources().getDisplayMetrics().density;
            overlay.controls.viewport(dp(8),0,r-l-dp(16),b-t-dp(8),d);
            float w=Math.min(dp(180),(r-l)*.24f),h=w*.75f;
            overlay.controls.stylusRect((r-l-w)/2,(b-t-h)/2,w,h);
            overlay.invalidate();
        });
        root.addView(stage,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
        overlay.opacity(prefs.getFloat("opacity",.38f));overlay.haptics(prefs.getBoolean("haptics",true));
        overlay.controls.scale(prefs.getFloat("scale",1));float[] positions=new float[18];
        for(int i=0;i<18;i++)positions[i]=prefs.getFloat("position"+i,-1);overlay.controls.positions(positions);
    }
    private int dp(float x){return Math.round(x*getResources().getDisplayMetrics().density);}
    private void save(){
        SharedPreferences.Editor e=prefs.edit().putFloat("opacity",overlay.opacity()).putFloat("scale",overlay.controls.scale()).putBoolean("haptics",overlay.haptics());
        float[] positions=overlay.controls.positions();for(int i=0;i<positions.length;i++)e.putFloat("position"+i,positions[i]);e.apply();
    }
    private interface Change{void value(int n);}
    private void slider(LinearLayout box,String name,int min,int max,int value,Change change){
        TextView label=new TextView(this);label.setText(name+" · "+value+" %");box.addView(label);
        SeekBar bar=new SeekBar(this);bar.setMax(max-min);bar.setProgress(value-min);bar.setContentDescription(name);
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
            public void onProgressChanged(SeekBar s,int p,boolean user){label.setText(name+" · "+(p+min)+" %");if(user){change.value(p+min);overlay.invalidate();}}
            public void onStartTrackingTouch(SeekBar s){}public void onStopTrackingTouch(SeekBar s){}
        });box.addView(bar,new LinearLayout.LayoutParams(-1,dp(48)));
    }
    private void showSettings(){
        overlay.release();NativeBridge.focus(false);
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(dp(24),dp(12),dp(24),0);
        slider(box,"Opacidad",15,85,Math.round(overlay.opacity()*100),n->overlay.opacity(n/100f));
        slider(box,"Tamaño",80,140,Math.round(overlay.controls.scale()*100),n->overlay.controls.scale(n/100f));
        CheckBox vibrate=new CheckBox(this);vibrate.setText("Vibración suave");vibrate.setChecked(overlay.haptics());vibrate.setOnCheckedChangeListener((v,c)->overlay.haptics(c));box.addView(vibrate);
        TextView help=new TextView(this);help.setText("A: saltar · B: atacar · X: correr · ZR: agachar\nL/R: cámara · Y: centrar\nMover no activa acciones del juego.");help.setPadding(0,dp(8),0,dp(8));box.addView(help);
        android.widget.ScrollView scroll=new android.widget.ScrollView(this);scroll.addView(box);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Controles táctiles").setView(scroll)
            .setPositiveButton("Listo",(d,w)->save())
            .setNeutralButton("Mover",(d,w)->{overlay.controls.editing(true);settings.setText("Guardar");overlay.invalidate();})
            .setNegativeButton("Restablecer",(d,w)->{overlay.controls.defaults();overlay.opacity(.38f);overlay.haptics(true);save();overlay.invalidate();}).create();
        dialog.setOnDismissListener(d->{save();NativeBridge.focus(resumed);});dialog.show();
    }
    @Override protected void onResume(){super.onResume();resumed=true;NativeBridge.focus(true);overlay.controls.focus(true);input.registerInputDeviceListener(this,null);}
    @Override protected void onPause(){resumed=false;overlay.release();overlay.controls.focus(false);NativeBridge.focus(false);input.unregisterInputDeviceListener(this);super.onPause();}
    @Override public void onWindowFocusChanged(boolean value){super.onWindowFocusChanged(value);if(overlay!=null){overlay.controls.focus(value&&resumed);NativeBridge.focus(value&&resumed);}}
    public void onInputDeviceAdded(int id){}public void onInputDeviceChanged(int id){NativeBridge.removeDevice(id);}public void onInputDeviceRemoved(int id){NativeBridge.removeDevice(id);}
    @Override public boolean dispatchKeyEvent(KeyEvent event){
        if(resumed&&overlay!=null&&!overlay.controls.editing()&&NativeBridge.key(event.getDeviceId(),event.getSource(),event.getKeyCode(),event.getAction(),event.isCanceled()))return true;
        return super.dispatchKeyEvent(event);
    }
    @Override public boolean onGenericMotionEvent(MotionEvent e){
        if(resumed&&(e.getSource()&InputDevice.SOURCE_JOYSTICK)==InputDevice.SOURCE_JOYSTICK){
            NativeBridge.axes(e.getDeviceId(),new float[]{e.getAxisValue(0),e.getAxisValue(1),e.getAxisValue(11),e.getAxisValue(14),e.getAxisValue(17),e.getAxisValue(18),e.getAxisValue(15),e.getAxisValue(16)});return true;
        }return super.onGenericMotionEvent(e);
    }
    /** Diagnostic consumer only. Production must let the game, not the overlay, poll input. */
    private final class Monitor extends View{
        final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);float markerX,markerY;
        Monitor(Context c){super(c);setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);}
        @Override protected void onDraw(Canvas c){
            float d=getResources().getDisplayMetrics().density;int[] s=NativeBridge.poll();
            markerX=Math.max(-1,Math.min(1,markerX+s[1]/32767f*.025f));markerY=Math.max(-1,Math.min(1,markerY-s[2]/32767f*.025f));
            p.setColor(0xff18232e);c.drawRoundRect(dp(14),dp(8),getWidth()-dp(14),getHeight()-dp(12),dp(22),dp(22),p);
            p.setColor(0xff849aaf);p.setTextAlign(Paint.Align.CENTER);p.setTextSize(12*d);
            c.drawText("PRUEBA NATIVA · SIN JUEGO",getWidth()/2f,dp(34),p);
            p.setTextSize(10*d);c.drawText("El escenario todavía no está conectado",getWidth()/2f,dp(51),p);
            p.setColor(0xffcee9f8);c.drawCircle(getWidth()/2f+markerX*getWidth()*.20f,dp(86)+markerY*dp(19),dp(6),p);
            float[] r=overlay.controls.stylusRect();p.setColor(0xff223340);c.drawRoundRect(r[0],r[1],r[0]+r[2],r[1]+r[3],dp(12),dp(12),p);
            p.setColor(0xffa5bccd);p.setTextSize(11*d);c.drawText("PANTALLA TÁCTIL",r[0]+r[2]/2,r[1]+r[3]/2,p);
            if(s[4]!=0){p.setColor(0xffb9edff);c.drawCircle(s[5],s[6],dp(9),p);}
            p.setColor(0xff8fa5b8);p.setTextSize(10*d);c.drawText(String.format(java.util.Locale.ROOT,"PAD %04X   ·   ZR %d",s[0],s[3]),getWidth()/2f,getHeight()-dp(73),p);
            if(resumed)postInvalidateOnAnimation();
        }
    }
}
