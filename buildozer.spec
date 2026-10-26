[app]

# (str) Title of your application
title = The Green Bakery

# (str) Package name
package.name = bakeryapp

# (str) Package domain (needed for android/ios packaging)
package.domain = org.bakery

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (list) List of directory to exclude
source.exclude_dirs = java,bin,.buildozer,__pycache__

# (str) Application versioning
version = 1.0

# (list) Application requirements
# Removed version pinning (==2.3.0) which breaks p4a recipe matching
requirements = python3,kivy,sqlite3,pyjnius,android

# (str) Supported orientation
orientation = portrait

# (int) Fullscreen mode (0 = status bar visible, 1 = fullscreen)
fullscreen = 0

# Your logo: used as launcher icon, splash screen and in-app header
icon.filename = %(source.dir)s/logo.png
presplash.filename = %(source.dir)s/logo.png
android.presplash_color = #FFF8EC

# Notifications (WorkManager + small Java helpers in ./java)
android.permissions = POST_NOTIFICATIONS,RECEIVE_BOOT_COMPLETED
android.add_src = ./java
android.enable_androidx = True
android.gradle_dependencies = androidx.work:work-runtime:2.8.1, androidx.core:core:1.9.0

# Android target settings
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
