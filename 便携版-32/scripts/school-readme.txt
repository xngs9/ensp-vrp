学校电脑使用顺序：

1. 先双击 start-school-normal.bat，或直接运行 ensp-vrp-ime-helper-school.exe。
2. 如果 eNSP 是用管理员方式打开的，再改用 start-school-admin.bat。
3. 打开助手控制窗口后，看两行状态：
   - 键盘钩子：正常，表示能监听键盘。
   - 前台窗口：已识别，表示当前 eNSP Console 被助手识别。
4. 如果“键盘钩子：失败”，通常是学校电脑安全策略拦截，需要换管理员启动或让机房软件放行。
5. 如果“前台窗口：未识别”，点开 eNSP 的设备 Console，再看这行是否变成已识别。

老版本没有删除，仍在原来的 ensp-vrp-ime-helper-portable 目录。
