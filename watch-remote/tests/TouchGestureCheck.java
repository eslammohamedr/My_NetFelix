import com.netfelix.watch.TouchGesture;
public class TouchGestureCheck {
    static void check(String wanted,float x,float y,long ms) {
        if(!java.util.Objects.equals(wanted,TouchGesture.command(x,y,ms))) throw new AssertionError("Unexpected command");
    }
    public static void main(String[] args) {
        check("KEY_ENTER",0,0,100); check("KEY_ENTER",5,-5,200);
        check("KEY_VOLUP",5,-60,300); check("KEY_VOLDOWN",0,60,1200);
        check(null,60,0,200); check(null,60,60,200); check(null,0,20,200);
        check(null,0,0,1000); check(null,0,-60,3000);
        System.out.println("Touch checks passed");
    }
}
