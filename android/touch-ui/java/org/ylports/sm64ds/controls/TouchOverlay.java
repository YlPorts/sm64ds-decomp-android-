package org.ylports.sm64ds.controls;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;

/** Reusable transparent overlay: it publishes input, and never consumes engine polls.
 * Place above the eventual game surface, with coordinates relative to that same surface.
 */
public final class TouchOverlay extends View {
    public final TouchControls controls;
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rect=new RectF();
    private final float[] glow=new float[9];
    private float opacity=.38f;
    private boolean haptics=true;
    private int previous;
    private boolean gestureOpen;
    public TouchOverlay(Context context,TouchControls.Sink sink){
        super(context);controls=new TouchControls(sink);setFocusable(true);
        setContentDescription("Controles de juego: palanca, saltar, atacar, correr, agachar, cámara y pausa");
    }
    public void opacity(float value){opacity=TouchControls.clamp(value,.15f,.85f);invalidate();}
    public float opacity(){return opacity;}
    public void haptics(boolean value){haptics=value;}
    public boolean haptics(){return haptics;}
    public void release(){controls.cancel();previous=0;gestureOpen=false;invalidate();}
    @Override public boolean onTouchEvent(MotionEvent event){
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_CANCEL){release();return true;}
        if(action==MotionEvent.ACTION_DOWN){
            // Clear an orphaned gesture, not the pending pulse of a completed tap.
            if(gestureOpen)controls.cancel();gestureOpen=true;
        }
        if(action==MotionEvent.ACTION_DOWN||action==MotionEvent.ACTION_POINTER_DOWN||
            action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_POINTER_UP){
            int i=event.getActionIndex();
            controls.event(event.getPointerId(i),action==MotionEvent.ACTION_DOWN||
                action==MotionEvent.ACTION_POINTER_DOWN?TouchControls.DOWN:TouchControls.UP,event.getX(i),event.getY(i));
        }else if(action==MotionEvent.ACTION_MOVE){
            // All IDs are stable even when Android reorders pointer indices.
            for(int i=0;i<event.getPointerCount();i++)controls.event(event.getPointerId(i),TouchControls.MOVE,event.getX(i),event.getY(i));
        }else return false;
        if(action==MotionEvent.ACTION_UP)gestureOpen=false;
        int rising=controls.buttons&~previous;
        if(rising!=0&&haptics&&!controls.editing())performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
        previous=controls.buttons;invalidate();return true;
    }
    @Override protected void onDetachedFromWindow(){release();super.onDetachedFromWindow();}
    @Override protected void onDraw(Canvas canvas){
        super.onDraw(canvas);float density=getResources().getDisplayMetrics().density;boolean animate=false;
        for(TouchControls.Control c:controls.controls){
            boolean pressed=c.stick?(controls.stickX!=0||controls.stickY!=0):(controls.buttons&c.mask)!=0;
            float goal=pressed?1:0;glow[c.id]+=(goal-glow[c.id])*.45f;
            if(Math.abs(goal-glow[c.id])>.01f)animate=true;
            int a=(int)(255*(opacity+(1-opacity)*glow[c.id]*.6f));
            paint.setColor(0xffffff);paint.setAlpha((int)(a*(controls.editing()?.22f:.12f)));
            paint.setStyle(Paint.Style.FILL);shape(canvas,c);
            paint.setColor(pressed?0xffbdeeff:0xffe5edf5);paint.setAlpha(a);paint.setStrokeWidth(Math.max(1,density));
            paint.setStyle(Paint.Style.STROKE);shape(canvas,c);paint.setStyle(Paint.Style.FILL);
            if(c.stick){
                paint.setAlpha((int)(a*.55f));canvas.drawCircle(c.x+controls.stickX*c.rx*.48f,
                    c.y-controls.stickY*c.ry*.48f,c.rx*.4f,paint);
                paint.setAlpha((int)(a*.7f));canvas.drawCircle(c.x,c.y,Math.max(1,density*1.2f),paint);
            }else{
                paint.setAlpha(Math.min(255,a+45));paint.setTextAlign(Paint.Align.CENTER);
                paint.setTypeface(android.graphics.Typeface.create("sans-serif-medium",0));
                paint.setTextSize(c.id==7?c.ry*.47f:c.ry*.70f);
                canvas.drawText(c.label,c.x,c.y-(paint.ascent()+paint.descent())*.5f,paint);
            }
            if(controls.editing()){
                paint.setAlpha(220);paint.setTextSize(10*density);paint.setTextAlign(Paint.Align.CENTER);
                canvas.drawText("mover",c.x,c.y+c.ry+12*density,paint);
            }
        }
        paint.setAlpha(255);if(animate)postInvalidateOnAnimation();
    }
    private void shape(Canvas canvas,TouchControls.Control c){
        if(c.pill){rect.set(c.x-c.rx,c.y-c.ry,c.x+c.rx,c.y+c.ry);canvas.drawRoundRect(rect,c.ry,c.ry,paint);}
        else canvas.drawCircle(c.x,c.y,c.rx,paint);
    }
}
