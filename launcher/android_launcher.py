"""Woohoo! Flight School - Android builder window: pick your dump, build the APK, install it on your phone.

Runs tools/android/build_apk.py (see there for the stages). Started by ../android-builder.sh, which on Bazzite runs it in a
distrobox with the build tools; it also runs anywhere with Python 3 + Tk, a JDK, CMake, Ninja and git.
Remembers the last dump and options in ~/.config/pwr-android/builder.json.
"""
import json, os, queue, shutil, subprocess, sys, threading, time, tkinter as tk
from tkinter import filedialog, messagebox, ttk

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools', 'android'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import build_apk  # noqa: E402
import pipeline  # noqa: E402
from pipeline import PipelineError  # noqa: E402

CONFIG = os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')), 'pwr-android', 'builder.json')
BG, PANEL, FG, DIM, ACCENT, OK, BAD = '#14202b', '#1d2d3b', '#e8eef3', '#93a7b8', '#f2a541', '#7ccf8a', '#ff7b72'


def load_config():
    try: return json.load(open(CONFIG))
    except (OSError, ValueError): return {}


def save_config(c):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True); json.dump(c, open(CONFIG, 'w'), indent=2)


class App:
    def __init__(self, root):
        self.root = root; self.cfg = load_config(); self.q = queue.Queue(); self.busy = False
        self.home = build_apk.default_home()
        root.title('Woohoo! Flight School - Android builder'); root.configure(bg=BG); root.minsize(760, 560)
        try: root.iconphoto(True, tk.PhotoImage(file=os.path.join(REPO, 'launcher', 'assets', 'icon.png')))
        except tk.TclError: pass
        st = ttk.Style(root); st.theme_use('clam')
        st.configure('.', background=BG, foreground=FG, fieldbackground=PANEL, font=('Sans', 10))
        st.configure('Panel.TFrame', background=PANEL); st.configure('Panel.TLabel', background=PANEL)
        st.configure('Dim.TLabel', background=PANEL, foreground=DIM)
        st.configure('H.TLabel', background=BG, foreground=ACCENT, font=('Sans', 15, 'bold'))
        st.configure('S.TLabel', background=PANEL, foreground=FG, font=('Sans', 11, 'bold'))
        st.configure('TButton', background='#2b4256', foreground=FG, borderwidth=0, padding=(12, 6))
        st.map('TButton', background=[('disabled', '#22313f'), ('active', '#36536b')], foreground=[('disabled', '#5d7083')])
        st.configure('Go.TButton', background=ACCENT, foreground='#1a1a1a', font=('Sans', 10, 'bold'))
        st.map('Go.TButton', background=[('disabled', '#6b5634'), ('active', '#ffbe5c')])
        st.configure('TCheckbutton', background=PANEL, foreground=FG); st.map('TCheckbutton', background=[('active', PANEL)])
        st.configure('TProgressbar', background=ACCENT, troughcolor=PANEL, borderwidth=0)

        ttk.Label(root, text='Woohoo! Flight School  ·  Android', style='H.TLabel').pack(anchor='w', padx=16, pady=(14, 2))
        ttk.Label(root, text='Builds an APK from your own decrypted Pilotwings Resort (USA) dump. The APK contains the game: '
                  'keep it to your own devices.', background=BG, foreground=DIM, wraplength=720).pack(anchor='w', padx=16, pady=(0, 10))

        # 1 dump
        p1 = self.panel('1  Your dump')
        row = ttk.Frame(p1, style='Panel.TFrame'); row.pack(fill='x')
        self.rom = tk.StringVar(value=self.cfg.get('rom', ''))
        ttk.Entry(row, textvariable=self.rom).pack(side='left', fill='x', expand=True, padx=(0, 8))
        ttk.Button(row, text='Browse...', command=self.browse).pack(side='left')
        self.rom_status = ttk.Label(p1, text='.cia, .3ds/.cci or .cxi, decrypted', style='Dim.TLabel'); self.rom_status.pack(anchor='w', pady=(6, 0))

        # 2 build
        p2 = self.panel('2  Build the APK')
        self.shaderc = tk.BooleanVar(value=self.cfg.get('shaderc', True))
        ttk.Checkbutton(p2, text='Faster vertex shaders (compiles a shader compiler for the phone once: +10-20 min on the first build)',
                        variable=self.shaderc).pack(anchor='w')
        row = ttk.Frame(p2, style='Panel.TFrame'); row.pack(fill='x', pady=(8, 0))
        self.build_btn = ttk.Button(row, text='Build APK', style='Go.TButton', command=self.build); self.build_btn.pack(side='left')
        ttk.Button(row, text='Open APK folder', command=self.open_folder).pack(side='left', padx=8)
        self.stage = ttk.Label(row, text=self.apk_status(), style='Dim.TLabel'); self.stage.pack(side='left', padx=8)
        self.bar = ttk.Progressbar(p2, maximum=7, mode='determinate'); self.bar.pack(fill='x', pady=(8, 0))

        # 3 phone
        p3 = self.panel('3  Install on your phone')
        ttk.Label(p3, text='Turn on Developer options > USB debugging (or Wireless debugging) on the phone, then connect it. '
                  'Or copy the APK to the phone any way you like and open it there.', style='Dim.TLabel', wraplength=700).pack(anchor='w')
        row = ttk.Frame(p3, style='Panel.TFrame'); row.pack(fill='x', pady=(8, 0))
        self.install_btn = ttk.Button(row, text='Install APK', command=self.install); self.install_btn.pack(side='left')
        ttk.Button(row, text='Pair over Wi-Fi...', command=self.pair).pack(side='left', padx=8)
        ttk.Button(row, text='Refresh', command=self.refresh_devices).pack(side='left')
        ttk.Button(row, text='Get phone log', command=self.pull_log).pack(side='left', padx=8)
        self.dev_status = ttk.Label(p3, text='', style='Dim.TLabel'); self.dev_status.pack(anchor='w', pady=(6, 0))

        # log
        lf = ttk.Frame(root); lf.pack(fill='both', expand=True, padx=16, pady=(4, 14))
        self.log_w = tk.Text(lf, bg='#0d151c', fg='#c9d6e0', insertbackground=FG, relief='flat', font=('Monospace', 9), wrap='none', height=12)
        sb = ttk.Scrollbar(lf, command=self.log_w.yview); self.log_w.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); self.log_w.pack(side='left', fill='both', expand=True)

        if self.rom.get(): self.verify_async()
        self.refresh_devices(); self.root.after(80, self.pump)

    def panel(self, title):
        f = ttk.Frame(self.root, style='Panel.TFrame', padding=12); f.pack(fill='x', padx=16, pady=4)
        ttk.Label(f, text=title, style='S.TLabel').pack(anchor='w', pady=(0, 6))
        return f

    # ---- plumbing: worker threads post ('log', text) / ('call', fn) to the queue; the Tk thread drains it
    def log(self, text): self.q.put(('log', text))
    def ui(self, fn): self.q.put(('call', fn))

    def pump(self):
        try:
            while True:
                kind, v = self.q.get_nowait()
                if kind == 'log':
                    self.log_w.insert('end', v + '\n'); self.log_w.see('end')
                    if v.startswith('[') and '/7]' in v[:6]:
                        n = int(v[1]); self.bar['value'] = n; self.stage.configure(text=f'step {n} of 7: {v[5:].strip()}')
                else: v()
        except queue.Empty: pass
        self.root.after(80, self.pump)

    def work(self, fn, done=None):
        if self.busy: return
        self.busy = True; self.build_btn.state(['disabled']); self.install_btn.state(['disabled'])
        def run():
            ok = True
            try: fn()
            except PipelineError as e: ok = False; self.log(f'error: {e}')
            except Exception as e: ok = False; self.log(f'error: {e.__class__.__name__}: {e}')
            def finish():
                self.busy = False; self.build_btn.state(['!disabled']); self.install_btn.state(['!disabled'])
                if done: done(ok)
            self.ui(finish)
        threading.Thread(target=run, daemon=True).start()

    # ---- 1
    def browse(self):
        start = os.path.dirname(self.rom.get()) if self.rom.get() else os.path.expanduser('~')
        p = filedialog.askopenfilename(title='Your Pilotwings Resort dump', initialdir=start,
                                       filetypes=[('3DS dumps', '*.cia *.3ds *.cci *.cxi *.CIA *.3DS *.CCI *.CXI'), ('All files', '*')])
        if p: self.rom.set(p); self.cfg['rom'] = p; save_config(self.cfg); self.verify_async()

    def verify_async(self):
        rom = self.rom.get(); self.rom_status.configure(text='checking...', foreground=DIM)
        def run():
            try:
                v = pipeline.verify(rom, log=lambda m: None)
                txt, col = (f'ok: {v["title"]}, code matches', OK) if v['ok'] else ('; '.join(v['problems']), BAD)
            except PipelineError as e: txt, col = str(e), BAD
            self.ui(lambda: self.rom_status.configure(text=txt, foreground=col))
        threading.Thread(target=run, daemon=True).start()

    # ---- 2
    def apk_status(self):
        apk = os.path.join(self.home, 'out', build_apk.APK_NAME)
        if not os.path.exists(apk): return 'no APK built yet'
        return f'last APK: {time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(apk)))}, {os.path.getsize(apk) >> 20} MB'

    def build(self):
        rom = self.rom.get()
        if not os.path.isfile(rom): messagebox.showerror('No dump', 'Pick your dump first.'); return
        self.cfg.update(rom=rom, shaderc=self.shaderc.get()); save_config(self.cfg)
        self.bar['value'] = 0; self.log_w.delete('1.0', 'end')
        if not os.path.exists(build_apk.Sdk(self.home).toolchain):
            self.log('First build: downloading the Android SDK and NDK into ' + os.path.join(self.home, 'sdk') + ' (about 2.5 GB, once).')
        def done(ok):
            self.stage.configure(text=self.apk_status() if ok else 'build failed: see the log')
            self.refresh_devices()
            if ok and self.ready_devices():
                if messagebox.askyesno('APK ready', 'The APK is built. Install it on the connected phone now?'): self.install()
        self.work(lambda: build_apk.build(rom, self.home, None, self.shaderc.get(), log=self.log), done)

    def open_folder(self):
        d = os.path.join(self.home, 'out'); os.makedirs(d, exist_ok=True)
        # distrobox: hand xdg-open to the host so the host's file manager opens
        cmd = ['distrobox-host-exec', 'xdg-open', d] if os.path.exists('/run/.containerenv') and shutil.which('distrobox-host-exec') else ['xdg-open', d]
        try: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: messagebox.showinfo('APK folder', d)

    # ---- 3
    def ready_devices(self): return [d for d in build_apk.devices(self.home) if ' device ' in d + ' ']

    def refresh_devices(self):
        def run():
            if not os.path.exists(build_apk.Sdk(self.home).adb): txt, col = 'adb arrives with the first build', DIM
            else:
                ds = build_apk.devices(self.home); ready = [d for d in ds if ' device ' in d + ' ']
                if ready:
                    model = next((t.split(':', 1)[1] for t in ready[0].split() if t.startswith('model:')), ready[0].split()[0])
                    txt, col = f'connected: {model.replace("_", " ")}' + (f' (+{len(ready) - 1} more)' if len(ready) > 1 else ''), OK
                elif any('unauthorized' in d for d in ds): txt, col = 'phone found: allow USB debugging on its screen, then Refresh', ACCENT
                else: txt, col = 'no phone connected', DIM
            self.ui(lambda: self.dev_status.configure(text=txt, foreground=col))
        threading.Thread(target=run, daemon=True).start()

    def install(self):
        self.work(lambda: build_apk.install(self.home, log=self.log), lambda ok: self.refresh_devices())

    def pull_log(self):
        dst = os.path.join(self.home, 'out', 'pwr-phone.log')
        def run():
            build_apk.adb(self.home, ['pull', f'/sdcard/Android/data/{build_apk.PACKAGE}/files/pwr.log', dst], self.log)
            self.log(f'phone log saved to {dst}')
        self.work(run)

    def pair(self):
        d = tk.Toplevel(self.root); d.title('Pair over Wi-Fi'); d.configure(bg=PANEL); d.transient(self.root)
        f = ttk.Frame(d, style='Panel.TFrame', padding=14); f.pack(fill='both', expand=True)
        ttk.Label(f, text='On the phone: Developer options > Wireless debugging > Pair device with pairing code.\n'
                  'Enter the IP address and port and the code it shows. Then enter the IP address and port\n'
                  'shown on the Wireless debugging screen itself (a different port) to connect.', style='Panel.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        v = {k: tk.StringVar() for k in ('pair', 'code', 'connect')}
        for i, (k, label) in enumerate([('pair', 'Pairing IP:port'), ('code', 'Pairing code'), ('connect', 'Connect IP:port')]):
            ttk.Label(f, text=label, style='Panel.TLabel').grid(row=i + 1, column=0, sticky='w', pady=3)
            ttk.Entry(f, textvariable=v[k], width=28).grid(row=i + 1, column=1, sticky='w', pady=3)
        def go():
            pair, code, conn = v['pair'].get().strip(), v['code'].get().strip(), v['connect'].get().strip()
            def run():
                if pair and code: build_apk.adb(self.home, ['pair', pair, code], self.log)
                if conn: build_apk.adb(self.home, ['connect', conn], self.log)
            self.work(run, lambda ok: self.refresh_devices()); d.destroy()
        ttk.Button(f, text='Pair and connect', style='Go.TButton', command=go).grid(row=4, column=1, sticky='w', pady=(10, 0))


if __name__ == '__main__':
    root = tk.Tk(); App(root); root.mainloop()
