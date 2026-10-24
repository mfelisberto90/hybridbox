import java.lang.reflect.Method;
import java.util.List;
import java.util.Set;

public class HybridBoxBridge {
    public static void main(String[] args) {
        String cmd = (args.length > 0) ? args[0] : "status";
        try {
            Class<?> smClass = Class.forName("android.os.ServiceManager");
            Method getService = smClass.getMethod("getService", String.class);

            Object ipm = null;
            Object wakeToken = null;
            int wakeFlags = 0x3000000a; // SCREEN_BRIGHT_WAKE_LOCK | ACQUIRE_CAUSES_WAKEUP | ON_AFTER_RELEASE
            Method acquireWakeLockMethod = null;

            if (cmd.equals("wake") || cmd.equals("hold_wake") || cmd.equals("scan_cast") || cmd.equals("daemon")) {
                try {
                    Object powerBinder = getService.invoke(null, "power");
                    if (powerBinder != null) {
                        Class<?> ipmStub = Class.forName("android.os.IPowerManager$Stub");
                        Method asInterface = ipmStub.getMethod("asInterface", Class.forName("android.os.IBinder"));
                        ipm = asInterface.invoke(null, powerBinder);

                        Class<?> binderClass = Class.forName("android.os.Binder");
                        wakeToken = binderClass.getDeclaredConstructor().newInstance();
                        String pkg = cmd.equals("daemon") ? "com.android.shell" : "com.termux";

                        for (Method m : ipm.getClass().getMethods()) {
                            if (m.getName().equals("acquireWakeLock") && m.getParameterTypes().length == 6) {
                                acquireWakeLockMethod = m;
                                m.invoke(ipm, wakeToken, wakeFlags, "hybridbox:wakeup", pkg, null, null);
                                System.out.println("WAKE_LOCK_ACQUIRED=true");
                                break;
                            }
                        }
                    }
                } catch (Throwable t) {
                    System.out.println("WAKE_ERR=" + t.getMessage());
                }
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
                        if (locked && (cmd.equals("wake") || cmd.equals("hold_wake") || cmd.equals("scan_cast"))) {
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
                            acquireWakeLockMethod.invoke(ipm, wakeToken, wakeFlags, "termux:wakeup", "com.termux", null, null);
                        } catch (Throwable ignored) {}
                    }
                }
            } else if (cmd.equals("daemon")) {
                int port = (args.length > 1) ? Integer.parseInt(args[1]) : 5558;
                java.net.ServerSocket server = new java.net.ServerSocket(port, 32, java.net.InetAddress.getByName("127.0.0.1"));
                System.out.println("DAEMON_LISTENING=" + port);
                System.out.flush();
                final Object fIpm = ipm;
                final Method fWake = acquireWakeLockMethod;
                final Object fToken = wakeToken;
                final int fFlags = wakeFlags;
                Thread watchdog = new Thread(new Runnable() {
                    public void run() {
                        while (true) {
                            try {
                                if (fIpm != null && fWake != null && fToken != null) {
                                    fWake.invoke(fIpm, fToken, fFlags, "shell:wakeup", "com.android.shell", null, null);
                                }
                                Runtime.getRuntime().exec(new String[]{"/system/bin/sh", "-c",
                                    "if [ \"$(getprop service.adb.tcp.port)\" != \"5555\" ]; then setprop service.adb.tcp.port 5555; start adbd; fi"
                                }).waitFor();
                                Thread.sleep(10000);
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
