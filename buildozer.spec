[app]

title = FireBrush Studio
package.name = firebrush
package.domain = org.firebrush

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,md

version = 1.0

requirements = python3,kivy,numpy,glm,psutil

orientation = landscape
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png

[buildozer]

log_level = 2
warn_on_root = 1
