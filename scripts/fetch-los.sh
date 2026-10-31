#!/usr/bin/env bash
#
# fetch-los.sh —— 下载 LineageOS 22.2 官方包（提供 vendor / boot / recovery）
#
# 用法:
#   ./fetch-los.sh [输出目录]
#
# 为什么要 LOS 的包: MI 6 是 A-only 单槽，从原厂 MIUI 直接刷 GSI 不保证能用。
# LOS 22.2 用 Android 15 重建了 vendor 分区，这是 GSI 能正常跑的前提。
#
set -euo pipefail

OUTDIR="${1:-./work}"
mkdir -p "$OUTDIR"
cd "$OUTDIR"

# 官方 nightly 目录：https://download.lineageos.org/devices/sagit/builds
# 具体文件名随日期变化，用环境变量覆盖。
ZIP="${LOS_ZIP:-lineage-22.2-20261009-nightly-sagit-signed.zip}"
BASE="${LOS_BASE:-https://mirrorbits.lineageos.org/full/sagit/20261009}"

if [ ! -f "$ZIP" ]; then
  echo "==> 下载 $BASE/$ZIP"
  echo "    （如果链接失效，去 https://download.lineageos.org/devices/sagit/builds 找当期包，"
  echo "      然后 LOS_ZIP=... LOS_BASE=... 重新跑本脚本）"
  curl -L -C - --retry 20 --retry-all-errors --retry-delay 3 \
       --speed-time 90 --speed-limit 20000 -o "$ZIP" "$BASE/$ZIP"
else
  echo "==> $ZIP 已存在"
fi

echo "==> 完整性检查（约 1 GB，10 秒）"
unzip -t "$ZIP" | tail -2
echo "==> 提取 vendor payload / boot / recovery"
unzip -o -j "$ZIP" vendor.new.dat.br vendor.transfer.list boot.img recovery.img \
      META-INF/com/google/android/update-binary META-INF/com/android/otacert \
      META-INF/com/android/metadata META-INF/com/android/metadata.pb \
      install/bin/backuptool.sh install/bin/backuptool.functions
echo "==> 完成"
