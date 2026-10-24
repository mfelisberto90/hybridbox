import java.io.File;
import java.lang.reflect.Method;

public class HybridBoxBridge {
    private static volatile boolean standbyMode = false;

    private static void acquireWifiAndMulticastLocks(Method getService, Class<?> binderClass) {
        try {
            Object wifiBinder = getService.invoke(null, "wifi");
            if (wifiBinder == null) return;
            Class<?> iwmStub = Class.forName("android.net.wifi.IWifiManager$Stub");
            Object iwm = iwmStub.getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, wifiBinder);
            if (iwm == null) return;

            for (Method m : iwm.getClass().getMethods()) {
                if (m.getName().equals("acquireWifiLock")) {
                    Class<?>[] pts = m.getParameterTypes();
                    if (pts.length == 4) {
                        Object tokHi = binderClass.getDeclaredConstructor().newInstance();
                        m.invoke(iwm, tokHi, 3, "hybridbox:hiperf", null); // WIFI_MODE_FULL_HIGH_PERF = 3
                        System.out.println("WIFI_LOCK_HIPERF=true");
                        try {
                            Object tokLow = binderClass.getDeclaredConstructor().newInstance();
                            m.invoke(iwm, tokLow, 4, "hybridbox:lowlatency", null); // WIFI_MODE_FULL_LOW_LATENCY = 4
                            System.out.println("WIFI_LOCK_LOWLATENCY=true");
                        } catch (Throwable ignored) {}
                    }
                } else if (m.getName().equals("acquireMulticastLock") && m.getParameterTypes().length == 2) {
                    try {
                        Object tokMcast = binderClass.getDeclaredConstructor().newInstance();
                        m.invoke(iwm, tokMcast, "hybridbox:mdns");
                        System.out.println("MULTICAST_LOCK=true");
                    } catch (Throwable ignored) {}
                }
            }
        } catch (Throwable t) {
            System.out.println("WIFI_LOCK_ERR=" + t.getMessage());
        }
    }

    public static void main(String[] args) {
        String cmd = (args.length > 0) ? args[0] : "status";
        try {
            Class<?> smClass = Class.forName("android.os.ServiceManager");
            Method getService = smClass.getMethod("getService", String.class);
            Class<?> binderClass = Class.forName("android.os.Binder");

            Object ipm = null;
            Object wakeToken = null;
            int wakeFlagsActive = 0x3000000a; // SCREEN_BRIGHT_WAKE_LOCK | ACQUIRE_CAUSES_WAKEUP | ON_AFTER_RELEASE
            int wakeFlagsStandby = 0x00000001; // PARTIAL_WAKE_LOCK (CPU + Network awake, Screen OFF)
            Method acquireWakeLockMethod = null;
            Method releaseWakeLockMethod = null;

            standbyMode = new File("/data/local/tmp/hb_standby_mode").exists() || cmd.equals("standby");

            if (cmd.equals("wake") || cmd.equals("hold_wake") || cmd.equals("scan_cast") || cmd.equals("daemon") || cmd.equals("standby")) {
                try {
                    Object powerBinder = getService.invoke(null, "power");
                    if (powerBinder != null) {
                        Class<?> ipmStub = Class.forName("android.os.IPowerManager$Stub");
                        Method asInterface = ipmStub.getMethod("asInterface", Class.forName("android.os.IBinder"));
                        ipm = asInterface.invoke(null, powerBinder);

                        wakeToken = binderClass.getDeclaredConstructor().newInstance();
                        String pkg = cmd.equals("daemon") ? "com.android.shell" : "com.termux";

                        for (Method m : ipm.getClass().getMethods()) {
                            if (m.getName().equals("acquireWakeLock") && m.getParameterTypes().length == 6) {
                                acquireWakeLockMethod = m;
                            } else if (m.getName().equals("releaseWakeLock") && m.getParameterTypes().length == 2) {
                                releaseWakeLockMethod = m;
                            }
                        }
                        if (acquireWakeLockMethod != null) {
                            int initialFlags = standbyMode ? wakeFlagsStandby : wakeFlagsActive;
                            acquireWakeLockMethod.invoke(ipm, wakeToken, initialFlags, "hybridbox:wakeup", pkg, null, null);
                            System.out.println("WAKE_LOCK_ACQUIRED=true standby=" + standbyMode);
                        }
                    }
                } catch (Throwable t) {
                    System.out.println("WAKE_ERR=" + t.getMessage());
                }
            }

            if (cmd.equals("daemon") || cmd.equals("hold_wake")) {
                acquireWifiAndMulticastLocks(getService, binderClass);
            }

            // WindowManager Keyguard state (null-safe on untrusted_app SELinux context)
            try {
                Object wmBinder = getService.invoke(null, "window");
                if (wmBinder != null) {
                    Class<?> iwmStub = Class.forName("android.view.IWindowManager$Stub");
                    Object iwm = iwmStub.getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, wmBinder);
                    if (iwm != null) {
                        boolean locked = (Boolean) iwm.getClass().getMethod("isKeyguardLocked").invoke(iwm);
                        System.out.println("KEYGUARD_LOCKED=" + locked);
                        if (locked && !standbyMode && (cmd.equals("wake") || cmd.equals("hold_wake") || cmd.equals("scan_cast"))) {
                            try {
                                iwm.getClass().getMethod("dismissKeyguard", Class.forName("com.android.internal.policy.IKeyguardDismissCallback"), CharSequence.class)
                                   .invoke(iwm, null, "hybridbox");
                            } catch (Throwable ignored) {}
                        }
                    }
                }
            } catch (Throwable ignored) {}

            // Display & WifiDisplayStatus
            Object dispBinder = getService.invoke(null, "display");
            Class<?> idmStub = Class.forName("android.hardware.display.IDisplayManager$Stub");
            Object idm = idmStub.getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, dispBinder);

            if (cmd.equals("scan_cast") && idm != null) {
                try {
                    idm.getClass().getMethod("startWifiDisplayScan").invoke(idm);
                } catch (Throwable ignored) {}
            }

            Object wfdStatus = idm.getClass().getMethod("getWifiDisplayStatus").invoke(idm);
            System.out.println("WFD_STATUS=" + wfdStatus);

            Object dispInfo = idm.getClass().getMethod("getDisplayInfo", int.class).invoke(idm, 0);
            if (dispInfo != null) {
                int lw = dispInfo.getClass().getField("logicalWidth").getInt(dispInfo);
                int lh = dispInfo.getClass().getField("logicalHeight").getInt(dispInfo);
                int st = dispInfo.getClass().getField("state").getInt(dispInfo);
                System.out.println("DISPLAY_BOUNDS=" + lw + "x" + lh + " state=" + st);
            }

            // Bluetooth status & bonded devices via IBluetoothManager
            try {
                Object btBinder = getService.invoke(null, "bluetooth_manager");
                if (btBinder != null) {
                    Class<?> ibtmStub = Class.forName("android.bluetooth.IBluetoothManager$Stub");
                    Object ibtm = ibtmStub.getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, btBinder);
                    if (ibtm != null) {
                        boolean btEnabled = (Boolean) ibtm.getClass().getMethod("isEnabled").invoke(ibtm);
                        System.out.println("BT_ENABLED=" + btEnabled);
                    }
                }
            } catch (Throwable t) {
                System.out.println("BT_ERR=" + t.getMessage());
            }

            // InputManager devices (Gamepads / Bluetooth controllers)
            Class<?> imClass = Class.forName("android.hardware.input.InputManager");
            Object im = imClass.getMethod("getInstance").invoke(null);
            int[] ids = (int[]) imClass.getMethod("getInputDeviceIds").invoke(im);
            Method getDev = imClass.getMethod("getInputDevice", int.class);
            for (int id : ids) {
                Object dev = getDev.invoke(im, id);
                if (dev != null) {
                    String name = (String) dev.getClass().getMethod("getName").invoke(dev);
                    int sources = (Integer) dev.getClass().getMethod("getSources").invoke(dev);
                    boolean isGamepad = ((sources & 0x401) == 0x401) || ((sources & 0x1000010) == 0x1000010);
                    System.out.println("INPUT_DEV=" + id + "|" + name + "|gamepad=" + isGamepad + "|sources=0x" + Integer.toHexString(sources));
                }
            }

            if (cmd.equals("hold_wake")) {
                System.out.flush();
                for (int i = 0; i < 180; i++) {
                    Thread.sleep(20000);
                    if (ipm != null && acquireWakeLockMethod != null && wakeToken != null) {
                        try {
                            int flags = new File("/data/local/tmp/hb_standby_mode").exists() ? wakeFlagsStandby : wakeFlagsActive;
                            acquireWakeLockMethod.invoke(ipm, wakeToken, flags, "termux:wakeup", "com.termux", null, null);
                        } catch (Throwable ignored) {}
                    }
                }
            } else if (cmd.equals("daemon")) {
                int port = (args.length > 1) ? Integer.parseInt(args[1]) : 5558;
                java.net.ServerSocket server = new java.net.ServerSocket(port, 64, java.net.InetAddress.getByName("127.0.0.1"));
                System.out.println("DAEMON_LISTENING=" + port);
                System.out.flush();
                final Object fIpm = ipm;
                final Method fWake = acquireWakeLockMethod;
                final Method fRelease = releaseWakeLockMethod;
                final Object[] fTokenHolder = new Object[]{wakeToken};
                final boolean[] lastStandby = new boolean[]{standbyMode};
                final Class<?> fBinderClass = binderClass;
                final int fFlagsActive = wakeFlagsActive;
                final int fFlagsStandby = wakeFlagsStandby;

                Thread watchdog = new Thread(new Runnable() {
                    public void run() {
                        while (true) {
                            try {
                                boolean wantStandby = new File("/data/local/tmp/hb_standby_mode").exists();
                                standbyMode = wantStandby;
                                if (fIpm != null && fWake != null) {
                                    if (wantStandby != lastStandby[0] && fRelease != null && fTokenHolder[0] != null) {
                                        try {
                                            fRelease.invoke(fIpm, fTokenHolder[0], 0);
                                        } catch (Throwable ignored) {}
                                        fTokenHolder[0] = fBinderClass.getDeclaredConstructor().newInstance();
                                        lastStandby[0] = wantStandby;
                                    }
                                    int flags = wantStandby ? fFlagsStandby : fFlagsActive;
                                    fWake.invoke(fIpm, fTokenHolder[0], flags, "shell:wakeup", "com.android.shell", null, null);
                                }
                                Runtime.getRuntime().exec(new String[]{"/system/bin/sh", "-c",
                                    "if [ \"$(getprop service.adb.tcp.port)\" != \"5555\" ]; then setprop service.adb.tcp.port 5555; start adbd; fi"
                                }).waitFor();
                                Thread.sleep(8000);
                            } catch (Throwable ignored) {}
                        }
                    }
                });
                watchdog.setDaemon(true);
                watchdog.start();

                while (true) {
                    final java.net.Socket client = server.accept();
                    new Thread(new Runnable() {
                        public void run() {
                            try {
                                client.setSoTimeout(15000);
                                java.io.BufferedReader reader = new java.io.BufferedReader(
                                    new java.io.InputStreamReader(client.getInputStream(), "UTF-8")
                                );
                                String shellCmd = reader.readLine();
                                if (shellCmd != null && !shellCmd.trim().isEmpty()) {
                                    String trimmed = shellCmd.trim();
                                    if (trimmed.equals("__HB_STANDBY_ON__")) {
                                        new File("/data/local/tmp/hb_standby_mode").createNewFile();
                                        standbyMode = true;
                                        if (fIpm != null && fRelease != null && fWake != null && fTokenHolder[0] != null) {
                                            try { fRelease.invoke(fIpm, fTokenHolder[0], 0); } catch (Throwable ignored) {}
                                            fTokenHolder[0] = fBinderClass.getDeclaredConstructor().newInstance();
                                            lastStandby[0] = true;
                                            fWake.invoke(fIpm, fTokenHolder[0], fFlagsStandby, "shell:wakeup", "com.android.shell", null, null);
                                        }
                                        client.getOutputStream().write("STANDBY_ON=true\n".getBytes("UTF-8"));
                                        client.getOutputStream().flush();
                                        return;
                                    } else if (trimmed.equals("__HB_STANDBY_OFF__")) {
                                        new File("/data/local/tmp/hb_standby_mode").delete();
                                        standbyMode = false;
                                        if (fIpm != null && fRelease != null && fWake != null && fTokenHolder[0] != null) {
                                            try { fRelease.invoke(fIpm, fTokenHolder[0], 0); } catch (Throwable ignored) {}
                                            fTokenHolder[0] = fBinderClass.getDeclaredConstructor().newInstance();
                                            lastStandby[0] = false;
                                            fWake.invoke(fIpm, fTokenHolder[0], fFlagsActive, "shell:wakeup", "com.android.shell", null, null);
                                        }
                                        client.getOutputStream().write("STANDBY_OFF=true\n".getBytes("UTF-8"));
                                        client.getOutputStream().flush();
                                        return;
                                    }
                                    Process proc = Runtime.getRuntime().exec(new String[]{"/system/bin/sh", "-c", shellCmd});
                                    java.io.InputStream stdout = proc.getInputStream();
                                    java.io.InputStream stderr = proc.getErrorStream();
                                    java.io.OutputStream out = client.getOutputStream();
                                    byte[] buf = new byte[4096];
                                    int n;
                                    while ((n = stdout.read(buf)) != -1) {
                                        out.write(buf, 0, n);
                                    }
                                    while ((n = stderr.read(buf)) != -1) {
                                        out.write(buf, 0, n);
                                    }
                                    out.flush();
                                    proc.waitFor();
                                }
                            } catch (Throwable ignored) {
                            } finally {
                                try { client.close(); } catch (Throwable ignored) {}
                            }
                        }
                    }).start();
                }
            } else if (cmd.equals("wake")) {
                Thread.sleep(600);
            }
        } catch (Throwable e) {
            e.printStackTrace();
        }
    }
}
