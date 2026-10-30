package com.netfelix.watch;

import android.app.Activity;
import android.os.*;
import android.hardware.*;
import android.view.*;
import android.widget.*;
import android.graphics.Color;

public class DirectionActivity extends Activity implements SensorEventListener {
    private final DirectionDetector detector=new DirectionDetector();
    private SensorManager sensors;
    private final float[] rotation=new float[9],rightAxis={1,0,0};
    private long orientationTime,lastDisplay,lastEvent;
    private int accelerationSamples,orientationSamples;
    private boolean referenceSet,busy;
    private TextView status,readings;
    private Switch active,live;
    private boolean gentle=true;
    private EditText server;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private ScrollView scroll;
    private int calibrationStep=-1,calibrationGeneration;
    private boolean capturing;
    private DirectionCalibration capture;
    private android.app.AlertDialog calibrationDialog;
    private float noise=0.3f,upLimit=3.2f,downLimit=3.2f,sideLimit=2f,speedLimit=0.3f;
    private android.content.SharedPreferences profile;
    private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);sensors=(SensorManager)getSystemService(SENSOR_SERVICE);
        // Remove obsolete recordings even when upgrading without a connected development computer.
        deleteFile("gesture-training.json");
        getSharedPreferences("MainActivity",MODE_PRIVATE).edit().remove("knockCaptured").remove("axesCalibrated")
            .remove("knock0").remove("knock1").remove("knock2").remove("twist0").remove("twist1").remove("twist2").apply();
        scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);root.setPadding(dp(24),dp(24),dp(24),dp(30));root.setBackgroundColor(Color.BLACK);scroll.addView(root);
        status=new TextView(this);status.setGravity(Gravity.CENTER);status.setTextSize(17);status.setText("Direction remote");root.addView(status);
        profile=getSharedPreferences("direction-profile",MODE_PRIVATE);
        gentle=profile.getBoolean("gentle",true);
        referenceSet=profile.getBoolean("saved",false);
        if(referenceSet){rightAxis[0]=profile.getFloat("rightX",1);rightAxis[1]=profile.getFloat("rightY",0);
            noise=profile.getFloat("noise",0.3f);upLimit=profile.getFloat("up",3.2f);downLimit=profile.getFloat("down",3.2f);sideLimit=profile.getFloat("side",2);speedLimit=profile.getFloat("speed",0.3f);
            applySensitivity();}
        readings=new TextView(this);readings.setTextSize(12);readings.setGravity(Gravity.CENTER);readings.setText(referenceSet?"Saved calibration loaded":"Calibrate your movements");root.addView(readings);
        Button checkSensors=new Button(this);checkSensors.setText("Check sensors");root.addView(checkSensors);
        checkSensors.setOnClickListener(v->{
            live.setChecked(false);
            if(!active.isChecked())active.setChecked(true);
            accelerationSamples=orientationSamples=0;status.setText("Checking sensors for 2 seconds…");scroll.smoothScrollTo(0,0);
            handler.postDelayed(()->{
                String result="Acceleration: "+accelerationSamples+" samples\nOrientation: "+orientationSamples+" samples";
                status.setText(accelerationSamples>0 && orientationSamples>0?"Sensors receiving data":"Sensor data missing");
                readings.setText(result);android.util.Log.i("NetFelixDirection",result);
                new android.app.AlertDialog.Builder(this).setTitle("Sensor check").setMessage(result).setPositiveButton("OK",null).show();
            },2000);
        });
        active=new Switch(this);active.setText("Detect movements");root.addView(active);
        live=new Switch(this);live.setText("Control TV");root.addView(live);
        Button directTest=new Button(this);directTest.setText("Test volume +");root.addView(directTest);
        directTest.setOnClickListener(v->send("KEY_VOLUP"));
        Switch sensitivity=new Switch(this);sensitivity.setText("Gentle movements");sensitivity.setChecked(gentle);root.addView(sensitivity);
        sensitivity.setOnCheckedChangeListener((v,on)->{gentle=on;profile.edit().putBoolean("gentle",on).apply();applySensitivity();
            Toast.makeText(this,on?"Gentler thresholds enabled":"Original calibrated thresholds",Toast.LENGTH_SHORT).show();});
        Button neutral=new Button(this);neutral.setText("Set starting position");root.addView(neutral);
        neutral.setText("Calibrate position & movements");
        neutral.setOnClickListener(v->{
            live.setChecked(false);
            if(!active.isChecked())active.setChecked(true);
            if(!active.isChecked())return;
            calibrationStep=0;calibrationGeneration++;promptCalibration();
        });
        Button cancel=new Button(this);cancel.setText("Cancel calibration");root.addView(cancel);
        cancel.setOnClickListener(v->cancelCalibration());
        Button values=new Button(this);values.setText("Show saved values");root.addView(values);
        values.setOnClickListener(v->{
            if(!profile.getBoolean("saved",false)){Toast.makeText(this,"Complete calibration first",Toast.LENGTH_SHORT).show();return;}
            new android.app.AlertDialog.Builder(this).setTitle("Saved calibration")
                .setMessage(String.format(java.util.Locale.US,"Up: %.2f m/s²\nDown: %.2f m/s²\nSide: %.2f m/s²\nRight speed estimate: %.2f m/s\nRest noise: %.2f m/s²\nRight direction: %.2f, %.2f",profile.getFloat("up",0),profile.getFloat("down",0),profile.getFloat("side",0),profile.getFloat("speed",0),profile.getFloat("noise",0),profile.getFloat("rightX",0),profile.getFloat("rightY",0)))
                .setPositiveButton("OK",null).show();
        });
        TextView help=new TextView(this);help.setText("1. Enable detection.\n2. Calibrate position and movements once; values are saved.\n3. Move hand UP: volume +10.\nMove DOWN: volume −10.\nMove RIGHT once: play/pause.\nPause between commands. Test with Control TV OFF first.");help.setTextSize(13);root.addView(help);
        server=new EditText(this);server.setSingleLine(true);server.setText(getSharedPreferences("MainActivity",MODE_PRIVATE).getString("server","http://192.168.1.15:8092"));root.addView(server);
        Button save=new Button(this);save.setText("Save server");root.addView(save);
        save.setOnClickListener(v->{try{java.net.URI u=java.net.URI.create(server.getText().toString().trim());if(u.getHost()==null || !("http".equals(u.getScheme()) || "https".equals(u.getScheme())) || u.getRawUserInfo()!=null || u.getRawQuery()!=null || u.getRawFragment()!=null || !(u.getPath().isEmpty() || u.getPath().equals("/")))throw new IllegalArgumentException();getSharedPreferences("MainActivity",MODE_PRIVATE).edit().putString("server",u.toString().replaceAll("/+$","")).apply();Toast.makeText(this,"Server saved",Toast.LENGTH_SHORT).show();}catch(Exception e){Toast.makeText(this,"Invalid server address",Toast.LENGTH_SHORT).show();}});
        active.setOnCheckedChangeListener((v,on)->{
            sensors.unregisterListener(this);detector.reset();referenceSet=profile.getBoolean("saved",false);orientationTime=lastEvent=0;
            if(on){
                Sensor a=sensors.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION),r=sensors.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR);
                if(a==null || r==null || !sensors.registerListener(this,a,20000) || !sensors.registerListener(this,r,20000)){active.setChecked(false);status.setText("Sensors unavailable");return;}
                getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);status.setText(referenceSet?"Saved calibration active":"Calibrate movements next");
            }else{cancelCalibration();live.setChecked(false);getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);status.setText("Detection off");}
        });
        live.setOnCheckedChangeListener((v,on)->{if(on && (!active.isChecked() || !referenceSet || calibrationStep>=0)){live.setChecked(false);Toast.makeText(this,"Enable detection and set position first",Toast.LENGTH_LONG).show();}});
        setContentView(scroll);
    }
    @Override public void onSensorChanged(SensorEvent e){
        if(e.sensor.getType()==Sensor.TYPE_ROTATION_VECTOR){orientationSamples++;SensorManager.getRotationMatrixFromVector(rotation,e.values);orientationTime=e.timestamp;return;}
        accelerationSamples++;
        if(!DirectionCalibration.acceptsSamples(active.isChecked(),referenceSet,capturing,calibrationStep>=0))return;
        if(Math.abs(e.timestamp-orientationTime)>200_000_000L){detector.reset();readings.setText("Waiting for orientation…");return;}
        float x=rotation[0]*e.values[0]+rotation[1]*e.values[1]+rotation[2]*e.values[2];
        float y=rotation[3]*e.values[0]+rotation[4]*e.values[1]+rotation[5]*e.values[2];
        float z=rotation[6]*e.values[0]+rotation[7]*e.values[1]+rotation[8]*e.values[2];
        float right=x*rightAxis[0]+y*rightAxis[1],depth=-x*rightAxis[1]+y*rightAxis[0];
        if(capturing){
            capture.sample(e.timestamp,z,right,depth);
            if(e.timestamp-lastDisplay>250_000_000L){lastDisplay=e.timestamp;readings.setText("Calibration receiving: "+capture.samples+" samples");}
            return;
        }
        if(calibrationStep>=0)return;
        String key=detector.sample(e.timestamp,z,right,depth);lastEvent=e.timestamp;
        if(e.timestamp-lastDisplay>500_000_000L){lastDisplay=e.timestamp;
            String info=String.format(java.util.Locale.US,"Up %.1f • Side %.1f m/s²\n%s",z,right,detector.status());
            readings.setText(info);android.util.Log.d("NetFelixDirection",info+" forward="+depth);
        }
        if(key!=null){String label=key.equals("KEY_ENTER")?"Play/pause":key.equals("KEY_VOLUP")?"Volume up":"Volume down";
            status.setText(label+(live.isChecked()?" • sending":" • TEST"));status.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);android.util.Log.i("NetFelixDirection",key+" live="+live.isChecked());if(live.isChecked())send(key,CommandBatch.volumeSteps(key));}
    }
    private void promptCalibration(){
        String[] instructions={"Hold your arm comfortably, watch face toward you. Keep completely still.","Raise your hand UP once, then hold it there until saved.","Lower your hand DOWN once, then hold it there until saved.","Move your hand RIGHT once, then hold it there until saved."};
        calibrationDialog=new android.app.AlertDialog.Builder(this).setTitle("Calibration "+(calibrationStep+1)+"/4")
            .setMessage(instructions[calibrationStep]+"\nTap Start, wait for GO, then move. TV commands are off.")
            .setPositiveButton("Start",(d,w)->startCapture())
            .setNegativeButton("Cancel",(d,w)->cancelCalibration()).setOnCancelListener(d->cancelCalibration()).show();
    }
    private void startCapture(){
        int token=++calibrationGeneration;
        status.setText("Hold still: 2…");scroll.smoothScrollTo(0,0);
        handler.postDelayed(()->{if(token==calibrationGeneration)status.setText("Hold still: 1…");},1000);
        handler.postDelayed(()->{
            if(token!=calibrationGeneration)return;
            if(SystemClock.elapsedRealtimeNanos()-orientationTime>300_000_000L){status.setText("No orientation readings; retry");promptCalibration();return;}
            if(calibrationStep==0){
                float x=rotation[0],y=rotation[3],n=(float)Math.hypot(x,y);
                if(n<0.3f){status.setText("Hold watch face upright toward you");promptCalibration();return;}
                rightAxis[0]=x/n;rightAxis[1]=y/n;
            }
            capture=new DirectionCalibration();capturing=true;status.setText(calibrationStep==0?"Recording rest — keep still":"GO — move now");
            handler.postDelayed(()->finishCapture(token),2500);
        },2000);
    }
    private void finishCapture(int token){
        if(token!=calibrationGeneration)return;capturing=false;
        try{
            android.util.Log.i("NetFelixDirection","Calibration step="+calibrationStep+" samples="+capture.samples);
            if(capture.samples<30)throw new IllegalArgumentException("Only "+capture.samples+" fresh samples received. Check sensors and retry.");
            if(calibrationStep==0){if(capture.noise>0.8f)throw new IllegalArgumentException("Arm moved during rest. Retry.");noise=Math.max(0.1f,capture.noise);}
            else if(calibrationStep==1)upLimit=capture.verticalThreshold(true,noise);
            else if(calibrationStep==2)downLimit=capture.verticalThreshold(false,noise);
            else{float[] values=capture.rightThresholds(noise);sideLimit=values[0];speedLimit=values[1];}
            calibrationStep++;
            if(calibrationStep<4){status.setText("Saved step "+calibrationStep+"/4");promptCalibration();}
            else{
                profile.edit().putBoolean("saved",true).putFloat("rightX",rightAxis[0]).putFloat("rightY",rightAxis[1])
                    .putFloat("noise",noise).putFloat("up",upLimit).putFloat("down",downLimit).putFloat("side",sideLimit).putFloat("speed",speedLimit).apply();
                calibrationStep=-1;referenceSet=true;applySensitivity();
                status.setText("Calibration saved. Test movements now.");
                readings.setText(String.format(java.util.Locale.US,"Up %.2f • Down %.2f\nSide %.2f m/s² • speed %.2f m/s",upLimit,downLimit,sideLimit,speedLimit));
            }
        }catch(IllegalArgumentException error){status.setText(error.getMessage());Toast.makeText(this,error.getMessage(),Toast.LENGTH_LONG).show();promptCalibration();}
    }
    private void cancelCalibration(){
        calibrationGeneration++;handler.removeCallbacksAndMessages(null);capturing=false;calibrationStep=-1;
        referenceSet=profile!=null && profile.getBoolean("saved",false);
        if(referenceSet){rightAxis[0]=profile.getFloat("rightX",1);rightAxis[1]=profile.getFloat("rightY",0);noise=profile.getFloat("noise",0.3f);
            upLimit=profile.getFloat("up",3.2f);downLimit=profile.getFloat("down",3.2f);sideLimit=profile.getFloat("side",2);speedLimit=profile.getFloat("speed",0.3f);}
        applySensitivity();
    }
    private void applySensitivity(){
        float factor=gentle?0.60f:1f;
        float floor=Math.max(0.8f,noise*2);
        detector.configure(Math.max(floor,upLimit*factor),Math.max(floor,downLimit*factor),Math.max(floor,sideLimit*factor),Math.max(0.12f,speedLimit*factor),Math.max(0.1f,noise));
    }
    private void send(String key){send(key,1);} // Direct connection test remains one press.
    private void send(String key,int count){
        if(busy){status.setText("Waiting for previous command…");return;}busy=true;status.setText("Sending "+key.substring(4)+" ×"+count+"…");
        android.util.Log.i("NetFelixDirection","HTTP batch "+key+" count="+count);
        final String base=getSharedPreferences("MainActivity",MODE_PRIVATE).getString("server","http://192.168.1.15:8092");
        new Thread(()->{
            int completed=CommandBatch.run(count,()->sendOne(base,key),()->Thread.sleep(100));
            android.util.Log.i("NetFelixDirection","HTTP batch response "+key+" completed="+completed+"/"+count);
            runOnUiThread(()->{busy=false;status.setText(completed==count?"Sent "+key.substring(4)+" ×"+count:"Sent "+completed+"/"+count+"; TV/server command failed");});
        }).start();
    }
    private boolean sendOne(String base,String key) throws Exception {
        java.net.HttpURLConnection c=null;
        try{
            c=(java.net.HttpURLConnection)java.net.URI.create(base+"/api/tv/send_key").toURL().openConnection();c.setConnectTimeout(4000);c.setReadTimeout(8000);c.setInstanceFollowRedirects(false);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");
            try(java.io.OutputStream out=c.getOutputStream()){out.write(new org.json.JSONObject().put("key",key).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
            if(c.getResponseCode()!=200)return false;
            try(java.io.InputStream in=c.getInputStream()){
                java.io.ByteArrayOutputStream b=new java.io.ByteArrayOutputStream();byte[] data=new byte[1024];int n;
                while((n=in.read(data))!=-1){if(b.size()+n>65536)throw new java.io.IOException();b.write(data,0,n);}
                return new org.json.JSONObject(b.toString("UTF-8")).optBoolean("success",false);
            }
        }finally{if(c!=null)c.disconnect();}
    }
    @Override public void onAccuracyChanged(Sensor s,int a){}
    @Override protected void onPause(){super.onPause();cancelCalibration();if(calibrationDialog!=null)calibrationDialog.dismiss();active.setChecked(false);sensors.unregisterListener(this);}
}
