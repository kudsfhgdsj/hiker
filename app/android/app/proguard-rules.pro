# BRouter (routing on the device) is called from MainActivity only; keep it whole, it
# loads its profile expressions by name.
-keep class btools.** { *; }
-dontwarn btools.**
