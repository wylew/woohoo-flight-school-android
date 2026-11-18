package io.github.wylew.woohoo;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * On-screen 3DS controls over the game (landscape): circle pad bottom left, D-pad above it, A/B/X/Y bottom right, L and R in
 * the top corners, Select/Start at the bottom centre, and ⇅ at the top centre to swap the one screen shown between the top
 * screen and the touch screen. Touches that start outside every control fall through to the game view, where SDL turns them
 * into touch-screen input (when the touch screen is shown).
 */
final class TouchControls extends View {
    // input.h positional buttons
    private static final int B = 0, A = 1, Y = 2, X = 3, L = 4, R = 5, SELECT = 6, START = 7, UP = 8, DOWN = 9, LEFT = 10, RIGHT = 11;
    private static final int SWAP = 100, HIDE = 101, STICK = 102;

    private static final class Ctl {
        final int id; final String label; final RectF r = new RectF(); final boolean round;
        boolean down;
        Ctl(int id, String label, boolean round) { this.id = id; this.label = label; this.round = round; }
    }

    private final List<Ctl> ctls = new ArrayList<>();
    private final Map<Integer, Ctl> byPointer = new HashMap<>();
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG), edge = new Paint(Paint.ANTI_ALIAS_FLAG), text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float density;
    private Ctl stick;
    private float stickCx, stickCy, stickR, knobX, knobY;
    private boolean hidden;

    TouchControls(Context c) {
        super(c);
        density = c.getResources().getDisplayMetrics().density;
        fill.setStyle(Paint.Style.FILL);
        edge.setStyle(Paint.Style.STROKE); edge.setStrokeWidth(2 * density); edge.setColor(Color.argb(150, 255, 255, 255));
        text.setColor(Color.argb(210, 255, 255, 255)); text.setTextAlign(Paint.Align.CENTER); text.setFakeBoldText(true);
        for (Object[] o : new Object[][] {
                { A, "A", true }, { B, "B", true }, { X, "X", true }, { Y, "Y", true }, { L, "L", false }, { R, "R", false },
                { SELECT, "SELECT", false }, { START, "START", false }, { UP, "▲", false }, { DOWN, "▼", false },
                { LEFT, "◀", false }, { RIGHT, "▶", false }, { SWAP, "⇅", false }, { HIDE, "◐", false } })
            ctls.add(new Ctl((Integer) o[0], (String) o[1], (Boolean) o[2]));
        stick = new Ctl(STICK, "", true);
        ctls.add(stick);
    }

    private Ctl get(int id) { for (Ctl c : ctls) if (c.id == id) return c; return null; }

    private static void place(RectF r, float cx, float cy, float w, float h) { r.set(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2); }

    @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
        float u = Math.min(w, h) / 9f;   // layout unit
        float btn = 1.25f * u, m = 0.3f * u;
        // face buttons, diamond at the bottom right
        float fx = w - m - 2.1f * u, fy = h - m - 2.1f * u, d = 1.15f * u;
        place(get(A).r, fx + d, fy, btn, btn); place(get(B).r, fx, fy + d, btn, btn);
        place(get(X).r, fx, fy - d, btn, btn); place(get(Y).r, fx - d, fy, btn, btn);
        // circle pad at the bottom left
        stickR = 1.7f * u; stickCx = m + stickR + 0.2f * u; stickCy = h - m - stickR - 0.2f * u;
        place(stick.r, stickCx, stickCy, 2 * stickR * 1.25f, 2 * stickR * 1.25f);
        knobX = stickCx; knobY = stickCy;
        // D-pad above the circle pad
        float dx = stickCx, dy = stickCy - stickR - 2.0f * u, ds = 0.9f * u;
        place(get(UP).r, dx, dy - ds, ds, ds); place(get(DOWN).r, dx, dy + ds, ds, ds);
        place(get(LEFT).r, dx - ds, dy, ds, ds); place(get(RIGHT).r, dx + ds, dy, ds, ds);
        // shoulders
        place(get(L).r, m + 1.2f * u, m + 0.5f * u, 2.4f * u, u); place(get(R).r, w - m - 1.2f * u, m + 0.5f * u, 2.4f * u, u);
        // select/start, swap, hide
        place(get(SELECT).r, w / 2f - 1.3f * u, h - m - 0.35f * u, 2.0f * u, 0.7f * u);
        place(get(START).r, w / 2f + 1.3f * u, h - m - 0.35f * u, 2.0f * u, 0.7f * u);
        place(get(SWAP).r, w / 2f, m + 0.5f * u, 1.4f * u, u);
        place(get(HIDE).r, w / 2f + 1.6f * u, m + 0.5f * u, 0.9f * u, 0.9f * u);
        text.setTextSize(0.45f * u);
    }

    @Override protected void onDraw(Canvas c) {
        for (Ctl k : ctls) {
            if (hidden && k.id != HIDE) continue;
            fill.setColor(k.down ? Color.argb(120, 255, 255, 255) : Color.argb(55, 0, 0, 0));
            if (k == stick) {
                c.drawCircle(stickCx, stickCy, stickR, fill); c.drawCircle(stickCx, stickCy, stickR, edge);
                fill.setColor(Color.argb(140, 255, 255, 255));
                c.drawCircle(knobX, knobY, stickR * 0.45f, fill);
                continue;
            }
            if (k.round) { c.drawOval(k.r, fill); c.drawOval(k.r, edge); }
            else { float rr = Math.min(k.r.width(), k.r.height()) / 3; c.drawRoundRect(k.r, rr, rr, fill); c.drawRoundRect(k.r, rr, rr, edge); }
            c.drawText(k.label, k.r.centerX(), k.r.centerY() - (text.descent() + text.ascent()) / 2, text);
        }
    }

    private Ctl hit(float x, float y) {
        for (Ctl k : ctls) {
            if (hidden && k.id != HIDE) continue;
            RectF r = k.r; float pad = k == stick ? 0 : 0.15f * Math.min(r.width(), r.height());
            if (x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad) return k;
        }
        return null;
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        int a = e.getActionMasked(), i = e.getActionIndex();
        switch (a) {
        case MotionEvent.ACTION_DOWN: case MotionEvent.ACTION_POINTER_DOWN: {
            Ctl k = hit(e.getX(i), e.getY(i));
            if (k == null) return a != MotionEvent.ACTION_DOWN;   // first finger outside the controls: the game view gets it
            byPointer.put(e.getPointerId(i), k);
            press(k, true, e.getX(i), e.getY(i));
            return true;
        }
        case MotionEvent.ACTION_MOVE:
            for (int p = 0; p < e.getPointerCount(); p++) {
                Ctl k = byPointer.get(e.getPointerId(p));
                if (k == stick) moveStick(e.getX(p), e.getY(p));
            }
            return true;
        case MotionEvent.ACTION_UP: case MotionEvent.ACTION_POINTER_UP: case MotionEvent.ACTION_CANCEL: {
            if (a == MotionEvent.ACTION_CANCEL) { for (Ctl k : byPointer.values()) press(k, false, 0, 0); byPointer.clear(); return true; }
            Ctl k = byPointer.remove(e.getPointerId(i));
            if (k != null) press(k, false, 0, 0);
            return true;
        }
        }
        return true;
    }

    private void press(Ctl k, boolean down, float x, float y) {
        if (k.down == down) return;
        k.down = down;
        if (down) performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
        if (k == stick) { if (down) moveStick(x, y); else { knobX = stickCx; knobY = stickCy; GameActivity.nativeStick(0, 0); } }
        else if (k.id == SWAP) { if (down) GameActivity.nativeSwapScreen(); }
        else if (k.id == HIDE) { if (down) hidden = !hidden; }
        else GameActivity.nativeButton(k.id, down);
        invalidate();
    }

    private void moveStick(float x, float y) {
        float dx = x - stickCx, dy = y - stickCy, len = (float) Math.hypot(dx, dy);
        if (len > stickR) { dx *= stickR / len; dy *= stickR / len; }
        knobX = stickCx + dx; knobY = stickCy + dy;
        GameActivity.nativeStick((int) (dx / stickR * 32767), (int) (-dy / stickR * 32767));
        invalidate();
    }
}
