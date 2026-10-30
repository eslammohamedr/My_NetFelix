package com.netfelix.companion;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Phone companion; the shared editor is served by the user's NetFelix server. */
public class MainActivity extends Activity {
    private static final int PICK_PHOTO = 41;
    private static final int SAVE_DESIGN = 42;
    private String exportUrl;
    private volatile boolean destroyed;
    private volatile java.net.DatagramSocket discoverySocket;
    private WebView web;
    private LinearLayout connection;
    private EditText address;
    private TextView status;
    private ValueCallback<Uri[]> photoCallback;
    private String server;
    private boolean mainLoadFailed;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(8, 13, 24));
        root.setFitsSystemWindows(true);
        setContentView(root);

        Button change = new Button(this);
        change.setText(R.string.tv_settings_short);
        LinearLayout navigation = new LinearLayout(this);
        navigation.addView(change, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        Button laptops = new Button(this); laptops.setText(R.string.laptops);
        navigation.addView(laptops, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        root.addView(navigation);
        laptops.setOnClickListener(v -> startActivity(new Intent(this, LaptopsActivity.class).putExtra("server", server)));
        connection = new LinearLayout(this);
        connection.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        connection.setPadding(padding, padding, padding, padding);
        root.addView(connection);
        TextView explanation = new TextView(this);
        explanation.setText(R.string.explanation);
        explanation.setTextColor(Color.rgb(204, 218, 239));
        connection.addView(explanation);
        address = new EditText(this);
        address.setSingleLine(true);
        address.setTextColor(Color.WHITE);
        address.setHint("http://192.168.1.15:8092");
        address.setHintTextColor(Color.LTGRAY);
        address.setContentDescription(getString(R.string.server_address));
        address.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        server = getPreferences(MODE_PRIVATE).getString("server", "http://192.168.1.15:8092");
        address.setText(server);
        connection.addView(address);
        Button connect = new Button(this);
        connect.setText(R.string.connect);
        connection.addView(connect);
        Button discover = new Button(this);
        discover.setText(R.string.discover);
        connection.addView(discover);
        discover.setOnClickListener(v -> discover(discover));
        status = new TextView(this);
        status.setTextColor(Color.rgb(202, 216, 238));
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        connection.addView(status);
        web = new WebView(this);
        root.addView(web, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        configureWeb();
        web.setDownloadListener((url, userAgent, disposition, mime, length) -> {
            Uri target = Uri.parse(url), base = Uri.parse(server);
            if (!base.getEncodedAuthority().equals(target.getEncodedAuthority())
                || !base.getScheme().equals(target.getScheme())
                || target.getPath() == null || !target.getPath().startsWith("/api/tv/appearance/export/")) return;
            exportUrl = url;
            Intent save = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            save.addCategory(Intent.CATEGORY_OPENABLE);
            save.setType("application/json");
            save.putExtra(Intent.EXTRA_TITLE, "netfelix-design.json");
            try { startActivityForResult(save, SAVE_DESIGN); }
            catch (ActivityNotFoundException error) { status.setText(R.string.no_saver); connection.setVisibility(View.VISIBLE); }
        });
        connect.setOnClickListener(v -> connect());
        change.setOnClickListener(v -> connection.setVisibility(connection.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        if (saved != null) exportUrl = saved.getString("exportUrl");
        if (saved != null && web.restoreState(saved) != null) connection.setVisibility(View.GONE);
        else if (getPreferences(MODE_PRIVATE).contains("server")) connect();
        else discover(discover);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWeb() {
        // Only the selected server is navigable; no native JavaScript bridge is exposed.
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.setBackgroundColor(Color.rgb(8, 13, 24));
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView view, String url, Bitmap icon) { mainLoadFailed = false; }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri destination = request.getUrl();
                Uri base = Uri.parse(server);
                boolean sameServer = base.getScheme().equals(destination.getScheme())
                    && base.getEncodedAuthority().equals(destination.getEncodedAuthority());
                if (!sameServer) {
                    connection.setVisibility(View.VISIBLE);
                    status.setText(R.string.external_link);
                }
                return !sameServer;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) return;
                mainLoadFailed = true;
                connection.setVisibility(View.VISIBLE);
                status.setText(R.string.connection_failed);
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (!request.isForMainFrame()) return;
                mainLoadFailed = true; connection.setVisibility(View.VISIBLE); status.setText(R.string.connection_failed);
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (!mainLoadFailed) status.setText(getString(R.string.connected, server));
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (photoCallback != null) photoCallback.onReceiveValue(null);
                photoCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                boolean design = java.util.Arrays.asList(params.getAcceptTypes()).stream().anyMatch(type -> type.contains("json"));
                intent.setType(design ? "application/json" : "image/*");
                if (!design) intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg", "image/png", "image/webp"});
                try { startActivityForResult(intent, PICK_PHOTO); }
                catch (ActivityNotFoundException error) {
                    callback.onReceiveValue(null); photoCallback = null;
                    connection.setVisibility(View.VISIBLE);
                    status.setText(R.string.no_picker);
                }
                return true;
            }
        });
    }

    private void connect() {
        String value = address.getText().toString().trim();
        if (!value.contains("://")) value = "http://" + value;
        Uri uri = Uri.parse(value);
        if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme()))
            || uri.getHost() == null || uri.getUserInfo() != null || uri.getQuery() != null
            || uri.getFragment() != null || !(uri.getPath() == null || uri.getPath().isEmpty() || "/".equals(uri.getPath()))) {
            status.setText(R.string.invalid_address);
            return;
        }
        server = value.replaceAll("/+$", "");
        getPreferences(MODE_PRIVATE).edit().putString("server", server).apply();
        ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(), 0);
        connection.setVisibility(View.GONE);
        web.loadUrl(server + "/tv-customize");
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == SAVE_DESIGN && result == RESULT_OK && data != null && data.getData() != null && exportUrl != null) {
            final Uri destination = data.getData();
            final String source = exportUrl;
            exportUrl = null;
            new Thread(() -> {
                java.net.HttpURLConnection http = null;
                try {
                    http = (java.net.HttpURLConnection) new java.net.URL(source).openConnection();
                    http.setConnectTimeout(5000); http.setReadTimeout(5000); http.setInstanceFollowRedirects(false);
                    if (http.getResponseCode() != 200) throw new java.io.IOException();
                    try (java.io.InputStream input = http.getInputStream();
                         java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream()) {
                        byte[] buffer = new byte[4096]; int count;
                        while ((count = input.read(buffer)) != -1) {
                            if (bytes.size() + count > 5700000) throw new java.io.IOException();
                            bytes.write(buffer, 0, count);
                        }
                        try (java.io.OutputStream output = getContentResolver().openOutputStream(destination)) {
                            if (output == null) throw new java.io.IOException();
                            bytes.writeTo(output);
                        }
                    }
                    runOnUiThread(() -> { if (!destroyed) android.widget.Toast.makeText(this,"Design exported",android.widget.Toast.LENGTH_SHORT).show(); });
                } catch (Exception error) {
                    runOnUiThread(() -> { if (!destroyed) { connection.setVisibility(View.VISIBLE); status.setText(R.string.export_failed); } });
                } finally { if (http != null) http.disconnect(); }
            }, "design-export").start();
        }
        if (request == PICK_PHOTO && photoCallback != null) {
            photoCallback.onReceiveValue(result == RESULT_OK && data != null && data.getData() != null ? new Uri[]{data.getData()} : null);
            photoCallback = null;
        }
    }
    /** Broadcast a nonce-bound query; trust only the responding packet's source IP. */
    private void discover(Button button) {
        button.setEnabled(false);
        status.setText(R.string.discovering);
        new Thread(() -> {
            java.util.Set<String> found = new java.util.LinkedHashSet<>();
            try (java.net.DatagramSocket socket = new java.net.DatagramSocket()) {
                discoverySocket = socket;
                socket.setBroadcast(true); socket.setSoTimeout(600);
                String nonce = java.util.UUID.randomUUID().toString().replace("-", "");
                byte[] query = new org.json.JSONObject().put("service","netfelix-discover").put("nonce",nonce).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
                java.util.Set<java.net.InetAddress> broadcasts = new java.util.HashSet<>();
                broadcasts.add(java.net.InetAddress.getByName("255.255.255.255"));
                try {
                    java.util.Enumeration<java.net.NetworkInterface> interfaces = java.net.NetworkInterface.getNetworkInterfaces();
                    while (interfaces.hasMoreElements()) {
                        java.net.NetworkInterface iface = interfaces.nextElement();
                        if (!iface.isUp() || iface.isLoopback()) continue;
                        for (java.net.InterfaceAddress entry : iface.getInterfaceAddresses()) if (entry.getBroadcast() != null) broadcasts.add(entry.getBroadcast());
                    }
                } catch (java.net.SocketException | NullPointerException | SecurityException ignored) { /* Limited broadcast remains available. */ }
                for (java.net.InetAddress host : broadcasts) {
                    try { socket.send(new java.net.DatagramPacket(query,query.length,host,8093)); } catch (java.io.IOException ignored) { }
                }
                long deadline = android.os.SystemClock.elapsedRealtime() + 4000;
                while (!destroyed && android.os.SystemClock.elapsedRealtime() < deadline) {
                    java.net.DatagramPacket reply = new java.net.DatagramPacket(new byte[512],512);
                    try { socket.receive(reply); } catch (java.net.SocketTimeoutException retry) { continue; }
                    try {
                        org.json.JSONObject value = new org.json.JSONObject(new String(reply.getData(),0,reply.getLength(),java.nio.charset.StandardCharsets.UTF_8));
                        if ("netfelix-companion".equals(value.optString("service")) && nonce.equals(value.optString("nonce")) && value.optInt("version") == 1 && value.optInt("port") == 8092) {
                            String candidate = "http://" + reply.getAddress().getHostAddress() + ":8092";
                            // Discovery only proposes servers that also pass the HTTP identity check.
                            java.net.HttpURLConnection probe = (java.net.HttpURLConnection) new java.net.URL(candidate + "/api/tv/companion/info").openConnection();
                            try {
                                probe.setConnectTimeout(800); probe.setReadTimeout(800); probe.setInstanceFollowRedirects(false);
                                if (probe.getResponseCode() == 200) {
                                    try (java.io.InputStream input = probe.getInputStream();
                                         java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream()) {
                                        byte[] buffer = new byte[256]; int count;
                                        while ((count = input.read(buffer)) != -1) {
                                            if (bytes.size() + count > 1024) throw new java.io.IOException();
                                            bytes.write(buffer,0,count);
                                        }
                                        if ("netfelix-companion".equals(new org.json.JSONObject(bytes.toString("UTF-8")).optString("service"))) found.add(candidate);
                                    }
                                }
                            } finally { probe.disconnect(); }
                        }
                    } catch (Exception ignored) { }
                }
            } catch (Exception ignored) { }
            finally { discoverySocket = null; }
            runOnUiThread(() -> {
                if (destroyed) return;
                button.setEnabled(true);
                if (found.isEmpty()) { status.setText(R.string.discovery_empty); return; }
                String[] servers = found.toArray(new String[0]);
                if (servers.length == 1) { address.setText(servers[0]); status.setText(R.string.discovery_found); }
                else new android.app.AlertDialog.Builder(this).setTitle("Choose your NetFelix server").setItems(servers,(dialog,which) -> address.setText(servers[which])).show();
            });
        }, "netfelix-discovery").start();
    }

    @Override public void onConfigurationChanged(android.content.res.Configuration config) {
        super.onConfigurationChanged(config);
        if (web != null) web.invalidate();
    }

    @Override public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else if (connection.getVisibility() != View.VISIBLE) connection.setVisibility(View.VISIBLE);
        else super.onBackPressed();
    }
    @Override public void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); state.putString("exportUrl",exportUrl); web.saveState(state); }
    @Override protected void onPause() { web.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override protected void onDestroy() {
        destroyed = true;
        if (discoverySocket != null) discoverySocket.close();
        if (photoCallback != null) photoCallback.onReceiveValue(null);
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
