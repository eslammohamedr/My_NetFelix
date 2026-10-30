package com.netfelix.watch;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.widget.*;
import android.graphics.Color;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONObject;

/** Dedicated non-scrolling surface: swipes change volume rather than scrolling settings. */
public class TouchActivity extends Activity {
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private TextView status;
    private boolean busy, cancelled;
    private float startX,startY,maxTravel;
    private long startTime;
    private int dp(float size) { return Math.round(size*getResources().getDisplayMetrics().density); }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL); root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(28),dp(24),dp(28),dp(24)); root.setBackgroundColor(Color.BLACK);
        status=new TextView(this); status.setText("Ready"); status.setTextSize(12); status.setGravity(Gravity.CENTER);
        status.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
        root.addView(status,new LinearLayout.LayoutParams(-1,dp(28)));
        TextView pad=new TextView(this);
        pad.setText("↑ Swipe up: Volume +\n▶ / Ⅱ Tap: Play/pause\n↓ Swipe down: Volume −");
        pad.setTextColor(Color.WHITE); pad.setTextSize(14); pad.setGravity(Gravity.CENTER);
        pad.setBackgroundColor(Color.rgb(20,40,65)); pad.setContentDescription("TV touch control. Tap for play or pause, swipe up for volume up, swipe down for volume down.");
        pad.setClickable(true); pad.setOnClickListener(v -> send("KEY_ENTER"));
        root.addView(pad,new LinearLayout.LayoutParams(-1,0,1));
        pad.setOnTouchListener((view,event) -> {
            switch(event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    startX=event.getX(); startY=event.getY(); startTime=event.getEventTime(); cancelled=false; maxTravel=0; return true;
                case MotionEvent.ACTION_POINTER_DOWN: case MotionEvent.ACTION_CANCEL:
                    cancelled=true; return true;
                case MotionEvent.ACTION_MOVE:
                    maxTravel=Math.max(maxTravel,Math.max(Math.abs(event.getX()-startX),Math.abs(event.getY()-startY)));
                    return true;
                case MotionEvent.ACTION_UP:
                    if (!cancelled) {
                        float density=getResources().getDisplayMetrics().density;
                        String key=TouchGesture.command((event.getX()-startX)/density,(event.getY()-startY)/density,event.getEventTime()-startTime);
                        if ("KEY_ENTER".equals(key) && maxTravel/density<=10) view.performClick();
                        else if ("KEY_ENTER".equals(key)) status.setText("Tap without dragging");
                        else if (key!=null) send(key);
                        else status.setText("Swipe straight up or down");
                    }
                    return true;
                default: return true;
            }
        });
        Button settings=new Button(this); settings.setText("Settings"); settings.setTextSize(12);
        root.addView(settings,new LinearLayout.LayoutParams(-1,dp(40)));
        settings.setOnClickListener(v -> startActivity(new android.content.Intent(this,DirectionActivity.class)));
        setContentView(root);
    }
    private void send(String key) {
        if (busy) { status.setText("Wait for previous command…"); return; }
        String base=getSharedPreferences("MainActivity",MODE_PRIVATE).getString("server","http://192.168.1.15:8092");
        busy=true; status.setText("Sending…");
        android.util.Log.i("NetFelixTouch","Request "+key);
        network.execute(() -> {
            HttpURLConnection c=null; String result;
            try {
                c=(HttpURLConnection)URI.create(base+"/api/tv/send_key").toURL().openConnection();
                c.setConnectTimeout(4000); c.setReadTimeout(8000); c.setInstanceFollowRedirects(false);
                c.setRequestMethod("POST"); c.setDoOutput(true); c.setRequestProperty("Content-Type","application/json");
                byte[] body=new JSONObject().put("key",key).toString().getBytes(StandardCharsets.UTF_8);
                c.setFixedLengthStreamingMode(body.length);
                try(java.io.OutputStream out=c.getOutputStream()) { out.write(body); }
                if(c.getResponseCode()!=200) throw new java.io.IOException("HTTP "+c.getResponseCode());
                java.io.ByteArrayOutputStream bytes=new java.io.ByteArrayOutputStream();
                try(java.io.InputStream in=c.getInputStream()) {
                    byte[] buffer=new byte[1024]; int n;
                    while((n=in.read(buffer))!=-1) { if(bytes.size()+n>65536) throw new java.io.IOException("Response too large"); bytes.write(buffer,0,n); }
                }
                boolean success=new JSONObject(bytes.toString("UTF-8")).optBoolean("success",false);
                result=success?(key.equals("KEY_ENTER")?"Sent: Play/pause":key.equals("KEY_VOLUP")?"Sent: Volume up":"Sent: Volume down"):"TV command failed";
                android.util.Log.i("NetFelixTouch","Response "+key+" success="+success);
            } catch(Exception e) { result="Server/TV connection failed"; android.util.Log.w("NetFelixTouch","Failed "+key+": "+e.getClass().getSimpleName()); }
            finally { if(c!=null)c.disconnect(); }
            final String message=result;
            runOnUiThread(() -> { busy=false; status.setText(message); });
        });
    }
    @Override protected void onDestroy() { network.shutdownNow(); super.onDestroy(); }
}
