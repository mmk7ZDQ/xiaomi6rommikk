#!/usr/bin/env python3
"""把 RestlessOS GSI 的 system 镜像改成「实体键模式」——去掉虚拟导航栏 / 手势条。

MI 6 (sagit) 有实体键：
  指纹键 = HOME (102)、返回 = BACK (158)、多任务 = APP_SWITCH (139)
所以不需要虚拟导航栏。

phh 系 treble GSI（RestlessOS 就是）默认假设设备没有实体键，会强制打开导航栏：
  /system/build.prop                  persist.sys.phh.mainkeys=0
  /system/product/etc/build.prop      ro.boot.vendor.overlay.theme=...navbar.gestural

本脚本改这三处，overlay APK 一个都不删（删 APK 会让 RRO 表残缺，风险高）：

  persist.sys.phh.mainkeys=0   ->  =1
  新增                            qemu.hw.mainkeys=1
  ro.boot.vendor.overlay.theme=...navbar.gestural  ->  留空

用法:
  patch-navbar.py <system.img>            # 原地改（建议先 cp 一份）
  patch-navbar.py <system.img> --dry-run  # 只打印将要改什么

依赖: e2fsprogs 的 debugfs（/usr/sbin/debugfs），需要镜像可写。
"""
import os, subprocess, sys, tempfile

DEBUGFS = '/usr/sbin/debugfs'

SYS_PROP = '/system/build.prop'
PROD_PROP = '/system/product/etc/build.prop'
MAINKEYS_OLD = 'persist.sys.phh.mainkeys=0'
MAINKEYS_NEW = 'persist.sys.phh.mainkeys=1'
QEMU_LINE = 'qemu.hw.mainkeys=1'
THEME_KEY = 'ro.boot.vendor.overlay.theme='


def dbg(img, *cmds, write=False):
    """跑 debugfs 命令。

    注意：debugfs 只接受**一个** -R，传多个只有最后一个生效。
    多条命令必须写进临时文件用 -f 执行（之前就栽在这）。
    """
    if len(cmds) == 1 and '\n' not in cmds[0]:
        args = [DEBUGFS]
        if write:
            args.append('-w')
        args += ['-R', cmds[0], img]
        r = subprocess.run(args, capture_output=True, text=True)
        return r.stdout + r.stderr

    with tempfile.NamedTemporaryFile('w', suffix='.cmds', delete=False) as f:
        f.write('\n'.join(cmds) + '\n')
        path = f.name
    try:
        args = [DEBUGFS]
        if write:
            args.append('-w')
        args += ['-f', path, img]
        r = subprocess.run(args, capture_output=True, text=True)
        return r.stdout + r.stderr
    finally:
        os.unlink(path)


def read_file(img, path, tmpdir):
    # 注意：/system/build.prop 和 /system/product/etc/build.prop 同名，
    # 必须用路径派生的唯一文件名，否则两个文件会互相覆盖。
    local = os.path.join(tmpdir, path.strip('/').replace('/', '_'))
    if os.path.exists(local):
        os.remove(local)
    dbg(img, f'dump {path} {local}')
    if not os.path.exists(local):
        raise SystemExit(f'读不出 {path}（镜像里没有这个文件？）')
    return open(local, 'rb').read()


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    img = sys.argv[1]
    dry = '--dry-run' in sys.argv

    if not os.path.exists(img):
        raise SystemExit(f'找不到镜像: {img}')

    with tempfile.TemporaryDirectory() as td:
        sys_prop = read_file(img, SYS_PROP, td).decode()
        prod_prop = read_file(img, PROD_PROP, td).decode()

        changed = []

        # 1) phh mainkeys
        if MAINKEYS_OLD in sys_prop:
            sys_prop = sys_prop.replace(MAINKEYS_OLD, MAINKEYS_NEW)
            changed.append(f'{SYS_PROP}: {MAINKEYS_OLD} -> {MAINKEYS_NEW}')
        elif MAINKEYS_NEW in sys_prop:
            print(f'[=] {SYS_PROP}: 已经是 {MAINKEYS_NEW}')
        else:
            print(f'[!] {SYS_PROP}: 没找到 mainkeys，跳过')

        # 2) qemu.hw.mainkeys（AOSP 标准开关：有硬件键就别画导航栏）
        if QEMU_LINE not in sys_prop:
            sys_prop = sys_prop.rstrip('\n') + (
                '\n\n# MI 6 有实体键（返回/多任务 + 指纹 Home），不要虚拟导航栏\n'
                f'{QEMU_LINE}\n')
            changed.append(f'{SYS_PROP}: 追加 {QEMU_LINE}')
        else:
            print(f'[=] {SYS_PROP}: 已有 {QEMU_LINE}')

        # 3) 强制手势主题 -> 清空
        lines = prod_prop.split('\n')
        for i, ln in enumerate(lines):
            if ln.startswith(THEME_KEY) and ln != THEME_KEY:
                old = ln
                lines[i] = THEME_KEY
                changed.append(f'{PROD_PROP}: {old} -> (空)')
        prod_prop = '\n'.join(lines)

        if not changed:
            print('没有需要改的地方，镜像已经是实体键模式。')
            return

        print('将要修改:')
        for c in changed:
            print('  -', c)

        if dry:
            print('\n--dry-run：没有写入。')
            return

        sys_local = os.path.join(td, 'new_system_build.prop')
        prod_local = os.path.join(td, 'new_product_build.prop')
        open(sys_local, 'w').write(sys_prop)
        open(prod_local, 'w').write(prod_prop)

        cmds = []
        for path, local in ((SYS_PROP, sys_local), (PROD_PROP, prod_local)):
            cmds += [
                f'rm {path}',
                f'write {local} {path}',
                f'sif {path} mode 0100600',
                f'sif {path} uid 0',
                f'sif {path} gid 0',
                f'ea_set {path} security.selinux u:object_r:system_file:s0',
            ]
        dbg(img, *cmds, write=True)

        # 回读校验
        v1 = read_file(img, SYS_PROP, td).decode()
        v2 = read_file(img, PROD_PROP, td).decode()
        assert v1 == sys_prop, 'system build.prop 回读不一致'
        assert v2 == prod_prop, 'product build.prop 回读不一致'
        print('\n✅ 写入并回读校验通过')
        print('   建议再跑一次 e2fsck -fn <img> 确认文件系统干净')


if __name__ == '__main__':
    main()
