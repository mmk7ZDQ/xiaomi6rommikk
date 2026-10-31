#!/usr/bin/env python3
"""把 raw ext4 镜像转成 block-OTA 的 transfer.list + .new.dat.br

用法: mkpayload.py <image> <outdir> <name> [quality]
输出: <outdir>/<name>.transfer.list  <outdir>/<name>.new.dat.br
"""
import os, sys, time, brotli

img, outdir, name = sys.argv[1], sys.argv[2], sys.argv[3]
Q = int(sys.argv[4]) if len(sys.argv) > 4 else 9
BS = 4096

size = os.path.getsize(img)
nblk = size // BS
print(f"image={img} size={size} blocks={nblk}", flush=True)

# pass 1: 扫描哪些块全零
t0 = time.time()
nonzero = bytearray(nblk)  # 1 = 有数据
zero4k = b"\x00" * BS
with open(img, "rb", buffering=1 << 20) as f:
    for i in range(nblk):
        if f.read(BS) != zero4k:
            nonzero[i] = 1
    rest = f.read()
print(f"scan done in {time.time()-t0:.1f}s, nonzero={sum(nonzero)}", flush=True)

# 生成命令
cmds = []
i = 0
while i < nblk:
    v = nonzero[i]
    j = i
    while j < nblk and nonzero[j] == v:
        j += 1
    cmds.append(("new" if v else "zero", i, j))
    i = j
print(f"runs={len(cmds)}", flush=True)

lines = ["4", str(nblk), "0", "0"]
lines.append("erase 2,0,%d" % nblk)
for op, s, e in cmds:
    lines.append(f"{op} 2,{s},{e}")
tl = os.path.join(outdir, name + ".transfer.list")
with open(tl, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"wrote {tl} ({os.path.getsize(tl)} bytes)", flush=True)

# 写 dat（只写 new 段的数据），流式 brotli
out = os.path.join(outdir, name + ".new.dat.br")
t0 = time.time()
comp = brotli.Compressor(quality=Q, lgwin=24)
written = 0
with open(img, "rb", buffering=1 << 20) as f, open(out, "wb") as o:
    for op, s, e in cmds:
        if op != "new":
            continue
        f.seek(s * BS)
        left = (e - s) * BS
        while left > 0:
            chunk = f.read(min(left, 1 << 20))
            if not chunk:
                raise SystemExit("image truncated")
            o.write(comp.process(chunk))
            written += len(chunk)
            left -= len(chunk)
        if written % (256 << 20) < (1 << 20):
            el = time.time() - t0
            print(f"  {written>>20} MiB, {el:.0f}s, {written/el/1048576:.1f} MiB/s", flush=True)
    o.write(comp.finish())

print(f"dat: {written} raw -> {os.path.getsize(out)} compressed in {time.time()-t0:.0f}s", flush=True)
