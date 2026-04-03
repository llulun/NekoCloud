# 🐱 NekoCloud (猫猫云)

> 一个高颜值、安全、易用的代理订阅分享与管理面板。
> A cute, secure, and easy-to-use proxy subscription sharing panel.

![NekoCloud Banner](https://via.placeholder.com/800x400.png?text=NekoCloud)

## ✨ 特性 (Features)

*   **🌸 高颜值 UI**：采用粉色/玻璃拟态 (Glassmorphism) 设计风格，清新可爱。
*   **🔒 安全隐私**：
    *   **订阅链接隐藏**：前端不直接暴露订阅链接，通过按钮一键复制。
    *   **强制规则阅读**：用户首次获取订阅前强制阅读并同意服务条款。
    *   **权限管理**：区分管理员与普通用户权限。
    *   **安全加固**：内置 CSRF 保护、限流防护 (Rate Limiting)、动态密钥生成。
*   **⚡ 双线路支持**：独立管理“优化线路”和“住宅 IP 线路”，互不干扰。
*   **🔄 自动同步**：支持后台配置 API，自动定时同步上游流量数据。
*   **💾 安全备份**：每次保存配置自动创建时间戳备份，自动清理旧备份，并支持后台一键恢复历史配置。
*   **📱 全平台兼容**：完美适配 PC、手机端显示。
*   **🎯 体验优化**：仪表盘支持实时使用率颜色提示、复制订阅非阻塞提示（Toast）和按钮加载态反馈。

## 🚀 一键安装 (Quick Install)

适用于 **Ubuntu / Debian** 系统。

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/llulun/NekoCloud/main/install.sh)"
```

脚本将自动执行以下操作：
1.  安装 Python3, pip, git 等必要依赖。
2.  拉取最新代码到 `/opt/NekoCloud`。
3.  创建虚拟环境并安装依赖。
4.  配置并启动 `systemd` 系统服务 (开机自启)。
5.  输出访问地址和默认账号密码。

---

## 🛠️ 手动部署 (Manual Deployment)

如果您不想使用一键脚本，或者使用其他系统，请参考以下步骤：

### 1. 环境要求
*   Python 3.8+
*   pip

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 运行
**开发环境：**
```bash
python app.py
```

**生产环境 (推荐)：**
使用 `waitress` (Windows) 或 `gunicorn` (Linux/Mac)。

```bash
# 安装 waitress
pip install waitress

# 启动服务 (端口 5001)
waitress-serve --port=5001 app:app
```

### 4. 初始配置
1.  访问后台：`http://localhost:5001/admin`
2.  默认管理员账号：
    *   用户名：`admin`
    *   密码：`adminpassword`
3.  **⚠️ 重要：** 请首次登录后立即在后台修改管理员密码！

## 📝 配置文件 (Config)
所有配置均保存在 `config.json` 中。
首次部署时，请在后台填入您的：
*   优化线路订阅链接
*   住宅 IP 订阅链接
*   流量同步 API 链接

## 📄 许可证
MIT License

## 🧩 版本号约定
页面底部会显示当前版本号（如 `v1.2.0`），每次发布更新时请同步修改 `app.py` 中的 `APP_VERSION`。
