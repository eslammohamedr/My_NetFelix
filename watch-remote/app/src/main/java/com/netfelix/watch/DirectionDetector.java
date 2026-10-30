package com.netfelix.watch;

/** Sustained up/down/right impulses, with stillness and cooldown between actions. */
public final class DirectionDetector {
    private long previous,quietSince,lastCommand;
    private float up,right,forward,velocity;
    private int verticalTicks,rightTicks;
    private boolean armed;
    private float upThreshold=3.2f,downThreshold=3.2f,sideThreshold=2f,speedThreshold=.30f,quietThreshold=.65f;
    private String message="Hold still briefly";
    public String status(){return message;}
    public void configure(float upValue,float downValue,float sideValue,float speedValue,float noise){
        for(float v:new float[]{upValue,downValue,sideValue,speedValue,noise})if(!Float.isFinite(v)||v<=0)throw new IllegalArgumentException("Invalid calibration");
        upThreshold=upValue;downThreshold=downValue;sideThreshold=sideValue;speedThreshold=speedValue;
        quietThreshold=Math.max(.4f,Math.min(1.2f,noise*1.5f));reset();
    }
    public void reset(){previous=quietSince=lastCommand=0;up=right=forward=velocity=0;verticalTicks=rightTicks=0;armed=false;message="Hold still briefly";}
    public String sample(long time,float vertical,float horizontal,float depth){
        if(previous!=0 && (time<=previous||time-previous>200_000_000L))reset();
        float dt=previous==0?0:Math.min((time-previous)/1e9f,.05f);previous=time;
        up+=.35f*(vertical-up);right+=.35f*(horizontal-right);forward+=.35f*(depth-forward);
        float norm=(float)Math.sqrt(up*up+right*right+forward*forward);
        if(lastCommand!=0 && time-lastCommand<1_200_000_000L){message="Pause before next movement";return null;}
        if(!armed)message="Hold still briefly to rearm";
        if(norm<quietThreshold){if(quietSince==0)quietSince=time;if(time-quietSince>200_000_000L){armed=true;velocity=0;message="Ready";}}
        else quietSince=0;
        if(!armed)return null;
        if(right < -sideThreshold && -right>Math.abs(up)*1.3f && -right>Math.abs(forward)*1.3f){
            armed=false;velocity=0;rightTicks=verticalTicks=0;message="Left ignored; hold still";return null;
        }
        if(Math.abs(up)>(up>0?upThreshold:downThreshold) && Math.abs(up)>Math.abs(right)*1.5f && Math.abs(up)>Math.abs(forward)*1.5f){
            if(++verticalTicks>=3)return emit(time,up>0?"KEY_VOLUP":"KEY_VOLDOWN");
        }else verticalTicks=0;
        if(right>Math.abs(up)*1.3f && right>Math.abs(forward)*1.3f){
            velocity=(velocity+right*dt)*(float)Math.exp(-dt*1.2f);
            if(right>sideThreshold)rightTicks++;else rightTicks=0;
            if(rightTicks>=3 && velocity>speedThreshold)return emit(time,"KEY_ENTER");
        }else{velocity*=.85f;rightTicks=0;}
        return null;
    }
    private String emit(long time,String key){lastCommand=time;armed=false;quietSince=0;velocity=0;rightTicks=verticalTicks=0;message="Detected "+key.substring(4);return key;}
}
