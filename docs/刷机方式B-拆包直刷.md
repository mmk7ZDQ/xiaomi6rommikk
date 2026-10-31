# 方式 B · 拆包直刷（fastboot）

> **比方式 A 快，但命令多。** 全程约 8 分钟。
>
> 不经过恢复模式，直接把每个分区单独写进去。掉线了可以从断的地方接着刷，
> 不像 sideload 断了就得从头来。

---

## 什么时候用这个

- 方式 A 老是掉线（我就是）
- 想要快
- 喜欢看清楚每一步在干什么

---

## 你需要的

- 已解锁 bootloader 的小米 6
- 电脑 + 数据线（**这条线很关键**，方式 B 最吃线）
- 四个文件：`boot.img`、`system-padded.img`、`vendor.img`、`OrangeFox-*.img`
- 约 **10 GB** 电脑空闲空间（放文件用）

> 如果你只有 `sagit-RestlessOS-*.zip`，先解压它：
> ```bash
> unzip sagit-RestlessOS-16.0.0-lineage22-xxxx.zip -d 拆包
> ```
> 里面是 `system.new.dat.br` 这种块文件，不是直接能刷的 img。
> 这时候建议直接跑仓库里的脚本（见文末「从源码自己构建」）。

---

## 第 1 步：装工具 + 备份 + 进 fastboot

跟[方式 A 的第 1～3 步](刷机方式A-ROM包.md)完全一样，照做就行。

到这里你应该已经在 fastboot 界面，`fastboot devices` 能看到设备。

---

## 第 2 步：先刷 boot（几秒）

```bash
fastboot flash boot boot.img
```

输出：

```
Sending 'boot' (15964 KB)     OKAY [  0.349s]
Writing 'boot'                OKAY [  0.095s]
Finished. Total time: 0.448s
```

---

## 第 3 步：刷 system（约 5 分钟，最久）

```bash
fastboot flash system system-padded.img
```

输出会一块一块滚动：

```
Invalid sparse file format at header magic
Sending sparse 'system' 1/6 (524236 KB)     OKAY [ 14.052s]
Writing 'system'                            OKAY [  3.310s]
Sending sparse 'system' 2/6 (524212 KB)     OKAY [ 11.211s]
Writing 'system'                            OKAY [  3.331s]
Sending sparse 'system' 3/6 (524256 KB)     OKAY [ 15.831s]
Writing 'system'                            OKAY [  3.312s]
Sending sparse 'system' 4/6 (524228 KB)     OKAY [ 11.168s]
Writing 'system'                            OKAY [  3.356s]
Sending sparse 'system' 5/6 (524216 KB)     OKAY [ 17.267s]
Writing 'system'                            OKAY [  3.341s]
Sending sparse 'system' 6/6 (427632 KB)     OKAY [  9.006s]
Writing 'system'                           OKAY [178.757s]
Finished. Total time: 283.882s
```

### 两件看起来像报错但不是的事

**`Invalid sparse file format at header magic`**
这是 fastboot 在说"这个文件不是 sparse 格式，我按原样发"。**正常**，继续。

**最后一块 `Writing 'system'` 卡了 3 分钟**
第 6 块写进 eMMC 特别慢（实测 178 秒）。**这时候千万不能拔线。**

> **怎么确认它真的在干活？**
> 另开一个终端：
> ```bash
> pgrep -af fastboot        # 拿到 PID
> cat /proc/<PID>/io        # 看 rchar
> ```
> `rchar` 已经涨到 3 GB 以上 = 数据发完了，设备在写，**等就行**。
> 如果 `rchar` 30 秒完全不动、进程状态是 `D`，那就卡死了，看下面「fastboot 卡死」。

---

## 第 4 步：刷 vendor 到 cust（约 1 分钟）

```bash
fastboot flash cust vendor.img
```

输出：

```
Sending sparse 'cust' 1/1 (422081 KB)     OKAY [  9.595s]
Writing 'cust'                            OKAY [ 37.333s]
Finished. Total time: 49.160s
```

> ⚠️ **是 `cust` 不是 `vendor`。**
> 小米 6 的 `/vendor` 实际挂在一个叫 `cust` 的分区上，这是它从 MIUI 时代留下来的怪癖。
> 写成 `fastboot flash vendor` 会报分区不存在，或者刷到一个没用的地方。

### 顺带确认大小

```bash
fastboot getvar partition-size:system
```

应该是：

```
partition-size:system:  0x140000000
```

`0x140000000` = 5 368 709 120 字节 = **5 GiB**。
`system-padded.img` 必须是这个大小，否则会留下旧系统的残块。

---

## 第 5 步：清数据

```bash
fastboot erase userdata
fastboot erase cache
fastboot erase misc
```

三条都要 `OKAY`。

> `erase misc` 是清掉上一次的启动标记。不清的话系统可能还想着"上次是从 A 槽启动的"
> 之类，导致跳过首次设置。

---

## 第 6 步：格式化 data（**最关键的一步**）

到这一步 `/data` 是**一片裸的空白块**，没有文件系统。

新系统的 fstab 里 data 分区**没有 `formattable` 标记**，所以系统**不会自动格式化**。
结果就是：挂不上 `/data` → `bpfloader` 启动失败 → init 自杀重启 → **无限重启**。

我那晚就是这么卡住的，日志里是：

```
Invalid ext4 superblock on '/dev/block/bootdevice/by-name/userdata'
Failed to mount an un-encryptable, interrupted, or wiped partition at /data
Service 'bpfloader' (pid 962) exited with status 1
reboot: Restarting system with command 'netbpfload-missing'
```

### 6.1 临时启动 OrangeFox

```bash
fastboot boot OrangeFox-24.03.16-Unofficial-sagit.img
```

> 注意是 `boot` 不是 `flash` —— 只是临时跑一下，不写进分区。
> 用完重启就没了。

等 20 秒，手机屏幕变成橙色界面。终端确认：

```bash
adb devices
```

应该显示 `recovery`。

### 6.2 格式化

```bash
adb shell "twrp format data"
```

输出：

```
使用 mke2fs 格式化 Data...
完成
您可能需重启 recovery 才能再次使用 /data。
处理脚本文件完成
正在更新分区详情...
...完成
```

然后：

```bash
adb shell "twrp wipe cache"
```

### 6.3 确认成功

```bash
adb shell "df -h /data"
```

应该看到：

```
Filesystem       Size  Used Avail Use% Mounted on
/dev/block/sda17   51G   20K   51G   1% /data
```

**看到 51G 左右就成功了。**

---

## 第 7 步：重启

```bash
adb reboot
```

等 2-5 分钟。看到 MTP 上线就活了：

```bash
lsusb | grep 2717
# Bus 001 Device 009: ID 2717:ff40 Xiaomi Inc. Mi/Redmi series (MTP)
```

---

## 一页速查

```bash
# 手机：音量下 + 电源 → fastboot
fastboot devices

fastboot flash boot    boot.img
fastboot flash system  system-padded.img
fastboot flash cust    vendor.img

fastboot erase userdata
fastboot erase cache
fastboot erase misc

fastboot boot OrangeFox-24.03.16-Unofficial-sagit.img
adb shell "twrp format data"
adb shell "twrp wipe cache"

adb reboot
```

---

## fastboot 卡死了怎么办

症状：命令不动了，`Ctrl+C` 也没反应，`fastboot devices` 也不回话。

**原因**：主机侧 fastboot 的 USB 端点卡在 D 状态（`usbfs_start_wait_urb`），
设备本身没事。

**按顺序试：**

### 1. 先确认是真卡死不是慢

```bash
pgrep -af fastboot
cat /proc/<PID>/io | grep rchar
```

等 30 秒再看一次 `rchar`：

- **涨了** → 在干活，等
- **完全不动 + 状态 D** → 真卡死

### 2. 杀掉进程

```bash
kill -9 <PID>
```

### 3. 试试复位 USB（Linux，普通用户可行）

```bash
python3 - <<'EOF'
import os, fcntl
# 先用 lsusb 找到总线号和设备号
fd = os.open('/dev/bus/usb/001/004', os.O_WRONLY)
fcntl.ioctl(fd, 0x5514, 0)      # USBDEVFS_RESET
os.close(fd)
print('reset ok')
EOF
```

### 4. 短信不通就长按电源

**手机上长按电源 15 秒**强制重启，然后音量下 + 电源重新进 fastboot。

这是最可靠的方法。我那晚两次都是这么救回来的，**没有任何数据损坏**。

---

## 从源码自己构建

如果你手上没有现成的 img 文件，只有仓库：

```bash
git clone https://github.com/mmk7ZDQ/xiaomi6rommikk.git
cd xiaomi6rommikk

# 全自动：下载 PSCI → 改属性 → 生成 payload → 拆出 vendor → 打包
./scripts/build-rom.sh ./work
```

产物在 `work/`：

| 文件 | 用途 |
|---|---|
| `work/system.img` | 打过补丁的 system（3 GB） |
| `work/system-padded.img` | 补齐到 5 GiB，**直接刷这个** |
| `work/vendor.img` | 驱动，刷到 cust |
| `work/boot.img` | 内核 |
| `work/out/*.zip` | 方式 A 用的包 |

然后：

```bash
./scripts/flash-fastboot.sh ./work
```

会交互式确认后自动刷完前面的第 2～5 步。
