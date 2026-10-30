package com.netfelix.watch;

/** Stops on the first failed command; never retries an already-sent volume press. */
public final class CommandBatch {
    public interface Sender { boolean send() throws Exception; }
    public interface Pause { void between() throws Exception; }
    public static int volumeSteps(String key){return key.equals("KEY_VOLUP")||key.equals("KEY_VOLDOWN")?10:1;}
    public static int run(int count,Sender sender,Pause pause){
        if(count<1 || count>10)throw new IllegalArgumentException("Invalid count");
        int completed=0;
        try{while(completed<count){if(!sender.send())break;completed++;if(completed<count)pause.between();}}
        catch(InterruptedException e){Thread.currentThread().interrupt();}
        catch(Exception ignored){}return completed;
    }
}
