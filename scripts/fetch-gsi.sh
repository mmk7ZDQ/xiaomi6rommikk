#!/usr/bin/env bash
#
# fetch-gsi.sh —— 下载 RestlessOS GSI 并校验
#
# 用法:
#   ./fetch-gsi.sh [版本] [输出目录]
#   默认版本 16.0.0-202606230923（实测可用的 Android 16 版）
#
# 说明: GitHub release 直连在国内实测比镜像快（10 MB/s vs 0.5 MB/s），
#       所以默认直连，慢的话设 MIRROR 环境变量换镜像。
#
set -euo pipefail

VERSION="${1:-16.0.0-202606230923}"
OUTDIR="${2:-./work}"
MIRROR="${MIRROR:-}"     # 例: MIRROR=https://ghfast.top/

NAME="RestlessOS-arm64-ab-${VERSION}.img"
BASE="https://github.com/cawilliamson/treble_restlessos/releases/download/${VERSION}"
URL="${MIRROR}${BASE}/${NAME}.xz"

# 已知版本的 sha256（针对 .img.xz）
case "$VERSION" in
  16.0.0-202606230923) EXPECT="52ea47d794faf6eafbb49a5f0d2301508757be0e30d1b73e033e1d5185bb492c" ;;
  *) EXPECT="" ;;
esac

mkdir -p "$OUTDIR"
cd "$OUTDIR"

if [ -f "$NAME.xz" ]; then
  echo "==> $NAME.xz 已存在，跳过下载"
else
  echo "==> 下载 $URL"
  curl -L -C - --retry 20 --retry-all-errors --retry-delay 3 \
       --speed-time 90 --speed-limit 20000 -o "$NAME.xz" "$URL"
fi

ACT=$(sha256sum "$NAME.xz" | awk '{print $1}')
echo "==> sha256(.xz) = $ACT"
if [ -n "$EXPECT" ]; then
  [ "$ACT" = "$EXPECT" ] || { echo "sha256 不匹配！期望 $EXPECT"; exit 1; }
  echo "==> 校验通过 ✓"
else
  echo "==> 该版本没有内置 sha256，请自行对照 release 页面"
fi

if [ ! -f "$NAME" ]; then
  echo "==> 解压（约 3 GB）"
  xz -T0 -dc "$NAME.xz" > "$NAME"
fi

echo "==> 镜像: $NAME  $(stat -c %s "$NAME") 字节"
