package com.netfelix.watch;

/** Coordinates are in dp. A drag must never fall back to a tap. */
public final class TouchGesture {
    public static String command(float dx, float dy, long durationMs) {
        if (durationMs<0 || durationMs>2500) return null;
        if (Math.abs(dy)>=40 && Math.abs(dy)>Math.abs(dx)*1.3f)
            return dy<0?"KEY_VOLUP":"KEY_VOLDOWN";
        if (Math.abs(dx)<=10 && Math.abs(dy)<=10 && durationMs<=500) return "KEY_ENTER";
        return null;
    }
}
