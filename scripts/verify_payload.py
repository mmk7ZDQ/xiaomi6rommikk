#!/usr/bin/env python3
"""校验 block-OTA payload：流式还原 + 逐块比对，内存占用 < 64MB。

用法: verify_payload.py <transfer.list> <new.dat.br> <reference.img> [out.img]
"""
import os, sys, brotli

tl, datbr, ref = sys.argv[1], sys.argv[2], sys.argv[3]
out = sys.argv[4] if len(sys.argv) > 4 else None
BS = 4096
CH = 1 << 20

lines = [l.strip() for l in open(tl) if l.strip()]
assert lines[0] == '4', lines[0]
total = int(lines[1])
cmds = lines[4:]
print(f"total_blocks={total} ({total*BS} bytes)", flush=True)

target = open(out, 'wb') if out else None
if target:
    target.truncate(total * BS)

d = brotli.Decompressor()
consumed = 0
pending = b''          # 尚未用完的解压数据
zero = b'\x00' * CH

with open(datbr, 'rb') as f, open(ref, 'rb') as r:
    def pull(n):
        """从 brotli 流里凑出 n 字节"""
        global pending
        while len(pending) < n:
            chunk = f.read(CH)
            if not chunk:
                raise SystemExit('❌ dat 提前结束')
            pending += d.process(chunk)
        out_b, pending = pending[:n], pending[n:]
        return out_b

    for cmd in cmds:
        op, _, rest = cmd.partition(' ')
        nums = [int(x) for x in rest.split(',') if x]
        assert nums[0] == len(nums) - 1, f"{op} 声明 {nums[0]} 实际 {len(nums)-1}"
        vals = nums[1:]
        for i in range(0, len(vals), 2):
            s, e = vals[i], vals[i + 1]
            left = (e - s) * BS
            pos = s * BS
            if op == 'erase':
                # erase 在 updater 里只是把分区抹零，之后必然被 new/zero 全量覆盖
                if target:
                    while left > 0:
                        n = min(left, CH)
                        target.seek(pos); target.write(zero[:n])
                        pos += n; left -= n
                continue
            if op == 'new':
                while left > 0:
                    n = min(left, CH)
                    buf = pull(n)
                    consumed += n
                    r.seek(pos)
                    if r.read(n) != buf:
                        for k in range(0, n, BS):
                            if r.seek(pos + k) or r.read(BS) != buf[k:k+BS]:
                                raise SystemExit(f'❌ 不一致 @ byte {pos+k} (block {(pos+k)//BS})')
                        raise SystemExit(f'❌ 长度不一致 @ byte {pos}')
                    if target:
                        target.seek(pos)
                        target.write(buf)
                    pos += n
                    left -= n
            else:
                while left > 0:
                    n = min(left, CH)
                    r.seek(pos)
                    if r.read(n) != zero[:n]:
                        raise SystemExit(f'❌ zero 段参考图非零 @ block {pos//BS}')
                    if target:
                        target.seek(pos)
                        target.write(zero[:n])
                    pos += n
                    left -= n

    rest = f.read()
    tail = (pending + d.process(rest)) if rest else pending

print(f"consumed={consumed}  dat_size={os.path.getsize(datbr)}", flush=True)
print(f"多余解压字节={len(tail)}（应为 0）", flush=True)
if target:
    target.close()
    print("已写出", out, os.path.getsize(out))
print("✅ 逐字节比对通过" if len(tail) == 0 else "⚠️ 有尾部残留")
