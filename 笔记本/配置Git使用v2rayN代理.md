# V2RayN端口配置与Git代理设置指南

V2RayN默认提供**SOCKS5端口(10808)**和**HTTP端口(10809)**，你需要先确认/修改这些端口，再配置Git使用它们，就能解决GitHub连接超时问题。

---

### 一、查看V2RayN当前端口（关键第一步）
1. 打开V2RayN，在主界面点击顶部**设置**按钮（齿轮图标）
2. 切换到**入站设置**选项卡
3. 查看以下两个核心端口：
   - **SOCKS5端口**：默认`10808`（用于Git的socks5代理）
   - **HTTP端口**：默认`10809`（用于Git的http/https代理）
   - 记下这两个端口号（后续Git配置会用到）

### 二、修改V2RayN端口（如需）
如果默认端口被占用或想自定义：
1. 在**入站设置**选项卡中，修改**SOCKS5端口**（如改为`7890`）
2. HTTP端口会**自动设为SOCKS5端口+1**（如`7891`），无需手动改
3. 点击**保存**，然后重启V2RayN使修改生效
4. ⚠️ 确保新端口未被其他程序占用（可用`netstat -ano | findstr "端口号"`检查）

### 三、开启V2RayN代理功能（必须）
1. 在V2RayN主界面：
   - 右键选择一个可用节点 → **设为活动服务器**
   - 点击底部**系统代理** → 选择**自动配置系统代理**（或PAC模式）
2. 验证代理是否正常工作：
   - 打开浏览器访问`https://github.com`，能正常打开说明代理生效
   - 或在命令行执行：`curl -x http://127.0.0.1:10809 https://github.com`，有返回内容则代理正常

---

### 四、配置Git使用V2RayN代理（解决443超时核心步骤）
根据V2RayN端口，选择以下任一方式配置Git代理：

#### 方案A：使用SOCKS5代理（推荐，更稳定）
```bash
# 配置全局Git使用SOCKS5代理（端口改为你的V2RayN SOCKS5端口）
git config --global http.proxy socks5://127.0.0.1:10808
git config --global https.proxy socks5://127.0.0.1:10808

# 验证配置是否生效
git config --global --get http.proxy
git config --global --get https.proxy
```

#### 方案B：使用HTTP代理
```bash
# 配置全局Git使用HTTP代理（端口改为你的V2RayN HTTP端口）
git config --global http.proxy http://127.0.0.1:10809
git config --global https.proxy http://127.0.0.1:10809
```

#### 方案C：临时使用代理（不修改全局配置）
```bash
# 仅当前命令行窗口生效
set http_proxy=http://127.0.0.1:10809
set https_proxy=http://127.0.0.1:10809
```

---

### 五、测试Git连接（验证是否成功）
```bash
# 测试GitHub连接
git push origin master

# 或用curl测试代理是否正常
curl -x socks5://127.0.0.1:10808 https://github.com
```

---

### 六、常见问题与解决
| 问题 | 解决方法 |
|------|----------|
| V2RayN启动失败 | 检查端口是否被占用，修改为未使用的端口（如7890） |
| Git仍连接超时 | 1. 确认V2RayN节点已激活<br>2. 确认系统代理已开启<br>3. 检查防火墙是否放行V2RayN |
| 端口冲突 | 用`netstat -ano | findstr "10808"`查找占用程序，关闭或修改端口 |

---

### 七、取消Git代理（如需）
```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

---

### 总结
1. V2RayN默认端口：**SOCKS5=10808**，**HTTP=10809**
2. 核心步骤：**查看端口→开启代理→配置Git→测试连接**
3. 推荐使用**SOCKS5代理**（更稳定），Git命令：
   ```bash
   git config --global http.proxy socks5://127.0.0.1:10808
   git config --global https.proxy socks5://127.0.0.1:10808
   ```

如果配置后仍有问题，可尝试切换V2RayN节点，或改用SSH方式连接GitHub（之前提供的方案）。

需要我按你当前V2RayN版本（告诉我版本号）给你生成一键复制的Git代理配置命令吗？