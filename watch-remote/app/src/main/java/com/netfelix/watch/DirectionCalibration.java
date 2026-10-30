package com.netfelix.watch;

/** Summarizes a short movement into thresholds; does not retain recordings. */
public final class DirectionCalibration {
    public static boolean acceptsSamples(boolean active,boolean referenceSet,boolean capturing,boolean calibrating){
        return active && (capturing || (referenceSet && !calibrating));
    }
    private float up,side,depth,prevUp,prev2Up,prevSide,prev2Side,velocity;
    public float upPeak,downPeak,positiveSide,negativeSide,positiveSpeed,negativeSpeed,noise;
    public int samples;
    private long previous;
    public void sample(long time,float vertical,float horizontal,float forward){
        float dt=previous==0?0:Math.min((time-previous)/1e9f,0.05f);previous=time;
        up+=0.35f*(vertical-up);side+=0.35f*(horizontal-side);depth+=0.35f*(forward-depth);
        noise=Math.max(noise,(float)Math.sqrt(up*up+side*side+depth*depth));
        if(samples>=2){
            if(up>Math.abs(side)*1.2f && up>Math.abs(depth)*1.2f)upPeak=Math.max(upPeak,Math.min(up,Math.min(prevUp,prev2Up)));
            if(-up>Math.abs(side)*1.2f && -up>Math.abs(depth)*1.2f)downPeak=Math.max(downPeak,Math.min(-up,Math.min(-prevUp,-prev2Up)));
            positiveSide=Math.max(positiveSide,Math.min(side,Math.min(prevSide,prev2Side)));
            negativeSide=Math.max(negativeSide,Math.min(-side,Math.min(-prevSide,-prev2Side)));
        }
        velocity=(velocity+side*dt)*(float)Math.exp(-dt*1.2f);
        positiveSpeed=Math.max(positiveSpeed,velocity);negativeSpeed=Math.max(negativeSpeed,-velocity);
        prev2Up=prevUp;prevUp=up;prev2Side=prevSide;prevSide=side;samples++;
    }
    public float verticalThreshold(boolean upwards,float restNoise){
        float peak=upwards?upPeak:downPeak;
        float floor=Math.max(0.8f,restNoise*3);
        if(samples<30 || peak<floor*1.3f)throw new IllegalArgumentException("Movement too small or unclear. Retry.");
        return Math.max(floor,peak*0.60f);
    }
    public float[] rightThresholds(float restNoise){
        float peak=positiveSide,speed=positiveSpeed;
        float floor=Math.max(0.7f,restNoise*3);
        if(samples<30 || peak<floor*1.3f || speed<0.18f)throw new IllegalArgumentException("Move clearly RIGHT once. Retry.");
        return new float[]{Math.max(floor,peak*0.55f),Math.max(0.12f,speed*0.55f)};
    }
}
