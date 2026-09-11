<div align="center">
  <img src="https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/logo.png" height="90" alt="Elys Logo">
  <h1>Elys Userbot</h1>
  <p><b>Next-generation modular Telegram userbot with enhanced security, rich inline UI, and modern features.</b></p>
  
  <p>
    <a href="https://github.com/ZavozDevs/Elys/stargazers">
      <img src="https://img.shields.io/github/stars/ZavozDevs/Elys?style=flat" alt="Stars">
    </a>
    <a href="https://github.com/ZavozDevs/Elys/network/members">
      <img src="https://img.shields.io/github/forks/ZavozDevs/Elys?style=flat" alt="Forks">
    </a>
    <a href="https://github.com/ZavozDevs/Elys/issues">
      <img src="https://img.shields.io/github/issues-raw/ZavozDevs/Elys" alt="Open Issues">
    </a>
    <a href="https://github.com/ZavozDevs/Elys/blob/master/LICENSE">
      <img src="https://img.shields.io/github/license/ZavozDevs/Elys" alt="License">
    </a>
    <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python" alt="Python 3.10+">
    </a>
    <a href="https://t.me/ElysTalk">
      <img src="https://img.shields.io/badge/Telegram-Chat-2ca5e0.svg?logo=telegram" alt="Telegram Chat">
    </a>
    <a href="https://github.com/psf/black">
      <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style: Black">
    </a>
    <br>
    <a href="https://github.com/ZavozDevs/Elys/blob/master/README.md">
      <img src="https://img.shields.io/badge/lang-en-red.svg" alt="En">
    </a>
    <a href="https://github.com/ZavozDevs/Elys/blob/master/README_RU.md">
      <img src="https://img.shields.io/badge/lang-ru-green.svg" alt="Ru">
    </a>
  </p>
</div>

---

## 🌟 About Elys Userbot

**Elys** is an advanced, high-performance, and modular **Telegram userbot** developed by **ZavozDevs**, powered by Python 3 and asynchronous [Telethon](https://github.com/LonamiWebs/Telethon).

Whether you want to automate routine messaging, manage groups and channels, add interactive inline widgets, or run custom plugins, **Elys Userbot** delivers unmatched flexibility and speed. It comes with out-of-the-box compatibility for **Hikka**, **Friendly-Telegram (FTG)**, and **GeekTG** modules.

### ✨ Why Elys?
- ⚡ **Blazing Fast & Lightweight:** Asynchronous architecture built for low resource consumption on VPS, servers, or local devices.
- 🧩 **Modular Ecosystem:** Easily install, update, and manage community modules using simple commands (`.dlmod`, `.help`).
- 🎨 **Modern Interactive UI:** Rich inline keyboards, menus, dynamic galleries, and full support for the latest Telegram features (forums, topics, reactions).
- 🛡️ **Enhanced Security:** Native API firewall, entity caching, permission safeguards, and malicious module detection.
- 🔄 **Full Compatibility:** Run your favorite modules from Hikka, FTG, and GeekTG without modifications.
- ☁️ **Cloud Ready:** Deploy anywhere in minutes — VPS, Docker, WSL, Android (UserLAnd / Termux), or 1-click cloud hosting via **RnHost**.

---

## ⚠️ Security Notice

> **Important Security Advisory**  
> While Elys implements extended security measures, installing modules from untrusted developers may still cause damage to your server/account.
> 
> **Recommendations:**
> - ✅ Download modules exclusively from official repositories or trusted developers
> - ❌ Do NOT install modules if unsure about their safety
> - ⚠️ Exercise caution with unknown commands (`.terminal`, `.eval`, `.ecpp`, etc.)

---

## 🚀 Installation

### VPS/VDS
> **Note for VPS/VDS Users:**  
> Add `--root` for root users (to avoid entering force_insecure)
<details> <summary><b>Ubuntu / Debian</b></summary>

  ```bash
  sudo apt update && sudo apt install git python3 -y && \
  git clone https://github.com/ZavozDevs/Elys && \
  cd Elys && \
  python3 -m venv .venv && \
  source .venv/bin/activate && \
  pip install -r requirements.txt && \
  python3 -m elys
  ```
</details>

<details>
<summary><b>Fedora</b></summary>
  
  ```bash
  sudo dnf update -y && sudo dnf install git python3 -y && \
  git clone https://github.com/ZavozDevs/Elys && \
  cd Elys && \
  python3 -m venv .venv && \
  source .venv/bin/activate && \
  python3 -m pip install -r requirements.txt && \
  python3 -m elys
  ```
</details>

<details>
<summary><b>Arch Linux</b></summary>
  
```bash
sudo pacman -Syu --noconfirm && sudo pacman -S git python --noconfirm --needed && \
git clone https://github.com/ZavozDevs/Elys && \
cd Elys && \
python3 -m venv .venv && \
source .venv/bin/activate && \
python3 -m pip install -r requirements.txt && \
python3 -m elys
```
</details>

### Other
<details>
  <summary><b>WSL (Windows)</b></summary>

  > **⚠️ WARNING: Can be unstable!**

  1. **Download WSL.** For this open PowerShell with admin rights and write in console:
  ```powershell
  wsl --install -d Ubuntu-22.04
  ```
  
  > *⚠️ Requires Windows 10 build 2004 or Windows 11 and a PC with virtualization support.*
  > *For installation on earlier OS versions, please refer to the [official manual](https://learn.microsoft.com/en-us/windows/wsl/install-manual).*
  
  2. **Restart PC and launch Ubuntu 22.04.x**
  3. **Install pip:** 
  ```bash
  curl -Ss https://bootstrap.pypa.io/get-pip.py | python3
  ```
  > *⚠️ If warnings appear, enter `export PATH="/home/username/.local/bin:$PATH"` replacing with your actual path.*
  
  4. **Run Elys:**
  ```bash
  clear && git clone https://github.com/ZavozDevs/Elys && cd Elys && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 -m elys
  ```
  > **🔗 How to get API_ID and API_HASH?:** [Video Guide](https://youtu.be/DcqDA249Lhg?t=24)
  
</details>

<details>
  <summary><b>Phone (UserLAnd / Android)</b></summary>
  
  1. <b>Install UserLAnd from</b> <a href="https://play.google.com/store/apps/details?id=tech.ula">Google Play</a>
  2. <b>Open it, choose Ubuntu —&gt; Minimal —&gt; Terminal</b>
  3. <b>Wait for the distribution to install</b> 
  4. <b>In the terminal, run:</b>
    
  ```bash
  sudo apt update && sudo apt upgrade -y && sudo apt install python3 git python3-pip -y && git clone https://github.com/ZavozDevs/Elys && cd Elys && python3 -m venv .venv && source .venv/bin/activate && sudo pip install -r requirements.txt && python3 -m elys
  ```

  5. <b>Follow the on-screen instructions to authorize your Telegram account.</b>
  > **Done! Elys is running on your Android device.**
</details>

<details>
  <summary><b>Phone (Termux)</b></summary>
  
  1. <b>Install Termux from</b> <a href="https://github.com/termux/termux-app/releases">GitHub Releases</a> or <a href="https://f-droid.org/packages/com.termux/">F-Droid</a> (do not use Google Play version).
  2. <b>Launch Termux and run:</b>
    
  ```bash
  pkg update -y && pkg install git python -y && git clone https://github.com/ZavozDevs/Elys && cd Elys && pip install -r requirements.txt && python3 -m elys
  ```

  3. <b>At the end of the installation, follow the web link or complete authorization in the terminal.</b>
  > **🪐 Voila! You have installed Elys on Termux.**
</details>

### Official Cloud Hosting
<details>
<summary><b>❤️🔥 RnHost (1-Click Deployment)</b></summary>
  
  1. Open [host.rooni.dev](https://host.rooni.dev)
  2. Deploy **🌟 Elys Userbot**
  3. Enter your account details to log in.
  > **Easy, fast and 24/7 cloud hosting for Elys!**

</details>

---

## 🎨 Additional Features

<details>
  <summary><b>🔒 Automatic Database Backuper</b></summary>
  <br>
  <img src="https://user-images.githubusercontent.com/36935426/202905566-964d2904-f3ce-4a14-8f05-0e7840e1b306.png" width="400">
</details>

<details>
  <summary><b>👋 Welcome Installation Screens</b></summary>
  <br>
  <img src="https://user-images.githubusercontent.com/36935426/202905720-6319993b-697c-4b09-a194-209c110c79fd.png" width="300">
  <img src="https://user-images.githubusercontent.com/36935426/202905746-2a511129-0208-4581-bb27-7539bd7b53c9.png" width="300">
</details>

---

## ✨ Key Features & Improvements

| Feature | Description |
|---------|-------------|
| 🆕 **Latest Telegram Layer** | Support for forums, topics, reactions and newest Telegram features |
| 🔒 **Enhanced Security** | Native entity caching, permission checks and targeted security rules |
| 🎨 **UI/UX Improvements** | Modern responsive interface and smooth user experience |
| 📦 **Core Modules** | Improved built-in modules and extended utility commands |
| ⏱ **Rapid Bug Fixes** | Active maintenance and faster issue resolution |
| 🔄 **Backward Compatibility** | Seamless support for FTG, GeekTG and Hikka modules |
| ▶️ **Inline Elements** | Dynamic forms, interactive galleries, and interactive lists |

---

## 📋 Requirements

- **Python 3.10+**
- **API Credentials** (API ID and API HASH from [my.telegram.org/apps](https://my.telegram.org/apps))

---

## 💬 Community & Support

| Platform | Link |
|----------|------|
| **Telegram Support & Chat** | [@ElysTalk](https://t.me/ElysTalk) |
| **Cloud Hosting** | [host.rooni.dev](https://host.rooni.dev) |
| **Bug Reports & Issues** | [GitHub Issues](https://github.com/ZavozDevs/Elys/issues) |

---

## ⚠️ Usage Disclaimer

> This project is provided as-is. The developer takes **NO responsibility** for:
> - Account bans or restrictions
> - Message deletions by Telegram
> - Security issues from untrusted third-party modules
> - Session leaks from malicious scripts
>
> **Security Recommendations:**
> - Enable `.api_fw_protection`
> - Avoid installing untrusted modules
> - Review [Telegram Terms of Service](https://core.telegram.org/api/terms)

---

## 🙏 Acknowledgements & Credits

- [**Codrago**](https://github.com/coddrago) for [Heroku Userbot](https://github.com/coddrago/Heroku)
- [**Hikari**](https://gitlab.com/hikariatama) for [Hikka Userbot](https://github.com/hikariatama/hikka) (project foundation)
- [**Lonami**](https://t.me/lonami) for [Telethon](https://codeberg.org/Lonami/Telethon)
