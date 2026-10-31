#!/usr/bin/env python3
"""sdat2img for block-OTA v4 transfer lists.

Line format:  <cmd> <N>,<start1>,<end1>,<start2>,<end2>,...
  N            = how many numbers follow
  pairs        = [start, end) block ranges
'new'  : read blocks sequentially from the .new.dat blob into those ranges
'zero' / 'erase' : zero-fill those ranges
"""
import os
import sys

def main():
    tl, dat, out = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(tl) as f:
        lines = [l.strip() for l in f if l.strip()]
    total = int(lines[1])
    cmds = lines[4:]

    dat_size = os.path.getsize(dat)
    print(f"total_blocks={total} dat={dat_size} bytes ({dat_size//4096} 块)")

    with open(dat, "rb") as f, open(out, "wb") as o:
        o.truncate(total * 4096)
        consumed = 0
        n_blocks = 0
        for cmd in cmds:
            op, _, rest = cmd.partition(" ")
            nums = [int(x) for x in rest.split(",") if x]
            assert nums[0] == len(nums) - 1, f"{op}: 声明 {nums[0]} 个数字，实际 {len(nums)-1}"
            vals = nums[1:]
            ranges = [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]
            for start, end in ranges:
                cnt = end - start
                n_blocks += cnt
                if op == "new":
                    o.seek(start * 4096)
                    left = cnt * 4096
                    while left > 0:
                        chunk = f.read(min(left, 4 << 20))
                        if not chunk:
                            raise SystemExit(f"new.dat 提前结束 (block {start})")
                        o.write(chunk)
                        left -= len(chunk)
                        consumed += len(chunk)
                elif op in ("zero", "erase"):
                    o.seek(start * 4096)
                    z = b"\x00" * (min(cnt, 1024) * 4096)
                    left = cnt * 4096
                    while left > 0:
                        w = min(left, len(z))
                        o.write(z[:w])
                        left -= w
                else:
                    raise SystemExit(f"未知指令 {op}")

    print(f"完成 {out}: {total*4096} bytes")
    print(f"覆盖 {n_blocks} 块 / {total}；.dat 消耗 {consumed} / {dat_size}")
    if consumed != dat_size:
        print("⚠️ .dat 未被完全消耗，解析可能仍有偏差")

main()
