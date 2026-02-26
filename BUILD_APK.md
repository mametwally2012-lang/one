# 🔨 بناء APK لـ FireBrush (دليل كامل)

## الطريقة الأولى: استخدام Python-for-Android (الأسهل للـ Python)

### المتطلبات:
```bash
pip install buildozer cython
sudo apt install openjdk-11-jdk-headless android-sdk
```

### الخطوات:
1. انسخ المشروع على جهازك
2. أنشئ ملف `buildozer.spec`:

```ini
[app]
title = FireBrush Studio
package.name = firebrush
package.domain = org.firebrush

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0
requirements = python3,kivy,numpy,glm,psutil

[buildozer]
log_level = 2
warn_on_root = 1
```

3. شغّل:
```bash
buildozer android debug
```

## الطريقة الثانية: استخدام Android Studio + PyCharm

1. اكتب الواجهة بـ Kotlin/Java
2. استدعِ الـ Python modules عبر JNI
3. بنِ عبر Gradle

## الطريقة الثالثة: استخدام Kivy + buildozer (الموصى به)

```bash
# ثبّت buildozer
pip install buildozer

# شغّل من مجلد المشروع
buildozer android debug
```

الملف `FireBrush-1.0-debug.apk` سيكون جاهز في `bin/`

---

**النتيجة**: ملف `.apk` يمكنك تحميله على أي جهاز Android! 🎉
