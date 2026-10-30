package com.netfelix.companion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;

/** Saved laptop launcher. Authentication and encrypted desktop sessions stay in RustDesk. */
public class LaptopsActivity extends Activity {
    private static final String ENGINE = "com.carriez.flutter_hbb";
    private LinearLayout cards;
    private TextView status;
    private EditText name, identifier;
    private JSONObject config;
    private String server;
    private volatile boolean destroyed;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        server = getIntent().getStringExtra("server");
        if (server == null) server = "http://192.168.1.15:8092";
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(8,13,24)); scroll.setFitsSystemWindows(true);
        int gap = (int)(20 * getResources().getDisplayMetrics().density);
        root.setPadding(gap,gap,gap,gap); scroll.addView(root); setContentView(scroll);
        TextView title = label(getString(R.string.laptops),26); root.addView(title);
        root.addView(label(getString(R.string.laptop_intro),15));
        status = label(getString(R.string.laptop_loading),14); status.setAccessibilityLiveRegion(TextView.ACCESSIBILITY_LIVE_REGION_POLITE); root.addView(status);
        Button refresh = button(getString(R.string.laptop_refresh)); root.addView(refresh); refresh.setOnClickListener(v -> load());
        cards = new LinearLayout(this); cards.setOrientation(LinearLayout.VERTICAL); root.addView(cards);
        root.addView(label(getString(R.string.laptop_add_title),20));
        name = new EditText(this); name.setSingleLine(); name.setHint(R.string.laptop_name); name.setTextColor(Color.WHITE); name.setHintTextColor(Color.LTGRAY); name.setContentDescription(getString(R.string.laptop_name)); root.addView(name);
        identifier = new EditText(this); identifier.setSingleLine(); identifier.setHint(R.string.laptop_id); identifier.setTextColor(Color.WHITE); identifier.setHintTextColor(Color.LTGRAY); identifier.setContentDescription(getString(R.string.laptop_id)); root.addView(identifier);
        if (saved != null) { name.setText(saved.getString("name","")); identifier.setText(saved.getString("id","")); }
        Button add = button(getString(R.string.laptop_save)); root.addView(add); add.setOnClickListener(v -> saveLaptop());
        Button setup = button(getString(R.string.laptop_copy_setup)); root.addView(setup); setup.setOnClickListener(v -> copySetup());
        Button engine = button(getString(R.string.laptop_open_engine)); root.addView(engine); engine.setOnClickListener(v -> openEngine());
        Button back = button(getString(R.string.laptop_back)); root.addView(back); back.setOnClickListener(v -> finish());
        load();
    }

    private TextView label(String text, int size) {
        TextView view = new TextView(this); view.setText(text); view.setTextColor(Color.rgb(218,229,245)); view.setTextSize(size); view.setPadding(0,12,0,12); return view;
    }
    private Button button(String text) { Button view = new Button(this); view.setText(text); view.setMinHeight(48); return view; }
    private JSONArray localDevices() {
        try { return new JSONArray(getSharedPreferences("laptop-control",MODE_PRIVATE).getString("devices","[]")); }
        catch (Exception error) { return new JSONArray(); }
    }
    private void saveLaptop() {
        String id = identifier.getText().toString().trim(), title = name.getText().toString().trim();
        if (!id.matches("[A-Za-z0-9_-]{3,64}") || title.isEmpty() || title.length()>64 || title.matches(".*[\\p{Cntrl}].*")) { status.setText(R.string.laptop_invalid); return; }
        try {
            JSONArray existing = localDevices(), next = new JSONArray();
            for (int i=0;i<existing.length();i++) if (!id.equals(existing.getJSONObject(i).optString("id"))) next.put(existing.getJSONObject(i));
            if (next.length()>=30) { status.setText(R.string.laptop_limit); return; }
            next.put(new JSONObject().put("id",id).put("name",title).put("os",getString(R.string.laptop_paired)));
            getSharedPreferences("laptop-control",MODE_PRIVATE).edit().putString("devices",next.toString()).apply();
            name.setText(""); identifier.setText(""); render(); status.setText(R.string.laptop_saved);
        } catch (Exception error) { status.setText(R.string.laptop_invalid); }
    }
    private void render() {
        cards.removeAllViews(); HashSet<String> seen = new HashSet<>();
        JSONArray devices = config == null ? new JSONArray() : config.optJSONArray("devices");
        if (devices == null) devices = new JSONArray();
        JSONArray local = localDevices();
        for (int source=0;source<2;source++) {
            JSONArray list = source==0 ? devices : local;
            for (int i=0;i<list.length();i++) {
                JSONObject device = list.optJSONObject(i); if (device==null) continue;
                String id = device.optString("id"); if (!id.matches("[A-Za-z0-9_-]{3,64}") || !seen.add(id)) continue;
                cards.addView(label(device.optString("name"),22));
                cards.addView(label(getString(R.string.laptop_details,device.optString("os"),id),14));
                Button connect = button(getString(R.string.laptop_connect)); cards.addView(connect); connect.setOnClickListener(v -> connect(id,false));
                Button files = button(getString(R.string.laptop_files)); cards.addView(files); files.setOnClickListener(v -> connect(id,true));
                if (source==1) {
                    Button remove = button(getString(R.string.laptop_remove)); cards.addView(remove);
                    remove.setOnClickListener(v -> {
                        JSONArray next = new JSONArray(), current = localDevices();
                        for (int j=0;j<current.length();j++) if (!id.equals(current.optJSONObject(j).optString("id"))) next.put(current.optJSONObject(j));
                        getSharedPreferences("laptop-control",MODE_PRIVATE).edit().putString("devices",next.toString()).apply(); render();
                    });
                }
            }
        }
        if (seen.isEmpty()) cards.addView(label(getString(R.string.laptop_empty),16));
    }
    private void connect(String id, boolean files) {
        if (config == null) { status.setText(R.string.laptop_no_config); return; }
        String host = config.optString("server"), key = config.optString("key");
        if (!host.matches("[A-Za-z0-9.-]+(:[0-9]{1,5})?") || !key.matches("[A-Za-z0-9+/]{43}=")) { status.setText(R.string.laptop_no_config); return; }
        Uri uri = files ? new Uri.Builder().scheme("rustdesk").authority("file-transfer").encodedPath("/"+id+"/r@"+host).appendQueryParameter("key",key).build()
                        : new Uri.Builder().scheme("rustdesk").authority(id).encodedPath("/r@"+host).appendQueryParameter("key",key).build();
        try { startActivity(new Intent(Intent.ACTION_VIEW,uri).setPackage(ENGINE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); }
        catch (ActivityNotFoundException error) { installHint(); }
    }
    private void copySetup() {
        if (config == null) { status.setText(R.string.laptop_no_config); return; }
        try {
            String json = new JSONObject().put("host",config.getString("server")).put("relay",config.getString("relay")).put("api","").put("key",config.getString("key")).toString();
            String encoded = android.util.Base64.encodeToString(json.getBytes(StandardCharsets.UTF_8),android.util.Base64.URL_SAFE|android.util.Base64.NO_PADDING|android.util.Base64.NO_WRAP);
            String exported = new StringBuilder(encoded).reverse().toString();
            ((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText(getString(R.string.laptops),exported));
            status.setText(R.string.laptop_setup_copied);
        } catch (Exception error) { status.setText(R.string.laptop_no_config); }
    }
    private void openEngine() {
        Intent intent = getPackageManager().getLaunchIntentForPackage(ENGINE);
        if (intent == null) installHint(); else startActivity(intent);
    }
    private void installHint() {
        new AlertDialog.Builder(this).setTitle(R.string.laptop_engine_needed).setMessage(R.string.laptop_engine_explanation)
            .setPositiveButton(R.string.laptop_download,(dialog,which) -> {
                try { startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(server+"/downloads/netfelix-desktop-engine.apk"))); }
                catch (ActivityNotFoundException error) { status.setText(R.string.laptop_no_browser); }
            }).setNegativeButton(android.R.string.cancel,null).show();
    }
    private void load() {
        status.setText(R.string.laptop_loading);
        new Thread(() -> {
            HttpURLConnection http = null;
            try {
                http = (HttpURLConnection)new URL(server+"/api/laptops").openConnection();
                http.setConnectTimeout(5000); http.setReadTimeout(8000); http.setInstanceFollowRedirects(false);
                if (http.getResponseCode()!=200) throw new java.io.IOException();
                JSONObject response;
                try (InputStream input=http.getInputStream(); ByteArrayOutputStream bytes=new ByteArrayOutputStream()) {
                    byte[] buffer=new byte[4096]; int count;
                    while ((count=input.read(buffer))!=-1) { if (bytes.size()+count>65536) throw new java.io.IOException(); bytes.write(buffer,0,count); }
                    response=new JSONObject(bytes.toString("UTF-8"));
                }
                runOnUiThread(() -> { if (!destroyed) { config=response; render(); status.setText(R.string.laptop_connected); } });
            } catch (Exception error) { runOnUiThread(() -> { if (!destroyed) { status.setText(R.string.laptop_load_failed); render(); } }); }
            finally { if (http != null) http.disconnect(); }
        },"laptop-list").start();
    }
    @Override public void onSaveInstanceState(Bundle saved) { super.onSaveInstanceState(saved); saved.putString("name",name.getText().toString()); saved.putString("id",identifier.getText().toString()); }
    @Override protected void onDestroy() { destroyed=true; super.onDestroy(); }
}
