#!/usr/bin/env python3
"""打包 sagit 的 block-OTA ROM zip（A-only，recovery sideload）

结构照抄 LineageOS 22.2 官方 zip：
  META-INF/com/android/metadata     (stored, 327B, extra 10B -> data@69)
  META-INF/com/android/metadata.pb  (stored, 207B, extra  6B -> data@464)
  system.new.dat.br / system.patch.dat
  vendor.new.dat.br / vendor.patch.dat
  META-INF/com/google/android/update-binary, updater-script
  boot.img, recovery.img, install/bin/backuptool.*,
  system.transfer.list, vendor.transfer.list, META-INF/com/android/otacert

offset 69 / 464 与 metadata.pb 里的 ota-property-files 一一对应。

用法: buildrom.py [工作目录] [--los-zip <path>] [--name <zipname>]
"""
import glob
import os
import struct
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
UPDATER = os.path.join(HERE, '..', 'updater-script')


def find_los_zip(work):
    """在 work 目录里找 LOS 官方 zip（fetch-los.sh 下载的）"""
    cands = sorted(glob.glob(os.path.join(work, 'lineage-*-sagit-signed.zip')))
    if not cands:
        cands = sorted(glob.glob(os.path.join(work, 'lineage-*sagit*.zip')))
    if not cands:
        raise SystemExit(f'{work} 里没有 LOS 官方 zip（先跑 fetch-los.sh）')
    return cands[-1]


class ZipWriter:
    def __init__(self, path):
        self.f = open(path, 'wb')
        self.cd = []
        self.off = 0
        self.n = 0

    def _local(self, name, payload, method, extra, crc, csize, usize):
        nb = name.encode()
        hdr = struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, 0x0800, method,
                          0, 0x21, crc, csize, usize, len(nb), len(extra))
        rec = hdr + nb + extra
        self.f.write(rec)
        self.f.write(payload)
        self.off += len(rec) + len(payload)
        return len(rec)

    def add(self, name, data, method=zipfile.ZIP_STORED, extra=b''):
        crc = zlib.crc32(data) & 0xFFFFFFFF
        if method == zipfile.ZIP_DEFLATED:
            c = zlib.compressobj(9, zlib.DEFLATED, -15)
            payload = c.compress(data) + c.flush()
        else:
            payload = data
        csize, usize = len(payload), len(data)
        hdr_off = self.off
        data_off = self.off + self._local(name, payload, method, extra, crc, csize, usize)
        # 中央目录要的是 local header 起点，不是数据起点
        self.cd.append((name, method, crc, csize, usize, hdr_off, extra))
        self.n += 1
        return data_off

    def close(self):
        cd_off = self.off
        for name, method, crc, csize, usize, hdr_off, extra in self.cd:
            nb = name.encode()
            rec = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 20, 20,
                              0x0800, method, 0, 0x21, crc, csize, usize,
                              len(nb), len(extra), 0, 0, 0, 0, hdr_off) + nb + extra
            self.f.write(rec)
            self.off += len(rec)
        cd_size = self.off - cd_off
        self.f.write(struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, self.n, self.n,
                                 cd_size, cd_off, 0))
        self.f.close()


def patch_metadata(los_zip, ts):
    with zipfile.ZipFile(los_zip) as z:
        txt = z.read('META-INF/com/android/metadata').decode()
        pb = bytearray(z.read('META-INF/com/android/metadata.pb'))

    # post-sdk-level 35 -> 36（等长）
    txt = txt.replace('post-sdk-level=35', 'post-sdk-level=36')

    # post-timestamp -> 打包时间（10 位等长）
    old_ts = None
    for line in txt.splitlines():
        if line.startswith('post-timestamp='):
            old_ts = line.split('=')[1]
    if not old_ts or len(old_ts) != 10:
        raise SystemExit(f'metadata 里 post-timestamp 异常: {old_ts!r}')
    txt = txt.replace('post-timestamp=' + old_ts, 'post-timestamp=%d' % ts)

    def varint(n):
        out = bytearray()
        while True:
            b = n & 0x7F
            n >>= 7
            out.append(b | (0x80 if n else 0))
            if not n:
                return bytes(out)

    ov, nv = varint(int(old_ts)), varint(ts)
    if len(ov) != len(nv):
        raise SystemExit('时间戳 varint 长度变了，无法等长替换')
    i = pb.find(ov)
    if i < 0:
        raise SystemExit('metadata.pb 里没找到时间戳')
    pb[i:i + len(ov)] = nv

    j = pb.find(b'*\x0235')
    if j > 0:
        pb[j + 2:j + 4] = b'36'

    txt_b = txt.encode()
    if len(txt_b) > 327:
        raise SystemExit(f'metadata 超长: {len(txt_b)} > 327')
    txt_b = txt_b + b' ' * (327 - len(txt_b))
    if len(pb) != 207:
        raise SystemExit(f'metadata.pb 长度变了: {len(pb)} != 207')
    return txt_b, bytes(pb)


def build(work, los_zip=None, name=None):
    los_zip = los_zip or find_los_zip(work)
    src = os.path.join(work, 'src')
    outdir = os.path.join(work, 'out')
    os.makedirs(outdir, exist_ok=True)

    if name is None:
        name = 'sagit-RestlessOS-16.0.0-lineage22-%s.zip' % time.strftime('%Y%m%d')

    ts = int(time.time())
    meta_b, meta_pb = patch_metadata(los_zip, ts)

    with zipfile.ZipFile(los_zip) as z:
        def los_read(n):
            return z.read(n)
        upd_bin = los_read('META-INF/com/google/android/update-binary')
        otacert = los_read('META-INF/com/android/otacert')
        bt_func = los_read('install/bin/backuptool.functions')
        bt_sh = los_read('install/bin/backuptool.sh')

    updater = open(os.path.abspath(UPDATER), 'rb').read()

    out = os.path.join(outdir, name)
    w = ZipWriter(out)

    d1 = w.add('META-INF/com/android/metadata', meta_b,
               extra=b'\xfe\xca\x00\x00' + b'\x00' * 6)
    if d1 != 69:
        raise SystemExit(f'metadata 数据偏移 {d1} != 69')
    d2 = w.add('META-INF/com/android/metadata.pb', meta_pb,
               extra=b'\xfe\xca\x00\x00\x00\x00')
    if d2 != 464:
        raise SystemExit(f'metadata.pb 数据偏移 {d2} != 464')

    for nm in ('system.new.dat.br', 'system.patch.dat',
               'vendor.new.dat.br', 'vendor.patch.dat'):
        p = os.path.join(src, nm)
        print(' +', nm, os.path.getsize(p), flush=True)
        with open(p, 'rb') as f:
            w.add(nm, f.read())

    w.add('META-INF/com/google/android/update-binary', upd_bin, zipfile.ZIP_DEFLATED)
    w.add('META-INF/com/google/android/updater-script', updater, zipfile.ZIP_DEFLATED)

    for nm in ('boot.img', 'recovery.img'):
        p = os.path.join(src, nm)
        print(' +', nm, os.path.getsize(p), flush=True)
        w.add(nm, open(p, 'rb').read(), zipfile.ZIP_DEFLATED)

    w.add('install/bin/backuptool.functions', bt_func, zipfile.ZIP_DEFLATED)
    w.add('install/bin/backuptool.sh', bt_sh, zipfile.ZIP_DEFLATED)

    for nm in ('system.transfer.list', 'vendor.transfer.list'):
        p = os.path.join(src, nm)
        w.add(nm, open(p, 'rb').read(), zipfile.ZIP_DEFLATED)

    w.add('META-INF/com/android/otacert', otacert, zipfile.ZIP_DEFLATED)
    w.close()
    print('wrote', out, os.path.getsize(out), flush=True)
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    work = './work'
    los_zip = None
    name = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--los-zip':
            i += 1
            los_zip = args[i]
        elif a == '--name':
            i += 1
            name = args[i]
        else:
            work = a
        i += 1
    build(work, los_zip, name)
