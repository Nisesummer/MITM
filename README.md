# Stash 覆写规则

个人 Stash MitM 重写与去广告覆写文件（原 QX 规则已迁移为 Stash `.stoverride` 格式）。

## 订阅链接

```
https://raw.githubusercontent.com/Nisesummer/MITM/main/rewrite.stoverride
```

## Stash 使用方式

1. 打开 Stash → **覆写** → 右上角 **+** → **从链接下载**，填入上方链接。
2. 启用该覆写。
3. 如需让 MitM 重写生效，在 Stash → **设置 → HTTP → MitM** 中开启 MitM 并安装信任根证书。
