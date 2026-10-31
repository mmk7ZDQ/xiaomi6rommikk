#!/usr/bin/env bash
#
# flash-fastboot.sh —— 拆包直刷（不用 recovery sideload）
#
# 适用: sideload 老掉线 / recovery 跑不动 update-binary 的情况。
# 会依次刷 boot、system、cust(vendor)，然后清 data。
#
# 用法:
#   ./flash-fastboot.sh [工作目录] [--yes]
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./work}"
YES=0
for a in "$@"; do [ "$a" = "--yes" ] && YES=1; done

export PATH="$HOME/Android/Sdk/platform-tools:$PATH"

SYS="$WORK/system.img"
VND="$WORK/vendor.img"
BOOT="$WORK/boot.img"

for f in "$SYS" "$VND" "$BOOT"; do
  [ -f "$f" ] || { echo "缺少 $f（先跑 build-rom.sh）"; exit 1; }
done

# system 必须补齐到真实分区大小（5 GiB），否则会留旧数据
PADDED="$WORK/system-padded.img"
PART_SIZE=5368709120
if [ ! -f "$PADDED" ]; then
  echo "==> 生成 $PADDED（补齐到 $PART_SIZE 字节）"
  cp --reflink=auto "$SYS" "$PADDED"
  truncate -s "$PART_SIZE" "$PADDED"
fi

echo "==> 检查设备"
adb devices | grep -qw device || { echo "没有 adb 设备"; exit 1; }
DEV="$(adb shell getprop ro.product.device | tr -d '\r')"
[ "$DEV" = "sagit" ] || { echo "本脚本只针对 sagit，当前是 '$DEV'"; exit 1; }

cat <<EOF

将执行:
  1) adb reboot bootloader
  2) fastboot flash boot    boot.img
  3) fastboot flash system  system-padded.img   (5 GiB，约 5 分钟)
  4) fastboot flash cust    vendor.img
  5) fastboot erase userdata / cache / misc
  6) 重启进 OrangeFox 执行 twrp format data
     （erase userdata 之后必须 format，否则 init 挂不上 /data 会无限重启）

EOF
if [ "$YES" -ne 1 ]; then
  read -r -p "确认继续？输入 yes: " a
  [ "$a" = "yes" ] || { echo "已取消"; exit 0; }
fi

adb reboot bootloader
for i in $(seq 1 30); do
  fastboot devices | grep -qw fastboot && break
  sleep 2
done
fastboot devices | grep -qw fastboot || { echo "fastboot 里没看到设备"; exit 1; }

fastboot flash boot "$BOOT"
fastboot flash system "$PADDED"
fastboot flash cust "$VND"

fastboot erase userdata
fastboot erase cache
fastboot erase misc

echo
echo "==> 分区刷完。现在需要格式化 /data："
echo "    1) fastboot boot <OrangeFox.img>"
echo "    2) adb shell 'twrp format data'"
echo "    3) adb shell 'twrp wipe cache'"
echo "    4) adb reboot"
