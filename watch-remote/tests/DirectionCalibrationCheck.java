import com.netfelix.watch.DirectionCalibration;
import com.netfelix.watch.DirectionDetector;
public class DirectionCalibrationCheck {
    static void require(boolean ok){if(!ok)throw new AssertionError();}
    static DirectionCalibration motion(int kind){
        DirectionCalibration c=new DirectionCalibration();long t=2_000_000_000L;
        for(int i=0;i<100;i++){float up=0,side=0;if(i>=20&&i<35){if(kind==1)up=5;if(kind==2)up=-6;if(kind==3)side=5;}
            if(kind==3&&i>=35&&i<65)side=-5;
            if(kind==3&&i>=65&&i<80)side=5;
            c.sample(t+=20_000_000L,up,side,0);
        }return c;
    }
    public static void main(String[] args){
        require(DirectionCalibration.acceptsSamples(true,false,true,true)); // first calibration must accept readings without saved reference
        require(DirectionCalibration.acceptsSamples(true,true,true,true)); // subsequent steps
        require(DirectionCalibration.acceptsSamples(true,true,false,false)); // remote controls
        require(!DirectionCalibration.acceptsSamples(true,false,false,false));
        require(!DirectionCalibration.acceptsSamples(true,true,false,true)); // countdown must not control TV
        require(!DirectionCalibration.acceptsSamples(false,true,true,true)); // paused app

        DirectionCalibration up=motion(1),down=motion(2),shake=motion(3);
        float u=up.verticalThreshold(true,.2f),d=down.verticalThreshold(false,.2f);
        require(u>2&&u<4);require(d>3&&d<5);
        float[] h=shake.rightThresholds(.2f);require(h[0]>1&&h[1]>.1f);
        try{motion(0).verticalThreshold(true,.2f);throw new AssertionError("Rest accepted");}catch(IllegalArgumentException expected){}
        try{up.verticalThreshold(false,.2f);throw new AssertionError("Wrong direction accepted");}catch(IllegalArgumentException expected){}
        try{up.rightThresholds(.2f);throw new AssertionError("No right movement accepted");}catch(IllegalArgumentException expected){}
        DirectionDetector detector=new DirectionDetector();detector.configure(u,d,h[0],h[1],.2f);
        long t=2_000_000_000L;for(int i=0;i<30;i++)detector.sample(t+=20_000_000L,0,0,0);
        String detected=null;for(int i=0;i<20;i++){String result=detector.sample(t+=20_000_000L,5,0,0);if(result!=null)detected=result;}
        require("KEY_VOLUP".equals(detected));
        System.out.println("Calibration checks passed");
    }
}
