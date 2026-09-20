package org.ylports.sm64ds.controls;
/** Two native-ratio panels above a separate control dock. No game pixels here. */
public final class DsLayout {
 public final float x, top, bottom, width, height, dockY, dockHeight;
 private DsLayout(float x,float top,float bottom,float w,float h,float dockY,float dockHeight){
  this.x=x;this.top=top;this.bottom=bottom;this.width=w;this.height=h;
  this.dockY=dockY;this.dockHeight=dockHeight;
 }
 public static DsLayout fit(float w,float h,float density){
  w=Math.max(1,w);h=Math.max(1,h);
  float d=TouchControls.clamp(density,.1f,10f);
  float gap=Math.min(8*d,h*.02f), margin=Math.min(8*d,w*.02f);
  float dock=Math.min(240*d,h*.36f);
  float screenW=Math.max(1,Math.min(w-2*margin,(h-dock-3*gap)/1.5f));
  float screenH=screenW*.75f;
  float top=gap, bottom=top+screenH+gap, dockY=bottom+screenH+gap;
  return new DsLayout((w-screenW)*.5f,top,bottom,screenW,screenH,dockY,Math.max(1,h-dockY));
 }
}
