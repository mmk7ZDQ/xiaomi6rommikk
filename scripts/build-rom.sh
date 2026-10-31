#!/usr/bin/env bash
#
# build-rom.sh —— 从零构建 sagit 的 block-OTA ROM zip
#
# 产物结构完全照抄 LineageOS 官方 zip，可直接 adb sideload。
#
# 用法:
#   ./build-rom.sh [工作目录] [--no-navbar-patch]
#
# 需要: python3 + brotli、unzip、xz、e2fsprogs(debugfs)、curl
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./work}"
PATCH_NAV=1
for a in "$@"; do [ "$a" = "--no-navbar-patch" ] && PATCH_NAV=0; done

mkdir -p "$WORK"

echo "==> [1/6] 取上游镜像"
"$HERE/fetch-gsi.sh" 16.0.0-202606230923 "$WORK"
"$HERE/fetch-los.sh" "$WORK"

IMG="$WORK/RestlessOS-arm64-ab-16.0.0-202606230923.img"
SYS="$WORK/system.img"

if [ ! -f "$SYS" ]; then
  echo "==> 复制一份可写的 system 镜像"
  cp --reflink=auto "$IMG" "$SYS"
fi

if [ "$PATCH_NAV" = "1" ]; then
  echo "==> [2/6] 改属性：去掉虚拟导航栏 / 手势条"
  python3 "$HERE/patch-navbar.py" "$SYS"
  echo "==> fsck 校验"
  /usr/sbin/e2fsck -fn "$SYS" | tail -2
else
  echo "==> [2/6] 跳过导航栏改动"
fi

echo "==> [3/6] vendor payload -> raw（用于校验 + 直接 fastboot 刷）"
python3 - "$WORK" <<'PY'
import brotli, os, sys
w = sys.argv[1]
src = os.path.join(w, 'vendor.new.dat.br')
dst = os.path.join(w, 'vendor.new.dat')
d = brotli.Decompressor()
with open(src, 'rb') as f, open(dst, 'wb') as o:
    while True:
        c = f.read(1 << 20)
        if not c:
            break
        o.write(d.process(c))
print('vendor.new.dat', os.path.getsize(dst))
PY
python3 "$HERE/sdat2img.py" "$WORK/vendor.transfer.list" "$WORK/vendor.new.dat" "$WORK/vendor.img"

echo "==> [4/6] system -> transfer.list + .new.dat.br"
mkdir -p "$WORK/payload"
python3 "$HERE/mkpayload.py" "$SYS" "$WORK/payload" system 6

echo "==> [5/6] 组装 zip"
mkdir -p "$WORK/src"
cp "$WORK/payload/system.new.dat.br" "$WORK/payload/system.transfer.list" \
   "$WORK/vendor.new.dat.br" "$WORK/vendor.transfer.list" \
   "$WORK/boot.img" "$WORK/recovery.img" "$WORK/src/"
: > "$WORK/src/system.patch.dat"
: > "$WORK/src/vendor.patch.dat"
python3 "$HERE/buildrom.py" "$WORK"

echo "==> [6/6] 完成"
ls -l "$WORK"/out/*.zip
echo
echo "刷法: adb sideload <zip>（recovery 会问 Install anyway，选 Yes）"
