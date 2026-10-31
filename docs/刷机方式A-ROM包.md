# 方式 A · ROM 包刷机（sideload）

> **适合第一次刷机的人。** 全程约 15 分钟，主要靠等。
>
> 这种方式把整个包（1.3 GB）一次性传进手机的恢复模式，由手机自己解压、写分区。
> 你只需要在电脑上敲一条命令。

---

## 你需要的

- 已解锁 bootloader 的小米 6
- 一台电脑（Windows / macOS / Linux 都行）+ 数据线
- 刷机包：`sagit-RestlessOS-16.0.0-lineage22-xxxx.zip`（约 1.3 GB）
- 一个第三方 recovery：`OrangeFox-24.03.16-Unofficial-sagit.img`

> 没解锁？先去 <https://www.miui.com/unlock/> 申请，等 72 小时。这步没捷径。

---

## 第 1 步：装工具（10 分钟）

### Windows

1. 下载 <https://dl.google.com/android/repository/platform-tools-latest-windows.zip>
2. 解压到好找的地方，比如 `C:\platform-tools`
3. 打开这个文件夹，地址栏输入 `cmd` 回车 —— 弹出的黑窗口就是终端

### macOS

```bash
brew install android-platform-tools
```

### Linux（Ubuntu / Mint）

```bash
sudo apt install android-tools-adb android-tools-fastboot
```

### Linux 额外一步（Windows/Mac 跳过）

不装这个，后面会报 `no permissions`：

```bash
sudo tee /etc/udev/rules.d/51-android.rules <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="2717", MODE="0666", GROUP="plugdev"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb
```

### 验证

```bash
adb version
```

看到版本号就行。报 `command not found` 说明没装好。

---

## 第 2 步：备份（别跳过）

刷完手机会变成出厂状态。

**必做：**

- 照片视频 → 拷到电脑
- 微信聊天 → 微信 → 我 → 设置 → 聊天 → 聊天记录备份与迁移 → 备份到电脑
- 通讯录 → 小米账号同步，或导出到 SIM 卡
- **小米账号密码记下来**（刷完要登录，不然可能卡激活界面）

**建议：** 拨号盘输入 `*#06#` 记下 IMEI，拍照存着。

---

## 第 3 步：进 fastboot（2 分钟）

1. 长按电源 → 关机
2. **同时按住「音量下」+「电源」**
3. 等屏幕出现**米兔修机器人**图案、下面写着 `FASTBOOT`，松手

### 让电脑认到它

插上数据线，终端敲：

```bash
fastboot devices
```

应该输出：

```
a5610dac	fastboot
```

看到一串字符 + `fastboot` 就对了。

> **认不到怎么办：**
> - 换根数据线（很多线只能充电）
> - 换 USB 口（别用 USB 3.0 蓝色的，有时会抽风）
> - Windows 装小米 USB 驱动
> - Linux 回第 1 步装 udev 规则

---

## 第 4 步：装一个能干活儿的 recovery（3 分钟）

手机自带的恢复模式只认官方签名，不认第三方包。所以要换一个。

### 4.1 刷进 recovery 分区

```bash
fastboot flash recovery OrangeFox-24.03.16-Unofficial-sagit.img
```

看到 `OKAY` 就成功。

### 4.2 用它启动

```bash
fastboot boot OrangeFox-24.03.16-Unofficial-sagit.img
```

> **为什么既 flash 又 boot？**
> `flash` 是写进分区，`boot` 是临时启动它。
> 小米 6 有个毛病：`fastboot reboot recovery` 有时会启动回原来的系统。
> 所以两个都做，最保险。

### 4.3 确认进对了

等 20 秒左右，手机屏幕变成**橙色背景**的 OrangeFox 界面。

终端敲：

```bash
adb devices
```

应该看到：

```
a5610dac	recovery
```

**关键是最后一列是 `recovery` 不是 `sideload`。** 现在还没到那一步。

---

## 第 5 步：进 sideload 模式（1 分钟）

在**手机屏幕上**操作（不是电脑）：

1. 点左上角菜单（三条横线）
2. 找 **"Apply update from ADB"** 或 **"ADB Sideload"**
3. 如果问要不要 wipe cache，选 **不用**（最后会单独清）
4. 点 **Start** 开始

手机屏幕会显示：

```
Now send the package you want to apply...
```

终端验证：

```bash
adb devices
```

现在应该变成：

```
a5610dac	sideload
```

**看到 `sideload` 就对了。**

---

## 第 6 步：传包（10 分钟，最久的一步）

```bash
adb sideload sagit-RestlessOS-16.0.0-lineage22-xxxx.zip
```

会滚动输出：

```
serving: 'sagit-RestlessOS-....zip'  (~0%)
serving: 'sagit-RestlessOS-....zip'  (~5%)
...
```

### 接下来会发生什么

1. 电脑传文件到手机，进度到 **100%** —— 这时文件传完了；
2. 手机开始解压、写分区，屏幕显示进度条；
3. 最后看到 `Total xfer: 1.00x` 或者类似的话。

> **1.3 GB 用好的线大概 3-5 分钟，慢的线可能 15 分钟。别拔线。**

### 中途看到这个别慌

```
Signature verification failed
Install anyway?
```

**点 Yes / 确认。**

原因：这个包是我自己打的，用的是自己生成的密钥，而 recovery 只信任 LineageOS 官方
签名。这是正常现象，不是包坏了。详见 [`我改了什么.md`](我改了什么.md)。

### 如果卡在 39% 或者显示 `Total xfer: 0.85x` 然后断了

这是数据线/USB 口的问题，不是包坏了。三条路：

1. 换线、换口，重来一遍；
2. 换个 USB 2.0 的 HUB；
3. **改用[方式 B 拆包直刷](刷机方式B-拆包直刷.md)** —— 我就是这么干的。

---

## 第 7 步：清数据（关键！）

刷完包之后，手机上回到 OrangeFox 主界面。

### 7.1 先清分区

手机上：**Wipe** → **Advanced Wipe** → 勾选：

- `Dalvik / ART Cache`
- `Data`
- `Cache`
- `System`（如果列出来了）

滑到底确认。

### 7.2 再格式化 data（**这步不能漏**）

手机上：**Wipe** → **Format Data**

会要求你输入 `yes` 确认，输入后确认。

> **为什么两个都要做？**
> `Wipe Data` 只是把文件删掉（分区结构还在），
> `Format Data` 是重新建立文件系统。
>
> 新系统的 fstab 里 data 分区没有 `formattable` 标记，如果你只 Wipe 不 Format，
> 开机会**无限重启**。这个坑我踩过。

### 7.3 验证

手机上如果在终端里：

```bash
adb shell "df -h /data"
```

应该看到 `/data` 有 **51G** 左右。

---

## 第 8 步：重启

手机上：**Reboot** → **System**

然后等。

### 首次开机要多久

**2 到 5 分钟**，屏幕一直转圈是正常的。别以为坏了。

### 怎么知道它活着

电脑终端：

```bash
lsusb | grep 2717
```

（Windows 用设备管理器，看有没有 `MI 6` 的 MTP 设备）

看到 `2717:ff40` = 系统已经起来了。

> `adb` 这时候通常**看不到设备** —— RestlessOS 默认关 USB 调试，这是安全设计。
> 要用 adb 得进系统里手动打开，见[首次开机](首次开机.md)。

---

## 第 9 步：开机设置

见 **[首次开机](首次开机.md)**。

---

## 一页速查

```bash
# 1. 进 fastboot（手机：音量下 + 电源）
fastboot devices

# 2. 装 recovery
fastboot flash recovery OrangeFox-24.03.16-Unofficial-sagit.img
fastboot boot  OrangeFox-24.03.16-Unofficial-sagit.img

# 3. 手机上：菜单 → Apply update from ADB → Start
adb devices                      # 应显示 recovery 或 sideload

# 4. 传包
adb sideload sagit-RestlessOS-16.0.0-lineage22-xxxx.zip

# 5. 手机上：Wipe Data → Format Data（输 yes）
# 6. 手机上：Reboot → System
```
