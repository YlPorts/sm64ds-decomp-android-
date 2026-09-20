package org.ylports.sm64ds.controls;
import java.util.Arrays;

public final class ControlsTest {
    private static int checks;
    private static void check(boolean yes,String what){checks++;if(!yes)throw new AssertionError(what);}
    static final class Sink implements TouchControls.Sink {
        int buttons,trigger,down,up,moves;float x,y;
        public void pad(int b,float x,float y,int t){buttons=b;this.x=x;this.y=y;trigger=t;NativeBridge.submit(b,x,y,t);}
        public void stylus(int id,int a,float x,float y){if(a==0)down++;if(a==1)up++;if(a==2)moves++;NativeBridge.pointer(id,a,x,y);}
        public void cancel(){buttons=trigger=0;x=y=0;NativeBridge.cancel();}
    }
    static void press(TouchControls c,int finger,int button){TouchControls.Control b=c.controls[button];check(c.event(finger,0,b.x,b.y),"press "+button);}
    static void release(TouchControls c,int finger,int button){TouchControls.Control b=c.controls[button];check(c.event(finger,1,b.x,b.y),"release "+button);}
    public static void main(String[] args){
        NativeBridge.init();Sink s=new Sink();TouchControls c=new TouchControls(s);
        c.viewport(10,5,960,450,1);c.stylusRect(390,130,160,120);
        press(c,50,0);c.event(50,2,c.controls[0].x+100,c.controls[0].y-100);
        press(c,12,1);press(c,37,4);int[] nativeState=NativeBridge.poll();
        check(nativeState[0]==0x1000&&nativeState[1]>20000&&nativeState[2]>20000&&nativeState[3]==255,"stick+jump+crouch reaches native pad");
        check(c.event(4,0,410,160),"stylus with controls");check(s.down==1&&NativeBridge.poll()[4]==1,"stylus independent");
        release(c,12,1);check((s.buttons&0x1000)==0&&s.trigger==255&&s.x>0,"release only own finger");
        c.event(37,2,410,160);check(s.down==1&&s.moves==0,"button cannot become stylus");
        c.event(4,2,c.controls[2].x,c.controls[2].y);check((s.buttons&0x2000)==0&&s.moves==1,"stylus cannot become button");
        c.event(4,1,410,160);check(NativeBridge.poll()[4]==0,"stylus up");c.cancel();
        press(c,1,1);press(c,2,1);release(c,1,1);check(s.buttons==0x1000,"two fingers same button retain held state");release(c,2,1);check(s.buttons==0,"last finger releases");NativeBridge.poll();
        press(c,9,3);c.event(9,2,c.controls[1].x,c.controls[1].y);check(s.buttons==0x1000,"slide run to jump");
        c.event(9,2,10,400);check(s.buttons==0,"drift releases without stylus leak");c.cancel();
        press(c,7,1);release(c,7,1);check(s.buttons==0,"UI not sticky after short tap");
        check((NativeBridge.poll()[0]&0x1000)!=0,"short tap survives until native consumer poll");
        check(NativeBridge.poll()[0]==0,"short tap released on second poll");
        press(c,7,4);release(c,7,4);check(NativeBridge.poll()[3]==255,"short crouch pulse");check(NativeBridge.poll()[3]==0,"crouch release");
        press(c,8,1);release(c,8,1);c.cancel();check(NativeBridge.poll()[0]==0,"cancel flushes unconsumed edges");
        press(c,4,1);c.focus(false);NativeBridge.focus(false);check(!c.event(7,0,400,160),"unfocused rejects");
        NativeBridge.focus(true);c.focus(true);check(NativeBridge.poll()[0]==0,"focus cycle no stale action");
        check(!c.event(4,2,1,2),"old pointer cannot revive");
        check(!c.event(-1,0,0,0)&&!c.event(1,0,Float.NaN,0),"invalid values rejected");
        c.event(1,0,300,40);c.event(1,2,c.controls[1].x,c.controls[1].y);check(s.buttons==0,"background cannot steal control");c.cancel();
        float old=c.controls[0].x;c.editing(true);press(c,10,0);
        c.event(10,2,180,300);c.event(10,1,180,300);check(s.buttons==0&&s.x==0,"editor never plays");
        check(c.controls[0].x!=old,"editor moves joystick");float[] stored=c.positions();
        TouchControls other=new TouchControls(s);other.positions(stored);other.viewport(10,5,960,450,1);
        check(Math.abs(other.controls[0].x-c.controls[0].x)<.01f,"saved normalized position restored");
        float prev=c.controls[1].x;press(c,2,1);c.event(2,1,420,160);check(c.rejectedMove&&c.controls[1].x==prev,"editor rejects stylus overlap");
        c.editing(false);c.defaults();check(c.controls[0].x==old,"reset defaults");
        float[] corrupt=new float[18];Arrays.fill(corrupt,Float.NaN);c.positions(corrupt);
        int[][] sizes={{640,360},{800,360},{840,360},{1280,720},{2340,1080}};
        for(int[] size:sizes)for(float scale:new float[]{.8f,1f,1.4f}){
            c.viewport(0,0,size[0],size[1],size[1]/360f);c.scale(scale);
            for(TouchControls.Control b:c.controls){check(Float.isFinite(b.x)&&Float.isFinite(b.y),"finite geometry");
                check(b.x-b.rx>=-.01f&&b.x+b.rx<=size[0]+.01f&&b.y-b.ry>=-.01f&&b.y+b.ry<=size[1]+.01f,"inside safe viewport");}
            press(c,1,0);c.event(1,2,-1000,2000);int[] p=NativeBridge.poll();check(Math.hypot(p[1],p[2])<=32768,"radial clamped stick");c.cancel();
        }
        for(int i=0;i<1000;i++){
            press(c,1,1);release(c,1,1);check(NativeBridge.poll()[0]==0x1000,"repeat short press "+i);check(NativeBridge.poll()[0]==0,"repeat release "+i);
        }
        System.out.println("PASS "+checks+" checks: Java gesture router -> JNI -> actual native pad backend; no game executed");
    }
}
