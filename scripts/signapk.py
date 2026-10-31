#!/usr/bin/env python3
"""SignApk 兼容的 whole-file 签名器 / 校验器。

footer（zip 注释尾部 6 字节）: <sig_len u16> 0xFFFF <comment_size u16>
comment = "signed by SignApk\\0" + PKCS7 DER
被签内容 = zip[0 : n - comment_size]

用法:
  signapk.py sign   <in.zip> <out.zip> <key.pem> <cert.pem>
  signapk.py verify <in.zip> [trusted.pem]
"""
import hashlib, os, struct, subprocess, sys, tempfile

MAGIC = b'signed by SignApk\x00'

def split(path):
    n = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(n - 6)
        foot = f.read(6)
    sig_len, marker, csize = struct.unpack('<HHH', foot)
    assert marker == 0xFFFF, 'footer marker 不对: %04x' % marker
    assert csize == sig_len + len(MAGIC), (csize, sig_len)
    with open(path, 'rb') as f:
        f.seek(n - csize)
        comment = f.read()
    assert comment.startswith(MAGIC)
    der = comment[len(MAGIC):]
    assert len(der) == sig_len
    return n - csize, der

def verify(path, trusted=None):
    content_len, der = split(path)
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, 'sig.der')
        open(d, 'wb').write(der)
        # 把被签内容截出来
        c = os.path.join(td, 'content.bin')
        with open(path, 'rb') as f, open(c, 'wb') as o:
            left = content_len
            while left > 0:
                b = f.read(min(left, 1 << 20))
                if not b:
                    break
                o.write(b)
                left -= len(b)
        cmd = ['openssl', 'smime', '-verify', '-inform', 'DER', '-in', d,
               '-content', c, '-binary', '-noverify', '-out', os.devnull]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip(), r.stderr.strip())
        if r.returncode != 0:
            print('❌ 签名校验失败')
            return False
        print('✅ 签名校验通过（content %d 字节）' % content_len)
        return True

def sign(src, dst, key, cert):
    content_len, _ = None, None
    n = os.path.getsize(src)
    with tempfile.TemporaryDirectory() as td:
        c = os.path.join(td, 'content.bin')
        with open(src, 'rb') as f, open(c, 'wb') as o:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                o.write(b)
        d = os.path.join(td, 'sig.der')
        cmd = ['openssl', 'smime', '-sign', '-binary', '-noattr', '-md', 'sha256',
               '-signer', cert, '-inkey', key, '-in', c, '-outform', 'DER', '-out', d]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr)
            raise SystemExit('openssl smime -sign 失败')
        der = open(d, 'rb').read()
    comment = MAGIC + der
    assert len(comment) < 0xFFFF
    foot = struct.pack('<HHH', len(der), 0xFFFF, len(comment))
    # 去掉原 zip 的 EOCD 注释（如果有）
    with open(src, 'rb') as f:
        head = f.read()
    eocd = head.rfind(b'PK\x05\x06')
    old_clen = struct.unpack_from('<H', head, eocd + 20)[0]
    if old_clen:
        head = head[:eocd + 22] + head[eocd + 22 + old_clen:]
    with open(dst, 'wb') as o:
        o.write(head)
        o.write(comment)
        o.write(foot)
    print('signed ->', dst, os.path.getsize(dst), 'DER', len(der))

if __name__ == '__main__':
    if sys.argv[1] == 'sign':
        sign(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        ok = verify(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        sys.exit(0 if ok else 1)
