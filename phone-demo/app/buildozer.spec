[app]
title = 儿童智能语音玩具
package.name = toyphone
package.domain = org.toy

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

requirements = python3,kivy,aiohttp,pyaudio
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0

fullscreen = 0
android.permissions = INTERNET,RECORD_AUDIO,MODIFY_AUDIO_SETTINGS
android.minapi = 21
android.sdk = 24
android.api = 30
android.ndk = 25b
android.arch = arm64-v8a
android.accept_sdk_license = True

p4a.source_dir =
p4a.bootstrap = sdl2
p4a.extra_args = --blacklist-requirements=libffi

[buildozer]
log_level = 2
warn_on_root = 1
