# eNSP VRP 输入法候选助手（学校兼容版）

这是免安装便携版。目标电脑不需要安装 Python、Node、Qt 或其他开发环境。

## 启动

优先双击 `start-school-normal.bat`。如果 eNSP 是管理员方式打开的，再双击 `start-school-admin.bat`。也可以直接运行本目录里的 `ensp-vrp-ime-helper-school.exe`。

## 使用

- 在 eNSP 设备 Console 中输入 VRP 关键词，候选框会自动出现。
- 数字键 `1-9` 选择候选。
- 左箭头或 `-` 上一页，右箭头或 `=` 下一页。
- `Esc` 关闭候选框。
- 控制窗口里的“中文查命令”只负责查询命令，不会自动输入到 eNSP。

## 文件

- `data/vrp_commands_unique.txt`：命令库。
- `rules/descriptions.json`：中文解释和风险说明。
- `daima.txt`：使用次数统计，运行后自动保存到本目录。
- `logs/`：自检和加载报告。

不要只拷贝 exe。请把整个文件夹一起拷到 U 盘或其他电脑上再运行。

## 自检

在本目录打开命令行，可以运行：

```powershell
.\ensp-vrp-ime-helper-school.exe --self-test
.\ensp-vrp-ime-helper-school.exe --paging-smoke-test
```

第二条会真实打开候选框，检查左箭头、右箭头、`-`、`=` 是否可以连续翻页。
