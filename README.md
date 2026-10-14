# eNSP VRP 输入法候选助手

在 [eNSP](https://support.huawei.com/enterprise/zh/software/250314204) 路由器的 Console 里敲命令时，自动弹出**候选框**：敲几个字母就能看到匹配的 VRP 命令，数字键选中，还能看到每条命令的中文解释和风险等级。

因为在 eNSP 里敲长命令太容易拼错，而 eNSP 自带的历史记录和补全都不够用。现在敲 `disp` 就能直接选 `display ip interface brief`，不用记全拼。

## 特点

- **隐身输入**：在设备 Console 里敲的字**不会出现在 eNSP 里**，只显示在候选框里；选中候选时整条命令直接落进去，**不需要先删掉已敲的字母**，所以不存在"退格没删干净、结果变成 `iipxxxx`"这类问题。
- **边敲边提示**：输入 VRP 关键词，候选框自动出现，不需要按额外热键。
- **中文解释**：每条命令配中文说明和**风险等级**（`low` / `medium` / `high`），像 `save`、`reset`、`undo` 这种要小心的会标出来。
- **中文查命令**：控制窗口里有独立入口，输入中文反查命令。**只查询，不会自动往 eNSP 里输入。**
- **免安装**：提供打包好的单文件 exe，目标电脑不需要装 Python 或任何运行环境。

## 怎么用

只有这几种操作会把内容送进 eNSP，其它按键都只在候选框里：

| 按键 | 作用 |
| --- | --- |
| 数字 `1-9` | 选中候选，整条命令落进 eNSP |
| 空格 | 把**当前正在敲的词**原样落进 eNSP，再补一个空格，接着敲下一个词 |
| `Esc` | 把当前正在敲的词原样落进 eNSP，**并退出隐身**（之后输入正常显示，方便手改） |
| `?` `/` `:` 等符号 | 先把当前正在敲的词落进 eNSP，再把这个符号送过去（顺序不会颠倒） |
| 退格 | 只改候选框里的词，不动 eNSP |
| `←` / `-` | 上一页候选 |
| `→` / `=` | 下一页候选 |
| `回车` | **原样放行，不会自动落字** |

以敲 `display ip interface brief` 为例：

| 你的动作 | eNSP 里显示 | 候选框里 |
| --- | --- | --- |
| 敲 `dis` | （空的） | 1 display... 2 display ip... |
| 按 `1` | `display` | |
| 敲空格 | `display ` | |
| 敲 `ip` | `display ` | 1 ip address... |
| 按 `1` | `display ip` | |
| 敲空格 | `display ip ` | |
| 敲 `int` | `display ip ` | 1 interface... |
| 按 `1` | `display ip interface` | |

多词命令（例如 `undo ip address`）就是这么一段一段拼出来的，全程一次退格都不发。

> **注意**：**回车不会把候选框里的字自动写进 eNSP**。如果你敲完不选候选、也不想用候选，请先按 `Esc`（或空格）把字落进 Console，再按回车执行；直接按回车的话，候选框里没落地的字会丢掉。

> **紧急退出**：按 `F8` 可以整体暂停/恢复本程序。隐身输入依赖键盘钩子，万一钩子异常导致 eNSP 里敲不进字，按 `F8` 即可让键盘恢复正常。

## 快速开始（用现成的 exe）

本仓库的以下目录里是打包好的成品，双击 exe 即可运行：

| 目录 | 说明 |
| --- | --- |
| `便携版-64/` | 64 位系统用（现代电脑基本都是） |
| `便携版-32/` | 32 位系统用 |
| `学校兼容版-64/` | 面向校园机房的老系统，附带自动提权脚本 |

> **注意**：**如果 eNSP 是以"管理员身份"打开的，本程序也得以管理员身份启动**，否则 Windows 的 UIPI 机制会拦掉键盘钩子，候选框不会出现（这不是 bug）。`学校兼容版-64/` 里的 `start-school-admin.bat` 会自动提权。

## 从源码运行

只需要 Python 3.8+ 和标准库（`tkinter`、`ctypes`），**没有第三方依赖**。

```powershell
python src\ensp_vrp_ime_helper.py
```

## 打包成 exe

仓库根目录的 `build.ps1` 一键打包，会自动找本机 Python、装 PyInstaller、输出到 `便携版-64\` 或 `便携版-32\`：

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1          # 自动按位数打
powershell -ExecutionPolicy Bypass -File build.ps1 -Arch 32  # 强制 32 位（需 32 位 Python）
```

> 32 位版本必须用 32 位 Python 打包（例如 `py -3.11-32`）。

## 自检

程序内置几项自检，改完代码可以先跑一遍：

```powershell
# 加载自检 + 候选逻辑自检
.\ensp-vrp-ime-helper.exe --self-test

# 真实弹出候选框，检查左/右箭头、- / = 能否连续翻页
.\ensp-vrp-ime-helper.exe --paging-smoke-test
```

（源码方式运行同理，把 exe 换成 `python src\ensp_vrp_ime_helper.py` 即可。）

## 目录结构

```
src/
  ensp_vrp_ime_helper.py   # 主程序（单文件）
  monitor_panel.py         # 调试用的小工具，非必需
data/
  vrp_commands_unique.txt  # VRP 命令库
rules/
  descriptions.json        # 命令的中文解释、所属视图、风险等级
build.ps1                  # 一键打包脚本
ensp-vrp-ime-helper.spec   # PyInstaller 配置
scripts/                   # 学校版启动脚本
```

程序所有路径都基于 `__file__` 动态解析，整个目录可以直接拷贝到别处运行。

## 数据来源说明

- `data/vrp_commands_unique.txt` 与 `rules/descriptions.json` 中的 VRP 命令、命令语法、中文释义，整理自华为 VRP 的**公开命令参考文档**，仅用于命令提示与教学。命令名称与语法属于事实性信息；中文释义为便于理解所作的转述。
- 本项目的**代码**以 MIT 许可证开源；上述**数据文件**的著作权归属华为技术有限公司，请注意使用范围。
- eNSP 与 VRP 是华为的商标/产品，本项目与华为无任何关联，非官方工具。

## 许可证

[MIT](LICENSE) © 2026 xngs9
