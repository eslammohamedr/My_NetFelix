import com.netfelix.watch.DirectionDetector;
public class DirectionDetectorCheck {
    static DirectionDetector d;static long time;
    static void fresh(){d=new DirectionDetector();time=2_000_000_000L;}
    static String step(float up,float side,float forward){time+=20_000_000L;return d.sample(time,up,side,forward);}
    static void quiet(){for(int i=0;i<30;i++)check(null,step(0,0,0));}
    static void check(String expected,String got){if(!java.util.Objects.equals(expected,got))throw new AssertionError(expected+" != "+got);}
    static String pulse(float up,float side,int frames){String result=null;for(int i=0;i<frames;i++){String key=step(up,side,0);if(key!=null){if(result!=null)throw new AssertionError("Duplicate");result=key;}}return result;}
    public static void main(String[] args){
        fresh();check(null,pulse(5,0,10)); // must hold still first
        fresh();quiet();check("KEY_VOLUP",pulse(5,0,10));check(null,pulse(-5,0,10)); // braking suppressed
        fresh();quiet();check("KEY_VOLDOWN",pulse(-5,0,10));
        fresh();quiet();check(null,step(15,0,0));check(null,pulse(0,0,20)); // spike
        fresh();quiet();check(null,pulse(5,5,15)); // diagonal
        fresh();quiet();check("KEY_ENTER",pulse(0,5,10));check(null,pulse(0,-5,22));
        fresh();quiet();check(null,pulse(0,-5,10));check(null,pulse(0,5,10)); // left plus braking ignored
        fresh();quiet();check(null,step(0,15,0));check(null,pulse(0,0,20));
        fresh();quiet();time+=2_000_000_000L;check(null,pulse(0,5,20)); // discontinuity disarms
        System.out.println("Direction checks passed (synthetic motion; wrist tuning still needed)");
    }
}
