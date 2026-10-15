import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from ctypes import wintypes
from pathlib import Path


APP_NAME = "eNSP VRP 输入法候选助手"
PAGE_SIZE = 9
DEFAULT_CANDIDATE_OPACITY = 1.0
MIN_CANDIDATE_OPACITY = 0.25
MANUAL_NAV_KEYSYMS = {"Left", "Right", "minus", "equal", "KP_Left", "KP_Right", "KP_Subtract", "KP_Add", "Escape"}
SINGLE_INSTANCE_MUTEX = "Local\\eNSP_VRP_IME_Helper_Single_Instance"
ERROR_ALREADY_EXISTS = 183
TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./:-]*|[\u4e00-\u9fff]+")
WORD_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*")
PREFIX_QUERY_RE = re.compile(r"[a-z0-9 _./:-]+")
TAIL_SEPARATOR_RE = re.compile(r"[\s:./\\]+")
PLACEHOLDER_RE = re.compile(r"\b(?:INTEGER|STRING|HEX)<[^>]+>|ENUM\{[^}]+\}|X\.X\.X\.X|X:X::X:X(?:/M)?|H-H-H|HH:MM:SS|YYYY/MM/DD|\bTEXT\b")
SYNTAX_MARK_RE = re.compile(r"[{}\[\]\|\*&<>]")
SAFE_CHOICE_OPTION_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/-]*(?:\s+[A-Za-z0-9_][A-Za-z0-9_.:/-]*)*")
MAX_CHOICE_OPTIONS = 64
CANDIDATE_MIN_WIDTH_PX = 420
CANDIDATE_BASE_WIDTH_PX = 780
CANDIDATE_MAX_WIDTH_PX = 1050
CANDIDATE_MIN_COMMAND_PX = 430
CANDIDATE_MIN_DESCRIPTION_PX = 190
CANDIDATE_INDEX_PX = 42
CANDIDATE_CHROME_PX = 32
CANDIDATE_COLUMN_PAD_PX = 18
CANDIDATE_SCREEN_MARGIN_PX = 16

COMMON_COMMANDS = [
    ("display", "查看设备信息", "any", "low"),
    ("undo", "撤销配置或恢复缺省", "any", "medium"),
    ("system-view", "进入系统视图", "user-view", "low"),
    ("sysname", "设置设备名称", "system-view", "low"),
    ("quit", "退出当前视图", "any", "low"),
    ("return", "返回用户视图", "any", "low"),
    ("save", "保存当前配置", "user-view", "high"),
    ("display current-configuration", "查看当前配置", "user-view", "low"),
    ("display ip interface brief", "查看接口 IP 摘要", "any", "low"),
    ("display interface brief", "查看接口状态摘要", "any", "low"),
    ("display vlan", "查看 VLAN 信息", "any", "low"),
    ("display port vlan", "查看端口 VLAN", "user-view", "low"),
    ("interface Ethernet", "进入以太网接口", "system-view", "low"),
    ("interface GigabitEthernet", "进入千兆以太网接口", "system-view", "low"),
    ("interface LoopBack", "进入 LoopBack 接口", "system-view", "low"),
    ("interface Vlanif", "进入 VLAN 虚接口", "system-view", "low"),
    ("interface range", "批量进入接口", "system-view", "medium"),
    ("vlan", "进入 VLAN 视图", "system-view", "low"),
    ("ospf", "进入 OSPF 视图", "system-view", "medium"),
    ("acl", "进入 ACL 视图", "system-view", "medium"),
]

COMMON_COMMANDS.extend([
    ("aaa", "进入 AAA 视图", "system-view", "low"),
    ("local-user", "配置本地用户", "aaa-view", "low"),
    ("user-interface vty", "进入 VTY 用户界面视图", "system-view", "low"),
    ("user-interface console", "进入 Console 用户界面视图", "system-view", "low"),
    ("authentication-mode", "配置认证方式", "user-interface-view", "low"),
    ("authentication-mode password", "配置密码认证方式", "user-interface-view", "low"),
    ("set authentication password", "设置用户界面认证密码", "user-interface-view", "medium"),
    ("user privilege level", "配置用户界面权限级别", "user-interface-view", "medium"),
    ("idle-timeout", "配置用户界面空闲超时时间", "user-interface-view", "low"),
    ("screen-length", "配置终端屏幕每页行数", "user-interface-view", "low"),
    ("screen-length 0 temporary", "临时关闭终端分屏显示", "user-view", "low"),
    ("history-command max-size", "配置历史命令缓存条数", "user-interface-view", "low"),
    ("protocol inbound", "配置允许登录协议", "user-interface-view", "low"),
    ("protocol inbound all", "允许 Telnet 和 SSH 登录", "user-interface-view", "low"),
    ("protocol inbound ssh", "只允许 SSH 登录", "user-interface-view", "low"),
    ("protocol inbound telnet", "只允许 Telnet 登录", "user-interface-view", "medium"),
    ("arp", "配置 ARP 参数", "system-view", "low"),
    ("clock", "配置系统时间", "user-view", "low"),
    ("clock datetime", "设置系统日期和时间", "user-view", "low"),
    ("clock timezone", "设置系统时区", "user-view", "low"),
    ("display clock", "查看系统时间", "user-view", "low"),
    ("display version", "查看版本信息", "user-view", "low"),
    ("display device", "查看设备信息", "user-view", "low"),
    ("display startup", "查看启动配置文件", "user-view", "low"),
    ("display users", "查看当前登录用户", "user-view", "low"),
    ("display history-command", "查看历史命令", "user-view", "low"),
    ("display diagnostic-information", "查看诊断信息", "user-view", "low"),
    ("display logbuffer", "查看日志缓冲区", "user-view", "low"),
    ("ftp", "使用 FTP 传输文件", "user-view", "low"),
    ("ftp server enable", "开启 FTP 服务", "system-view", "medium"),
    ("header", "配置登录提示信息", "system-view", "low"),
    ("header login", "配置登录前提示信息", "system-view", "low"),
    ("header shell", "配置登录后提示信息", "system-view", "low"),
    ("help", "查看命令帮助", "any", "low"),
    ("ip route-static", "配置静态路由", "system-view", "low"),
    ("language-mode Chinese", "切换为中文显示", "user-view", "low"),
    ("language-mode English", "切换为英文显示", "user-view", "low"),
    ("ntp-service", "配置 NTP 时间同步", "system-view", "low"),
    ("ping", "测试网络连通性", "user-view", "low"),
    ("reboot", "重启设备", "user-view", "high"),
    ("reset saved-configuration", "清空下次启动配置文件", "user-view", "high"),
    ("rip", "进入 RIP 视图", "system-view", "medium"),
    ("rsa local-key-pair create", "创建本地 RSA 密钥对", "system-view", "medium"),
    ("isis", "进入 IS-IS 视图", "system-view", "medium"),
    ("route-policy", "配置路由策略", "system-view", "medium"),
    ("snmp-agent", "配置 SNMP 管理", "system-view", "low"),
    ("ssh user", "配置 SSH 用户", "system-view", "low"),
    ("stelnet", "使用 Stelnet 登录设备", "user-view", "low"),
    ("stelnet server enable", "开启 Stelnet 服务", "system-view", "medium"),
    ("telnet", "使用 Telnet 登录设备", "user-view", "low"),
    ("telnet server enable", "开启 Telnet 服务", "system-view", "medium"),
    ("terminal monitor", "开启终端监视信息", "user-view", "low"),
    ("undo terminal monitor", "关闭终端监视信息", "user-view", "low"),
    ("terminal debugging", "开启终端调试信息", "user-view", "medium"),
    ("undo terminal debugging", "关闭终端调试信息", "user-view", "low"),
    ("terminal trapping", "开启终端告警信息", "user-view", "medium"),
    ("undo terminal trapping", "关闭终端告警信息", "user-view", "low"),
    ("terminal logging", "开启终端日志信息", "user-view", "medium"),
    ("undo terminal logging", "关闭终端日志信息", "user-view", "low"),
    ("tftp", "使用 TFTP 传输文件", "user-view", "low"),
    ("tracert", "跟踪报文转发路径", "user-view", "low"),
    ("vrrp", "配置 VRRP 虚拟路由冗余", "interface-view", "medium"),
    ("display this", "查看当前视图配置", "any", "low"),
    ("display arp", "查看 ARP 表项", "user-view", "low"),
    ("display ip routing-table", "查看 IP 路由表", "user-view", "low"),
    ("display ospf peer", "查看 OSPF 邻居", "user-view", "low"),
    ("display saved-configuration", "查看已保存配置", "user-view", "low"),
    ("local-user password irreversible-cipher", "配置本地用户不可逆密文密码", "aaa-view", "medium"),
    ("local-user privilege level", "配置本地用户权限级别", "aaa-view", "medium"),
    ("local-user service-type ssh", "允许本地用户使用 SSH", "aaa-view", "low"),
    ("local-user service-type telnet", "允许本地用户使用 Telnet", "aaa-view", "medium"),
    ("ip address", "configure interface IP address", "interface-view", "low"),
    ("undo ip address", "remove interface IP address", "interface-view", "medium"),
    ("shutdown", "关闭接口", "interface-view", "medium"),
    ("undo shutdown", "开启接口", "interface-view", "low"),
    ("port link-type access", "set port link type access", "interface-view", "low"),
    ("port link-type trunk", "set port link type trunk", "interface-view", "low"),
    ("port link-type hybrid", "set port link type hybrid", "interface-view", "low"),
    ("port default vlan", "配置接口缺省 VLAN", "interface-view", "low"),
    ("port trunk allow-pass vlan", "配置 Trunk 允许通过的 VLAN", "interface-view", "low"),
    ("vlan batch", "批量创建 VLAN", "system-view", "low"),
])

COMMON_COMMANDS.extend([
    ("display cpu-usage", "查看 CPU 使用率", "user-view", "low"),
    ("display memory-usage", "查看内存使用率", "user-view", "low"),
    ("display stp brief", "查看 STP 简要状态", "user-view", "low"),
    ("display lldp neighbor brief", "查看 LLDP 邻居摘要", "user-view", "low"),
    ("display trapbuffer", "查看告警缓冲区", "user-view", "low"),
    ("display ntp-service status", "查看 NTP 服务状态", "user-view", "low"),
    ("display ssh user-information", "查看 SSH 用户信息", "user-view", "low"),
    ("display stelnet server status", "查看 Stelnet 服务状态", "user-view", "low"),
    ("display telnet server status", "查看 Telnet 服务状态", "user-view", "low"),
    ("display ftp-server", "查看 FTP 服务状态", "user-view", "low"),
    ("display ospf routing", "查看 OSPF 路由", "user-view", "low"),
    ("display ospf lsdb", "查看 OSPF 链路状态数据库", "user-view", "low"),
    ("display rip route", "查看 RIP 路由", "user-view", "low"),
    ("display ip pool", "查看 IP 地址池", "user-view", "low"),
    ("display dhcp server ip-in-use", "查看 DHCP 已分配地址", "user-view", "low"),
    ("info-center enable", "开启信息中心", "system-view", "medium"),
    ("undo info-center enable", "关闭信息中心", "system-view", "medium"),
    ("info-center loghost", "配置日志主机", "system-view", "medium"),
    ("debugging all", "开启全部调试信息", "user-view", "high"),
    ("undo debugging all", "关闭全部调试信息", "user-view", "low"),
    ("reset counters interface", "清除接口统计计数", "user-view", "medium"),
    ("reset logbuffer", "清空日志缓冲区", "user-view", "medium"),
    ("lldp enable", "开启 LLDP 功能", "system-view", "low"),
    ("undo lldp enable", "关闭 LLDP 功能", "system-view", "medium"),
    ("stp edged-port enable", "开启 STP 边缘端口", "interface-view", "low"),
    ("undo stp edged-port enable", "关闭 STP 边缘端口", "interface-view", "medium"),
    ("version 2", "配置 RIP 版本 2", "rip-view", "low"),
    ("rule permit", "配置 ACL 允许规则", "acl-view", "low"),
    ("rule deny", "配置 ACL 拒绝规则", "acl-view", "medium"),
    ("nat outbound", "配置出方向 NAT", "interface-view", "medium"),
    ("dhcp enable", "开启 DHCP 功能", "system-view", "low"),
    ("dhcp select global", "接口使用全局地址池分配地址", "interface-view", "low"),
    ("dhcp select interface", "接口使用接口地址池分配地址", "interface-view", "low"),
    ("ip pool", "进入 IP 地址池视图", "system-view", "low"),
    ("gateway-list", "配置地址池网关", "ip-pool-view", "low"),
    ("excluded-ip-address", "配置地址池排除地址", "ip-pool-view", "low"),
    ("dns-list", "配置地址池 DNS 服务器", "ip-pool-view", "low"),
    ("lease day", "配置地址租期天数", "ip-pool-view", "low"),
    ("dir", "查看文件目录", "user-view", "low"),
    ("more", "查看文件内容", "user-view", "low"),
    ("delete", "删除文件", "user-view", "medium"),
    ("copy", "复制文件", "user-view", "medium"),
    ("rename", "重命名文件", "user-view", "medium"),
    ("mkdir", "创建目录", "user-view", "medium"),
    ("rmdir", "删除目录", "user-view", "medium"),
])

COMMON_COMMANDS.extend([
    ("display interface GigabitEthernet", "查看千兆以太网接口信息", "user-view", "low"),
    ("display interface Ethernet", "查看以太网接口信息", "user-view", "low"),
    ("display interface Vlanif", "查看 VLAN 虚接口信息", "user-view", "low"),
    ("interface Eth-Trunk", "进入链路聚合接口", "system-view", "low"),
    ("interface NULL 0", "进入 NULL 0 接口", "system-view", "low"),
    ("port hybrid pvid vlan", "配置混合端口缺省 VLAN", "interface-view", "low"),
    ("port hybrid tagged vlan", "配置混合端口允许带标签 VLAN", "interface-view", "low"),
    ("port hybrid untagged vlan", "配置混合端口允许不带标签 VLAN", "interface-view", "low"),
    ("undo port hybrid pvid vlan", "恢复混合端口缺省 VLAN", "interface-view", "medium"),
    ("undo port hybrid tagged vlan", "删除混合端口带标签 VLAN", "interface-view", "medium"),
    ("undo port hybrid untagged vlan", "删除混合端口不带标签 VLAN", "interface-view", "medium"),
    ("display ospf brief", "查看 OSPF 简要信息", "user-view", "low"),
    ("display ospf interface", "查看 OSPF 接口信息", "user-view", "low"),
    ("display rip interface", "查看 RIP 接口信息", "user-view", "low"),
    ("stp root primary", "配置本设备为 STP 主根桥", "system-view", "medium"),
    ("stp root secondary", "配置本设备为 STP 备根桥", "system-view", "medium"),
    ("authentication-mode aaa", "配置 AAA 认证方式", "user-interface-view", "low"),
    ("set authentication password cipher", "设置用户界面密文认证密码", "user-interface-view", "medium"),
    ("password cipher", "配置密文密码", "aaa-view", "medium"),
    ("password irreversible-cipher", "配置不可逆密文密码", "aaa-view", "medium"),
    ("authentication-type password", "配置密码认证类型", "system-view", "low"),
    ("service-type stelnet", "允许使用 Stelnet 服务", "system-view", "low"),
    ("service-type ssh", "允许使用 SSH 服务", "aaa-view", "low"),
    ("service-type telnet", "允许使用 Telnet 服务", "aaa-view", "medium"),
    ("undo network", "删除路由协议网络配置", "routing-view", "medium"),
    ("undo vlan batch", "批量删除 VLAN", "system-view", "medium"),
])

COMMAND_PRIORITY = {
    "display": 900,
    "system-view": 820,
    "save": 760,
    "quit": 700,
    "return": 680,
    "undo": 500,
    "display ip": 360,
    "display ip interface brief": 350,
    "display current-configuration": 340,
    "display interface GigabitEthernet": 330,
    "display interface Ethernet": 325,
    "display interface Vlanif": 320,
    "interface GigabitEthernet": 620,
    "interface Ethernet": 610,
    "interface Vlanif": 600,
    "interface LoopBack": 590,
    "interface range": 580,
    "interface Eth-Trunk": 570,
    "interface NULL 0": 560,
    "undo terminal monitor": 520,
    "terminal monitor": 480,
    "undo terminal debugging": 470,
    "terminal debugging": 460,
    "undo terminal trapping": 450,
    "terminal trapping": 440,
    "undo terminal logging": 430,
    "terminal logging": 420,
    "undo info-center enable": 260,
    "undo debugging all": 250,
    "port link-type access": 300,
    "port link-type trunk": 290,
    "port link-type hybrid": 280,
    "port hybrid pvid vlan": 275,
    "port hybrid tagged vlan": 270,
    "port hybrid untagged vlan": 265,
    "ip address": 30,
}

DESCRIPTION_OVERRIDES = {
    "display": "查看设备信息",
    "undo": "撤销配置或恢复缺省",
    "aaa": "进入 AAA 视图",
    "arp": "配置 ARP 参数",
    "clock": "配置系统时间",
    "clock datetime": "设置系统日期和时间",
    "clock timezone": "设置系统时区",
    "ftp": "使用 FTP 传输文件",
    "ftp server enable": "开启 FTP 服务",
    "header": "配置登录提示信息",
    "header login": "配置登录前提示信息",
    "header shell": "配置登录后提示信息",
    "help": "查看命令帮助",
    "authentication-mode": "配置认证方式",
    "authentication-mode password": "配置密码认证方式",
    "set authentication password": "设置用户界面认证密码",
    "user privilege level": "配置用户界面权限级别",
    "idle-timeout": "配置用户界面空闲超时时间",
    "screen-length": "配置终端屏幕每页行数",
    "screen-length 0 temporary": "临时关闭终端分屏显示",
    "history-command max-size": "配置历史命令缓存条数",
    "protocol inbound": "配置允许登录协议",
    "protocol inbound all": "允许 Telnet 和 SSH 登录",
    "protocol inbound ssh": "只允许 SSH 登录",
    "protocol inbound telnet": "只允许 Telnet 登录",
    "ip address": "配置接口 IP 地址",
    "undo ip address": "删除接口 IP 地址",
    "ip route-static": "配置静态路由",
    "l3-diag": "三层诊断",
    "local-user": "配置本地用户",
    "local-user password irreversible-cipher": "配置本地用户不可逆密文密码",
    "local-user privilege level": "配置本地用户权限级别",
    "local-user service-type ssh": "允许本地用户使用 SSH",
    "local-user service-type telnet": "允许本地用户使用 Telnet",
    "language-mode Chinese": "切换为中文显示",
    "language-mode English": "切换为英文显示",
    "ntp-service": "配置 NTP 时间同步",
    "ping": "测试网络连通性",
    "port link-type access": "设置接口为接入模式",
    "port link-type trunk": "设置接口为干道模式",
    "port link-type hybrid": "设置接口为混合模式",
    "port default vlan": "配置接口缺省 VLAN",
    "port trunk allow-pass vlan": "配置 Trunk 允许通过的 VLAN",
    "reboot": "重启设备",
    "reset saved-configuration": "清空下次启动配置文件",
    "route-policy": "配置路由策略",
    "rsa local-key-pair create": "创建本地 RSA 密钥对",
    "shutdown": "关闭接口",
    "snmp-agent": "配置 SNMP 管理",
    "ssh user": "配置 SSH 用户",
    "stelnet": "使用 Stelnet 登录设备",
    "stelnet server enable": "开启 Stelnet 服务",
    "stop": "停止当前操作",
    "sysname": "设置设备名称",
    "telnet": "使用 Telnet 登录设备",
    "telnet server enable": "开启 Telnet 服务",
    "terminal": "配置终端信息输出",
    "undo terminal": "关闭终端信息输出配置",
    "terminal monitor": "开启终端监视信息",
    "undo terminal monitor": "关闭终端监视信息",
    "terminal debugging": "开启终端调试信息",
    "undo terminal debugging": "关闭终端调试信息",
    "terminal trapping": "开启终端告警信息",
    "undo terminal trapping": "关闭终端告警信息",
    "terminal logging": "开启终端日志信息",
    "undo terminal logging": "关闭终端日志信息",
    "tftp": "使用 TFTP 传输文件",
    "tracert": "跟踪报文转发路径",
    "undo shutdown": "开启接口",
    "user-interface console": "进入 Console 用户界面视图",
    "user-interface vty": "进入 VTY 用户界面视图",
    "vlan batch": "批量创建 VLAN",
    "vrrp": "配置 VRRP 虚拟路由冗余",
    "display cpu-usage": "查看 CPU 使用率",
    "display memory-usage": "查看内存使用率",
    "display stp brief": "查看 STP 简要状态",
    "display lldp neighbor brief": "查看 LLDP 邻居摘要",
    "display trapbuffer": "查看告警缓冲区",
    "display ntp-service status": "查看 NTP 服务状态",
    "display ssh user-information": "查看 SSH 用户信息",
    "display stelnet server status": "查看 Stelnet 服务状态",
    "display telnet server status": "查看 Telnet 服务状态",
    "display ftp-server": "查看 FTP 服务状态",
    "display ospf routing": "查看 OSPF 路由",
    "display ospf lsdb": "查看 OSPF 链路状态数据库",
    "display rip route": "查看 RIP 路由",
    "display ip pool": "查看 IP 地址池",
    "display dhcp server ip-in-use": "查看 DHCP 已分配地址",
    "info-center enable": "开启信息中心",
    "undo info-center enable": "关闭信息中心",
    "info-center loghost": "配置日志主机",
    "debugging all": "开启全部调试信息",
    "undo debugging all": "关闭全部调试信息",
    "reset counters interface": "清除接口统计计数",
    "reset logbuffer": "清空日志缓冲区",
    "lldp enable": "开启 LLDP 功能",
    "undo lldp enable": "关闭 LLDP 功能",
    "stp edged-port enable": "开启 STP 边缘端口",
    "undo stp edged-port enable": "关闭 STP 边缘端口",
    "version 2": "配置 RIP 版本 2",
    "rule permit": "配置 ACL 允许规则",
    "rule deny": "配置 ACL 拒绝规则",
    "nat outbound": "配置出方向 NAT",
    "dhcp enable": "开启 DHCP 功能",
    "dhcp select global": "接口使用全局地址池分配地址",
    "dhcp select interface": "接口使用接口地址池分配地址",
    "ip pool": "进入 IP 地址池视图",
    "gateway-list": "配置地址池网关",
    "excluded-ip-address": "配置地址池排除地址",
    "dns-list": "配置地址池 DNS 服务器",
    "lease day": "配置地址租期天数",
    "display interface GigabitEthernet": "查看千兆以太网接口信息",
    "display interface Ethernet": "查看以太网接口信息",
    "display interface Vlanif": "查看 VLAN 虚接口信息",
    "interface Eth-Trunk": "进入链路聚合接口",
    "interface NULL 0": "进入 NULL 0 接口",
    "port hybrid pvid vlan": "配置混合端口缺省 VLAN",
    "port hybrid tagged vlan": "配置混合端口允许带标签 VLAN",
    "port hybrid untagged vlan": "配置混合端口允许不带标签 VLAN",
    "undo port hybrid pvid vlan": "恢复混合端口缺省 VLAN",
    "undo port hybrid tagged vlan": "删除混合端口带标签 VLAN",
    "undo port hybrid untagged vlan": "删除混合端口不带标签 VLAN",
    "display ospf brief": "查看 OSPF 简要信息",
    "display ospf interface": "查看 OSPF 接口信息",
    "display rip interface": "查看 RIP 接口信息",
    "stp root primary": "配置本设备为 STP 主根桥",
    "stp root secondary": "配置本设备为 STP 备根桥",
    "authentication-mode aaa": "配置 AAA 认证方式",
    "set authentication password cipher": "设置用户界面密文认证密码",
    "password cipher": "配置密文密码",
    "password irreversible-cipher": "配置不可逆密文密码",
    "authentication-type password": "配置密码认证类型",
    "service-type stelnet": "允许使用 Stelnet 服务",
    "service-type ssh": "允许使用 SSH 服务",
    "service-type telnet": "允许使用 Telnet 服务",
    "undo network": "删除路由协议网络配置",
    "undo vlan batch": "批量删除 VLAN",
    "display port vlan": "查看端口 VLAN",
    "mac-address static": "配置静态 MAC 地址",
    "mac-address blackhole": "配置黑洞 MAC 地址",
    "undo mac-address static": "删除静态 MAC 地址",
    "undo mac-address blackhole": "删除黑洞 MAC 地址",
    "duplex half": "配置接口为半双工模式",
    "duplex full": "配置接口为全双工模式",
    "speed 10": "配置接口速率为 10M",
    "speed 100": "配置接口速率为 100M",
    "speed 1000": "配置接口速率为 1000M",
    "dir": "查看文件目录",
    "more": "查看文件内容",
    "delete": "删除文件",
    "copy": "复制文件",
    "rename": "重命名文件",
    "mkdir": "创建目录",
    "rmdir": "删除目录",
    "display ip interface brief": "查看接口 IP 摘要",
    "display interface brief": "查看接口状态摘要",
    "display this": "查看当前视图配置",
    "display arp": "查看 ARP 表项",
    "display clock": "查看系统时间",
    "display version": "查看版本信息",
    "display device": "查看设备信息",
    "display startup": "查看启动配置文件",
    "display users": "查看当前登录用户",
    "display history-command": "查看历史命令",
    "display diagnostic-information": "查看诊断信息",
    "display logbuffer": "查看日志缓冲区",
    "display ip routing-table": "查看 IP 路由表",
    "display ospf peer": "查看 OSPF 邻居",
    "display saved-configuration": "查看已保存配置",
    "startup saved-configuration": "指定下次启动配置文件",
    "undo startup saved-configuration": "取消下次启动配置文件",
    "display debugging": "查看调试状态",
    "save": "保存当前配置",
    "commit": "提交配置",
    "synchronization-config": "配置同步功能",
}


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir()))


_INSTANCE_MUTEX_HANDLE = None


def acquire_single_instance() -> bool:
    global _INSTANCE_MUTEX_HANDLE
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = wintypes.DWORD
    handle = kernel32.CreateMutexW(None, True, SINGLE_INSTANCE_MUTEX)
    if not handle:
        return True
    _INSTANCE_MUTEX_HANDLE = handle
    return kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def close_other_helper_instances():
    current_pid = os.getpid()
    command = (
        "$current = " + str(current_pid) + "; "
        "Get-Process -Name 'ensp-vrp-ime-helper','ensp-vrp-ime-helper-school' -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Id -ne $current } | "
        "Stop-Process -Force -ErrorAction SilentlyContinue"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
        )
    except Exception:
        pass


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def clamp_candidate_opacity(value) -> float:
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        opacity = DEFAULT_CANDIDATE_OPACITY
    return max(MIN_CANDIDATE_OPACITY, min(1.0, opacity))


def fit_candidate_layout(command_px: int, description_px: int, header_px: int, footer_px: int, screen_width: int) -> dict:
    screen_limit = max(
        CANDIDATE_MIN_WIDTH_PX,
        min(int(screen_width or 0) - CANDIDATE_SCREEN_MARGIN_PX, CANDIDATE_MAX_WIDTH_PX),
    )
    base_width = min(screen_limit, max(CANDIDATE_BASE_WIDTH_PX, CANDIDATE_MIN_WIDTH_PX))
    command_col = max(CANDIDATE_MIN_COMMAND_PX, int(command_px) + CANDIDATE_COLUMN_PAD_PX)
    description_col = max(CANDIDATE_MIN_DESCRIPTION_PX, int(description_px) + CANDIDATE_COLUMN_PAD_PX)
    columns_width = CANDIDATE_INDEX_PX + command_col + description_col + CANDIDATE_CHROME_PX
    desired_width = max(
        base_width,
        columns_width,
        int(header_px) + CANDIDATE_CHROME_PX,
        int(footer_px) + CANDIDATE_CHROME_PX,
    )
    width = min(desired_width, screen_limit)
    available_columns = max(
        300,
        width - CANDIDATE_INDEX_PX - CANDIDATE_CHROME_PX,
    )
    if command_col + description_col > available_columns:
        if available_columns >= CANDIDATE_MIN_COMMAND_PX + CANDIDATE_MIN_DESCRIPTION_PX:
            description_target = min(description_col, CANDIDATE_MIN_DESCRIPTION_PX)
            command_target = max(CANDIDATE_MIN_COMMAND_PX, available_columns - description_target)
            command_col = max(CANDIDATE_MIN_COMMAND_PX, command_target)
            description_col = max(CANDIDATE_MIN_DESCRIPTION_PX, available_columns - command_col)
        else:
            command_col = max(170, int(available_columns * 0.64))
            description_col = max(120, available_columns - command_col)
    if command_col + description_col > available_columns:
        command_col = max(CANDIDATE_MIN_COMMAND_PX, available_columns - description_col)
    return {
        "width": width,
        "command_px": command_col,
        "description_px": description_col,
        "command_wrap": 0,
        "description_wrap": 0,
    }


def is_query_char(ch: str) -> bool:
    return bool(ch and re.fullmatch(r"[A-Za-z0-9_./:-]", ch))


def has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def chinese_search_key(text: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fff]+", text or ""))


def hint_description_label(desc: str) -> str:
    clean = normalize_spaces(desc)
    compact = chinese_search_key(clean)
    if compact and compact != clean.replace(" ", "") and len(compact) >= 4:
        return f"{compact}（{clean}）"
    return clean


def candidate_hint_text(query: str, items: list, limit: int = 3) -> str:
    if not items:
        return ""
    seen = set()
    parts = []
    max_items = 5 if has_chinese(query) else limit
    for item in items:
        command = item.get("insert") or item.get("command") or ""
        if not command:
            continue
        if command in seen:
            continue
        seen.add(command)
        parts.append(command)
        if len(parts) >= max_items:
            break
    if not parts:
        return ""
    return "  " + "；".join(parts)


def chinese_query_priority(query_zh: str, item: dict) -> int:
    if not query_zh:
        return 0
    command = (item.get("insert") or item.get("command") or "").lower()
    if query_zh in {"查看路由", "查路由", "路由", "查看路由表", "查路由表", "路由表"}:
        if command == "display ip routing-table":
            return 1200
        if command.startswith("display ip routing-table "):
            return 850
        if command.startswith("display ipv6 routing-table"):
            return 520
        if " routing-table" in command:
            return 420
        if command.startswith("display ") and "route" in command:
            return 180
    return 0


def clean_for_insert(command: str) -> str:
    fixed = []
    for token in normalize_spaces(command).split(" "):
        if PLACEHOLDER_RE.search(token) or SYNTAX_MARK_RE.search(token):
            break
        fixed.append(token)
    return " ".join(fixed).strip() or normalize_spaces(command).split(" ")[0]


def prefix_parts_match(insert_parts, query_parts):
    idx = 0
    last_idx = None
    for part in query_parts:
        if idx < len(insert_parts) and insert_parts[idx].startswith(part):
            last_idx = idx
            idx += 1
            continue
        if last_idx is not None and insert_parts[last_idx].startswith(part):
            continue
        return False
    return bool(query_parts)


def polish_description(desc: str) -> str:
    desc = re.sub(r"([\u4e00-\u9fff])([A-Za-z][A-Za-z0-9_.+-]*)", r"\1 \2", desc)
    desc = re.sub(r"([A-Za-z0-9_.+-])([\u4e00-\u9fff])", r"\1 \2", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc.replace("： ", "：")


def split_top_level_options(text: str):
    options = []
    current = []
    depth = 0
    pairs = {"{": "}", "[": "]"}
    closers = set(pairs.values())
    for char in text:
        if char in pairs:
            depth += 1
        elif char in closers and depth > 0:
            depth -= 1
        if char == "|" and depth == 0:
            options.append(normalize_spaces("".join(current)))
            current = []
        else:
            current.append(char)
    options.append(normalize_spaces("".join(current)))
    return [option for option in options if option]


def leading_choice_expansions(command: str):
    raw = normalize_spaces(command)
    if not raw or raw[0] not in "{[":
        return []
    opener = raw[0]
    closer = "}" if opener == "{" else "]"
    depth = 0
    end = -1
    for idx, char in enumerate(raw):
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end <= 0:
        return []
    options = split_top_level_options(raw[1:end])
    tail = normalize_spaces(raw[end + 1:])
    if len(options) < 2:
        return []
    expanded = []
    for option in options:
        if is_safe_choice_option(option):
            expanded.append(normalize_spaces((option + " " + tail).strip()))
    return expanded


def find_top_level_groups(text: str, opener: str, closer: str):
    depth = 0
    start = -1
    for idx, char in enumerate(text):
        if char == opener:
            if depth == 0:
                start = idx
            depth += 1
        elif char == closer and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                yield start, idx
                start = -1


def strip_optional_groups(text: str) -> str:
    output = []
    depth = 0
    for char in text:
        if char == "[":
            depth += 1
            if depth == 1:
                output.append(" ")
            continue
        if char == "]" and depth > 0:
            depth -= 1
            if depth == 0:
                output.append(" ")
            continue
        if depth == 0:
            output.append(char)
    return normalize_spaces("".join(output))


def is_safe_choice_option(option: str) -> bool:
    option = normalize_spaces(option)
    return bool(
        option
        and SAFE_CHOICE_OPTION_RE.fullmatch(option)
        and not PLACEHOLDER_RE.search(option)
        and not SYNTAX_MARK_RE.search(option)
    )


def unwrap_single_group(text: str) -> str:
    raw = normalize_spaces(text)
    if not raw or raw[0] not in "{[":
        return raw
    opener = raw[0]
    closer = "}" if opener == "{" else "]"
    depth = 0
    for idx, char in enumerate(raw):
        if char == opener:
            depth += 1
        elif char == closer and depth > 0:
            depth -= 1
            if depth == 0:
                if idx == len(raw) - 1:
                    return normalize_spaces(raw[1:idx])
                return raw
    return raw


def safe_optional_inclusion_forms(text: str):
    raw = normalize_spaces(text)
    forms = []
    for start, end in find_top_level_groups(raw, "[", "]"):
        prefix = normalize_spaces(raw[:start])
        inside = normalize_spaces(raw[start + 1:end])
        tail = normalize_spaces(raw[end + 1:])
        inside_options = split_top_level_options(inside)
        if len(inside_options) == 1 and not is_safe_choice_option(inside_options[0]):
            return forms
        for option in inside_options:
            option = normalize_spaces(option)
            if not is_safe_choice_option(option):
                continue
            candidate = clean_for_insert(normalize_spaces(f"{prefix} {option} {tail}"))
            if candidate and is_safe_choice_option(candidate) and candidate not in forms:
                forms.append(candidate)
        return forms
    return forms


def safe_choice_option_forms(option: str):
    raw = normalize_spaces(option)
    forms = []
    seen = set()

    def add(candidate: str):
        candidate = normalize_spaces(candidate)
        if candidate and is_safe_choice_option(candidate) and candidate not in seen:
            seen.add(candidate)
            forms.append(candidate)

    add(raw)
    stripped = strip_optional_groups(raw)
    if stripped != raw:
        add(stripped)
    for optional_form in safe_optional_inclusion_forms(raw):
        add(optional_form)

    unwrapped = unwrap_single_group(raw)
    if unwrapped != raw:
        for form in safe_choice_option_forms(unwrapped):
            add(form)

    top_level_options = split_top_level_options(raw)
    if len(top_level_options) > 1:
        for nested_option in top_level_options:
            for form in safe_choice_option_forms(nested_option):
                add(form)

    for start, end in find_top_level_groups(raw, "{", "}"):
        if start == 0:
            continue
        prefix = normalize_spaces(raw[:start])
        if not prefix or clean_for_insert(prefix) != prefix:
            continue
        tail = normalize_spaces(raw[end + 1:])
        had_inner_form = False
        for form in safe_choice_option_forms(raw[start + 1:end]):
            had_inner_form = True
            candidate = clean_for_insert(normalize_spaces(f"{prefix} {form} {tail}"))
            add(candidate)
        if not had_inner_form and PLACEHOLDER_RE.search(raw[start + 1:end]):
            add(prefix)
        break

    return forms


def internal_choice_expansions(command: str):
    raw = normalize_spaces(command)
    if not raw:
        return []
    for start, end in find_top_level_groups(raw, "{", "}"):
        if start == 0:
            continue
        prefix = normalize_spaces(raw[:start])
        if not prefix or clean_for_insert(prefix) != prefix:
            continue
        inside = raw[start + 1:end]
        if "|" not in inside:
            option_forms = safe_choice_option_forms(inside)
            if not option_forms:
                continue
            tail = normalize_spaces(raw[end + 1:])
            expanded = []
            for option in option_forms:
                candidate = clean_for_insert(normalize_spaces(f"{prefix} {option} {tail}"))
                if candidate and candidate != prefix and candidate not in expanded:
                    expanded.append(candidate)
            return expanded
        options = split_top_level_options(inside)
        if not (1 <= len(options) <= MAX_CHOICE_OPTIONS):
            continue
        option_forms = []
        seen_options = set()
        for option in options:
            for form in safe_choice_option_forms(option):
                if form not in seen_options:
                    seen_options.add(form)
                    option_forms.append(form)
        if not option_forms:
            continue
        tail = normalize_spaces(raw[end + 1:])
        expanded = []
        for option in option_forms:
            candidate = clean_for_insert(normalize_spaces(f"{prefix} {option} {tail}"))
            if candidate and candidate != prefix and candidate not in expanded:
                expanded.append(candidate)
        return expanded
    return []


def choice_prefix_variants(command: str):
    raw = normalize_spaces(command)
    if not raw:
        return []
    seeds = leading_choice_expansions(raw) or [raw]
    variants = []
    seen = set()
    for seed in seeds:
        candidate_seeds = [seed]
        stripped = strip_optional_groups(seed)
        if stripped != seed and len(clean_for_insert(stripped).split()) > len(clean_for_insert(seed).split()):
            candidate_seeds.append(stripped)
        for candidate_seed in candidate_seeds:
            for candidate in [candidate_seed] + internal_choice_expansions(candidate_seed):
                candidate = normalize_spaces(candidate)
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    variants.append(candidate)
    return variants


def translate_subject(subject: str) -> str:
    mapping = {
        "acl": "ACL",
        "acl6": "IPv6 ACL",
        "aaa": "AAA",
        "active": "活动",
        "address": "地址",
        "additive": "追加",
        "admin": "管理",
        "alarm": "告警",
        "area": "区域",
        "advanced": "高级",
        "all": "全部",
        "allow": "允许",
        "allow-default-route": "允许缺省路由",
        "apply": "应用",
        "arp": "ARP",
        "arp-fake": "ARP 防欺骗",
        "arp-proxy": "ARP 代理",
        "arp-suppress": "ARP 抑制",
        "as": "AS",
        "as-path-filter": "AS 路径过滤器",
        "authentication": "认证",
        "authentication-mode": "认证方式",
        "backup": "备份",
        "by": "按",
        "bytes": "字节",
        "bfd": "BFD",
        "bfd-session": "BFD 会话",
        "bgp": "BGP",
        "binding": "绑定",
        "black": "黑盒",
        "black-box": "黑盒",
        "box": "黑盒",
        "brief": "摘要",
        "broadcast": "广播",
        "cache": "缓存",
        "combo": "组合",
        "combo-port": "组合端口",
        "configuration": "配置",
        "config": "配置",
        "control": "控制",
        "control-word": "控制字",
        "cpu": "CPU",
        "cpu-usage": "CPU 使用率",
        "current-configuration": "当前配置",
        "default": "缺省",
        "delay": "延迟",
        "detail": "详细信息",
        "deny": "拒绝",
        "description": "描述",
        "different": "不同",
        "diagnosis": "诊断",
        "diagnostic": "诊断",
        "discard": "丢弃",
        "discovery": "发现",
        "download": "下载",
        "duplex": "双工",
        "enable": "使能",
        "entry": "表项",
        "event": "事件",
        "eth-trunk": "链路聚合接口",
        "excluded-ip-address": "排除地址",
        "export": "导出",
        "extcommunity-filter": "扩展团体属性过滤器",
        "filter": "过滤器",
        "file": "文件",
        "flow": "流控",
        "flow-control": "流控",
        "get": "获取",
        "getfile": "获取文件",
        "gateway": "网关",
        "gateway-list": "网关列表",
        "generate": "生成",
        "gigabitethernet": "千兆以太网",
        "global": "全局",
        "graceful": "平滑",
        "graceful-restart": "平滑重启",
        "group": "组",
        "gtsm": "GTSM",
        "guard": "保护",
        "guard-timer": "保护定时器",
        "history": "历史",
        "http": "HTTP",
        "http-url": "HTTP 地址",
        "hybrid": "混合",
        "inbound": "入方向",
        "increment": "增量",
        "increment-command": "增量命令",
        "interface": "接口",
        "ip": "IP",
        "ip-prefix": "IP 前缀列表",
        "ipv4": "IPv4",
        "ipv6": "IPv6",
        "ipv6-prefix": "IPv6 前缀列表",
        "ipv6-transport": "IPv6 传输",
        "internet": "互联网",
        "learn": "学习",
        "learn-style": "学习方式",
        "listening": "监听",
        "limit": "限制",
        "link": "链路",
        "login": "登录提示",
        "log": "日志",
        "loghost": "日志主机",
        "image": "镜像文件",
        "interval": "间隔",
        "mac-address": "MAC 地址",
        "mac": "MAC",
        "manual": "手动",
        "ma": "维护集",
        "match": "匹配",
        "max": "最大",
        "maximum": "最大",
        "management": "管理",
        "memory-usage": "内存使用率",
        "mirror": "镜像",
        "mpls": "MPLS",
        "md": "维护域",
        "mep": "维护端点",
        "multicast": "组播",
        "liveness": "存活检测",
        "local": "本地",
        "loose": "松散检查",
        "med": "MED",
        "neighbor": "邻居",
        "negotiation": "协商",
        "no-advertise": "不通告",
        "no-export": "不导出",
        "no-export-subconfed": "不导出到子联盟",
        "nqa": "NQA",
        "null": "NULL 接口",
        "none": "无",
        "num": "数量",
        "order": "顺序",
        "outbound": "出方向",
        "ospf": "OSPF",
        "ospfv3": "OSPFv3",
        "packet": "报文",
        "packets": "报文",
        "packet-type": "报文类型",
        "parameter": "参数",
        "patch": "补丁",
        "patch-command": "补丁命令",
        "peer": "对等体",
        "permanent": "永久",
        "permit": "允许",
        "pvid": "缺省 VLAN",
        "policy": "策略",
        "policy-based-route": "策略路由",
        "prefix": "前缀",
        "prefix-priority": "前缀优先级",
        "prefix-priority-scheduler": "前缀优先级调度",
        "preempt": "抢占",
        "preference": "优先级",
        "primary": "主用",
        "program": "程序",
        "protect-switch": "保护倒换",
        "public": "公网",
        "period": "周期",
        "port": "端口",
        "reconnect": "重连接",
        "recovery": "恢复",
        "raw-packet": "原始报文",
        "redirect": "重定向",
        "remark": "重标记",
        "restart": "重启",
        "response": "响应",
        "rib": "RIB",
        "rd-filter": "RD 过滤器",
        "refresh": "刷新",
        "refresh-time": "刷新时间",
        "relay": "递归",
        "relay-depth": "递归深度",
        "remote": "远端",
        "remove": "删除",
        "routing-table": "路由表",
        "routing": "路由",
        "route": "路由",
        "route-policy": "路由策略",
        "route-static": "静态路由",
        "routes": "路由",
        "rpf": "反向路径转发",
        "rpf-route-static": "RPF 静态路由",
        "rule": "规则",
        "secondary": "备用",
        "selection": "选择",
        "selection-rule": "选择规则",
        "session": "会话",
        "slot": "槽位",
        "command": "命令",
        "command-table": "命令表",
        "commit": "提交",
        "community": "团体属性",
        "community-filter": "团体属性过滤器",
        "compare": "比较",
        "compare-different-as-med": "比较不同 AS 的 MED",
        "cluster": "集群",
        "cluster-increment-result": "集群增量结果",
        "chinese": "中文",
        "clock": "系统时间",
        "console": "Console",
        "datetime": "日期时间",
        "detect-mode": "检测模式",
        "detect-times": "检测次数",
        "diagnostic-information": "诊断信息",
        "diag-info": "诊断信息",
        "display-rm-detailed-info": "路由管理详细信息",
        "rm-detailed-info": "路由管理详细信息",
        "display-db-info": "数据库信息",
        "db-info": "数据库信息",
        "display-db-info6": "IPv6 数据库信息",
        "db-info6": "IPv6 数据库信息",
        "english": "英文",
        "expire-time": "老化时间",
        "fake": "防欺骗",
        "feature": "特性",
        "feature-name": "特性名称",
        "filename": "文件名",
        "filesize": "文件大小",
        "ftp": "FTP",
        "header": "登录提示",
        "history-command": "历史命令",
        "hello": "Hello",
        "helper": "辅助",
        "helper-role": "辅助角色",
        "host": "主机",
        "host-route": "主机路由",
        "ignore-tc": "忽略拓扑变化",
        "idle-timeout": "空闲超时时间",
        "irreversible-cipher": "不可逆密文",
        "local-user": "本地用户",
        "language-mode": "语言显示模式",
        "logbuffer": "日志缓冲区",
        "lsp": "LSP",
        "max-size": "最大数量",
        "mode": "方式",
        "ntp": "NTP",
        "ntp-service": "NTP 时间同步",
        "operation": "操作",
        "password": "密码",
        "privilege": "权限",
        "proxy": "代理",
        "reboot": "重启",
        "role": "角色",
        "router": "路由器",
        "router-id": "路由器 ID",
        "saved-configuration": "已保存配置",
        "screen-length": "屏幕每页行数",
        "server": "服务",
        "service-type": "服务类型",
        "shell": "登录后提示",
        "create": "创建",
        "snmp": "SNMP",
        "snmp-agent": "SNMP 管理",
        "snmp-host": "SNMP 主机",
        "ssh": "SSH",
        "static": "静态",
        "stelnet": "Stelnet",
        "stp": "STP",
        "sysname": "设备名称",
        "te": "TE 隧道工程",
        "telnet": "Telnet",
        "tftp": "TFTP",
        "this": "当前视图配置",
        "timezone": "时区",
        "tracert": "路径跟踪",
        "trap": "Trap 告警",
        "trapbuffer": "告警缓冲区",
        "trapping": "告警输出",
        "user": "用户",
        "username": "用户名",
        "user-interface": "用户界面",
        "vrrp": "VRRP",
        "vty": "VTY",
        "abr-summary": "区域边界汇总",
        "active-route-advertise": "活动路由通告",
        "advertise": "通告",
        "aggregate": "聚合",
        "algorithm": "算法",
        "application-apperceive": "应用感知",
        "asbr-summary": "自治系统边界汇总",
        "attribute-policy": "属性策略",
        "autoconfig": "自动配置",
        "automatic": "自动",
        "backoff": "退避",
        "balance": "负载分担",
        "bandwidth-reference": "带宽参考值",
        "bcmfpi": "转发芯片接口",
        "between-clients": "客户端之间",
        "bestroute": "最优路由",
        "blackhole": "黑洞路由",
        "block": "阻断",
        "bootrom": "BootROM",
        "broadcast-suppression": "广播抑制",
        "buffer": "缓冲区",
        "build": "构建",
        "c-bsr": "候选 BSR",
        "carrier": "载波",
        "cbs": "承诺突发尺寸",
        "checkzero": "零值检查",
        "circuit-cost": "链路开销",
        "clear": "清除",
        "clear-records": "清除记录",
        "compatible": "兼容",
        "compatible-information": "兼容信息",
        "component": "组件",
        "confederation": "联盟",
        "continual": "持续",
        "cost": "开销",
        "count": "计数",
        "counters": "计数器",
        "cp-car": "控制平面限速",
        "c-rp": "候选 RP",
        "custom-device-name": "自定义设备名称",
        "dampening": "路由抑制",
        "database": "数据库",
        "datasize": "数据大小",
        "day": "天",
        "delete-member": "删除成员",
        "detect": "检测",
        "detect-multiplier": "检测倍数",
        "device": "设备",
        "df": "不分片标志",
        "dhcp": "DHCP",
        "dip": "目的 IP",
        "db": "数据库",
        "detailed": "详细",
        "disable": "禁用",
        "discriminator": "鉴别符",
        "distribute-delay": "分发延迟",
        "dmac": "目的 MAC",
        "dn-bit-set": "DN 位设置",
        "dns": "DNS",
        "dns-alg": "DNS ALG",
        "dns-list": "DNS 服务器列表",
        "domain": "域",
        "domain-id": "域 ID",
        "down-hold-time": "Down 保持时间",
        "dynamic": "动态",
        "energy-efficient-ethernet": "节能以太网",
        "encapsulation": "封装",
        "entity-attr": "实体属性",
        "entity-id": "实体 ID",
        "environment": "环境",
        "eoam-1ag": "以太网 OAM 1ag",
        "error-down": "错误关闭",
        "error-info": "错误信息",
        "eth-loop": "以太环路",
        "explicit-null": "显式空标签",
        "fail-percent": "失败比例",
        "fault": "故障",
        "fault-management": "故障管理",
        "faultresume": "故障恢复",
        "fib": "转发表",
        "flash-flood": "快速泛洪",
        "flood-list": "泛洪列表",
        "flap-info": "震荡信息",
        "flapping": "震荡",
        "force": "强制",
        "forwarding-table": "转发表",
        "frequency": "频率",
        "getting-files": "获取文件",
        "group-policy": "组策略",
        "gresm": "GRESM",
        "hash-length": "哈希长度",
        "holdoff": "延迟保护",
        "holdtime": "保持时间",
        "icmp": "ICMP",
        "icmp-reply": "ICMP 回应",
        "igmp-proxy": "IGMP 代理",
        "igmp-snooping": "IGMP Snooping",
        "if-down": "接口断开",
        "ifadp": "接口适配",
        "ifpdt": "接口诊断",
        "implicit-null": "隐式空标签",
        "import-source": "导入源",
        "info": "信息",
        "info6": "IPv6 信息",
        "information": "信息",
        "ingress": "入方向",
        "instance": "实例",
        "instance-info-detail": "实例详细信息",
        "instance_info_detail": "实例详细信息",
        "is-level": "IS-IS 级别",
        "is-name": "IS-IS 名称",
        "isolate": "隔离",
        "jitter-packetnum": "抖动报文数",
        "join-prune": "加入/剪枝",
        "job-records": "任务记录",
        "jumboframe": "巨帧",
        "key-id": "密钥 ID",
        "key-string": "密钥字符串",
        "keychain": "密钥链",
        "l2adp": "二层适配",
        "l2vpn": "二层 VPN",
        "l2-topology": "二层拓扑",
        "label": "标签",
        "label-table": "标签表",
        "label-index": "标签索引",
        "lastmember-queryinterval": "最后成员查询间隔",
        "ldp-sync": "LDP 同步",
        "lease": "租期",
        "level-1": "一级",
        "level-1-2": "一/二级",
        "level-2": "二级",
        "license": "许可证",
        "load-balance": "负载分担",
        "load-balancing": "负载分担",
        "loop-detect": "环路检测",
        "loopback": "环回",
        "loss-measure": "丢包测量",
        "lldp": "LLDP",
        "lsdb": "链路状态数据库",
        "lsa-checking-ignore": "忽略 LSA 检查",
        "lsr-id": "LSR ID",
        "max-grace-period": "最大宽限期",
        "max-timer-interval": "最大定时间隔",
        "member-number": "成员编号",
        "memory": "内存",
        "metricin": "入方向度量值",
        "metricout": "出方向度量值",
        "mld-snooping": "MLD Snooping",
        "multicast-suppression": "组播抑制",
        "natpt": "NAT-PT",
        "network": "网络",
        "next-hop": "下一跳",
        "nexthop": "下一跳",
        "non-null": "非空标签",
        "nonstandard": "非标准",
        "notify": "通知",
        "nssa": "NSSA",
        "oam-bind": "OAM 绑定",
        "oam-mgr": "OAM 管理",
        "one-way": "单向",
        "opaque-capability": "不透明 LSA 能力",
        "origin-policy": "起源策略",
        "originating-rp": "起源 RP",
        "passroute": "透传路由",
        "pathmtu": "路径 MTU",
        "periodic-messages": "周期报文",
        "planned-only": "仅计划内",
        "poison-reverse": "毒性逆转",
        "power": "电源",
        "portswitch": "端口二三层切换",
        "priority": "优先级",
        "process": "进程",
        "probe-count": "探测次数",
        "probe-failtimes": "探测失败次数",
        "prompt-leave": "快速离开",
        "propagate": "传播",
        "protected-instance": "保护实例",
        "protocol-transparent": "协议透明传输",
        "protocol-info-detail": "协议详细信息",
        "protocol_info_detail": "协议详细信息",
        "pw-template": "PW 模板",
        "queue": "队列",
        "queue-size": "队列大小",
        "receive": "接收",
        "record": "记录",
        "reflect": "反射",
        "register-list": "注册列表",
        "rip": "RIP",
        "ripng": "RIPng",
        "robust-count": "健壮性计数",
        "rrpp": "RRPP",
        "segment": "段",
        "sendpacket": "发送报文",
        "security-key": "安全密钥",
        "selftest": "自检",
        "service-id": "服务 ID",
        "set-df": "设置不分片标志",
        "shutdown": "关闭",
        "sip": "源 IP",
        "smac": "源 MAC",
        "simulate": "模拟",
        "silent": "静默",
        "socket": "套接字",
        "socket-process": "套接字处理",
        "source": "源",
        "split-horizon": "水平分割",
        "spf-priority": "SPF 优先级",
        "ssm-mapping": "SSM 映射",
        "start": "启动",
        "state": "状态",
        "stop": "停止",
        "summary": "汇总",
        "table": "表",
        "tagged": "带标签",
        "table-id": "表 ID",
        "table-type": "表类型",
        "tc-notify": "拓扑变化通知",
        "tc-protection": "拓扑变化保护",
        "threshold": "阈值",
        "timers": "定时器",
        "token": "令牌",
        "token-map": "令牌映射",
        "topology-error-info": "拓扑错误信息",
        "tos": "服务类型",
        "trace": "跟踪",
        "transceiver": "光模块",
        "trigger": "触发",
        "triggered-message-pack": "触发报文包",
        "trunkport": "Trunk 端口",
        "turn-off": "关闭",
        "unknown-frame": "未知帧",
        "unknown-unicast": "未知单播",
        "unknown-unicast-suppression": "未知单播抑制",
        "untagged": "不带标签",
        "up-hold-time": "上线保持时间",
        "upgrade": "升级",
        "upe-npe": "UPE-NPE",
        "upe-upe": "UPE-UPE",
        "utask-info": "任务信息",
        "v6bound": "IPv6 绑定",
        "v6v4-aaaa-query": "IPv6 到 IPv4 AAAA 查询",
        "version": "版本",
        "virtual-cable-test": "虚拟电缆检测",
        "ability": "能力",
        "acl6-name": "IPv6 ACL 名称",
        "adp-l3": "三层适配",
        "adp-l3vpn": "三层 VPN 适配",
        "adjacency-hold": "邻接保持",
        "agetime": "老化时间",
        "attach": "绑定",
        "auto-rp": "自动 RP",
        "auto-select": "自动选择",
        "basic": "基础",
        "batch": "批量",
        "boundary": "边界",
        "bridge": "桥接",
        "capability": "能力",
        "check": "检查",
        "circuit": "链路",
        "damping": "抑制",
        "datafill": "数据填充",
        "destination": "目的地址",
        "dhcp-snooping": "DHCP Snooping",
        "entity-tree": "实体树",
        "failed-allocated-resource": "分配失败资源",
        "frontcard": "前插卡",
        "h-h-h": "MAC 地址",
        "ifagt": "接口代理",
        "ignore-stp-loopcheck": "忽略 STP 环路检查",
        "import": "导入",
        "indirectid": "间接 ID",
        "ipctest": "IPC 测试",
        "keepalive": "保活",
        "l3vpn": "三层 VPN",
        "l3": "三层",
        "l3-diag": "三层诊断",
        "least": "最小值",
        "level": "级别",
        "loopbacktest": "环回测试",
        "lspagt": "LSP 代理",
        "lswdiag": "交换诊断",
        "microsecond": "微秒",
        "millisecond": "毫秒",
        "mngvlanid": "管理 VLAN ID",
        "mos-system-info": "MOS 系统信息",
        "msend": "组播发送",
        "multi-hop": "多跳",
        "notification": "通知",
        "npe-upe": "NPE-UPE",
        "number": "编号",
        "originate": "发起",
        "other-querier-present": "存在其他查询器",
        "p2p-vsi": "点到点 VSI",
        "path-vectors": "路径向量",
        "performance": "性能",
        "phy_register": "PHY 寄存器",
        "pim_hogtime": "PIM 占用时间",
        "pkt-transmit": "报文发送",
        "query": "查询",
        "raps-mel": "RAPS MEL",
        "reflector": "反射器",
        "region-name": "区域名称",
        "resend": "重发",
        "retransmit": "重传",
        "revision-level": "修订级别",
        "rfc1583": "RFC1583 兼容",
        "rm-code-coverage": "路由管理代码覆盖率",
        "set-overload": "设置过载",
        "simple": "简单",
        "spf-slice-size": "SPF 分片大小",
        "stale": "陈旧",
        "statistic": "统计",
        "subordinate": "下级",
        "separate": "分离",
        "switch-l2vc": "切换二层 VC",
        "tables": "表",
        "tag-value": "标签值",
        "task-id": "任务 ID",
        "tcp-kind": "TCP 类型",
        "test-failtimes": "测试失败次数",
        "test-version": "测试版本",
        "tick-counter": "计时计数器",
        "timeslice": "时间片",
        "timestamp-unit": "时间戳单位",
        "trunkfwdtbl": "Trunk 转发表",
        "trunkmembership": "Trunk 成员",
        "trunkshow": "Trunk 显示",
        "ttl-copymode": "TTL 复制模式",
        "unicast": "单播",
        "update": "更新",
        "update-peer-group": "更新对等体组",
        "virtual-system": "虚拟系统",
        "vpls-ac-hash": "VPLS AC 哈希",
        "vsi-id": "VSI ID",
        "y1731": "Y.1731",
        "access": "接入",
        "administrator": "管理员",
        "arpadp": "ARP 适配",
        "bpdu-protection": "BPDU 保护",
        "ccm-send": "CCM 发送",
        "center": "中心",
        "change": "变更",
        "detection": "检测",
        "diffluence": "分流",
        "ethernet": "以太网",
        "extcommunity": "扩展团体属性",
        "fragmentation": "分片",
        "ha-info": "高可用信息",
        "hash-based": "基于哈希",
        "ignore-request": "忽略请求",
        "imported": "已导入",
        "inactive-times": "非活跃次数",
        "ip6token": "IPv6 令牌",
        "keep-batchpkt-uptgrpnum": "保持批量报文组数",
        "l2macvlan": "二层 MAC VLAN",
        "l2muxvlan": "二层 MUX VLAN",
        "l2povlan": "二层 PO VLAN",
        "l2protocolvlan": "二层协议 VLAN",
        "l2subnetvlan": "二层子网 VLAN",
        "l2vovlan": "二层 VO VLAN",
        "logging": "日志记录",
        "loop-protection": "环路保护",
        "mainloop-ticks": "主循环计数",
        "martini": "Martini",
        "message": "消息",
        "message-info": "消息信息",
        "miscellaneous": "杂项",
        "multiplier": "倍数",
        "neighbour": "邻居",
        "non-register-oif": "非注册出接口",
        "oam-mapping": "OAM 映射",
        "on-demand": "按需",
        "origin": "起源",
        "other-flag": "其他标志",
        "overwrite": "覆盖",
        "pe-vid": "PE VLAN ID",
        "preferred-value": "首选值",
        "pwsignal": "PW 信令",
        "pw-ttl": "PW TTL",
        "range": "范围",
        "redundancy": "冗余",
        "register": "注册",
        "reroute": "重路由",
        "resolve": "解析",
        "root-protection": "根保护",
        "semantic": "语义",
        "service": "服务",
        "stack": "堆叠",
        "stat-debugging": "统计调试",
        "stream-dual-receiving": "双流接收",
        "switchover": "倒换",
        "tcpconnect": "TCP 连接",
        "tdisplay": "测试显示",
        "temperature": "温度",
        "udpecho": "UDP Echo",
        "vpnv4": "VPNv4",
        "vsi-name": "VSI 名称",
        "ack-list": "确认列表",
        "acklist": "确认列表",
        "action": "动作",
        "adjacency-down": "邻接断开",
        "advertisement": "通告",
        "aging": "老化",
        "assert": "断言",
        "assert-info": "断言信息",
        "attempts": "尝试次数",
        "available": "可用",
        "bandwidth-affected-linknumber": "受带宽影响链路数",
        "behavior": "行为",
        "bsr-info": "BSR 信息",
        "bucket": "桶",
        "candidates": "候选项",
        "cause": "原因",
        "compliance": "兼容性",
        "common": "公共",
        "connect-retry": "连接重试",
        "converge": "收敛",
        "counter": "计数器",
        "customize-spec": "自定义规格",
        "daily": "每日",
        "debug-switches": "调试开关",
        "dictionary": "字典",
        "dis-name": "DIS 名称",
        "downloadrecord": "下载记录",
        "drop-unknown": "丢弃未知报文",
        "dummy": "虚拟项",
        "du-readvertise": "DU 重通告",
        "egress": "出方向",
        "eibgp": "EIBGP",
        "entitymib": "实体 MIB",
        "error": "错误",
        "explicit-tracking": "显式跟踪",
        "explore": "探测",
        "fibv4": "IPv4 转发表",
        "forwarding-info": "转发信息",
        "frame": "帧",
        "fromspt": "从 SPT",
        "graft-retry": "嫁接重试",
        "grafts": "嫁接",
        "ha-events": "高可用事件",
        "heart-beat": "心跳",
        "icmpv6": "ICMPv6",
        "if-net": "接口网络",
        "ifindex": "接口索引",
        "igp-sync": "IGP 同步",
        "include-interframe": "包含帧间隙",
        "internal": "内部",
        "lsptoken": "LSP 令牌",
        "l2service": "二层服务",
        "mandatory": "强制",
        "mcast-subif": "组播子接口",
        "member": "成员",
        "members": "成员",
        "minimum-ttl": "最小 TTL",
        "miss-drop": "未命中丢弃",
        "mld_snooping": "MLD Snooping",
        "modulo": "取模",
        "month": "每月",
        "msgctrl-item": "消息控制项",
        "multi-sa": "多 SA",
        "nhlfe": "下一跳标签转发表项",
        "original-rp": "原始 RP",
        "overlapping-fragment": "重叠分片",
        "p2mp-mask-ignore": "忽略 P2MP 掩码",
        "paf_lcs": "PAF LCS",
        "pathcost-standard": "路径开销标准",
        "paths": "路径",
        "pim-dm": "PIM-DM",
        "pim-ssm": "PIM-SSM",
        "portindexinfo": "端口索引信息",
        "precedence": "优先级",
        "protect-action": "保护动作",
        "pvid-map-info": "PVID 映射信息",
        "pw-info": "PW 信息",
        "rcclockthreshold": "RC 时钟阈值",
        "rcnodesthreshold": "RC 节点阈值",
        "ratelimit": "速率限制",
        "recursive-lookup": "递归查找",
        "replay-protect": "重放保护",
        "require-genid": "要求 GENID",
        "request-list": "请求列表",
        "result": "结果",
        "results": "结果",
        "reserved": "保留",
        "retry": "重试",
        "rm": "路由管理",
        "revs-trans-info": "反向转换信息",
        "rp-info": "RP 信息",
        "sa-count": "SA 计数",
        "sa-request": "SA 请求",
        "schedule": "调度",
        "selected": "已选择",
        "send-jp-rate": "发送 JP 速率",
        "send-key-id": "发送密钥 ID",
        "send-pdu": "发送 PDU",
        "serial": "串口",
        "serial-baudrate": "串口波特率",
        "set-cpup-hook": "设置 CPU 报文钩子",
        "short-pipe": "短管道",
        "signal": "信令",
        "smart-discover": "智能发现",
        "spf-tree": "SPF 树",
        "spoken": "隔离标记",
        "spt-switch": "SPT 切换",
        "sticky": "粘滞",
        "subrack": "子架",
        "temperature": "温度",
        "tcpcb": "TCP 控制块",
        "topology": "拓扑",
        "transit": "中转",
        "uniform": "统一模式",
        "upcall-rate": "上送速率",
        "urgent": "紧急告警",
        "users": "当前登录用户",
        "usual": "常规",
        "utask-id": "任务 ID",
        "v6server": "IPv6 服务",
        "valid-ttl-hops": "有效 TTL 跳数",
        "variable": "变量",
        "vlantrans": "VLAN 转换",
        "vll-info": "VLL 信息",
        "vp-info": "VP 信息",
        "vpindex": "VP 索引",
        "vsi-info": "VSI 信息",
        "vsi-index": "VSI 索引",
        "whitelist": "白名单",
        "window": "窗口",
        "adjacency": "邻接",
        "cipher": "密文",
        "copy-attr-req": "复制属性请求",
        "cpldcheck": "CPLD 检查",
        "cpucoreclock": "CPU 核心时钟",
        "dev-backtype": "设备背板类型",
        "eepromcheck": "EEPROM 检查",
        "fast-sense": "快速感知",
        "first-ttl": "首个 TTL",
        "fpgacheck": "FPGA 检查",
        "insegment": "入段",
        "jitter": "抖动",
        "ldp-vc": "LDP VC",
        "load-splitting": "负载拆分",
        "lsa-debug": "LSA 调试",
        "mapping": "映射",
        "mcheck": "模块检查",
        "monitor": "监控",
        "mos-debugging": "MOS 调试",
        "mp-info": "MP 信息",
        "mtu-ignore": "忽略 MTU",
        "mtu-signalling": "MTU 信令",
        "mulcast": "组播",
        "neighbors": "邻居",
        "notifyagtdelay": "通知代理延迟",
        "plain": "明文",
        "qualify": "合格判定",
        "records": "记录",
        "reg-attr-req": "注册属性请求",
        "resource": "资源",
        "rtccheck": "RTC 检查",
        "subfancheck": "风扇子卡检查",
        "subfrontcheck": "前面板子卡检查",
        "subpwrcheck": "电源子卡检查",
        "system-id": "系统 ID",
        "system-software": "系统软件",
        "temporary": "临时",
        "timeq": "时间队列",
        "xctable": "交叉连接表",
        "weight": "权重",
        "xordip": "目的 IP 异或",
        "xordmac": "目的 MAC 异或",
        "xorsip": "源 IP 异或",
        "xorsmac": "源 MAC 异或",
        "speed": "速率",
        "startup": "启动配置",
        "statistics": "统计",
        "status": "状态",
        "style": "方式",
        "strict": "严格检查",
        "suppress": "抑制",
        "suppression": "抑制",
        "synchronization": "同步",
        "synchronization-config": "同步功能",
        "synchronization-result": "同步结果",
        "time": "时间",
        "timeout": "超时时间",
        "timer": "定时器",
        "to": "到",
        "traffic": "流量",
        "track": "联动跟踪",
        "trunk": "干道",
        "tunnel": "隧道",
        "tunnel-id": "隧道 ID",
        "tunnel-info": "隧道信息",
        "type": "类型",
        "urpf": "反向路径检查",
        "url": "地址",
        "verbose": "详细",
        "vlanif": "VLAN 虚接口",
        "vlan": "VLAN",
        "vpn": "VPN",
        "vpn-instance": "VPN 实例",
        "withdraw": "撤销",
        "wait": "等待",
        "abr": "区域边界路由器",
        "asbr": "自治系统边界路由器",
        "abr-asbr": "ABR/ASBR 路由器",
        "iih": "IS-IS Hello",
        "iih-cache": "IS-IS Hello 缓存",
        "iih-send-optimize": "IS-IS Hello 发送优化",
        # 2026-10-15 补：这些是普通英文词，词表里漏了，导致释义里原样留着英文。
        # 只收「意思不随上下文变」的；set/show/on/off/up/down 那类会看语境变意思
        # （如 bfd-down 是"BFD 失效"不是"离线"），盲补反而错，先不收。
        "auto": "自动",
        "name": "名称",
        "into": "到",
        "high": "高",
        "low": "低",
        "lsb": "低位",
        "msb": "高位",
        "lock": "锁定",
        "test": "测试",
    }
    key = subject.lower()
    if key in mapping:
        return mapping[key]
    parts = [part for part in re.split(r"[-_./:]+", key) if part]
    translated = [mapping.get(part, part.upper() if part in ("ip", "mac", "vpn") else "") for part in parts]
    translated = [part for part in translated if part]
    if translated:
        return " ".join(translated)
    if re.fullmatch(r"[a-z][a-z0-9]*", key):
        return key.upper() if len(key) <= 4 else ""
    if re.fullmatch(r"[a-z0-9_./:-]+", key):
        return ""
    return subject


def has_meaningful_translation(subject: str) -> bool:
    key = subject.lower()
    known = {
        "acl", "active", "address", "admin", "alarm", "area", "advanced", "all", "allow",
        "allow-default-route", "arp", "as", "as-path-filter", "backup", "bfd", "bfd-session", "bgp",
        "binding", "brief", "broadcast", "cache", "configuration", "config", "cpu", "cpu-usage", "current-configuration",
        "default", "delay", "deny", "description", "detail", "diagnosis", "diagnostic", "different", "discard", "discovery",
        "download", "duplex", "enable", "entry", "eth-trunk", "event", "excluded-ip-address", "export", "extcommunity-filter", "filter", "file", "gateway", "gateway-list",
        "generate", "get", "getfile", "gigabitethernet", "global", "graceful",
        "graceful-restart", "group", "gtsm", "guard", "guard-timer", "history",
        "image", "increment", "increment-command", "interface", "interval", "internet", "ip", "ip-prefix", "ipv4", "ipv6", "ipv6-prefix", "learn", "learn-style",
        "limit", "link", "log", "loghost", "liveness", "local", "loose", "ma", "mac", "mac-address", "management", "manual", "memory-usage",
        "max", "maximum", "md", "med", "mep", "mirror", "mpls", "neighbor", "no-advertise", "no-export",
        "no-export-subconfed", "nqa", "null", "num", "order", "ospf", "ospfv3", "packet",
        "parameter", "patch", "patch-command", "peer", "permanent", "permit", "period",
        "policy", "policy-based-route", "port", "preempt", "preference", "primary", "pvid", "prefix",
        "prefix-priority", "prefix-priority-scheduler", "program", "reconnect",
        "rd-filter", "recovery", "redirect", "refresh", "refresh-time", "relay", "relay-depth",
        "remark", "response", "restart", "rib", "rip", "routing", "route", "routes",
        "route-policy", "route-static", "routing-table", "rpf", "rpf-route-static", "rule",
        "secondary", "selection", "selection-rule", "session", "slot", "command", "command-table", "commit",
        "community", "community-filter", "compare", "compare-different-as-med", "cluster",
        "cluster-increment-result", "speed", "startup", "statistics",
        "status", "stp", "strict", "style", "suppress", "suppression", "synchronization-config", "tagged", "time",
        "timer", "track", "traffic", "trunk", "type", "untagged", "urpf", "vlan", "vlanif", "vpn", "vpn-instance", "wait", "withdraw",
    }
    known.update({
        "additive", "apply", "by", "bytes", "combo", "combo-port", "control",
        "control-word", "flow", "flow-control", "http", "http-url", "hybrid",
        "inbound", "listening", "match", "multicast", "negotiation", "none",
        "outbound", "public", "remote", "remove", "to", "tunnel", "tunnel-id",
        "tunnel-info", "url", "verbose",
        "aaa", "arp-fake", "arp-proxy", "arp-suppress", "authentication",
        "authentication-mode", "clock", "console", "datetime", "detect-mode",
        "detect-times", "expire-time", "fake", "feature", "feature-name",
        "filename", "filesize", "ftp", "header", "hello", "helper",
        "helper-role", "host", "host-route", "ignore-tc", "local-user",
        "day", "dhcp", "dns-list", "lease", "lldp", "lsdb", "lsp", "mode", "ntp", "ntp-service", "operation", "password",
        "proxy", "reboot", "role", "router", "router-id",
        "saved-configuration", "server", "snmp", "snmp-agent", "snmp-host",
        "ssh", "static", "stelnet", "sysname", "te", "telnet", "tftp",
        "this", "timezone", "tracert", "trap", "trapbuffer", "user", "username",
        "user-interface", "vrrp", "vty",
    })
    if key in known:
        return True
    translated = translate_subject(key)
    if translated and translated.lower() != key and translated != key.upper():
        return True
    parts = [part for part in re.split(r"[-_./:]+", key) if part]
    return bool(parts) and all(part in known for part in parts)


def describe_command_body(command: str) -> str:
    clean = normalize_spaces(PLACEHOLDER_RE.sub(" ", command))
    words = []
    for token in TOKEN_RE.findall(clean):
        if token.lower() in {"undo", "display", "reset", "debugging", "integer", "string", "hex"}:
            continue
        translated = translate_subject(token)
        if translated and translated not in words:
            words.append(translated)
    if not words:
        return "命令功能"
    return " ".join(words)


def infer_description(command: str) -> str:
    command = normalize_spaces(command)
    if command == "undo debugging":
        return "关闭调试"
    if command.startswith("undo debugging "):
        body = command.removeprefix("undo debugging ").strip()
        return "关闭调试：" + describe_command_body(body)
    if command == "undo _debugging":
        return "关闭内部调试"
    if command.startswith("undo _debugging "):
        body = command.removeprefix("undo _debugging ").strip()
        return "关闭内部调试：" + describe_command_body(body)
    raw = command.removeprefix("undo ").strip()
    if command.startswith("undo "):
        return "撤销或恢复缺省：" + infer_description(raw)
    if raw == "display":
        return "查看设备信息"
    if raw == "debugging" or raw == "_debugging":
        return "内部调试" if raw.startswith("_") else "开启调试"
    if raw == "ip":
        return "配置 IP 功能"
    if raw == "port":
        return "配置端口功能"
    if raw.startswith("display "):
        body = raw.removeprefix("display ").strip()
        if body.startswith(("{", "[", "|")):
            return "查看设备信息"
        return "查看" + describe_command_body(body)
    if raw.startswith("display-"):
        return "查看" + describe_command_body(raw.removeprefix("display-").strip())
    if raw.startswith("reset "):
        return "清除或重置" + describe_command_body(raw.removeprefix("reset ").strip())
    if raw.startswith("debugging "):
        return "开启调试：" + describe_command_body(raw.removeprefix("debugging ").strip())
    if raw.startswith("_debugging "):
        return "内部调试：" + describe_command_body(raw.removeprefix("_debugging ").strip())
    if raw.startswith("_"):
        visible = raw[1:].strip()
        if not visible:
            return "隐藏/诊断命令"
        return "隐藏/诊断：" + infer_description(visible)
    head = raw.split(" ", 1)[0] if raw else "命令"
    mapping = {
        "aaa": "进入 AAA 视图",
        "arp": "配置 ARP 参数",
        "authentication-mode": "配置认证方式",
        "clock": "配置系统时间",
        "ftp": "使用 FTP 传输文件",
        "header": "配置登录提示信息",
        "help": "查看命令帮助",
        "interface": "进入或配置接口",
        "vlan": "配置 VLAN",
        "ospf": "配置 OSPF",
        "bgp": "配置 BGP",
        "acl": "配置 ACL",
        "ip": "配置 IP 相关参数",
        "isis": "配置 IS-IS",
        "local-user": "配置本地用户",
        "ntp-service": "配置 NTP 时间同步",
        "ping": "测试网络连通性",
        "port": "配置端口参数",
        "protocol": "配置协议参数",
        "reboot": "重启设备",
        "reset": "清除或重置运行信息",
        "rip": "配置 RIP",
        "route-policy": "配置路由策略",
        "router": "配置路由器参数",
        "router-id": "配置路由器 ID",
        "snmp-agent": "配置 SNMP 管理",
        "ssh": "配置 SSH",
        "stelnet": "使用 Stelnet 登录设备",
        "shutdown": "关闭接口",
        "traffic": "配置流量策略",
        "telnet": "使用 Telnet 登录设备",
        "tftp": "使用 TFTP 传输文件",
        "trace": "跟踪诊断信息",
        "tracert": "跟踪报文转发路径",
        "mpls": "配置 MPLS",
        "peer": "配置对等体",
        "sysname": "设置设备名称",
        "synchronization-config": "配置同步功能",
        "user-interface": "进入用户界面视图",
        "vrrp": "配置 VRRP 虚拟路由冗余",
    }
    if head in mapping:
        if len(raw.split()) == 1:
            return mapping[head]
        return "配置" + describe_command_body(raw)
    return "配置" + describe_command_body(raw)


def description_is_weak(desc: str) -> bool:
    d = desc.strip()
    lower = d.lower()
    return (
        d in ("配置相关参数", "配置相关", "相关命令", "配置命令功能", "命令功能", "调试相关命令", "隐藏/诊断命令")
        or d.startswith("补全词：")
        or d == "撤销或恢复缺省：调试相关命令"
        or d.endswith("命令功能")
        or "complete prefix" in lower
        or "configure " in lower
        or "相关参数" in d
        or d.endswith("相关")
        or "查看 { 信息" in d
        or "配置{" in d
        or "配置[" in d
    )


def description_has_untranslated_ascii(desc: str) -> bool:
    allowed = {
        "IP", "IPv4", "IPv6", "MAC", "VLAN", "VPN", "ACL", "ARP", "BFD", "BGP",
        "CPU", "GTSM", "MPLS", "OSPF", "OSPFv3", "RIB", "NQA", "AS", "MED", "RD",
        "HTTP", "L2IF", "LoopBack", "AAA", "BSR", "BootROM", "CIR", "Console",
        "CPLD", "DHCP", "DIS", "Down", "EEPROM", "EFM", "FPGA", "FTP", "GENID",
        "IGMP", "IS", "ISIS", "LCS", "LDP", "LSP", "LSA", "LSR", "Martini",
        "MLD", "MP", "MTU", "NAT", "NPE", "OAM", "Opaque", "PAF", "PDU", "PE",
        "PIM", "PW", "RP", "RIP", "RIPng", "RTC", "Snooping", "SNMP", "SPF",
        "SPT", "SSH", "Stelnet", "TCP", "TE", "Telnet", "TFTP", "Trap", "Trunk",
        "TTL", "UDP", "UPE", "VPLS", "VPNv4", "VRRP", "VSI", "VxWorks",
        "Echo", "Hello", "ICMPv6", "Level-1", "Level-2", "Router", "ag",
    }
    for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", desc):
        if word not in allowed and not word.isupper():
            return True
    return False


def infer_view(command: str) -> str:
    c = command.removeprefix("undo ").strip()
    if c.startswith(("display ", "reset ", "debugging ", "_debugging ")):
        return "user-view"
    if c.startswith("interface "):
        return "system-view"
    if c.startswith(("ip address", "ospf enable", "port ", "shutdown", "duplex", "speed")):
        return "interface-view"
    if c.startswith(("vlan ", "access-vlan", "aggregate-vlan")):
        return "vlan-view"
    if c.startswith("ospf "):
        return "ospf-view"
    if c.startswith("acl "):
        return "acl-view"
    return "system-view"


def infer_risk(command: str) -> str:
    c = command.strip()
    if c.startswith(("reset ", "save")):
        return "high"
    if c.startswith(("debugging ", "_debugging ", "undo ", "_")):
        return "medium"
    return "low"


def infer_view_after_enter(command: str, current_view: str) -> str:
    c = normalize_spaces(command).lower()
    if not c:
        return current_view
    if c == "return":
        return "user-view"
    if c == "quit":
        if current_view in ("interface-view", "vlan-view", "ospf-view", "acl-view"):
            return "system-view"
        return "user-view"
    if c == "system-view":
        return "system-view"
    if c.startswith("interface "):
        return "interface-view"
    if c.startswith("vlan"):
        return "vlan-view"
    if c.startswith("ospf"):
        return "ospf-view"
    if c.startswith("acl"):
        return "acl-view"
    return current_view


class CommandStore:
    def __init__(self, root: Path):
        self.root = root
        self.data_dir = root / "data"
        self.rules_dir = root / "rules"
        self.logs_dir = root / "logs"
        for folder in (self.data_dir, self.rules_dir, self.logs_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self.commands_path = self.data_dir / "vrp_commands_unique.txt"
        self.usage_path = self.root / "daima.txt"
        self.legacy_usage_path = self.data_dir / "usage.json"
        self.settings_path = self.data_dir / "settings.json"
        self.desc_path = self.rules_dir / "descriptions.json"
        self.usage = self.load_usage()
        self.settings = self.load_json(self.settings_path, {"candidateOpacity": DEFAULT_CANDIDATE_OPACITY, "candidateXOffset": 0, "candidateYOffset": 0})
        self.descriptions = self.load_json(self.desc_path, {})
        self.commands = []
        self.head_tokens = set()

    @staticmethod
    def load_json(path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return default
        return default

    def load_usage(self):
        usage = {}
        if self.usage_path.exists():
            for line in self.usage_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                command = parts[0].strip()
                if not command:
                    continue
                try:
                    usage_count = int(parts[1])
                except ValueError:
                    continue
                try:
                    last_used = float(parts[2]) if len(parts) > 2 else 0
                except ValueError:
                    last_used = 0
                usage[command] = {"usageCount": max(0, usage_count), "lastUsed": last_used}
            return usage
        legacy = self.load_json(self.legacy_usage_path, {})
        return legacy if isinstance(legacy, dict) else {}

    def ensure_command_file(self):
        if self.commands_path.exists():
            return
        bundled = resource_dir() / "data" / "vrp_commands_unique.txt"
        if bundled.exists():
            self.commands_path.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")

    def load(self):
        self.ensure_command_file()
        seen = set()
        rows = [(cmd, desc, view, risk, "built-in") for cmd, desc, view, risk in COMMON_COMMANDS]
        if self.commands_path.exists():
            for line in self.commands_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                raw = normalize_spaces(line.replace("\ufeff", ""))
                if not raw:
                    continue
                if raw.startswith("[ undo ]"):
                    body = normalize_spaces(raw[len("[ undo ]"):])
                    for variant in choice_prefix_variants(body):
                        rows.append((variant, infer_description(variant), infer_view(variant), infer_risk(variant), raw))
                        undo_variant = "undo " + variant
                        rows.append((undo_variant, infer_description(undo_variant), infer_view(undo_variant), "medium", raw))
                else:
                    for variant in choice_prefix_variants(raw):
                        rows.append((variant, infer_description(variant), infer_view(variant), infer_risk(variant), raw))

        derived_rows = []
        token_rows = []
        suffix_rows = []
        for cmd, desc, view, risk, source in rows:
            insert_text = clean_for_insert(cmd)
            insert_tokens = insert_text.split()
            for end in range(1, len(insert_tokens)):
                prefix = " ".join(insert_tokens[:end])
                derived_rows.append((prefix, infer_description(prefix), view, risk, "derived"))
            for start in range(1, len(insert_tokens)):
                suffix = " ".join(insert_tokens[start:])
                if suffix:
                    suffix_rows.append((suffix, infer_description(insert_text), view, risk, "suffix", insert_text))
            for token in insert_tokens[1:]:
                if WORD_TOKEN_RE.fullmatch(token) and len(token) >= 2 and has_meaningful_translation(token):
                    token_rows.append((token, "含义：" + translate_subject(token), view, risk, "token"))
        common_tokens = set()
        for common_cmd, _, _, _ in COMMON_COMMANDS:
            for common_token in clean_for_insert(common_cmd).split()[1:]:
                if WORD_TOKEN_RE.fullmatch(common_token) and len(common_token) >= 2:
                    common_tokens.add(common_token)
        token_rows = [
            item[:4] + ("token-common",) if item[0] in common_tokens else item
            for item in token_rows
        ]
        base_inserts = {
            clean_for_insert(row[0])
            for row in rows + derived_rows
            if clean_for_insert(row[0])
        }
        token_rows = [item for item in token_rows if item[0] not in base_inserts]
        rows.extend(derived_rows)
        rows.extend(suffix_rows)
        rows.extend(token_rows)

        merged_desc = dict(self.descriptions)
        out = []
        for row in rows:
            cmd, desc, view, risk, source = row[:5]
            full_insert = row[5] if len(row) > 5 else cmd
            cmd = normalize_spaces(cmd)
            if source not in ("built-in", "derived", "suffix", "token", "token-common"):
                cleaned_cmd = clean_for_insert(cmd)
                if cleaned_cmd:
                    # 说明要按"清理后的短命令"算。原来 desc 是按整条语法行算的，
                    # 会把 { be | af1 | ... } 这类可选关键字统统译进来（关键词堆）
                    if cleaned_cmd != cmd:
                        desc = infer_description(cleaned_cmd)
                    cmd = cleaned_cmd
            seen_key = cmd
            if source == "suffix":
                seen_key = cmd + "\0" + clean_for_insert(full_insert)
            elif source.startswith("token"):
                seen_key = cmd + "\0" + source
            if not cmd or seen_key in seen:
                continue
            if not re.search(r"[A-Za-z\u4e00-\u9fff]", cmd):
                continue
            if source.startswith("token") and not has_meaningful_translation(cmd):
                continue
            seen.add(seen_key)
            desc_obj = merged_desc.get(cmd)
            if isinstance(desc_obj, (str, dict)):
                # built-in 的译文来自 COMMON_COMMANDS，是权威的：不能被上次落盘的旧值
                # 覆盖（否则一旦某次写坏，之后每次启动都会把坏值读回来，永久化）
                if source != "built-in":
                    if isinstance(desc_obj, dict):
                        desc = desc_obj.get("description", desc)
                        view = desc_obj.get("view", view)
                        risk = desc_obj.get("risk", risk)
                    else:
                        desc = desc_obj
            else:
                if source != "suffix":
                    merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            if source not in ("token", "token-common") and desc.startswith("含义："):
                desc = infer_description(cmd)
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            if description_is_weak(desc) or description_has_untranslated_ascii(desc):
                desc = infer_description(cmd)
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            if desc.startswith("补全词：") or desc.startswith("补全："):
                desc = "含义：" + translate_subject(cmd)
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            if source == "derived":
                desc = infer_description(cmd)
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            elif source == "suffix":
                full_clean = clean_for_insert(full_insert)
                desc_command = full_clean
                if full_clean.startswith("undo ") and not cmd.startswith("undo "):
                    desc_command = full_clean.removeprefix("undo ").strip()
                desc = DESCRIPTION_OVERRIDES.get(desc_command, infer_description(desc_command))
                # 这里算的是"整条长命令"的意思，只用来显示这一行（尾词补全）；
                # 绝不能写进 merged_desc[cmd] —— 那会把短命令自己的译文覆盖掉
            elif source.startswith("token"):
                desc = "含义：" + translate_subject(cmd)
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            elif cmd in DESCRIPTION_OVERRIDES:
                desc = DESCRIPTION_OVERRIDES[cmd]
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            if not cmd.startswith("undo ") and desc.startswith("撤销或恢复缺省："):
                desc = DESCRIPTION_OVERRIDES.get(cmd, infer_description(cmd))
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            if cmd.startswith("display ") and len(cmd.split()) > 2 and desc in {"查看 OSPF", "查看OSPF", "查看 OSPFv3", "查看OSPFv3", "查看 BGP", "查看BGP", "查看 ISIS", "查看ISIS"}:
                desc = DESCRIPTION_OVERRIDES.get(cmd, infer_description(cmd))
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            insert_text = clean_for_insert(cmd)
            if source not in ("built-in", "derived", "token", "token-common") and insert_text != cmd:
                insert_desc = infer_description(insert_text)
                if not description_is_weak(insert_desc):
                    desc = insert_desc
            if cmd in DESCRIPTION_OVERRIDES:
                desc = DESCRIPTION_OVERRIDES[cmd]
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            desc = polish_description(desc)
            # 后缀行是"尾词补全"用的，它描述的是整条长命令、不是这个词本身：
            # 只在还没有任何译文时才落盘，绝不覆盖已有条目
            if source != "suffix" or cmd not in merged_desc:
                merged_desc[cmd] = {"description": desc, "view": view, "risk": risk}
            insert_tokens = [t.lower() for t in TOKEN_RE.findall(insert_text)]
            searchable = normalize_spaces(SYNTAX_MARK_RE.sub(" ", PLACEHOLDER_RE.sub(" ", cmd)))
            out.append({
                "command": cmd,
                "insert": insert_text,
                "description": desc,
                "view": view,
                "risk": risk,
                "source": source,
                "fullInsert": clean_for_insert(full_insert),
                "contextMatched": False,
                "replaceMode": "tail" if source == "suffix" else ("token" if source.startswith("token") else "line"),
                "searchable": searchable,
                "descriptionZh": chinese_search_key(desc),
                "insertTokens": insert_tokens,
                "prefixTokens": set(insert_tokens),
                "tokens": set(t.lower() for t in TOKEN_RE.findall(searchable + " " + desc)),
            })
        self.commands = out
        self.head_tokens = {
            item["insertTokens"][0]
            for item in out
            if item["insertTokens"] and item["source"] not in ("suffix", "token", "token-common", "derived")
        }
        active_commands = {item["command"] for item in out}
        cleaned_desc = {}
        for cmd, obj in merged_desc.items():
            if cmd not in active_commands:
                continue
            desc_text = obj.get("description", "") if isinstance(obj, dict) else str(obj)
            if description_is_weak(desc_text) or description_has_untranslated_ascii(desc_text):
                continue
            cleaned_desc[cmd] = obj
        merged_desc = cleaned_desc
        self.desc_path.write_text(json.dumps(merged_desc, ensure_ascii=False, indent=2), encoding="utf-8")
        original_lines = len(self.commands_path.read_text(encoding="utf-8", errors="ignore").splitlines()) if self.commands_path.exists() else 0
        (self.logs_dir / "load_report.json").write_text(json.dumps({
            "loadedCommands": len(out),
            "originalLines": original_lines,
            "generatedDescriptions": len(merged_desc),
            "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_usage(self):
        lines = []
        for command, item in sorted(self.usage.items(), key=lambda kv: (-int(kv[1].get("usageCount", 0)), kv[0])):
            count = int(item.get("usageCount", 0))
            last = float(item.get("lastUsed", 0) or 0)
            if count > 0:
                lines.append(f"{command}\t{count}\t{last:.6f}")
        self.usage_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def save_settings(self):
        self.settings_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_use(self, command: str):
        item = self.usage.setdefault(command, {"usageCount": 0, "lastUsed": 0})
        item["usageCount"] = int(item.get("usageCount", 0)) + 1
        item["lastUsed"] = time.time()
        self.save_usage()

    def search(self, query: str, page: int = 0, current_view: str = "any", tail_only: bool = False, context_prefix: str = ""):
        q = normalize_spaces(query).lower()
        if not q:
            return [], 0, 0
        q_zh = chinese_search_key(q)
        if prefix_query := (q.isascii() and bool(PREFIX_QUERY_RE.fullmatch(q))):
            parts = TOKEN_RE.findall(q)
        else:
            parts = TOKEN_RE.findall(q)
        if not parts and not q.isascii():
            return [], 0, 0
        # 中文夹英文（"查看arp"、"配置ospf"）是最常见的输入方式
        mixed_query = bool(q_zh) and bool(re.search(r"[A-Za-z0-9]", q))
        query_is_command_head = len(parts) == 1 and parts[0] in self.head_tokens
        scored = []
        token_scored = []
        now = time.time()
        context = normalize_spaces(context_prefix).lower()
        for item in self.commands:
            if not tail_only and item["source"] == "suffix":
                continue
            if tail_only and item["source"] not in ("suffix", "token", "token-common"):
                continue
            context_match = False
            if tail_only and context and item["source"] == "suffix":
                full_insert = item.get("fullInsert", "").lower()
                context_parts = context.split()
                full_parts = full_insert.split()
                context_match = len(context_parts) <= len(full_parts) and full_parts[:len(context_parts)] == context_parts
                if not context_match:
                    continue
                item = dict(item)
                item["contextMatched"] = True
            cmd = item["command"].lower()
            insert = item["insert"].lower()
            searchable = item["searchable"].lower()
            desc = item["description"].lower()
            desc_zh = item.get("descriptionZh", "")
            if prefix_query and item["source"] == "derived" and insert == q:
                continue
            if prefix_query and item["source"].startswith("token") and insert == q:
                continue
            if prefix_query:
                insert_parts = item["insertTokens"]
                query_parts = parts
                direct = insert.startswith(q) or (
                    item["source"].startswith("token")
                    and bool(query_parts)
                    and insert.startswith(query_parts[-1])
                ) or (
                    len(query_parts) == 1
                    and len(query_parts[0]) >= 3
                    and not query_is_command_head
                    and any(token.startswith(query_parts[0]) for token in insert_parts)
                ) or prefix_parts_match(insert_parts, query_parts)
            else:
                if mixed_query:
                    # 中文夹英文时不能只看中文部分：q_zh 会把 "arp"/"ospf"/"IP" 丢掉，
                    # 结果变成"所有含『查看』的命令"，真正的 display arp 反而排在后面
                    direct = bool(parts) and all(
                        p in item["tokens"]
                        or p in searchable
                        or p in desc
                        or bool(chinese_search_key(p) and chinese_search_key(p) in desc_zh)
                        for p in parts
                    )
                else:
                    direct = q in searchable or q in desc or bool(q_zh and q_zh in desc_zh)
            token_match = False if prefix_query else bool(parts) and all(
                p in item["tokens"]
                or p in searchable
                or p in desc
                or bool(chinese_search_key(p) and chinese_search_key(p) in desc_zh)
                for p in parts
            )
            if not direct and not token_match:
                continue
            score = 0
            if cmd == q:
                score += 120
            if insert.startswith(q):
                score += 110
            elif searchable.startswith(q):
                score += 90
            if prefix_query:
                insert_parts = item["insertTokens"]
                query_parts = parts
                if len(insert_parts) == len(query_parts):
                    score += 95
                score += 45 * sum(
                    1 for idx, part in enumerate(query_parts)
                    if idx < len(insert_parts) and insert_parts[idx] == part
                )
                if item["source"] == "derived":
                    score += 25
                elif item["source"].startswith("token"):
                    score += 35
                score += max(0, 40 - len(insert_parts) * 4)
            if any(tok.startswith(q) for tok in item["tokens"]):
                score += 55
            if q_zh:
                if desc_zh == q_zh:
                    score += 130
                elif desc_zh.startswith(q_zh):
                    score += 105
                elif q_zh in desc_zh:
                    score += 85
                score += chinese_query_priority(q_zh, item)
            score += 18 * sum(1 for p in parts if p in item["tokens"] or p in cmd or p in desc)
            if item["source"] == "built-in":
                score += 60
            score += COMMAND_PRIORITY.get(item["command"], 0)
            if current_view and current_view != "any":
                if item["view"] == current_view:
                    score += 70
                elif item["view"] == "any":
                    score += 10
                else:
                    score -= 130
            if item["risk"] == "low":
                score += 8
            elif item["risk"] == "high":
                score -= 25
            usage_candidates = [
                self.usage.get(item["insert"], {}),
                self.usage.get(item["command"], {}),
                self.usage.get(item.get("fullInsert", ""), {}),
            ]
            usage = max(usage_candidates, key=lambda u: int(u.get("usageCount", 0) or 0))
            score += int(usage.get("usageCount", 0)) * 100000
            last = max(float(u.get("lastUsed", 0) or 0) for u in usage_candidates)
            if last:
                score += max(0, 12 - (now - last) / 86400)
            if tail_only and item["source"] == "suffix":
                score += 90
                if context_match:
                    score += 300
                    full_insert = item.get("fullInsert", "").lower()
                    if full_insert.startswith((context + " " + q).strip()):
                        score += 120
                        score += max(0, 80 - len(item["insert"]) * 2)
            if tail_only and item["source"] == "token-common":
                score += 1000
            is_token_item = item["source"].startswith("token")
            if is_token_item and item["source"] == "token-common" and prefix_query and len(q) >= 2 and tail_only:
                scored.append((score + 70, item))
            elif is_token_item:
                token_scored.append((score, item))
            else:
                scored.append((score, item))
        if prefix_query and len(parts) == 1:
            # 词条（"含义：xxx"）只补位，不加分：原来 +20 会让 ip-address 这类
            # 词条反超 ip pool / ip route-static 这类真命令，把有用的挤到后面
            if query_is_command_head:
                # 敲的本身就是现成的命令头（ip、display…）时，词条纯属噪声，
                # 一律沉到所有真命令之后；敲 br 这种没对应命令的片段时行为不变
                scored.extend((score - 500, item) for score, item in token_scored)
            else:
                scored.extend(token_scored)
        elif not scored:
            scored = token_scored
        scored.sort(key=lambda x: (-x[0], x[1]["command"]))
        unique_scored = []
        seen_visible = {}
        for score, item in scored:
            visible_key = (item["insert"] or item["command"]).lower()
            if visible_key in seen_visible:
                existing_idx = seen_visible[visible_key]
                existing_item = unique_scored[existing_idx][1]
                if existing_item["source"].startswith("token") and not item["source"].startswith("token"):
                    unique_scored[existing_idx] = (score, item)
                continue
            seen_visible[visible_key] = len(unique_scored)
            unique_scored.append((score, item))
        scored = unique_scored
        pages = max(1, (len(scored) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        return [x[1] for x in scored[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]], pages, len(scored)


class Keyboard:
    user32 = ctypes.windll.user32
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104
    VK_BACK = 0x08
    VK_RETURN = 0x0D
    VK_ESCAPE = 0x1B
    VK_LEFT = 0x25
    VK_RIGHT = 0x27
    VK_OEM_PLUS = 0xBB
    VK_OEM_MINUS = 0xBD
    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    LLKHF_INJECTED = 0x10

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    def __init__(self, callback, accept_injected: bool = False):
        self.callback = callback
        self.accept_injected = accept_injected
        self.hook = None
        self.installed = threading.Event()
        self.install_error = None
        self.user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.CallNextHookEx.restype = wintypes.LPARAM
        self.user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.HINSTANCE, wintypes.DWORD]
        self.user32.SetWindowsHookExW.restype = wintypes.HHOOK
        self.proc = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)(self._proc)

    def start(self):
        self.hook = self.user32.SetWindowsHookExW(self.WH_KEYBOARD_LL, self.proc, None, 0)
        if not self.hook:
            self.install_error = ctypes.GetLastError()
            self.installed.set()
            return
        self.installed.set()
        msg = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))

    def _proc(self, n_code, w_param, l_param):
        if n_code == 0 and w_param in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN):
            kb = ctypes.cast(l_param, ctypes.POINTER(self.KBDLLHOOKSTRUCT)).contents
            if (kb.flags & self.LLKHF_INJECTED) and not self.accept_injected:
                return self.user32.CallNextHookEx(self.hook, n_code, w_param, l_param)
            if self.callback(kb.vkCode):
                return 1
        return self.user32.CallNextHookEx(self.hook, n_code, w_param, l_param)


class App:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    GWL_EXSTYLE = -20
    SW_SHOWNOACTIVATE = 4
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    RDW_INVALIDATE = 0x0001
    RDW_ERASE = 0x0004
    RDW_ALLCHILDREN = 0x0080
    RDW_UPDATENOW = 0x0100
    RDW_FRAME = 0x0400
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    def __init__(self, hook_smoke_test: bool = False, start_keyboard: bool = True, accept_injected_keys: bool = False):
        enable_dpi_awareness()
        self.root_dir = app_dir()
        self.store = CommandStore(self.root_dir)
        self.store.load()
        self.candidate_opacity = clamp_candidate_opacity(self.store.settings.get("candidateOpacity", DEFAULT_CANDIDATE_OPACITY))
        if self.store.settings.get("candidateOpacity") != self.candidate_opacity:
            self.store.settings["candidateOpacity"] = self.candidate_opacity
            self.store.save_settings()
        self.candidate_x_offset = int(self.store.settings.get("candidateXOffset", 0))
        self.candidate_y_offset = int(self.store.settings.get("candidateYOffset", 0))
        self.compat_mode = bool(self.store.settings.get("compatMode", True))
        self.enabled = True
        self.buffer = ""
        self.host_buffer_len = 0
        self.ctrl_query_mode = False
        self.ctrl_virtual_len = 0
        self.ctrl_space_latched = False
        self.page = 0
        self.items = []
        self.pages = 1
        self.total = 0
        self.manual_lookup_active = False
        self.manual_lookup_query = ""
        self.current_view = "user-view"
        self.pending_command = ""
        self.suppress_until = 0
        self.suppress_key_events = 0
        # 有字正在往 eNSP 送（送一趟要花一点时间）。这期间按下的回车要先扣住，
        # 等字落地再放行，否则 eNSP 会先执行眼前那半截命令。
        self.commit_in_flight = False
        self.queued_enter = False
        self.candidate_closed_by_escape = False
        self.tail_search_mode = False
        self.replace_current_token_only = False
        # 隐身输入：在 eNSP 里敲的字只进候选框，不落到 Console；
        # 只有"数字键补全 / 空格 / 符号 / Esc"才会把内容送进 eNSP。
        # Esc 会把它关掉（方便接着手改），按回车开始新的一行时重新打开。
        self.invisible_input = True
        self.last_target_hwnd = None
        self.smoke_mode = hook_smoke_test
        self.start_keyboard = bool(start_keyboard or hook_smoke_test)
        self.accept_injected_keys = bool(accept_injected_keys)
        self.smoke_events = []
        self.exit_code = 0
        self.ui_queue = queue.Queue()
        self.root_hwnd = None
        self.status_hwnd = None
        self.trace_lock = threading.Lock()
        self.page_trace_path = self.store.logs_dir / "page_trace.log"

        self.root = tk.Tk()
        try:
            dpi = self.root.winfo_fpixels("1i")
            self.root.tk.call("tk", "scaling", max(1.0, dpi / 72.0))
        except tk.TclError:
            pass
        self.root.title(APP_NAME)
        self.root.configure(bg="#fff5f9")
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        self.root.overrideredirect(True)
        self.root.geometry("+80+80")
        self.root.withdraw()
        self.header_font = tkfont.Font(root=self.root, family="Microsoft YaHei UI", size=10)
        self.index_font = tkfont.Font(root=self.root, family="Consolas", size=12, weight="bold")
        self.command_font = tkfont.Font(root=self.root, family="Consolas", size=12, weight="bold")
        self.description_font = tkfont.Font(root=self.root, family="Microsoft YaHei UI", size=11)
        self.footer_font = tkfont.Font(root=self.root, family="Microsoft YaHei UI", size=10, weight="bold")
        self.hint_font = tkfont.Font(root=self.root, family="Microsoft YaHei UI", size=10)
        self.frame = tk.Frame(self.root, bg="#fff5f9", highlightthickness=1, highlightbackground="#e989b2")
        self.frame.pack(fill="both", expand=True)
        self.header = tk.Label(self.frame, bg="#fff5f9", fg="#8f6c7f", anchor="w", font=self.header_font)
        self.header.pack(fill="x", padx=10, pady=(5, 0))
        self.rows = []
        for _ in range(PAGE_SIZE):
            row = tk.Frame(self.frame, bg="#fff5f9")
            idx = tk.Label(row, width=3, bg="#fff5f9", fg="#ed75a0", font=self.index_font, anchor="e")
            cmd = tk.Label(row, bg="#fff5f9", fg="#000000", font=self.command_font, anchor="w", justify="left")
            desc = tk.Label(row, bg="#fff5f9", fg="#8f7584", font=self.description_font, anchor="w", justify="left")
            idx.grid(row=0, column=0, sticky="e")
            cmd.grid(row=0, column=1, sticky="w")
            desc.grid(row=0, column=2, sticky="w")
            row.pack(fill="x", padx=5, pady=1)
            self.rows.append((row, idx, cmd, desc))
        self.footer = tk.Label(self.frame, bg="#e77ba8", fg="white", anchor="w", font=self.footer_font)
        self.footer.pack(fill="x", pady=(4, 0), ipady=5)
        self.hint = tk.Label(self.frame, bg="#fff5f9", fg="#8f6c7f", anchor="w", justify="left", font=self.hint_font)
        self.hint.pack(fill="x", padx=10, pady=(4, 5))
        if hook_smoke_test:
            self.status = None
        else:
            self.build_tray_hint()
        self.root.update_idletasks()
        self.root_hwnd = self.root.winfo_id()
        self.make_no_activate(self.root)
        self.root.after(10, self.drain_ui_queue)
        if self.start_keyboard:
            self.keyboard = Keyboard(self.on_key, accept_injected=self.accept_injected_keys)
            threading.Thread(target=self.keyboard.start, daemon=True).start()
        if hook_smoke_test:
            self.root.after(800, lambda: threading.Thread(target=self.run_hook_smoke_test, daemon=True).start())

    def build_tray_hint(self):
        self.status = tk.Toplevel(self.root)
        self.status_hwnd = self.status.winfo_id()
        self.status.title(APP_NAME)
        self.status.geometry("650x370+120+120")
        self.status.configure(bg="#fff5f9")
        tk.Label(self.status, text=APP_NAME, bg="#fff5f9", fg="#222", font=("Microsoft YaHei UI", 16, "bold")).pack(pady=(18, 8))
        tk.Label(self.status, text="只在 eNSP 设备 Console 中生效；F8 暂停/启用，F9 重新加载。", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 11)).pack()
        self.status_info = tk.Label(self.status, text=f"已加载 {len(self.store.commands)} 条候选。", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 11))
        self.status_info.pack(pady=6)
        self.hook_info = tk.Label(self.status, text="键盘钩子：检测中", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 10))
        self.hook_info.pack()
        self.target_info = tk.Label(self.status, text="前台窗口：未检测", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 10), wraplength=610, justify="left")
        self.target_info.pack(padx=18, pady=(2, 6), fill="x")
        manual_row = tk.Frame(self.status, bg="#fff5f9")
        manual_row.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(manual_row, text="中文查命令", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.manual_query_var = tk.StringVar()
        self.manual_query_seen_text = ""
        self.manual_query_entry = tk.Entry(manual_row, textvariable=self.manual_query_var, bg="white", fg="#222", relief="solid", borderwidth=1, font=("Microsoft YaHei UI", 10))
        self.manual_query_entry.pack(side="left", padx=(10, 8), fill="x", expand=True)
        self.manual_query_entry.bind("<Return>", lambda _event: self.show_manual_query())
        self.manual_query_entry.bind("<KeyPress>", self.on_manual_query_key_press)
        self.manual_query_entry.bind("<KeyRelease>", self.on_manual_query_key_release)
        tk.Button(manual_row, text="查", command=self.show_manual_query, bg="#e77ba8", fg="white", relief="flat", width=4, font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        screen_w = max(800, self.status.winfo_screenwidth())
        screen_h = max(600, self.status.winfo_screenheight())
        compat_row = tk.Frame(self.status, bg="#fff5f9")
        compat_row.pack(fill="x", padx=28, pady=(0, 8))
        self.compat_var = tk.BooleanVar(value=self.compat_mode)
        tk.Checkbutton(compat_row, text="兼容模式：放宽 eNSP 控制台识别", variable=self.compat_var, command=self.set_compat_mode, bg="#fff5f9", fg="#735d6b", activebackground="#fff5f9", highlightthickness=0, font=("Microsoft YaHei UI", 10)).pack(side="left")
        opacity_row = tk.Frame(self.status, bg="#fff5f9")
        opacity_row.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(opacity_row, text="候选框透明度", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.opacity_value = tk.Label(opacity_row, text=f"{int(self.candidate_opacity * 100)}", bg="#fff5f9", fg="#735d6b", width=4, font=("Microsoft YaHei UI", 10))
        self.opacity_value.pack(side="left", padx=(8, 0))
        self.opacity_var = tk.IntVar(value=int(self.candidate_opacity * 100))
        tk.Scale(opacity_row, from_=int(MIN_CANDIDATE_OPACITY * 100), to=100, orient="horizontal", variable=self.opacity_var, command=self.set_candidate_opacity, bg="#fff5f9", fg="#735d6b", highlightthickness=0, length=250).pack(side="left", padx=10)
        x_offset_row = tk.Frame(self.status, bg="#fff5f9")
        x_offset_row.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(x_offset_row, text="候选框左右偏移", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.x_offset_var = tk.IntVar(value=self.candidate_x_offset)
        tk.Scale(x_offset_row, from_=-screen_w, to=screen_w, orient="horizontal", variable=self.x_offset_var, command=self.set_candidate_x_offset, bg="#fff5f9", fg="#735d6b", highlightthickness=0, length=250).pack(side="left", padx=10)
        offset_row = tk.Frame(self.status, bg="#fff5f9")
        offset_row.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(offset_row, text="候选框上下偏移", bg="#fff5f9", fg="#735d6b", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.offset_var = tk.IntVar(value=self.candidate_y_offset)
        tk.Scale(offset_row, from_=-screen_h, to=screen_h, orient="horizontal", variable=self.offset_var, command=self.set_candidate_offset, bg="#fff5f9", fg="#735d6b", highlightthickness=0, length=250).pack(side="left", padx=10)
        buttons = tk.Frame(self.status, bg="#fff5f9")
        buttons.pack(pady=8)
        btn_font = ("Microsoft YaHei UI", 11, "bold")
        tk.Button(buttons, text="暂停/启用", command=self.toggle_enabled, bg="#e77ba8", fg="white", relief="flat", width=10, font=btn_font).pack(side="left", padx=5)
        tk.Button(buttons, text="重载命令库", command=self.reload, bg="#e77ba8", fg="white", relief="flat", width=10, font=btn_font).pack(side="left", padx=5)
        tk.Button(buttons, text="隐藏到后台", command=self.status.withdraw, bg="#b68ca2", fg="white", relief="flat", width=10, font=btn_font).pack(side="left", padx=5)
        tk.Button(buttons, text="退出助手", command=self.exit_app, bg="#555555", fg="white", relief="flat", width=10, font=btn_font).pack(side="left", padx=5)
        tk.Label(self.status, text="关闭此窗口会退出助手。隐藏后可重新双击程序启动一个新的控制窗。", bg="#fff5f9", fg="#9b7588", font=("Microsoft YaHei UI", 10)).pack()
        self.status.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.update_status_panel()

    def toggle_enabled(self):
        self.enabled = not self.enabled
        self.buffer = ""
        self.host_buffer_len = 0
        self.ctrl_query_mode = False
        self.ctrl_virtual_len = 0
        self.ctrl_space_latched = False
        self.invisible_input = True
        self.hide()
        if hasattr(self, "status_info"):
            state = "启用" if self.enabled else "暂停"
            self.status_info.config(text=f"已加载 {len(self.store.commands)} 条候选。当前状态：{state}")

    def set_candidate_opacity(self, value):
        self.candidate_opacity = clamp_candidate_opacity(float(value) / 100.0)
        if hasattr(self, "opacity_value"):
            self.opacity_value.config(text=f"{int(self.candidate_opacity * 100)}")
        self.store.settings["candidateOpacity"] = self.candidate_opacity
        self.store.save_settings()
        self.refresh_candidate_window()

    def set_compat_mode(self):
        self.compat_mode = bool(self.compat_var.get())
        self.store.settings["compatMode"] = self.compat_mode
        self.store.save_settings()
        self.update_status_panel()

    def update_status_panel(self):
        if not hasattr(self, "hook_info") or self.smoke_mode:
            return
        if not self.start_keyboard:
            self.hook_info.config(text="键盘钩子：测试模式未启动", fg="#8f6c7f")
            self.target_info.config(text="前台窗口：测试模式", fg="#8f6c7f")
            return
        if not hasattr(self, "keyboard"):
            self.hook_info.config(text="键盘钩子：检测中", fg="#8f6c7f")
            self.root.after(1000, self.update_status_panel)
            return
        if self.keyboard.installed.is_set() and self.keyboard.hook:
            hook_text = "键盘钩子：正常"
            hook_color = "#2d7d46"
        elif self.keyboard.installed.is_set():
            hook_text = f"键盘钩子：失败，错误码 {self.keyboard.install_error}"
            hook_color = "#c0395e"
        else:
            hook_text = "键盘钩子：检测中"
            hook_color = "#8f6c7f"
        target_text = self.target_window_text()
        target_ok = self.is_target_window()
        target_short = target_text[:160] + ("..." if len(target_text) > 160 else "")
        mode = "兼容模式开" if self.compat_mode else "兼容模式关"
        self.hook_info.config(text=hook_text, fg=hook_color)
        self.target_info.config(
            text=f"前台窗口：{'已识别' if target_ok else '未识别'} | {mode} | {target_short or '无'}",
            fg="#2d7d46" if target_ok else "#9b7588",
        )
        self.root.after(1000, self.update_status_panel)

    def refresh_candidate_window(self, repaint: bool = True):
        try:
            self.root.attributes("-alpha", self.candidate_opacity)
        except tk.TclError:
            pass
        if self.items or getattr(self, "window_should_show", False):
            self.position_near_foreground()
            hwnd = self.root.winfo_id()
            self.user32.SetWindowPos(hwnd, self.HWND_TOPMOST, self.root.winfo_x(), self.root.winfo_y(), 0, 0, self.SWP_NOSIZE | self.SWP_NOACTIVATE | self.SWP_SHOWWINDOW)
            if repaint:
                self.force_candidate_repaint()

    def force_candidate_repaint(self):
        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            return
        try:
            hwnd = self.root.winfo_id()
            flags = self.RDW_INVALIDATE | self.RDW_ERASE | self.RDW_ALLCHILDREN | self.RDW_UPDATENOW | self.RDW_FRAME
            self.user32.RedrawWindow(hwnd, None, None, flags)
        except Exception:
            pass

    def set_candidate_x_offset(self, value):
        self.candidate_x_offset = int(float(value))
        self.store.settings["candidateXOffset"] = self.candidate_x_offset
        self.store.save_settings()
        self.refresh_candidate_window()

    def set_candidate_offset(self, value):
        self.candidate_y_offset = int(float(value))
        self.store.settings["candidateYOffset"] = self.candidate_y_offset
        self.store.save_settings()
        self.refresh_candidate_window()

    def exit_app(self):
        self.exit_code = 0
        try:
            self.root.quit()
        except tk.TclError:
            pass
        self.root.destroy()

    @staticmethod
    def schedule_ui(target, callback):
        if hasattr(target, "ui_queue"):
            target.ui_queue.put(callback)
            return
        root = getattr(target, "root", None)
        if root is not None and hasattr(root, "after"):
            root.after(0, callback)
            return
        callback()

    def drain_ui_queue(self):
        try:
            while True:
                callback = self.ui_queue.get_nowait()
                callback()
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            self.root.after(10, self.drain_ui_queue)
        except tk.TclError:
            pass

    def log_page_trace(self, event: str, **data):
        try:
            payload = {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event": event,
                "page": getattr(self, "page", None),
                "pages": getattr(self, "pages", None),
                "total": getattr(self, "total", None),
                "items": len(getattr(self, "items", []) or []),
                "manual": bool(getattr(self, "manual_lookup_active", False)),
                "query": getattr(self, "manual_lookup_query", ""),
            }
            payload.update(data)
            with self.trace_lock:
                self.page_trace_path.parent.mkdir(parents=True, exist_ok=True)
                with self.page_trace_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    @staticmethod
    def maybe_log_page_trace(target, event: str, **data):
        logger = getattr(target, "log_page_trace", None)
        if callable(logger):
            logger(event, **data)

    @staticmethod
    def call_manual_page(target, delta: int, source: str):
        try:
            return target.manual_page(delta, source=source)
        except TypeError:
            return target.manual_page(delta)

    def show(self, repaint: bool = True):
        self.render()
        if not getattr(self, "window_should_show", True):
            return
        self.refresh_candidate_window(repaint=repaint)
        hwnd = self.root.winfo_id()
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        self.user32.ShowWindow(hwnd, self.SW_SHOWNOACTIVATE)
        self.user32.SetWindowPos(hwnd, self.HWND_TOPMOST, self.root.winfo_x(), self.root.winfo_y(), 0, 0, self.SWP_NOSIZE | self.SWP_NOACTIVATE | self.SWP_SHOWWINDOW)
        if repaint:
            self.force_candidate_repaint()

    def hide(self):
        self.root.withdraw()

    def render(self):
        search_text = self.search_text()
        manual_lookup = bool(getattr(self, "manual_lookup_active", False))
        self.items, self.pages, self.total = self.store.search(search_text, self.page, self.current_view, False, "")
        # 隐身模式下敲的字母只存在候选框里（不落进 eNSP）。如果一条都没匹配上就直接
        # 把框隐藏，用户既看不见自己敲了什么、那串字也没进 eNSP，接着按回车就全丢了
        # （回车是"原样放行、不落字"）。所以"有输入但无匹配"必须保留窗口提示。
        if not self.items and (manual_lookup or not search_text.strip()):
            self.window_should_show = False
            self.hide()
            return
        if not self.items:
            self.pages = 1
            self.total = 0
        self.window_should_show = True
        if manual_lookup:
            header_text = f"◄ {self.page + 1}/{self.pages} ► 共 {self.total} | ←/- 上页 | →/= 下页 | Esc关闭"
            footer_text = f"  中文查询：{search_text}   仅查命令，不自动输入"
            hint_text = ""
        else:
            if not self.items:
                header_text = "无匹配命令 | 空格 或 Esc 把已敲的字落进 eNSP | 退格删字"
            else:
                header_text = f"◄ {self.page + 1}/{self.pages} ► 共 {self.total} | ←/- 上页 | →/= 下页 | 1-{PAGE_SIZE}选择 | Esc"
            footer_text = f"  输入：{self.buffer}   查询：{search_text}   视图：{self.current_view}   不自动回车"
            hint_text = candidate_hint_text(search_text, self.items)
        visible = self.items[:PAGE_SIZE]
        rendered_rows = []
        for item in visible:
            risk = {"low": "", "medium": "  中风险", "high": "  高风险"}.get(item["risk"], "")
            rendered_rows.append((item["insert"] or item["command"], item["description"] + risk, item["risk"]))
        max_command_px = max((self.command_font.measure(row[0]) for row in rendered_rows), default=0)
        max_description_px = max((self.description_font.measure(row[1]) for row in rendered_rows), default=0)
        layout = fit_candidate_layout(
            max_command_px,
            max_description_px,
            self.header_font.measure(header_text),
            max(self.footer_font.measure(footer_text), self.hint_font.measure(hint_text)),
            self.root.winfo_screenwidth(),
        )
        self.header.config(text=header_text, wraplength=max(300, layout["width"] - 20))
        for idx, (_, lab_i, lab_cmd, lab_desc) in enumerate(self.rows):
            if idx < len(self.items):
                command_text, description_text, risk_level = rendered_rows[idx]
                lab_i.config(text=str(idx + 1))
                lab_cmd.config(text=command_text, width=0, wraplength=layout["command_wrap"])
                lab_desc.config(text=description_text, width=0, wraplength=layout["description_wrap"], fg="#c0395e" if risk_level == "high" else "#967f8d")
            else:
                lab_i.config(text="")
                lab_cmd.config(text="", width=0, wraplength=0)
                lab_desc.config(text="", width=0, wraplength=0)
            self.rows[idx][0].grid_columnconfigure(1, minsize=layout["command_px"])
            self.rows[idx][0].grid_columnconfigure(2, minsize=layout["description_px"])
        self.footer.config(text=footer_text, wraplength=max(300, layout["width"] - 20))
        self.hint.config(text=hint_text, wraplength=max(300, layout["width"] - 20))
        self.root.update_idletasks()
        self.root.geometry(f"{layout['width']}x{self.root.winfo_reqheight()}")

    def search_text(self):
        if getattr(self, "manual_lookup_active", False):
            return self.manual_lookup_query
        return self.buffer

    def is_tail_search(self):
        return False

    def context_prefix(self):
        return ""

    def reload(self):
        self.store = CommandStore(self.root_dir)
        self.store.load()
        self.page = 0
        self.render()

    def on_manual_query_key_release(self, event):
        if getattr(event, "keysym", "") in MANUAL_NAV_KEYSYMS:
            return "break"
        if hasattr(self, "root"):
            self.root.after(80, self.show_manual_query_if_changed)
        return None

    def on_manual_query_key_press(self, event):
        keysym = getattr(event, "keysym", "")
        char = getattr(event, "char", "")
        if keysym == "Escape":
            return self.close_manual_candidates(event)
        if keysym in ("Left", "KP_Left", "minus", "KP_Subtract") or char == "-":
            return App.call_manual_page(self, -1, "manual_entry")
        if keysym in ("Right", "KP_Right", "equal", "KP_Add") or char == "=":
            return App.call_manual_page(self, 1, "manual_entry")
        return None

    def show_manual_query_if_changed(self):
        if not hasattr(self, "manual_query_var"):
            return
        query = normalize_spaces(self.manual_query_var.get())
        previous = getattr(self, "manual_query_seen_text", "")
        if query == previous:
            return
        self.manual_query_seen_text = query
        if has_chinese(query):
            self.show_manual_query(reset_page=True)
        elif not query:
            self.close_manual_candidates()

    def show_manual_query_if_chinese(self):
        if hasattr(self, "manual_query_var") and has_chinese(self.manual_query_var.get()):
            self.show_manual_query(reset_page=True)

    def show_manual_query(self, reset_page: bool = True):
        if not hasattr(self, "manual_query_var"):
            return
        query = normalize_spaces(self.manual_query_var.get())
        self.manual_query_seen_text = query
        self.manual_lookup_active = bool(query)
        self.manual_lookup_query = query
        self.buffer = ""
        self.host_buffer_len = 0
        self.ctrl_query_mode = False
        self.ctrl_virtual_len = 0
        self.ctrl_space_latched = False
        self.pending_command = ""
        self.tail_search_mode = False
        self.replace_current_token_only = False
        self.candidate_closed_by_escape = False
        if reset_page:
            self.page = 0
        if self.manual_lookup_query:
            self.show()
        else:
            self.hide()
        App.maybe_log_page_trace(self, "show_manual_query", reset_page=bool(reset_page), query=query, after_page=self.page, after_pages=self.pages)

    def start_manual_page_debug(self):
        if not hasattr(self, "manual_query_var"):
            return
        try:
            self.status.deiconify()
            self.status.lift()
            self.status.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.manual_query_var.set("d")
        self.manual_query_seen_text = ""
        self.show_manual_query(reset_page=True)
        try:
            self.manual_query_entry.focus_force()
        except tk.TclError:
            pass
        App.maybe_log_page_trace(self, "manual_page_debug_ready", query="d", page=self.page, pages=self.pages)

    def start_manual_page_auto_test(self, count: int = 15, delay_ms: int = 700):
        state = {"done": 0}
        App.maybe_log_page_trace(self, "manual_page_auto_start", count=count, delay_ms=delay_ms, page=self.page, pages=self.pages)

        def step():
            if state["done"] >= count:
                App.maybe_log_page_trace(self, "manual_page_auto_done", count=count, page=self.page, pages=self.pages)
                return
            state["done"] += 1
            before_page = self.page
            result = self.on_key(Keyboard.VK_RIGHT)
            App.maybe_log_page_trace(self, "manual_page_auto_key", step=state["done"], result=bool(result), before_page=before_page, queued_page=self.page)
            try:
                self.root.after(delay_ms, step)
            except tk.TclError:
                pass

        try:
            self.root.after(delay_ms, step)
        except tk.TclError:
            pass

    def close_manual_candidates(self, _event=None):
        App.maybe_log_page_trace(self, "close_manual_candidates", before_page=self.page)
        self.items = []
        self.manual_lookup_active = False
        self.manual_lookup_query = ""
        self.buffer = ""
        self.host_buffer_len = 0
        self.ctrl_query_mode = False
        self.ctrl_virtual_len = 0
        self.ctrl_space_latched = False
        self.pending_command = ""
        self.tail_search_mode = False
        self.candidate_closed_by_escape = True
        self.page = 0
        self.hide()
        return "break"

    def manual_page(self, delta: int, source: str = "manual"):
        if not hasattr(self, "manual_query_var"):
            App.maybe_log_page_trace(self, "manual_page_no_query_widget", source=source, delta=delta)
            return "break"
        query = normalize_spaces(self.manual_query_var.get())
        if not query:
            App.maybe_log_page_trace(self, "manual_page_empty_query", source=source, delta=delta)
            return "break"
        before_page = self.page
        before_pages = self.pages
        before_items = len(self.items)
        refreshed = False
        if (not self.items) or self.root.state() == "withdrawn" or (not getattr(self, "manual_lookup_active", False)) or query != getattr(self, "manual_lookup_query", ""):
            # 刷新时保留当前页（原来 reset_page=True 会把页码打回 0，
            # 紧接着 +delta 后永远停在第 2 页 —— 中文查命令翻不了页的根因）
            self.show_manual_query(reset_page=False)
            if self.pages > 0:
                self.page = min(before_page, self.pages - 1)
            refreshed = True
        changed = False
        if self.items and self.pages > 1:
            self.page = (self.page + delta) % self.pages
            self.show(repaint=False)
            changed = True
        App.maybe_log_page_trace(
            self,
            "manual_page",
            source=source,
            delta=delta,
            before_page=before_page,
            before_pages=before_pages,
            before_items=before_items,
            after_page=self.page,
            after_pages=self.pages,
            after_items=len(self.items),
            refreshed=refreshed,
            changed=changed,
            query=query,
        )
        return "break"

    def on_key(self, vk):
        if self.smoke_mode:
            self.smoke_events.append({"vk": int(vk), "buffer": self.buffer, "target": self.target_window_text()})
        if self.is_own_window_foreground():
            if getattr(self, "manual_lookup_active", False):
                if vk == Keyboard.VK_ESCAPE:
                    App.maybe_log_page_trace(self, "hook_manual_escape_own", vk=int(vk), before_page=self.page)
                    App.schedule_ui(self, self.close_manual_candidates)
                    return True
                page_delta = self.page_key_delta(vk)
                if page_delta:
                    App.maybe_log_page_trace(self, "hook_manual_nav_key_own", vk=int(vk), delta=page_delta, before_page=self.page)
                    App.schedule_ui(self, lambda delta=page_delta: App.call_manual_page(self, delta, "hook_own_focus"))
                    return True
            return False
        if getattr(self, "manual_lookup_active", False):
            if vk == Keyboard.VK_ESCAPE:
                App.maybe_log_page_trace(self, "hook_manual_escape_any", vk=int(vk), before_page=self.page)
                App.schedule_ui(self, self.close_manual_candidates)
                return True
            page_delta = self.page_key_delta(vk)
            if page_delta:
                App.maybe_log_page_trace(self, "hook_manual_nav_key_any", vk=int(vk), delta=page_delta, before_page=self.page)
                App.schedule_ui(self, lambda delta=page_delta: App.call_manual_page(self, delta, "hook_any_focus"))
                return True
            App.maybe_log_page_trace(self, "manual_lookup_cleared_by_non_page_key", vk=int(vk), before_page=self.page)
            self.manual_lookup_active = False
            self.manual_lookup_query = ""
            self.items = []
            self.page = 0
            App.schedule_ui(self, self.hide)
        if vk == Keyboard.VK_RETURN:
            if self.commit_in_flight:
                # 有字正在往 eNSP 送。这一下回车先扣住不放行：等字到了再替用户放行，
                # 否则 eNSP 会先执行眼前那半截命令（行里还缺后面那段字）。
                self.queued_enter = True
                return True
            entered = self.pending_command or self.buffer
            pending = self.buffer
            if entered:
                self.current_view = infer_view_after_enter(entered, self.current_view)
            self.pending_command = ""
            self.buffer = ""
            self.host_buffer_len = 0
            self.ctrl_query_mode = False
            self.ctrl_virtual_len = 0
            self.ctrl_space_latched = False
            self.candidate_closed_by_escape = False
            self.tail_search_mode = False
            self.replace_current_token_only = False
            self.invisible_input = True
            App.schedule_ui(self, self.hide)
            if pending:
                # 候选框里还有没落地的字：这一下回车只把它【写进 eNSP】，不执行
                # （跟输入法一样：回车是把字落下去，不是把命令跑起来）。
                # 要执行请再按一次回车，那次会原样放行给 eNSP。
                self.commit_buffer_to_host(pending.rstrip())
                return True
            return False
        if self.suppress_key_events > 0:
            self.suppress_key_events -= 1
            return False
        if time.time() < self.suppress_until:
            return False
        if self.ctrl_shift_pressed() and vk in (ord("O"), ord("C"), ord("R")):
            App.schedule_ui(self, lambda vk=vk: self.handle_manager_shortcut(vk))
            return True
        if vk == Keyboard.VK_F8:
            App.schedule_ui(self, self.toggle_enabled)
            return True
        if vk == Keyboard.VK_F9:
            App.schedule_ui(self, self.reload)
            return True
        if not self.enabled:
            return False
        if not self.is_target_window():
            self.buffer = ""
            self.host_buffer_len = 0
            self.ctrl_query_mode = False
            self.ctrl_virtual_len = 0
            self.ctrl_space_latched = False
            self.manual_lookup_active = False
            self.manual_lookup_query = ""
            self.candidate_closed_by_escape = False
            self.tail_search_mode = False
            self.invisible_input = True
            App.schedule_ui(self, self.hide)
            return False
        self.last_target_hwnd = self.user32.GetForegroundWindow()
        if vk == Keyboard.VK_ESCAPE:
            return self.handle_escape_key()
        if 0x31 <= vk <= 0x39 and self.number_key_should_choose_candidate():
            idx = vk - 0x31
            if idx < len(self.items):
                item = self.items[idx]
                App.schedule_ui(self, lambda item=item: self.choose(item))
                return True
        candidate_visible = bool(self.items) and bool(self.buffer) and self.root.state() != "withdrawn"
        page_delta = self.page_key_delta(vk)
        if page_delta and candidate_visible:
            App.schedule_ui(self, lambda delta=page_delta: self.candidate_page(delta))
            return True
        if vk == Keyboard.VK_BACK:
            return self.handle_backspace_key()
        ch = self.vk_to_char(vk)
        if ch is None:
            return False
        return self.handle_char_key(ch)

    def reset_query_state(self):
        self.buffer = ""
        self.host_buffer_len = 0
        self.ctrl_query_mode = False
        self.ctrl_virtual_len = 0
        self.ctrl_space_latched = False
        self.items = []
        self.page = 0
        self.pending_command = ""
        self.tail_search_mode = False
        self.replace_current_token_only = False

    def commit_buffer_to_host(self, text, tail_key=None):
        """把正在候选框里组好的内容送进 eNSP（由 UI 线程执行，保证按键顺序）。"""
        if not text and tail_key is None:
            return
        App.maybe_log_page_trace(self, "ghost_commit", text=text, tail_key=tail_key)
        self.commit_in_flight = True

        def finish():
            ok = self.type_into_host(text, tail_key)
            queued = self.queued_enter
            self.queued_enter = False
            self.commit_in_flight = False
            if ok and queued:
                # 落字期间用户按过回车（当时扣住没放行）：现在替他放行，
                # 这样 eNSP 执行到的是完整那行，而不是半截。
                self.send_key(Keyboard.VK_RETURN)

        App.schedule_ui(self, finish)

    def handle_escape_key(self):
        # Esc：把组好的词原样落进 eNSP 输入行，然后退出隐身，方便接着手改。
        # 没有在组词时保持原行为：关掉候选框，Esc 本身交给 eNSP。
        had_items = bool(self.items)
        pending = self.buffer
        self.reset_query_state()
        self.candidate_closed_by_escape = False
        self.replace_current_token_only = True
        self.invisible_input = False
        App.schedule_ui(self, self.hide)
        if pending:
            self.commit_buffer_to_host(pending)
            return True
        return had_items

    def handle_backspace_key(self):
        # 退格只改候选框里的词，绝不发给 eNSP —— 这样就不存在"删不干净"。
        if not self.buffer:
            return False
        if self.ctrl_pressed():
            self.buffer = self.buffer[:-1].rstrip()
        else:
            self.buffer = self.buffer[:-1]
        self.ctrl_virtual_len = len(self.buffer)
        self.ctrl_query_mode = bool(self.buffer)
        self.ctrl_space_latched = bool(self.buffer)
        self.page = 0
        App.schedule_ui(self, self.hide if not self.buffer else self.show)
        return True

    def handle_char_key(self, ch):
        if not self.invisible_input:
            return False
        if ch == " " and self.ctrl_pressed():
            # Ctrl+空格：往查询词里加一个空格，方便一次搜多个词。
            # 不落地、不提交（普通空格才是"提交当前词"）。
            if self.buffer and not self.buffer.endswith(" "):
                self.buffer += " "
            self.ctrl_virtual_len = len(self.buffer)
            self.ctrl_query_mode = True
            self.ctrl_space_latched = True
            self.page = 0
            self.candidate_closed_by_escape = False
            App.schedule_ui(self, self.show if self.buffer.strip() else self.hide)
            return True
        if is_query_char(ch) and self.accept_query_char(ch):
            # 隐身：这个字只进候选框，eNSP 里不出现，所以永远不需要删。
            self.buffer = (self.buffer + ch)[-48:]
            self.ctrl_virtual_len = len(self.buffer)
            self.ctrl_query_mode = True
            self.ctrl_space_latched = True
            self.page = 0
            self.candidate_closed_by_escape = False
            self.replace_current_token_only = False
            App.schedule_ui(self, self.show)
            return True
        # 空格 / ? / : / 等符号：先把组好的词落进 eNSP，再连同这个字符一起送过去，
        # 顺序才不会颠倒。没有在组词时交给 eNSP 正常处理。
        pending = self.buffer
        self.reset_query_state()
        App.schedule_ui(self, self.hide)
        if pending:
            if ch == " ":
                # 空格用真按键补：粘贴内容末尾的空格会被控制台丢掉。
                # 先 rstrip：查询词尾部可能已有 Ctrl+空格 加的空格，否则会多出一个。
                self.commit_buffer_to_host(pending.rstrip(), tail_key=0x20)
            else:
                self.commit_buffer_to_host(pending + ch)
            return True
        return False


    @staticmethod
    def page_key_delta(vk):
        if vk in (Keyboard.VK_LEFT, Keyboard.VK_OEM_MINUS):
            return -1
        if vk in (Keyboard.VK_RIGHT, Keyboard.VK_OEM_PLUS):
            return 1
        return 0

    def candidate_page(self, delta: int, source: str = "candidate"):
        before_page = self.page
        before_pages = self.pages
        if self.items and self.pages > 1:
            self.page = (self.page + delta) % self.pages
            self.show(repaint=False)
        App.maybe_log_page_trace(self, "candidate_page", source=source, delta=delta, before_page=before_page, before_pages=before_pages, after_page=self.page, after_pages=self.pages)

    def accept_query_char(self, ch: str) -> bool:
        if not ch:
            return False
        if ch.isalpha() or ("\u4e00" <= ch <= "\u9fff") or ch == "_":
            return True
        if ch.isdigit():
            return bool(self.buffer and any(c.isalpha() for c in self.buffer))
        if ch == "-":
            return bool(self.buffer)
        return False

    def vk_to_char(self, vk):
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if vk == 0x20:
            return " "
        oem_chars = {
            0xBA: ":",
            0xBB: "=",
            0xBD: "-",
            0xBE: ".",
            0xBF: "/",
            0xE2: "\\",
        }
        if vk in oem_chars:
            return oem_chars[vk]
        return None

    def number_key_should_choose_candidate(self):
        return bool(self.items) and bool(self.buffer) and not self.candidate_closed_by_escape and self.root.state() != "withdrawn"

    def handle_manager_shortcut(self, vk):
        if vk == ord("O"):
            os.startfile(str(self.root_dir))
        elif vk == ord("C"):
            os.startfile(str(self.store.commands_path))
        elif vk == ord("R"):
            self.store.usage = {}
            self.store.save_usage()
            self.page = 0
            self.render()

    def ctrl_shift_pressed(self):
        return bool((self.user32.GetAsyncKeyState(Keyboard.VK_CONTROL) & 0x8000) and (self.user32.GetAsyncKeyState(Keyboard.VK_SHIFT) & 0x8000))

    def ctrl_pressed(self):
        return bool(self.user32.GetAsyncKeyState(Keyboard.VK_CONTROL) & 0x8000)

    def typed_delete_len(self):
        virtual_len = min(len(self.buffer), max(0, int(getattr(self, "ctrl_virtual_len", 0) or 0)))
        return max(0, len(self.buffer) - virtual_len)

    def type_into_host(self, text, tail_key=None):
        # 把 text 送进 eNSP 当前光标处：优先剪贴板粘贴，失败则逐键敲。
        # tail_key 是"跟在后面"的一个按键（比如空格）：粘贴会把尾部空格吃掉，
        # 所以这类收尾字符必须用真按键补，不能塞进粘贴内容里。
        if not text and tail_key is None:
            return True
        self.suppress_key_events = 0
        target_hwnd = self.last_target_hwnd or self.user32.GetForegroundWindow()
        if not target_hwnd:
            # 没有目标窗口：字一个字都进不去。必须如实返回失败，
            # 否则调用方会以为送成功了、接着去执行——eNSP 就会执行控制台里残留的东西。
            return False
        self.user32.ShowWindow(target_hwnd, 5)
        self.user32.SetForegroundWindow(target_hwnd)
        time.sleep(0.12)
        if text:
            previous_clipboard = self.read_clipboard_text()
            clipboard_ready = self.write_clipboard_text(text)
            for _ in range(10):
                if clipboard_ready and self.read_clipboard_text() == text:
                    break
                time.sleep(0.03)
            else:
                clipboard_ready = False
            if target_hwnd:
                self.user32.SetForegroundWindow(target_hwnd)
                time.sleep(0.05)
            if clipboard_ready and self.read_clipboard_text() == text:
                self.send_ctrl_v()
            else:
                self.send_text(text)
            if previous_clipboard is not None:
                self.root.after(5000, lambda value=previous_clipboard: self.restore_clipboard_text(value))
        if tail_key is not None:
            time.sleep(0.05)
            self.send_key(tail_key)
        return True

    def choose(self, item):
        text = item["insert"] or item["command"]
        typed_token_len = self.typed_delete_len()
        self.hide()
        self.reset_query_state()
        self.invisible_input = True
        self.pending_command = text
        self.store.record_use(text)
        App.maybe_log_page_trace(self, "choose", text=text, delete_len=typed_token_len)
        if typed_token_len > 0:
            # 隐身模式下这里恒为 0（候选框里的字从没进过 eNSP）；保留兜底以防残留。
            self.send_backspaces(typed_token_len)
            time.sleep(0.05)
        self.type_into_host(text)

    def cancel_current_input(self, target_hwnd=None):
        self.hide()
        if target_hwnd:
            self.user32.ShowWindow(target_hwnd, 5)
            self.user32.SetForegroundWindow(target_hwnd)
            time.sleep(0.08)
        self.send_ctrl_u()

    def read_clipboard_text(self):
        self.configure_clipboard_api()
        if not self.user32.OpenClipboard(None):
            return None
        try:
            handle = self.user32.GetClipboardData(self.CF_UNICODETEXT)
            if not handle:
                return None
            locked = self.kernel32.GlobalLock(handle)
            if not locked:
                return None
            try:
                return ctypes.wstring_at(locked)
            finally:
                self.kernel32.GlobalUnlock(handle)
        finally:
            self.user32.CloseClipboard()

    def write_clipboard_text(self, value):
        self.configure_clipboard_api()
        data = ctypes.create_unicode_buffer(value + "\0")
        size = ctypes.sizeof(data)
        for _ in range(12):
            if self.user32.OpenClipboard(None):
                try:
                    self.user32.EmptyClipboard()
                    handle = self.kernel32.GlobalAlloc(self.GMEM_MOVEABLE, size)
                    if not handle:
                        return False
                    locked = self.kernel32.GlobalLock(handle)
                    if not locked:
                        self.kernel32.GlobalFree(handle)
                        return False
                    ctypes.memmove(locked, data, size)
                    self.kernel32.GlobalUnlock(handle)
                    if not self.user32.SetClipboardData(self.CF_UNICODETEXT, handle):
                        self.kernel32.GlobalFree(handle)
                        return False
                    return True
                finally:
                    self.user32.CloseClipboard()
            time.sleep(0.03)
        return False

    def restore_clipboard_text(self, value):
        self.write_clipboard_text(value)

    @classmethod
    def configure_clipboard_api(cls):
        cls.user32.OpenClipboard.argtypes = [wintypes.HWND]
        cls.user32.OpenClipboard.restype = wintypes.BOOL
        cls.user32.EmptyClipboard.argtypes = []
        cls.user32.EmptyClipboard.restype = wintypes.BOOL
        cls.user32.GetClipboardData.argtypes = [wintypes.UINT]
        cls.user32.GetClipboardData.restype = wintypes.HANDLE
        cls.user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        cls.user32.SetClipboardData.restype = wintypes.HANDLE
        cls.user32.CloseClipboard.argtypes = []
        cls.user32.CloseClipboard.restype = wintypes.BOOL
        cls.kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        cls.kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        cls.kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        cls.kernel32.GlobalLock.restype = ctypes.c_void_p
        cls.kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        cls.kernel32.GlobalUnlock.restype = wintypes.BOOL
        cls.kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        cls.kernel32.GlobalFree.restype = wintypes.HGLOBAL

    def position_near_foreground(self):
        hwnd = self.user32.GetForegroundWindow()
        if (not hwnd or not self.is_target_hwnd(hwnd, self.compat_mode)) and self.last_target_hwnd:
            hwnd = self.last_target_hwnd
        rect = self.RECT()
        if not hwnd or not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            self.root.geometry("+80+80")
            return
        self.root.update_idletasks()
        width = max(self.root.winfo_reqwidth(), self.root.winfo_width())
        height = max(self.root.winfo_reqheight(), self.root.winfo_height())
        prompt_x = rect.left + 18 + self.candidate_x_offset
        prompt_y = rect.bottom - 44 + self.candidate_y_offset
        space_below = rect.bottom - prompt_y
        space_above = prompt_y - rect.top
        if space_below >= height + 8:
            y = prompt_y + 8
        elif space_above >= height + 8:
            y = prompt_y - height - 8
        else:
            y = max(rect.top + 8, min(prompt_y - height // 2, rect.bottom - height - 8))
        x = min(max(prompt_x, 0), max(self.root.winfo_screenwidth() - width - 8, 0))
        self.root.geometry(f"+{x}+{max(y, 0)}")

    def make_no_activate(self, window):
        hwnd = window.winfo_id()
        style = self.user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
        self.user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, style | self.WS_EX_TOOLWINDOW | self.WS_EX_NOACTIVATE)

    def is_target_window(self):
        hwnd = self.user32.GetForegroundWindow()
        return self.is_target_hwnd(hwnd, self.compat_mode)

    def is_own_window_foreground(self):
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False
        own_hwnds = {x for x in (getattr(self, "root_hwnd", None), getattr(self, "status_hwnd", None)) if x}
        return hwnd in own_hwnds

    @staticmethod
    def is_target_hwnd(hwnd, compat=True):
        text = App.window_text(hwnd).lower()
        allow = (
            "ensp",
            "vrp",
            "huawei",
        )
        block = (APP_NAME.lower(),)
        if any(x in text for x in block):
            return False
        if any(x in text for x in allow):
            return True
        # eNSP device console windows are sometimes titled only with the device name.
        device_like = bool(re.search(r"\b(ar|lsw|sw|rt|router|switch|ne|ce|s|r)\s*-?\s*\d+\b", text, re.IGNORECASE))
        if device_like:
            return True
        if compat and ("qt" in text or "qwidget" in text):
            return bool(re.search(r"\b(console|console\d*|vrp|huawei|ar\d+|lsw\d+|s\d{3,}|r\d+)\b", text, re.IGNORECASE))
        return False

    @staticmethod
    def target_window_text():
        return App.window_text(ctypes.windll.user32.GetForegroundWindow())

    @staticmethod
    def window_text(hwnd):
        title = ctypes.create_unicode_buffer(512)
        cls = ctypes.create_unicode_buffer(256)
        if not hwnd:
            return ""
        ctypes.windll.user32.GetWindowTextW(hwnd, title, 512)
        ctypes.windll.user32.GetClassNameW(hwnd, cls, 256)
        return title.value + " " + cls.value + " " + App.window_process_path(hwnd)

    @staticmethod
    def window_process_path(hwnd):
        pid = wintypes.DWORD()
        try:
            ctypes.windll.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            ctypes.windll.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            ctypes.windll.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            ctypes.windll.kernel32.OpenProcess.restype = wintypes.HANDLE
            ctypes.windll.kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            ctypes.windll.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle.restype = wintypes.BOOL
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""
            handle = ctypes.windll.kernel32.OpenProcess(App.PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not handle:
                return ""
            try:
                size = wintypes.DWORD(1024)
                buf = ctypes.create_unicode_buffer(size.value)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    return buf.value
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return ""
        return ""

    @staticmethod
    def send_key(vk):
        scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        ctypes.windll.user32.keybd_event(vk, scan, 0, 0)
        ctypes.windll.user32.keybd_event(vk, scan, 2, 0)

    @staticmethod
    def send_ctrl_v():
        ctrl_scan = ctypes.windll.user32.MapVirtualKeyW(0x11, 0)
        v_scan = ctypes.windll.user32.MapVirtualKeyW(0x56, 0)
        ctypes.windll.user32.keybd_event(0x11, ctrl_scan, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, v_scan, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, v_scan, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, ctrl_scan, 2, 0)

    @staticmethod
    def send_ctrl_u():
        ctrl_scan = ctypes.windll.user32.MapVirtualKeyW(0x11, 0)
        u_scan = ctypes.windll.user32.MapVirtualKeyW(0x55, 0)
        ctypes.windll.user32.keybd_event(0x11, ctrl_scan, 0, 0)
        ctypes.windll.user32.keybd_event(0x55, u_scan, 0, 0)
        ctypes.windll.user32.keybd_event(0x55, u_scan, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, ctrl_scan, 2, 0)

    @staticmethod
    def send_backspaces(count: int):
        for _ in range(max(0, count)):
            App.send_key(Keyboard.VK_BACK)
            time.sleep(0.015)

    def run(self):
        self.root.mainloop()

    def smoke_type_text(self, text: str):
        for char in text:
            vk = self.vk_for_char(char)
            if vk is None:
                continue
            swallowed = self.on_key(vk)
            if not swallowed:
                self.send_key(vk)
            time.sleep(0.12)

    def smoke_press_key(self, vk: int):
        swallowed = self.on_key(vk)
        if not swallowed:
            self.send_key(vk)
        time.sleep(0.12)

    def run_hook_smoke_test(self):
        report_path = self.store.logs_dir / "hook_smoke_report.json"
        for path in self.store.logs_dir.glob("hook_smoke_result_*.txt"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            report_path.unlink()
        except FileNotFoundError:
            pass
        original_usage = json.loads(json.dumps(self.store.usage))
        self.store.usage = {}
        self.store.save_usage()
        result_path = self.store.logs_dir / "hook_smoke_result_multi.txt"
        cases = [
            {"name": "ghost_single_word", "input": "d", "target": "display", "expected": "display", "view": "user-view"},
            {"name": "ghost_three_letter_prefix", "input": "dis", "target": "display", "expected": "display", "view": "user-view"},
            {"name": "ghost_port_access", "input": "p", "target": "port link-type access", "expected": "port link-type access", "view": "interface-view"},
            {"name": "ghost_space_commit", "input": "dis", "expected": "dis", "view": "user-view",
             "steps": [{"input": "dis"}, {"input": " "}]},
            {"name": "ghost_escape_commit", "input": "dis", "expected": "dis", "view": "user-view",
             "steps": [{"input": "dis"}, {"press": 27}]},
            {"name": "ghost_multi_word", "input": "dis", "expected_prefix": "dis ", "view": "user-view",
             "steps": [{"input": "dis"}, {"input": " "}, {"input": "i", "target_prefix": "i"}]},
            {"name": "ghost_space_then_digit", "input": "dis", "expected": "dis 1", "view": "user-view",
             "steps": [{"input": "dis"}, {"input": " "}, {"press": 0x31}]},
            # 敲一条谁都匹配不到的东西：候选框必须继续显示（原来会直接隐藏，
            # 字被静默扣在 buffer 里，用户看不见、再按回车就全丢）
            {"name": "ghost_no_match_keeps_candidates", "input": "zzzz", "expected": "zzzz", "view": "user-view",
             "steps": [{"input": "zzzz", "expect_visible": True}, {"input": " "}]},
            # 回车：候选框里还有没落地的字 → 把字【写进】eNSP，但不执行（跟输入法一样）。
            # 这一下只写；最后那下由测试框架自己按的回车负责执行。
            {"name": "ghost_enter_writes_without_executing", "input": "zzzz", "expected": "zzzz", "view": "user-view",
             "steps": [{"input": "zzzz"}, {"press": 0x0D}]},
            # 连按两下回车：第二下落在"字还在路上"的窗口里，必须被扣住、等字落地再放行，
            # 否则第二下会抢在字前面被执行，控制台读到的是空行（半截都没有）。
            {"name": "ghost_enter_double_tap_keeps_order", "input": "zzzz", "expected": "zzzz", "view": "user-view",
             "steps": [{"input": "zzzz"}, {"press": 0x0D}, {"press": 0x0D}]},
        ]
        report = {"ok": False, "steps": [], "resultPath": str(result_path), "cases": []}
        proc = None
        try:
            if not self.keyboard.installed.wait(timeout=5):
                raise RuntimeError("keyboard hook install timed out")
            if not self.keyboard.hook:
                raise RuntimeError(f"keyboard hook install failed: {self.keyboard.install_error}")
            report["steps"].append("keyboard hook installed")
            for case_index, case in enumerate(cases):
                case_result_path = self.store.logs_dir / f"hook_smoke_result_{case_index}_{re.sub(r'[^A-Za-z0-9_-]+', '_', case['name'])}.txt"
                case_report = {"name": case["name"], "input": case.get("input") or [step.get("input", "") for step in case.get("steps", [])], "resultPath": str(case_result_path)}
                proc = None
                try:
                    try:
                        case_result_path.unlink()
                    except FileNotFoundError:
                        pass
                    case_literal = str(case_result_path).replace("'", "''")
                    smoke_title = f"eNSP Console Smoke {case_index}"
                    script = (
                        f"$Host.UI.RawUI.WindowTitle='{smoke_title}'; "
                        f"Remove-Item -LiteralPath '{case_literal}' -ErrorAction SilentlyContinue; "
                        "$x=Read-Host 'SMOKE'; "
                        f"Set-Content -LiteralPath '{case_literal}' -Value $x -Encoding UTF8; "
                        "exit"
                    )
                    proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    time.sleep(0.5)
                    hwnd = self.wait_for_window(smoke_title, timeout=15)
                    if not hwnd:
                        raise RuntimeError("target PowerShell window not found")
                    self.user32.ShowWindow(hwnd, 5)
                    self.user32.SetForegroundWindow(hwnd)
                    time.sleep(1.2)
                    self.current_view = case["view"]
                    self.buffer = case.get("pre_buffer", "")
                    self.items = [{"command": "interface Vlanif", "insert": "interface Vlanif"}] if case.get("pre_items") else []
                    self.candidate_closed_by_escape = bool(case.get("candidate_closed_by_escape", False))
                    self.page = 0
                    self.pending_command = ""
                    self.smoke_events = []
                    selected = []
                    steps = case.get("steps") or [{
                        "input": case["input"],
                        "target": case.get("target"),
                        "target_prefix": case.get("target_prefix"),
                    }]
                    for step in steps:
                        if step.get("press") is not None:
                            self.smoke_press_key(step["press"])
                            time.sleep(1.2)
                            continue
                        self.smoke_type_text(step["input"])
                        time.sleep(1.0)
                        if step.get("expect_visible"):
                            # 黑盒断言：真窗口、真按键之后，候选框不能是隐藏状态
                            state = self.root.state()
                            case_report["visibleAfterTyping"] = state
                            if state == "withdrawn":
                                raise RuntimeError("candidate window withdrawn while buffer=" + repr(self.buffer))
                        if not (step.get("target") or step.get("target_prefix")):
                            continue
                        target = step.get("target")
                        target_prefix = step.get("target_prefix")
                        chosen = None
                        for idx, item in enumerate(self.items[:PAGE_SIZE]):
                            command = item["command"]
                            if command == target or (target_prefix and command.startswith(target_prefix)):
                                chosen = {"index": idx + 1, "command": command, "replaceMode": item.get("replaceMode")}
                                selected.append(chosen)
                                self.smoke_press_key(0x31 + idx)
                                break
                        if not chosen:
                            raise RuntimeError("target candidate not found: " + ", ".join(item["command"] for item in self.items[:PAGE_SIZE]))
                        time.sleep(1.2)
                    # 落字是异步注入的（UI 线程做剪贴板粘贴），回车前等它做完。
                    time.sleep(1.5)
                    self.smoke_press_key(Keyboard.VK_RETURN)
                    deadline = time.time() + 8
                    lines = []
                    while time.time() < deadline:
                        if case_result_path.exists():
                            lines = case_result_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
                            if lines:
                                break
                        time.sleep(0.1)
                    if not lines:
                        raise RuntimeError("Read-Host result line was not created")
                    result = lines[0].strip()
                    with result_path.open("a", encoding="utf-8") as result_file:
                        result_file.write(result + "\n")
                    ok = result == case.get("expected") if case.get("expected") else result.startswith(case.get("expected_prefix", ""))
                    case_report.update({"ok": ok, "capturedInput": result, "selected": selected, "events": self.smoke_events[-60:]})
                    if not ok:
                        raise RuntimeError(f"unexpected result: {result!r}")
                except Exception as exc:
                    case_report["ok"] = False
                    case_report["error"] = str(exc)
                finally:
                    if proc and proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                report["cases"].append(case_report)
            report["ok"] = all(case.get("ok") for case in report["cases"])
            if not report["ok"]:
                raise RuntimeError("one or more smoke cases failed")
        except Exception as exc:
            report["error"] = str(exc)
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.store.usage = original_usage
            self.store.save_usage()
            print("PASS hook_smoke_test" if report.get("ok") else "FAIL hook_smoke_test", report_path)
            self.root.after(100, lambda: self.finish_hook_smoke_test(report.get("ok", False)))

    def finish_hook_smoke_test(self, ok: bool):
        self.exit_code = 0 if ok else 1
        self.root.destroy()

    def wait_for_window(self, title_part: str, timeout: float):
        deadline = time.time() + timeout
        needle = title_part.lower()
        while time.time() < deadline:
            found = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_proc(hwnd, _):
                if self.user32.IsWindowVisible(hwnd):
                    title = ctypes.create_unicode_buffer(512)
                    self.user32.GetWindowTextW(hwnd, title, 512)
                    if needle in title.value.lower():
                        found.append(hwnd)
                        return False
                return True

            self.user32.EnumWindows(enum_proc, 0)
            if found:
                return found[0]
            time.sleep(0.1)
        return None

    @staticmethod
    def send_text(text: str):
        for char in text:
            vk = App.vk_for_char(char)
            if vk is None:
                continue
            App.send_key(vk)
            time.sleep(0.03)

    @staticmethod
    def vk_for_char(char: str):
        if char.isalpha():
            return ord(char.upper())
        if char.isdigit():
            return ord(char)
        mapping = {
            " ": 0x20,
            ":": 0xBA,
            "-": 0xBD,
            ".": 0xBE,
            "/": 0xBF,
            "\\": 0xE2,
        }
        return mapping.get(char)


def run_self_test() -> int:
    store = CommandStore(app_dir())
    store.load()
    checks = []

    def check(name, ok, detail):
        checks.append((name, bool(ok), detail))

    interface_items, _, _ = store.search("interface", 0)
    interface_commands = {item["command"] for item in interface_items}
    check("command_count", len(store.commands) >= 4500, f"loaded={len(store.commands)}")
    check("page_size", 0 < len(interface_items) <= PAGE_SIZE == 9, f"page_items={len(interface_items)} page_size={PAGE_SIZE}")
    check("common_interface_entries", {"interface GigabitEthernet", "interface Ethernet", "interface Vlanif", "interface LoopBack", "interface range"}.issubset(interface_commands), "first_page=" + ", ".join(item["command"] for item in interface_items[:9]))
    check("self_prefix_filtered", all(item["command"] != "interface" for item in interface_items), "first_page=" + ", ".join(item["command"] for item in interface_items[:9]))
    i_items, _, _ = store.search("i", 0, "system-view")
    in_items, _, _ = store.search("in", 0, "system-view")
    i_user_items, _, _ = store.search("i", 0, "user-view")
    in_user_items, _, _ = store.search("in", 0, "user-view")
    check("short_prefix_i", bool(i_items) and all((item["insert"] or item["command"]).lower().startswith("i") for item in i_items[:PAGE_SIZE]) and any(item["command"].startswith("interface ") for item in i_items), "first_page=" + ", ".join(item["command"] for item in i_items[:9]))
    check("short_prefix_in", bool(in_items) and in_items[0]["command"].startswith("interface "), "first=" + (in_items[0]["command"] if in_items else "NONE"))
    check("short_prefix_i_no_display", bool(i_user_items) and not i_user_items[0]["command"].startswith("display "), "first=" + (i_user_items[0]["command"] if i_user_items else "NONE"))
    check("short_prefix_in_no_display", bool(in_user_items) and not in_user_items[0]["command"].startswith("display "), "first=" + (in_user_items[0]["command"] if in_user_items else "NONE"))
    dis_ip_items, _, _ = store.search("dis ip", 0, "user-view")
    ctrl_space_items, _, _ = store.search("dis i in b", 0, "user-view")
    ctrl_space_port_items, _, _ = store.search("d p p", 0, "user-view")
    dis_ip_br_items, _, _ = store.search("display ip interface br", 0, "user-view")
    br_items, _, _ = store.search("br", 0, "user-view")
    dis_items, _, _ = store.search("dis", 0, "user-view")
    sy_items, _, _ = store.search("sy", 0, "user-view")
    sy_system_items, _, _ = store.search("sy", 0, "system-view")
    sysn_items, _, _ = store.search("sysn", 0, "system-view")
    save_items, _, _ = store.search("sa", 0, "user-view")
    u_items, _, u_total = store.search("u", 0, "user-view")
    undo_terminal_items, _, _ = store.search("u t m", 0, "user-view")
    undo_terminal_full_items, _, _ = store.search("undo terminal", 0, "user-view")
    int_g_items, _, _ = store.search("int g", 0, "system-view")
    system_dash_items, _, _ = store.search("system-", 0, "user-view")
    cpu_dash_items, _, _ = store.search("cpu-", 0, "user-view")
    info_dash_items, _, _ = store.search("info-", 0, "system-view")
    user_dash_items, _, _ = store.search("user-", 0, "system-view")
    gigabit_items, _, _ = store.search("gigabitethernet", 0, "system-view")
    ip_dot_items, _, ip_dot_total = store.search("ip.", 0, "any")
    x_dot_items, _, x_dot_total = store.search("x.x", 0, "any")
    port_hybrid_items, _, _ = store.search("port hybrid", 0, "interface-view")
    ospf_br_items, _, _ = store.search("dis o br", 0, "user-view")
    rip_if_items, _, _ = store.search("dis rip in", 0, "user-view")
    auth_aaa_items, _, _ = store.search("auth aaa", 0, "user-interface-view")
    service_stelnet_items, _, _ = store.search("service-type st", 0, "system-view")
    dedup_queries = [
        ("dis", "user-view"),
        ("vlan", "any"),
        ("ospf", "any"),
        ("br", "any"),
        ("eth-trunk", "any"),
    ]
    dedup_failures = []
    for dedup_query, dedup_view in dedup_queries:
        dedup_items, _, _ = store.search(dedup_query, 0, dedup_view)
        visible = [(item["insert"] or item["command"]).lower() for item in dedup_items]
        if len(visible) != len(set(visible)):
            dedup_failures.append(dedup_query)
    active_commands = {item["command"] for item in store.commands}
    common_required_commands = {
        "display clock",
        "display version",
        "display device",
        "display startup",
        "display users",
        "display history-command",
        "display diagnostic-information",
        "display logbuffer",
        "reset saved-configuration",
        "screen-length",
        "screen-length 0 temporary",
        "idle-timeout",
        "history-command max-size",
        "authentication-mode password",
        "set authentication password",
        "user privilege level",
        "header login",
        "header shell",
        "protocol inbound all",
        "protocol inbound ssh",
        "protocol inbound telnet",
        "language-mode Chinese",
        "language-mode English",
        "rsa local-key-pair create",
        "local-user password irreversible-cipher",
        "local-user privilege level",
        "local-user service-type ssh",
        "local-user service-type telnet",
        "undo terminal monitor",
        "display cpu-usage",
        "display memory-usage",
        "display stp brief",
        "display lldp neighbor brief",
        "display trapbuffer",
        "display ntp-service status",
        "display ssh user-information",
        "display stelnet server status",
        "display telnet server status",
        "display ftp-server",
        "display ospf routing",
        "display ospf lsdb",
        "display rip route",
        "display ip pool",
        "display dhcp server ip-in-use",
        "info-center enable",
        "undo info-center enable",
        "info-center loghost",
        "debugging all",
        "undo debugging all",
        "reset counters interface",
        "reset logbuffer",
        "lldp enable",
        "undo lldp enable",
        "stp edged-port enable",
        "undo stp edged-port enable",
        "version 2",
        "rule permit",
        "rule deny",
        "nat outbound",
        "dhcp enable",
        "dhcp select global",
        "dhcp select interface",
        "ip pool",
        "gateway-list",
        "excluded-ip-address",
        "dns-list",
        "lease day",
        "dir",
        "more",
        "delete",
        "copy",
        "rename",
        "mkdir",
        "rmdir",
        "display interface GigabitEthernet",
        "display interface Ethernet",
        "display interface Vlanif",
        "interface Eth-Trunk",
        "interface NULL 0",
        "port hybrid pvid vlan",
        "port hybrid tagged vlan",
        "port hybrid untagged vlan",
        "undo port hybrid pvid vlan",
        "undo port hybrid tagged vlan",
        "undo port hybrid untagged vlan",
        "display ospf brief",
        "display ospf interface",
        "display rip interface",
        "stp root primary",
        "stp root secondary",
        "authentication-mode aaa",
        "set authentication password cipher",
        "password cipher",
        "password irreversible-cipher",
        "authentication-type password",
        "service-type stelnet",
        "service-type ssh",
        "service-type telnet",
        "undo network",
        "undo vlan batch",
    }
    missing_common_required = sorted(common_required_commands - active_commands)
    check("abbr_display_prefix", any(item["command"] == "display" for item in dis_items), "first_page=" + ", ".join(item["command"] for item in dis_items[:9]))
    check("search_visible_dedup", not dedup_failures, "failed=" + (", ".join(dedup_failures) if dedup_failures else "NONE"))
    check("abbr_display_ip", any(item["command"].startswith("display ip") for item in dis_ip_items), "first_page=" + ", ".join(item["command"] for item in dis_ip_items[:9]))
    check("ctrl_space_abbr", bool(ctrl_space_items) and ctrl_space_items[0]["command"] == "display ip interface brief", "first=" + (ctrl_space_items[0]["command"] if ctrl_space_items else "NONE"))
    check("ctrl_space_repeated_initial", bool(ctrl_space_port_items) and ctrl_space_port_items[0]["command"].startswith("display port vlan"), "first=" + (ctrl_space_port_items[0]["command"] if ctrl_space_port_items else "NONE"))
    check("brief_full_line", bool(dis_ip_br_items) and dis_ip_br_items[0]["command"] == "display ip interface brief", "first=" + (dis_ip_br_items[0]["command"] if dis_ip_br_items else "NONE"))
    check("brief_token", any(item["command"] == "brief" for item in br_items[:3]), "first_three=" + ", ".join(item["command"] for item in br_items[:3]))
    check("abbr_system_view", bool(sy_items) and sy_items[0]["command"] == "system-view", "first=" + (sy_items[0]["command"] if sy_items else "NONE"))
    check("sysname_command", any(item["command"] == "sysname" for item in sy_system_items + sysn_items), "sy_system=" + ", ".join(item["command"] for item in sy_system_items[:9]) + " sysn=" + ", ".join(item["command"] for item in sysn_items[:9]))
    check("save_command", any(item["command"] == "save" for item in save_items[:3]), "first_three=" + ", ".join(item["command"] for item in save_items[:3]))
    check("u_prefix_is_not_truncated", u_total > PAGE_SIZE and any(item["command"] == "undo terminal monitor" for item in u_items[:PAGE_SIZE]), f"total={u_total} first_page=" + ", ".join(item["command"] for item in u_items[:9]))
    check("undo_terminal_monitor_shortcut", any(item["command"] == "undo terminal monitor" for item in undo_terminal_items[:PAGE_SIZE]), "first_page=" + ", ".join(item["command"] for item in undo_terminal_items[:9]))
    check("undo_terminal_monitor_full", any(item["command"] == "undo terminal monitor" for item in undo_terminal_full_items[:PAGE_SIZE]), "first_page=" + ", ".join(item["command"] for item in undo_terminal_full_items[:9]))
    check("common_vrp_basics_present", not missing_common_required, "missing=" + (", ".join(missing_common_required) if missing_common_required else "NONE"))
    undo_meta = next((item for item in store.commands if item["command"] == "undo" and item["source"] == "built-in"), None)
    check("built_in_metadata_not_stale", bool(undo_meta) and undo_meta["view"] == "any", "undo_view=" + (undo_meta["view"] if undo_meta else "NONE"))
    check(
        "dash_is_single_token",
        any(item["insert"] == "system-view" for item in system_dash_items)
        and any(item["insert"] == "cpu-usage" for item in cpu_dash_items)
        and any(item["insert"] == "info-center" for item in info_dash_items)
        and any(item["insert"] == "user-interface" for item in user_dash_items),
        "system-=" + ", ".join(item["insert"] for item in system_dash_items[:3])
        + " cpu-=" + ", ".join(item["insert"] for item in cpu_dash_items[:3])
        + " info-=" + ", ".join(item["insert"] for item in info_dash_items[:3])
        + " user-=" + ", ".join(item["insert"] for item in user_dash_items[:3])
    )
    check("punctuated_token_search", any("GigabitEthernet" in item["insert"] for item in gigabit_items) and any(item["insert"] == "cpu-usage" for item in cpu_dash_items), "gigabit=" + ", ".join(item["insert"] for item in gigabit_items[:3]))
    check("punctuation_query_guard", ip_dot_total == 0 and x_dot_total == 0 and not ip_dot_items and not x_dot_items, f"ip.={ip_dot_total} x.x={x_dot_total}")
    check(
        "new_common_prefixes",
        {"port hybrid pvid vlan", "port hybrid tagged vlan", "port hybrid untagged vlan"}.issubset({item["command"] for item in port_hybrid_items[:PAGE_SIZE]})
        and any(item["command"] == "display ospf brief" for item in ospf_br_items[:PAGE_SIZE])
        and any(item["command"] == "display rip interface" for item in rip_if_items[:PAGE_SIZE])
        and any(item["command"] == "authentication-mode aaa" for item in auth_aaa_items[:PAGE_SIZE])
        and any(item["command"] == "service-type stelnet" for item in service_stelnet_items[:PAGE_SIZE]),
        "hybrid=" + ", ".join(item["command"] for item in port_hybrid_items[:9])
        + " ospf=" + ", ".join(item["command"] for item in ospf_br_items[:5])
        + " rip=" + ", ".join(item["command"] for item in rip_if_items[:5])
        + " auth=" + ", ".join(item["command"] for item in auth_aaa_items[:5])
        + " service=" + ", ".join(item["command"] for item in service_stelnet_items[:5])
    )
    check("abbr_interface_gigabit", bool(int_g_items) and int_g_items[0]["command"] == "interface GigabitEthernet", "first=" + (int_g_items[0]["command"] if int_g_items else "NONE"))
    reset_adp_items, _, _ = store.search("reset adp-ipv4", 0, "user-view")
    multicast_items, _, _ = store.search("multicast-suppression", 0, "interface-view")
    clear_records_items, _, _ = store.search("clear-records", 0, "any")
    igmp_proxy_items, _, _ = store.search("igmp-proxy group-policy", 0, "vlan-view")
    check("leading_choice_expansion", any(item["command"].startswith("reset adp-ipv4 l3-diag") for item in reset_adp_items) and any(item["command"].startswith("multicast-suppression") for item in multicast_items) and any(item["command"] == "clear-records" for item in clear_records_items) and any(item["command"].startswith("igmp-proxy group-policy") for item in igmp_proxy_items), "reset=" + ", ".join(item["command"] for item in reset_adp_items[:3]) + " multicast=" + ", ".join(item["command"] for item in multicast_items[:3]))
    expanded_leading_choices = []
    if store.commands_path.exists():
        for line in store.commands_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = normalize_spaces(line.replace("\ufeff", ""))
            if raw.startswith("[ undo ]"):
                continue
            expanded_leading_choices.extend(leading_choice_expansions(raw))
    missing_leading_choices = [cmd for cmd in expanded_leading_choices if clean_for_insert(cmd) not in active_commands]
    check("leading_choice_expansion_all", not missing_leading_choices, f"expanded={len(expanded_leading_choices)} missing=" + (missing_leading_choices[0] if missing_leading_choices else "NONE"))
    expected_source_variants = []
    if store.commands_path.exists():
        for line in store.commands_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = normalize_spaces(line.replace("\ufeff", ""))
            if not raw:
                continue
            if raw.startswith("[ undo ]"):
                body = normalize_spaces(raw[len("[ undo ]"):])
                for variant in choice_prefix_variants(body):
                    expected_source_variants.append(clean_for_insert(variant))
                    expected_source_variants.append(clean_for_insert("undo " + variant))
            else:
                for variant in choice_prefix_variants(raw):
                    expected_source_variants.append(clean_for_insert(variant))
    missing_source_variants = [
        cmd for cmd in dict.fromkeys(expected_source_variants)
        if cmd and cmd not in active_commands
    ]
    check(
        "source_choice_variant_coverage",
        not missing_source_variants,
        f"expected={len(dict.fromkeys(expected_source_variants))} missing="
        + ("; ".join(missing_source_variants[:5]) if missing_source_variants else "NONE")
    )
    check(
        "internal_choice_parser",
        internal_choice_expansions("duplex { half | full }") == ["duplex half", "duplex full"]
        and internal_choice_expansions("port link-type { access | hybrid | trunk }") == ["port link-type access", "port link-type hybrid", "port link-type trunk"]
        and internal_choice_expansions("display mac-address { blackhole | H-H-H } vsi STRING<1-31> [ verbose ]") == ["display mac-address blackhole vsi"],
        "duplex=" + ", ".join(internal_choice_expansions("duplex { half | full }"))
    )
    check(
        "partial_safe_choice_parser",
        internal_choice_expansions("port trunk allow-pass vlan { { INTEGER<1-4094> } [ to INTEGER<1-4094> ] | all }") == ["port trunk allow-pass vlan all"]
        and internal_choice_expansions("apply ip-address next-hop { X.X.X.X | peer-address }") == ["apply ip-address next-hop peer-address"]
        and set(internal_choice_expansions("efm loopback { start [ timeout INTEGER<0-1000> ] | stop }")) == {"efm loopback start", "efm loopback stop"},
        "port_trunk=" + ", ".join(internal_choice_expansions("port trunk allow-pass vlan { { INTEGER<1-4094> } [ to INTEGER<1-4094> ] | all }"))
    )
    check(
        "optional_group_skip_parser",
        strip_optional_groups("display ospf [ INTEGER<1-65535> ] brief") == "display ospf brief"
        and clean_for_insert(strip_optional_groups("display bgp routing-table [ statistics ] regular-expression TEXT")) == "display bgp routing-table regular-expression"
        and clean_for_insert("ip route-static X.X.X.X { X.X.X.X | INTEGER<0-32> } X.X.X.X") == "ip route-static",
        "ospf=" + strip_optional_groups("display ospf [ INTEGER<1-65535> ] brief")
    )
    choice_required = {
        "duplex half",
        "duplex full",
        "speed 10",
        "speed 100",
        "display traffic-statistics interface inbound",
        "display traffic-statistics interface outbound",
        "undo mac-address static",
        "undo mac-address blackhole",
    }
    missing_choice_required = sorted(choice_required - active_commands)
    check("internal_choice_commands_present", not missing_choice_required, "missing=" + (", ".join(missing_choice_required) if missing_choice_required else "NONE"))
    optional_required = {
        "display ospf abr-asbr",
        "display ospf bfd session",
        "display bgp routing-table regular-expression",
        "display bgp ipv6 routing-table regular-expression",
        "display ipv6 fib entry",
        "display ospfv3 lsdb external",
        "isis iih-cache",
        "traffic-filter inbound acl",
        "traffic-filter outbound acl",
    }
    missing_optional_required = sorted(optional_required - active_commands)
    check("optional_group_commands_present", not missing_optional_required, "missing=" + (", ".join(missing_optional_required) if missing_optional_required else "NONE"))
    source_choice_required = {
        "display adp-ipv6 nd-drop statistics",
        "reset adp-ipv6 fib statistics",
        "broadcast-suppression cir",
        "multicast-suppression cir",
        "clear-records",
        "restart",
        "stop",
        "display adp-ipv4 l3-diag arp",
        "reset adp-ipv4 l3-diag pingf",
        "igmp-proxy table limit",
        "igmp-snooping table limit",
        "port trunk allow-pass vlan all",
        "apply community none",
        "apply ip-address next-hop peer-address",
        "display tunnel-info all",
        "display acl ipv6 all",
        "display mac-address blackhole vsi",
        "display mpls label-table dynamic summary",
        "display mpls label-table all summary",
        "display fan verbose",
        "efm loopback stop",
        "ospf authentication-mode null",
    }
    missing_source_choice_required = sorted(source_choice_required - active_commands)
    check("source_choice_commands_present", not missing_source_choice_required, "missing=" + (", ".join(missing_source_choice_required) if missing_source_choice_required else "NONE"))
    visible_syntax_commands = [
        item for item in store.commands
        if re.search(r"[{}\[\]|*&<>]", item["command"]) or PLACEHOLDER_RE.search(item["command"])
    ]
    check("no_visible_syntax_or_placeholders", not visible_syntax_commands, "first_bad=" + (visible_syntax_commands[0]["command"] if visible_syntax_commands else "NONE"))
    leading_underscore_commands = [item for item in store.commands if (item["insert"] or item["command"]).startswith("_")]
    bad_mpls_label_commands = [
        item for item in store.commands
        if (item["insert"] or item["command"]).startswith("display mpls label table-type")
        or (item["insert"] or item["command"]).startswith("display mpls label-table table-type")
    ]
    check("no_leading_underscore_candidates", not leading_underscore_commands, "first_bad=" + (leading_underscore_commands[0]["command"] if leading_underscore_commands else "NONE"))
    check("mpls_label_table_normalized", not bad_mpls_label_commands and {"display mpls label-table dynamic summary", "display mpls label-table all summary"}.issubset(active_commands), "bad=" + (bad_mpls_label_commands[0]["command"] if bad_mpls_label_commands else "NONE"))
    iface_i_items, _, _ = store.search("i", 0, "interface-view")
    iface_ip_items, _, _ = store.search("ip add", 0, "interface-view")
    p_items, _, _ = store.search("p", 0, "interface-view")
    port_link_items, _, _ = store.search("port link-type", 0, "interface-view")
    p_commands = {item["command"] for item in p_items}
    port_link_commands = {item["command"] for item in port_link_items}
    check("interface_i_has_ip_address", any(item["command"] == "ip address" for item in iface_i_items), "first_page=" + ", ".join(item["command"] for item in iface_i_items[:9]))
    check("interface_ip_clean_prefix", bool(iface_ip_items) and iface_ip_items[0]["command"] == "ip address", "first=" + (iface_ip_items[0]["command"] if iface_ip_items else "NONE"))
    check("derived_port_prefix", any(item["command"] == "port" for item in p_items), "first_page=" + ", ".join(item["command"] for item in p_items[:9]))
    check("port_link_type_shortcuts", {"port link-type access", "port link-type trunk", "port link-type hybrid"}.issubset(p_commands), "first_page=" + ", ".join(item["command"] for item in p_items[:9]))
    check("port_link_type_order", {"port link-type access", "port link-type trunk", "port link-type hybrid"}.issubset(port_link_commands), "first_page=" + ", ".join(item["command"] for item in port_link_items[:9]))
    original_usage = json.loads(json.dumps(store.usage))
    store.usage = {
        "port link-type access": {"usageCount": 2, "lastUsed": 1},
        "port link-type trunk": {"usageCount": 4, "lastUsed": 1},
        "port link-type hybrid": {"usageCount": 3, "lastUsed": 1},
    }
    used_p_items, _, _ = store.search("p", 0, "interface-view")
    check("usage_count_ranking", [item["command"] for item in used_p_items[:3]] == ["port link-type trunk", "port link-type hybrid", "port link-type access"], "first_three=" + ", ".join(item["command"] for item in used_p_items[:3]))
    store.usage = original_usage
    check("usage_file_root", store.usage_path == store.root / "daima.txt", str(store.usage_path))
    undo_items, _, undo_total = store.search("undo cfm enable", 0)
    check("undo_expansion", any(item["command"] == "undo cfm enable" for item in undo_items), f"matches={undo_total}")
    zh_items, _, zh_total = store.search("接口", 0)
    check("chinese_description_search", zh_total > 0 and any("接口" in item["description"] for item in zh_items), f"matches={zh_total}")
    zh_route_items, _, zh_route_total = store.search("查看路由", 0, "user-view")
    zh_route_hint = candidate_hint_text("查看路由", zh_route_items)
    check(
        "chinese_route_hint_outputs_code_only",
        bool(zh_route_items)
        and zh_route_items[0]["command"] == "display ip routing-table"
        and zh_route_hint.strip().startswith("display ip routing-table")
        and "查看" not in zh_route_hint
        and "→" not in zh_route_hint,
        f"matches={zh_route_total} first=" + (zh_route_items[0]["command"] if zh_route_items else "NONE") + " hint=" + zh_route_hint
    )
    dis_hint = candidate_hint_text("dis", dis_items)
    check(
        "english_query_hint_outputs_code_only",
        dis_hint.strip().startswith("display")
        and "查看" not in dis_hint
        and "→" not in dis_hint,
        "hint=" + dis_hint
    )
    weak_descriptions = [
        item for item in store.commands
        if description_is_weak(item["description"])
        or item["description"] in {"配置命令功能", "命令功能"}
        or item["description"].endswith("命令功能")
    ]
    check("no_generic_descriptions", not weak_descriptions, "first_bad=" + (weak_descriptions[0]["command"] + "=>" + weak_descriptions[0]["description"] if weak_descriptions else "NONE"))
    wrong_undo_descriptions = [
        item for item in store.commands
        if not item["command"].startswith("undo ") and item["description"].startswith("撤销或恢复缺省：")
    ]
    check("no_undo_description_on_normal_commands", not wrong_undo_descriptions, "first_bad=" + (wrong_undo_descriptions[0]["command"] + "=>" + wrong_undo_descriptions[0]["description"] if wrong_undo_descriptions else "NONE"))
    sample_items = {}
    for item in store.commands:
        existing = sample_items.get(item["command"])
        if existing is None or (existing["source"].startswith("token") and not item["source"].startswith("token")):
            sample_items[item["command"]] = item
    sample_desc = {cmd: item["description"] for cmd, item in sample_items.items()}
    check(
        "expanded_description_sanity",
        "ABR/ASBR" in sample_desc.get("display ospf abr-asbr", "")
        and sample_desc.get("isis iih-cache", "").startswith("配置")
        and sample_desc.get("traffic-filter inbound acl", "").startswith("配置"),
        "ospf=" + sample_desc.get("display ospf abr-asbr", "NONE")
        + " isis=" + sample_desc.get("isis iih-cache", "NONE")
        + " traffic=" + sample_desc.get("traffic-filter inbound acl", "NONE")
    )
    check(
        "debug_description_detail",
        sample_desc.get("debugging acl event") == "开启调试：ACL 事件"
        and sample_desc.get("undo debugging acl event") == "关闭调试：ACL 事件"
        and sample_desc.get("debugging bgp update-peer-group all") == "开启调试：BGP 更新对等体组 全部"
        and sample_desc.get("undo debugging bgp update-peer-group all") == "关闭调试：BGP 更新对等体组 全部",
        "debug=" + sample_desc.get("debugging acl event", "NONE")
        + " undo=" + sample_desc.get("undo debugging acl event", "NONE")
        + " bgp=" + sample_desc.get("debugging bgp update-peer-group all", "NONE")
    )
    completion_label_descriptions = [item for item in store.commands if item["description"].startswith(("补全：", "补全词："))]
    check("no_completion_label_descriptions", not completion_label_descriptions, "first_bad=" + (completion_label_descriptions[0]["command"] + "=>" + completion_label_descriptions[0]["description"] if completion_label_descriptions else "NONE"))
    untranslated_descriptions = [item for item in store.commands if description_has_untranslated_ascii(item["description"])]
    check("no_untranslated_ascii_descriptions", not untranslated_descriptions, "first_bad=" + (untranslated_descriptions[0]["command"] + "=>" + untranslated_descriptions[0]["description"] if untranslated_descriptions else "NONE"))
    stuck_descriptions = [item for item in store.commands if re.search(r"[\u4e00-\u9fff][A-Za-z]|[A-Za-z][\u4e00-\u9fff]", item["description"])]
    check("description_spacing", not stuck_descriptions, "first_bad=" + (stuck_descriptions[0]["command"] + "=>" + stuck_descriptions[0]["description"] if stuck_descriptions else "NONE"))
    view_items, _, view_total = store.search("ospf e", 0, "interface-view")
    check("view_aware_ranking", bool(view_items) and view_items[0]["command"].startswith("ospf enable"), "first=" + (view_items[0]["command"] if view_items else "NONE") + f" matches={view_total}")
    check("view_state_transitions", infer_view_after_enter("system-view", "user-view") == "system-view" and infer_view_after_enter("interface GigabitEthernet", "system-view") == "interface-view" and infer_view_after_enter("quit", "interface-view") == "system-view" and infer_view_after_enter("return", "interface-view") == "user-view", "ok")
    visible_stub = type("T", (), {"items": [object()], "buffer": "x", "candidate_closed_by_escape": False, "root": type("R", (), {"state": lambda self: "normal"})()})()
    hidden_stub = type("T", (), {"items": [object()], "buffer": "", "candidate_closed_by_escape": False, "root": type("R", (), {"state": lambda self: "withdrawn"})()})()
    check("number_candidate_policy", App.number_key_should_choose_candidate(visible_stub) and not App.number_key_should_choose_candidate(hidden_stub), "digits choose only while candidate is visible")
    check(
        "page_key_policy",
        App.page_key_delta(Keyboard.VK_LEFT) == -1
        and App.page_key_delta(Keyboard.VK_OEM_MINUS) == -1
        and App.page_key_delta(Keyboard.VK_RIGHT) == 1
        and App.page_key_delta(Keyboard.VK_OEM_PLUS) == 1,
        "minus is previous page; equal is next page"
    )
    manual_stub = type("T", (), {
        "manual_query_var": type("V", (), {"get": lambda self: "查看路由"})(),
        "items": [object()],
        "root": type("R", (), {"state": lambda self: "normal"})(),
        "pages": 4,
        "page": 0,
        "manual_lookup_active": True,
        "manual_lookup_query": "查看路由",
        "show": lambda self, repaint=True: None,
        "show_manual_query": lambda self: None,
    })()
    manual_result = App.manual_page(manual_stub, 1)
    manual_result_2 = App.manual_page(manual_stub, -1)
    check("manual_query_page_keys", manual_result == "break" and manual_result_2 == "break" and manual_stub.page == 0, f"page={manual_stub.page} result={manual_result}/{manual_result_2}")
    manual_keypress_stub = type("T", (), {
        "deltas": [],
        "closed": False,
        "manual_page": lambda self, delta: (self.deltas.append(delta) or "break"),
        "close_manual_candidates": lambda self, event=None: (setattr(self, "closed", True) or "break"),
    })()
    equal_press = App.on_manual_query_key_press(manual_keypress_stub, type("E", (), {"keysym": "equal", "char": "="})())
    minus_press = App.on_manual_query_key_press(manual_keypress_stub, type("E", (), {"keysym": "minus", "char": "-"})())
    escape_press = App.on_manual_query_key_press(manual_keypress_stub, type("E", (), {"keysym": "Escape", "char": "\x1b"})())
    check(
        "manual_query_keypress_pages_not_text",
        equal_press == "break" and minus_press == "break" and escape_press == "break" and manual_keypress_stub.deltas == [1, -1] and manual_keypress_stub.closed,
        f"equal={equal_press} minus={minus_press} escape={escape_press} deltas={manual_keypress_stub.deltas} closed={manual_keypress_stub.closed}"
    )
    manual_close_stub = type("T", (), {
        "items": [object()],
        "buffer": "查看路由",
        "manual_lookup_active": True,
        "manual_lookup_query": "查看路由",
        "host_buffer_len": 0,
        "ctrl_query_mode": False,
        "ctrl_virtual_len": 0,
        "ctrl_space_latched": False,
        "pending_command": "",
        "tail_search_mode": False,
        "candidate_closed_by_escape": False,
        "page": 2,
        "manual_query_var": type("V", (), {"get": lambda self: "查看路由"})(),
        "hide": lambda self: setattr(self, "hidden", True),
        "hidden": False,
    })()
    manual_close_result = App.close_manual_candidates(manual_close_stub)
    check(
        "manual_query_escape_closes_candidates",
        manual_close_result == "break"
        and not manual_close_stub.items
        and manual_close_stub.buffer == ""
        and manual_close_stub.manual_query_var.get() == "查看路由"
        and manual_close_stub.hidden,
        f"result={manual_close_result} buffer={manual_close_stub.buffer} hidden={manual_close_stub.hidden}"
    )

    # 有输入却一条都没匹配上时，候选框绝不能隐藏：隐身模式下敲的字只存在框里，
    # 框一消失用户既看不见、字也没进 eNSP，接着按回车就全丢了。
    class _StubLabel:
        def config(self, **kwargs):
            pass

    class _StubFrame:
        def grid_columnconfigure(self, *args, **kwargs):
            pass

    class _StubFont:
        def measure(self, text):
            return len(str(text)) * 7

    class _StubRoot:
        def __init__(self):
            self.withdrawn = False

        def withdraw(self):
            self.withdrawn = True

        def winfo_screenwidth(self):
            return 1920

        def winfo_reqheight(self):
            return 200

        def update_idletasks(self):
            pass

        def geometry(self, spec):
            pass

    def _make_render_stub(buffer, matches):
        root = _StubRoot()
        stub = type("T", (), {
            "root": root,
            "store": type("S", (), {"search": lambda s, *a: (matches, 1, len(matches))})(),
            "search_text": lambda s: buffer,
            "buffer": buffer,
            "page": 0,
            "pages": 1,
            "total": 0,
            "current_view": "any",
            "items": list(matches),
            "manual_lookup_active": False,
            "command_font": _StubFont(),
            "description_font": _StubFont(),
            "header_font": _StubFont(),
            "footer_font": _StubFont(),
            "hint_font": _StubFont(),
            "rows": [(_StubFrame(), _StubLabel(), _StubLabel(), _StubLabel()) for _ in range(PAGE_SIZE)],
            "header": _StubLabel(),
            "footer": _StubLabel(),
            "hint": _StubLabel(),
            "hidden": False,
            "hide": lambda s: (setattr(s, "hidden", True), root.withdraw()),
        })()
        return root, stub

    _root_a, _stub_a = _make_render_stub("zzzz", [])
    App.render(_stub_a)
    check(
        "no_match_with_input_keeps_window",
        _stub_a.hidden is False and getattr(_stub_a, "window_should_show", False) and _root_a.withdrawn is False,
        f"hidden={_stub_a.hidden} show={getattr(_stub_a, 'window_should_show', None)} withdrawn={_root_a.withdrawn}",
    )

    _root_b, _stub_b = _make_render_stub("", [])
    App.render(_stub_b)
    check(
        "no_match_without_input_hides_window",
        _stub_b.hidden is True and _root_b.withdrawn is True,
        f"hidden={_stub_b.hidden} withdrawn={_root_b.withdrawn}",
    )

    # 回车的行为：候选框里还有没落地的字 → 只"写进 eNSP"，不执行（跟输入法一样）；
    # 落字期间按下的回车要先扣住，等字落地再放行；没有未落地的字 → 原样放行。
    def _make_enter_stub(buffer="", commit_in_flight=False):
        calls = {}

        def _commit(self, text, tail_key=None):
            calls["committed"] = (text, tail_key)

        stub = type("T", (), {
            "smoke_mode": False,
            "is_own_window_foreground": lambda s: False,
            "manual_lookup_active": False,
            "commit_in_flight": commit_in_flight,
            "queued_enter": False,
            "pending_command": "",
            "buffer": buffer,
            "current_view": "user-view",
            "host_buffer_len": 0,
            "ctrl_query_mode": False,
            "ctrl_virtual_len": 0,
            "ctrl_space_latched": False,
            "candidate_closed_by_escape": False,
            "tail_search_mode": False,
            "replace_current_token_only": False,
            "invisible_input": False,
            "items": [],
            "page": 0,
            "hide": lambda s: None,
            "commit_buffer_to_host": _commit,
        })()
        return stub, calls

    _s1, _c1 = _make_enter_stub(buffer="R1")
    _r1 = App.on_key(_s1, Keyboard.VK_RETURN)
    check(
        "enter_with_pending_writes_without_executing",
        _r1 is True and _s1.buffer == "" and _c1.get("committed") == ("R1", None),
        f"result={_r1} buffer={_s1.buffer!r} committed={_c1.get('committed')}",
    )

    _s2, _c2 = _make_enter_stub(buffer="R1", commit_in_flight=True)
    _r2 = App.on_key(_s2, Keyboard.VK_RETURN)
    check(
        "enter_during_commit_is_held_back",
        _r2 is True and _s2.queued_enter is True and not _c2,
        f"result={_r2} queued={_s2.queued_enter} committed={_c2}",
    )

    _s3, _c3 = _make_enter_stub(buffer="")
    _r3 = App.on_key(_s3, Keyboard.VK_RETURN)
    check(
        "enter_without_pending_passes_through",
        _r3 is False and not _c3,
        f"result={_r3} committed={_c3}",
    )

    manual_release_stub = type("T", (), {
        "root": type("R", (), {"after": lambda self, delay, cb: cb()})(),
        "manual_query_var": type("V", (), {"get": lambda self: "查看路由"})(),
        "manual_query_seen_text": "查看路由",
        "called": 0,
        "show_manual_query": lambda self, reset_page=True: setattr(self, "called", self.called + 1),
        "show_manual_query_if_changed": lambda self: App.show_manual_query_if_changed(self),
    })()
    nav_event = type("E", (), {"keysym": "Right"})()
    text_event = type("E", (), {"keysym": "a"})()
    nav_release = App.on_manual_query_key_release(manual_release_stub, nav_event)
    text_release = App.on_manual_query_key_release(manual_release_stub, text_event)
    check("manual_query_release_does_not_reset_page", nav_release == "break" and text_release is None and manual_release_stub.called == 0, f"nav={nav_release} text={text_release} called={manual_release_stub.called}")
    own_window_stub = type("T", (), {
        "smoke_mode": False,
        "is_own_window_foreground": lambda self: True,
        "items": [object()],
        "buffer": "查看路由",
        "page": 1,
    })()
    own_window_result = App.on_key(own_window_stub, Keyboard.VK_RIGHT)
    check(
        "own_window_hook_does_not_clear_manual_candidates",
        own_window_result is False and own_window_stub.items and own_window_stub.buffer == "查看路由" and own_window_stub.page == 1,
        f"result={own_window_result} page={own_window_stub.page} buffer={own_window_stub.buffer} items={len(own_window_stub.items)}"
    )
    own_manual_stub = type("T", (), {
        "smoke_mode": False,
        "is_own_window_foreground": lambda self: True,
        "manual_lookup_active": True,
        "items": [object()],
        "pages": 248,
        "page": 0,
        "shown": 0,
        "root": type("R", (), {"after": lambda self, delay, cb: cb()})(),
        "show": lambda self, repaint=True: setattr(self, "shown", self.shown + 1),
        "manual_page": lambda self, delta: (setattr(self, "page", (self.page + delta) % self.pages), setattr(self, "shown", self.shown + 1), "break")[-1],
        "page_key_delta": staticmethod(App.page_key_delta),
    })()
    own_manual_r1 = App.on_key(own_manual_stub, Keyboard.VK_RIGHT)
    own_manual_r2 = App.on_key(own_manual_stub, Keyboard.VK_RIGHT)
    own_manual_l1 = App.on_key(own_manual_stub, Keyboard.VK_LEFT)
    check(
        "own_window_manual_lookup_repeated_page_keys",
        own_manual_r1 is True and own_manual_r2 is True and own_manual_l1 is True and own_manual_stub.page == 1 and own_manual_stub.shown == 3,
        f"r={own_manual_r1}/{own_manual_r2}/{own_manual_l1} page={own_manual_stub.page} shown={own_manual_stub.shown}"
    )
    own_manual_refresh_gap_stub = type("T", (), {
        "smoke_mode": False,
        "is_own_window_foreground": lambda self: True,
        "manual_lookup_active": True,
        "items": [],
        "pages": 1,
        "page": 1,
        "deltas": [],
        "root": type("R", (), {"after": lambda self, delay, cb: cb()})(),
        "manual_page": lambda self, delta: (self.deltas.append(delta) or "break"),
        "page_key_delta": staticmethod(App.page_key_delta),
    })()
    own_manual_refresh_gap = App.on_key(own_manual_refresh_gap_stub, Keyboard.VK_RIGHT)
    check(
        "own_window_manual_lookup_pages_during_refresh_gap",
        own_manual_refresh_gap is True and own_manual_refresh_gap_stub.deltas == [1],
        f"result={own_manual_refresh_gap} deltas={own_manual_refresh_gap_stub.deltas}"
    )
    empty_query_stub = type("T", (), {"buffer": ""})()
    ip_query_stub = type("T", (), {"buffer": "ipv"})()
    mac_query_stub = type("T", (), {"buffer": "mac"})()
    check(
        "query_buffer_char_policy",
        App.accept_query_char(empty_query_stub, "d")
        and not App.accept_query_char(empty_query_stub, "1")
        and not App.accept_query_char(empty_query_stub, ".")
        and not App.accept_query_char(empty_query_stub, "/")
        and not App.accept_query_char(empty_query_stub, "-")
        and App.accept_query_char(ip_query_stub, "6")
        and App.accept_query_char(mac_query_stub, "-")
        and not App.accept_query_char(mac_query_stub, "."),
        "digits/punctuation do not start IME buffer; command suffix chars still work after letters"
    )
    normal_delete_stub = type("T", (), {"ctrl_query_mode": False, "ctrl_virtual_len": 0, "buffer": "s"})()
    ctrl_delete_stub = type("T", (), {"ctrl_query_mode": True, "ctrl_virtual_len": len("dis i in b"), "buffer": "dis i in b"})()
    mixed_ctrl_delete_stub = type("T", (), {"ctrl_query_mode": True, "ctrl_virtual_len": len(" i"), "buffer": "d i"})()
    latched_ctrl_delete_stub = type("T", (), {"ctrl_query_mode": True, "ctrl_virtual_len": len(" p p"), "buffer": "d p p"})()
    check("choose_delete_len_normal", App.typed_delete_len(normal_delete_stub) == 1, f"delete_len={App.typed_delete_len(normal_delete_stub)}")
    check("choose_delete_len_ctrl", App.typed_delete_len(ctrl_delete_stub) == 0, f"delete_len={App.typed_delete_len(ctrl_delete_stub)}")
    check("choose_delete_len_mixed_ctrl", App.typed_delete_len(mixed_ctrl_delete_stub) == 1, f"delete_len={App.typed_delete_len(mixed_ctrl_delete_stub)}")
    check("choose_delete_len_latched_ctrl_space", App.typed_delete_len(latched_ctrl_delete_stub) == 1, f"delete_len={App.typed_delete_len(latched_ctrl_delete_stub)}")
    bad_items, _, bad_total = store.search("??", 0)
    check("mojibake_query_guard", bad_total == 0 and not bad_items, f"matches={bad_total}")
    check(
        "insert_prefix_cleanup",
        clean_for_insert("display vlan INTEGER<1-4094> [ statistics | verbose ]") == "display vlan"
        and clean_for_insert("ospf [ INTEGER<1-65535> | router-id X.X.X.X ] *") == "ospf"
        and clean_for_insert("mac-address H-H-H vlan INTEGER<1-4094>") == "mac-address"
        and clean_for_insert("description TEXT") == "description",
        "display_vlan=" + clean_for_insert("display vlan INTEGER<1-4094> [ statistics | verbose ]")
        + " mac=" + clean_for_insert("mac-address H-H-H vlan INTEGER<1-4094>")
        + " desc=" + clean_for_insert("description TEXT")
    )
    check("candidate_opacity_clamp", clamp_candidate_opacity(0.1) == MIN_CANDIDATE_OPACITY and clamp_candidate_opacity(0.37) == 0.37 and clamp_candidate_opacity(1.2) == 1.0, f"min={MIN_CANDIDATE_OPACITY}")
    base_layout = fit_candidate_layout(280, 220, 360, 380, 1600)
    wide_layout = fit_candidate_layout(620, 320, 360, 380, 1600)
    tight_layout = fit_candidate_layout(900, 900, 360, 380, 800)
    check(
        "candidate_width_follows_text",
        base_layout["width"] == CANDIDATE_BASE_WIDTH_PX
        and wide_layout["width"] == CANDIDATE_MAX_WIDTH_PX
        and wide_layout["command_px"] == 638
        and wide_layout["description_px"] == 338
        and wide_layout["command_wrap"] == 0
        and wide_layout["description_wrap"] == 0
        and tight_layout["width"] <= 800 - CANDIDATE_SCREEN_MARGIN_PX,
        f"base={base_layout} wide={wide_layout} tight={tight_layout}"
    )
    check("portable_paths", store.data_dir.exists() and store.rules_dir.exists() and store.logs_dir.exists(), "data/rules/logs ok")
    check("ime_buffer_model", App.search_text(type("T", (), {"buffer": "dis"})()) == "dis" and not App.is_tail_search(type("T", (), {"tail_search_mode": False, "buffer": "display ip"})()), "space/esc clear IME buffer; host text untouched")
    check("query_char_set", all(is_query_char(ch) for ch in "-_./:") and not is_query_char("="), "query chars keep command punctuation")

    failed = [item for item in checks if not item[1]]
    report = {"ok": not failed, "checkedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks]}
    report_path = store.logs_dir / "self_test_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, ok, detail in checks:
        print(("PASS" if ok else "FAIL"), name, detail)
    print("REPORT", report_path)
    return 1 if failed else 0


def run_paging_smoke_test() -> int:
    app = App(hook_smoke_test=False, start_keyboard=False)
    report_path = app.store.logs_dir / "paging_smoke_report.json"
    report = {"ok": False, "checkedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": []}

    def check(name: str, ok: bool, detail: str):
        report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    def event(keysym: str, char: str = ""):
        return type("ManualKeyEvent", (), {"keysym": keysym, "char": char})()

    def sync_ui():
        app.drain_ui_queue()
        app.root.update_idletasks()
        app.root.update()

    def run_steps():
        original_is_own = app.is_own_window_foreground
        try:
            app.manual_query_var.set("d")
            app.show_manual_query(reset_page=True)
            sync_ui()
            check("manual_query_has_many_pages", app.total > PAGE_SIZE * 3 and app.pages > 3, f"total={app.total} pages={app.pages}")

            widget_results = []
            widget_pages = [app.page]
            for keysym, char in (("Right", ""), ("Right", ""), ("Left", ""), ("equal", "="), ("minus", "-")):
                widget_results.append(app.on_manual_query_key_press(event(keysym, char)))
                sync_ui()
                widget_pages.append(app.page)
            check(
                "manual_entry_page_keys",
                widget_pages == [0, 1, 2, 1, 2, 1] and all(result == "break" for result in widget_results),
                f"pages={widget_pages} results={widget_results}",
            )

            app.show_manual_query(reset_page=True)
            sync_ui()
            app.is_own_window_foreground = lambda: True
            hook_results = []
            hook_pages = [app.page]
            for vk in (Keyboard.VK_RIGHT, Keyboard.VK_RIGHT, Keyboard.VK_LEFT, Keyboard.VK_OEM_PLUS, Keyboard.VK_OEM_MINUS):
                hook_results.append(app.on_key(vk))
                sync_ui()
                hook_pages.append(app.page)
            check(
                "manual_own_window_page_keys",
                hook_pages == [0, 1, 2, 1, 2, 1] and all(result is True for result in hook_results),
                f"pages={hook_pages} results={hook_results}",
            )

            app.show_manual_query(reset_page=True)
            sync_ui()
            app.items = []
            app.pages = 1
            app.page = 0
            refresh_gap_result = app.on_key(Keyboard.VK_RIGHT)
            sync_ui()
            check(
                "manual_own_window_page_key_during_refresh_gap",
                refresh_gap_result is True and app.page == 1 and app.pages > 1 and bool(app.items),
                f"result={refresh_gap_result} page={app.page} pages={app.pages} items={len(app.items)}",
            )

            # 回归：翻到第 3 页后，列表变"过期"再翻页，页码必须继续往前走，
            # 不能被重置回第 1 页（中文查命令"一直卡第二页"的根因）
            app.show_manual_query(reset_page=True)
            sync_ui()
            app.on_manual_query_key_press(event("Right", ""))
            sync_ui()
            app.on_manual_query_key_press(event("Right", ""))
            sync_ui()
            before_stale = app.page
            app.items = []
            app.pages = 1
            app.on_manual_query_key_press(event("Right", ""))
            sync_ui()
            check(
                "manual_page_continues_after_stale_refresh",
                before_stale == 2 and app.page == 3 and app.pages > 3,
                f"before={before_stale} after={app.page} pages={app.pages}",
            )

            app.is_own_window_foreground = original_is_own
            app.show_manual_query(reset_page=True)
            sync_ui()
            escape_result = app.on_manual_query_key_press(event("Escape", ""))
            sync_ui()
            check(
                "manual_escape_closes_candidates",
                escape_result == "break" and app.root.state() == "withdrawn" and not app.manual_lookup_active,
                f"result={escape_result} state={app.root.state()} active={app.manual_lookup_active}",
            )
        except Exception as exc:
            check("paging_smoke_exception", False, repr(exc))
        finally:
            app.is_own_window_foreground = original_is_own
            failed = [item for item in report["checks"] if not item["ok"]]
            report["ok"] = not failed
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            for item in report["checks"]:
                print(("PASS" if item["ok"] else "FAIL"), item["name"], item["detail"])
            print("REPORT", report_path)
            app.exit_code = 0 if report["ok"] else 1
            app.exit_app()

    app.root.after(500, run_steps)
    app.run()
    return app.exit_code


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(run_self_test())
    if "--paging-smoke-test" in sys.argv:
        raise SystemExit(run_paging_smoke_test())
    if not acquire_single_instance():
        raise SystemExit(0)
    if "--hook-smoke-test" not in sys.argv:
        close_other_helper_instances()
    manual_page_debug = "--manual-page-debug" in sys.argv
    app = App(hook_smoke_test="--hook-smoke-test" in sys.argv, accept_injected_keys=manual_page_debug)
    if manual_page_debug:
        app.root.after(500, app.start_manual_page_debug)
    if "--manual-page-auto-test" in sys.argv:
        app.root.after(1400, lambda: app.start_manual_page_auto_test(count=15, delay_ms=700))
    app.run()
    raise SystemExit(app.exit_code)
