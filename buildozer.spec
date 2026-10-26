[app]
title = The Green Bakery
package.name = bakeryapp
package.domain = org.bakery

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_dirs = java,bin,.buildozer,__pycache__

version = 1.0
requirements = python3,kivy==2.3.0,sqlite3,pyjnius,android

orientation = portrait
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

android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
