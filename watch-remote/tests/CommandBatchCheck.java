import com.netfelix.watch.CommandBatch;
public class CommandBatchCheck {
    static void require(boolean ok){if(!ok)throw new AssertionError();}
    public static void main(String[] args){
        for(String key:new String[]{"KEY_VOLUP","KEY_VOLDOWN","KEY_ENTER"}){
            int[] calls={0},pauses={0};int n=CommandBatch.volumeSteps(key);
            int sent=CommandBatch.run(n,()->{calls[0]++;return true;},()->pauses[0]++);
            require(sent==(key.equals("KEY_ENTER")?1:10));require(calls[0]==sent);require(pauses[0]==sent-1);
        }
        int[] calls={0};int sent=CommandBatch.run(10,()->++calls[0]<=3,()->{});
        require(sent==3&&calls[0]==4); // stop without replaying successful presses
        calls[0]=0;sent=CommandBatch.run(10,()->{if(++calls[0]==2)throw new java.io.IOException();return true;},()->{});
        require(sent==1&&calls[0]==2);
        System.out.println("Volume batch checks passed");
    }
}
