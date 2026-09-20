package org.ylports.sm64ds.controls;

import java.util.HashMap;
import java.util.Map;

/** UI-thread gesture router. Android-independent so the actual rules can be tested.
 * A finger owns either a control group or the DS stylus for its whole gesture.
 * Positions use fractions of the safe viewport; sizes use density-independent units.
 */
public final class TouchControls {
    public static final int DOWN=0, UP=1, MOVE=2, CANCEL=3;
    public static final int CROUCH=0x20000;
    public interface Sink {
        void pad(int buttons, float x, float y, int rightTrigger);
        void stylus(int id, int action, float x, float y);
        void cancel();
    }
    public static final class Control {
        public final int id, mask;
        public final String label;
        public final boolean stick, pill;
        public float x,y,rx,ry;
        Control(int id,String label,int mask,boolean stick,boolean pill) {
            this.id=id;this.label=label;this.mask=mask;this.stick=stick;this.pill=pill;
        }
        boolean hit(float px,float py,float extra) {
            float dx=Math.abs(px-x),dy=Math.abs(py-y);
            if(pill)return dx<=rx+extra && dy<=ry+extra;
            return dx*dx+dy*dy<=(rx+extra)*(rx+extra);
        }
    }
    private static final int IGNORE=0,STICK=1,FACE=2,STYLUS=3,EDIT=4;
    private static final class Finger {
        int kind,control;float x,y,offsetX,offsetY,oldX,oldY;
        Finger(int k,int c,float px,float py){kind=k;control=c;x=px;y=py;}
    }
    public final Control[] controls={
        new Control(0,"",0,true,false),new Control(1,"A",0x1000,false,false),
        new Control(2,"B",0x2000,false,false),new Control(3,"X",0x4000,false,false),
        new Control(4,"ZR",CROUCH,false,false),new Control(5,"L",0x100,false,true),
        new Control(6,"R",0x200,false,true),new Control(7,"START",0x10,false,true),
        new Control(8,"Y",0x8000,false,false)
    };
    private final Sink sink;
    private final Map<Integer,Finger> fingers=new HashMap<>();
    private final float[] positions=new float[18];
    private float left,top,width=1,height=1,dp=1,scale=1;
    private float sx,sy,sw,sh;
    private boolean editing,focused=true,configured,compact;
    public int buttons;
    public float stickX,stickY;
    public boolean rejectedMove;
    public TouchControls(Sink sink){this.sink=sink;for(int i=0;i<positions.length;i++)positions[i]=-1;}
    private static boolean finite(float x){return !Float.isNaN(x)&&!Float.isInfinite(x);}
    public static float clamp(float value,float lo,float hi) {
        return Float.isNaN(value)||Float.isInfinite(value)?lo:Math.max(lo,Math.min(hi,value));
    }
    public void compact(boolean value){cancel();compact=value;layout();}
    public void viewport(float x,float y,float w,float h,float density) {
        cancel();left=x;top=y;width=Math.max(1,w);height=Math.max(1,h);
        dp=Math.max(.1f,Math.min(clamp(density,.1f,10),Math.min(width/(compact?400f:620f),height/(compact?240f:330f))));
        configured=true;layout();
    }
    public void stylusRect(float x,float y,float w,float h){cancel();sx=x;sy=y;sw=Math.max(0,w);sh=Math.max(0,h);}
    public float[] stylusRect(){return new float[]{sx,sy,sw,sh};}
    public void scale(float value){cancel();scale=clamp(value,.8f,1.4f);layout();}
    public float scale(){return scale;}
    private void layout() {
        if(!configured)return;
        if(compact){layoutCompact();return;}
        float u=Math.min(dp*scale,Math.min(width/620f,height/275f));
        float fit=u/dp;
        float[][] defaults={{90,height/dp-91},{width/dp-124,height/dp-57},
            {width/dp-64,height/dp-113},{width/dp-184,height/dp-113},
            {width/dp-124,height/dp-169},{width/dp-191,height/dp-232},
            {width/dp-62,height/dp-232},{width/dp*.5f,height/dp-30},
            {width/dp-126,height/dp-232}};
        for(int i=0;i<controls.length;i++){
            Control c=controls[i];c.rx=(c.stick?59:c.pill?(i==7?35:27):i==1?32:28)*u;
            c.ry=c.stick?c.rx:c.pill?24*u:c.rx;
            // Group spreads with size; edge anchors stay reachable on ultrawide screens.
            float x=defaults[i][0]*dp, y=defaults[i][1]*dp;
            if(i>=1 && i<=6){x=width-(width-x)*fit;y=height-(height-y)*fit;}
            if(i==8){x=width-126*u;y=height-232*u;}
            if(i==0){x=90*u;y=height-91*u;}
            c.x=positions[2*i]>=0?left+positions[2*i]*width:left+x;
            c.y=positions[2*i+1]>=0?top+positions[2*i+1]*height:top+y;
            bound(c);
        }
    }
    private void layoutCompact(){
        float u=Math.min(dp*scale,Math.min(width/400f,height/240f));
        float[][] centers={{78,150},{300,193},{349,145},{251,145},{300,97},
            {42,32},{358,32},{193,213},{189,98}};
        for(Control c:controls){
            c.rx=(c.stick?54:c.pill?30:c.id==1?28:c.id==8?23:25)*u;
            c.ry=c.pill?(c.id==7?18:20)*u:c.rx;
            float x=centers[c.id][0]*u, y=height-(240-centers[c.id][1])*u;
            if(c.id>=1&&c.id<=4 || c.id==6)x=width-(400-centers[c.id][0])*u;
            if(c.id==7||c.id==8)x=width*.5f+(centers[c.id][0]-200)*u;
            c.x=positions[2*c.id]>=0?left+positions[2*c.id]*width:left+x;
            c.y=positions[2*c.id+1]>=0?top+positions[2*c.id+1]*height:top+y;
            bound(c);
        }
    }
    private void bound(Control c){c.x=clamp(c.x,left+c.rx,left+width-c.rx);c.y=clamp(c.y,top+c.ry,top+height-c.ry);}
    public float[] positions(){return positions.clone();}
    public void positions(float[] p){
        cancel();if(p==null||p.length!=positions.length)return;
        for(int i=0;i<p.length;i++)positions[i]=finite(p[i])&&p[i]>=0&&p[i]<=1?p[i]:-1;
        layout();
    }
    public void defaults(){cancel();for(int i=0;i<positions.length;i++)positions[i]=-1;scale=1;layout();}
    public void editing(boolean on){cancel();editing=on;}
    public boolean editing(){return editing;}
    public void focus(boolean value){cancel();focused=value;}
    public void cancel(){fingers.clear();buttons=0;stickX=stickY=0;sink.cancel();}
    private boolean inStylus(float x,float y){return sw>0&&sh>0&&x>=sx&&x<sx+sw&&y>=sy&&y<sy+sh;}
    private boolean owned(int kind){for(Finger f:fingers.values())if(f.kind==kind)return true;return false;}
    private int hit(float x,float y,boolean facesOnly){
        int best=-1;float distance=Float.MAX_VALUE;
        for(Control c:controls){if(facesOnly && (c.id<1||c.id>4))continue;
            if(c.hit(x,y,2*dp)){float d=(x-c.x)*(x-c.x)+(y-c.y)*(y-c.y);
                if(d<distance){best=c.id;distance=d;}}}
        return best;
    }
    /** Returns ownership, not whether a button happens to be pressed at this coordinate. */
    public boolean event(int id,int action,float x,float y) {
        if(action==CANCEL){cancel();return true;}
        if(!configured||!focused||id<0||!finite(x)||!finite(y))return false;
        if(action==DOWN){
            if(fingers.containsKey(id)||fingers.size()>=16)return false;
            int c=hit(x,y,false),kind=IGNORE;
            if(editing){if(c>=0&&!owned(EDIT))kind=EDIT;}
            else if(c>=0){kind=c==0?(owned(STICK)?IGNORE:STICK):FACE;}
            else if(inStylus(x,y)&&!owned(STYLUS))kind=STYLUS;
            Finger f=new Finger(kind,c,x,y);fingers.put(id,f);
            if(kind==EDIT){Control ctl=controls[c];f.offsetX=ctl.x-x;f.offsetY=ctl.y-y;f.oldX=ctl.x;f.oldY=ctl.y;}
            if(kind==STYLUS)sink.stylus(id,DOWN,x,y);
        }else{
            Finger f=fingers.get(id);if(f==null)return false;
            if(action!=MOVE&&action!=UP)return false;
            f.x=x;f.y=y;
            if(f.kind==STYLUS)sink.stylus(id,action,x,y);
            if(f.kind==EDIT){Control c=controls[f.control];c.x=x+f.offsetX;c.y=y+f.offsetY;bound(c);
                if(action==UP){rejectedMove=overlaps(c);
                    if(rejectedMove){c.x=f.oldX;c.y=f.oldY;}
                    positions[2*c.id]=(c.x-left)/width;positions[2*c.id+1]=(c.y-top)/height;}}
            if(action==UP)fingers.remove(id);
        }
        publish();return true;
    }
    private boolean overlaps(Control c){
        if(c.x+c.rx>sx&&c.x-c.rx<sx+sw&&c.y+c.ry>sy&&c.y-c.ry<sy+sh)return true;
        for(Control o:controls)if(o!=c){
            if(!c.pill&&!o.pill){float dx=c.x-o.x,dy=c.y-o.y;
                if(dx*dx+dy*dy<(c.rx+o.rx+2*dp)*(c.rx+o.rx+2*dp))return true;
            }else if(Math.abs(c.x-o.x)<c.rx+o.rx+2*dp&&Math.abs(c.y-o.y)<c.ry+o.ry+2*dp)return true;
        }return false;
    }
    private void publish(){
        int mask=0;float ax=0,ay=0;
        if(!editing)for(Finger f:fingers.values()){
            if(f.kind==STICK){Control c=controls[0];float dx=(f.x-c.x)/(c.rx*.72f),dy=(c.y-f.y)/(c.ry*.72f);
                float length=(float)Math.sqrt(dx*dx+dy*dy);if(length>.08f){ax=dx/Math.max(1,length);ay=dy/Math.max(1,length);}}
            else if(f.kind==FACE){Control original=controls[f.control];int chosen=f.control;
                if(f.control>=1&&f.control<=4){int candidate=hit(f.x,f.y,true);if(candidate>=0)chosen=candidate;}
                Control c=controls[chosen];if(c.hit(f.x,f.y,9*dp))mask|=c.mask;
            }
        }
        buttons=mask;stickX=ax;stickY=ay;sink.pad(mask&0xffff,ax,ay,(mask&CROUCH)!=0?255:0);
    }
}
