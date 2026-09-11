<div align="center">
  <img src="https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/logo.png" height="90" alt="Elys Logo">
  <h1>Elys Userbot</h1>
  <p><b>Продвинутый модульный юзербот для Telegram с повышенной безопасностью, инлайн-интерфейсом и современными функциями.</b></p>

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
      <img src="https://img.shields.io/badge/Telegram-Чат-2ca5e0.svg?logo=telegram" alt="Telegram Чат">
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

## 🌟 О проекте Elys Userbot

**Elys** (Элис) — это современный, быстрый и модульный **юзербот для Telegram**, разработанный командой **ZavozDevs** на базе Python 3 и асинхронной библиотеки [Telethon](https://github.com/LonamiWebs/Telethon).

**Elys Userbot** создан для автоматизации задач в Telegram, расширения возможностей личного аккаунта, удобного администрирования групп и каналов, создания интерактивных инлайн-меню и запуска пользовательских модулей. Юзербот полностью совместим с экосистемой модулей для **Hikka**, **Friendly-Telegram (FTG)** и **GeekTG**.

### ✨ Главные преимущества:
- ⚡ **Скорость и оптимизация:** Асинхронное ядро с минимальным потреблением RAM/CPU — бот летает даже на слабых VPS и смартфонах.
- 🧩 **Модульная экосистема:** Установка сотен готовых модулей прямо через чат в Telegram (`.dlmod`, `.help`).
- 🎨 **Интерактивный UI:** Инлайн-кнопки, формы, галереи, кастомные эмодзи и полная поддержка тем и форумов.
- 🛡️ **Безопасность:** Встроенный API Firewall, защита от спама, кэширование сущностей и проверка подозрительных модулей.
- 🔄 **Полная совместимость:** Запускайте любые свои модули от Hikka, FTG и GeekTG без каких-либо изменений.
- ☁️ **Быстрый деплой:** Установка в одну команду на Linux VPS (Debian, Ubuntu, Arch, Fedora), в Docker, на ПК (WSL), смартфон (UserLAnd / Termux) или хостинг в 1 клик на **RnHost**.

---

## ⚠️ Уведомление о безопасности

> **Важное предупреждение о безопасности**  
> Хотя Elys реализует расширенные меры безопасности, установка модулей от ненадежных разработчиков все еще может нанести вред вашему серверу/аккаунту.
> 
> **Рекомендации:**
> - ✅ Загружайте модули исключительно из официальных репозиториев или от доверенных разработчиков
> - ❌ НЕ устанавливайте модули, если не уверены в их безопасности
> - ⚠️ Будьте осторожны с неизвестными командами (`.terminal`, `.eval`, `.ecpp` и т.д.)

---

## 🚀 Установка

### VPS/VDS
> **Примечание для пользователей VPS/VDS:**  
> Добавьте `--root` для пользователей root (чтобы избежать ввода force_insecure)

<details>
  <summary><b>Ubuntu / Debian</b></summary>

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

### Другие платформы
<details>
  <summary><b>WSL (Windows)</b></summary>

  > **⚠️ ВНИМАНИЕ: Может быть нестабильно!**

1. **Скачайте WSL.** Для этого откройте PowerShell с правами администратора и выполните:
```powershell
wsl --install -d Ubuntu-22.04
```

> *⚠️ Для установки требуется Windows 10 сборки 2004 или Windows 11 любой версии и ПК с поддержкой виртуализации.*
> *Для установки на более ранние ОС обратитесь к [инструкции](https://learn.microsoft.com/ru-ru/windows/wsl/install-manual).*

2. **Перезагрузите ПК и запустите Ubuntu 22.04.x**
3. **Установите pip:**
```bash
curl -Ss https://bootstrap.pypa.io/get-pip.py | python3
```
> *⚠️ Если появятся предупреждения, выполните `export PATH="/home/username/.local/bin:$PATH"`, заменив на ваш путь.*

4. **Запустите Elys:**
```bash
clear && git clone https://github.com/ZavozDevs/Elys && cd Elys && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 -m elys
```
> **🔗 Как получить API_ID и API_HASH?:** [Видео-гайд](https://youtu.be/DcqDA249Lhg?t=24)
  
</details>

<details>
  <summary><b>Телефон (UserLAnd / Android)</b></summary>
  
1. <b>Установите UserLAnd по</b> <a href="https://play.google.com/store/apps/details?id=tech.ula">ссылке в Google Play</a>
2. <b>Откройте приложение, выберите Ubuntu —&gt; Minimal —&gt; Terminal</b>
3. <b>Дождитесь установки дистрибутива</b>
4. <b>В открывшемся терминале введите:</b>
```bash
sudo apt update && sudo apt upgrade -y && sudo apt install python3 git python3-pip -y && git clone https://github.com/ZavozDevs/Elys && cd Elys && python3 -m venv .venv && source .venv/bin/activate && sudo pip install -r requirements.txt && python3 -m elys
```
5. <b>Следуйте инструкциям в консоли для авторизации Telegram аккаунта.</b>
> **Готово! Elys запущен прямо на вашем Android-устройстве.**
</details>

### Официальные хостинги
<details>
<summary><b>❤️🔥 RnHost (Облачный запуск в 1 клик)</b></summary>
  
  1. Перейдите на [host.rooni.dev](https://host.rooni.dev)
  2. Закажите размещение **🌟 Elys Userbot**
  3. Введите данные своей учетной записи для входа.
  > **Простой, быстрый и круглосуточный облачный хостинг для Elys!**

</details>

---

## 🎨 Дополнительные функции

<details>
  <summary><b>🔒 Автоматическое резервное копирование базы данных</b></summary>
  <br>
  <img src="https://user-images.githubusercontent.com/36935426/202905566-964d2904-f3ce-4a14-8f05-0e7840e1b306.png" width="400">
</details>

<details>
  <summary><b>👋 Приветственные экраны установки</b></summary>
  <br>
  <img src="https://user-images.githubusercontent.com/36935426/202905720-6319993b-697c-4b09-a194-209c110c79fd.png" width="300">
  <img src="https://user-images.githubusercontent.com/36935426/202905746-2a511129-0208-4581-bb27-7539bd7b53c9.png" width="300">
</details>

---

## ✨ Ключевые особенности и улучшения

| Особенность | Описание |
|-------------|------------|
| 🆕 **Последний слой Telegram** | Поддержка форумов, топиков, реакций и новейших функций Telegram |
| 🔒 **Повышенная безопасность** | Нативное кэширование сущностей, защита от спама и целевые правила безопасности |
| 🎨 **Улучшения UI/UX** | Современный интерфейс и удобный пользовательский опыт |
| 📦 **Основные модули** | Улучшенный и расширенный встроенный функционал |
| ⏱️ **Быстрое исправление ошибок** | Активная поддержка и оперативное решение багов |
| 🔄 **Обратная совместимость** | Полная совместимость с модулями FTG, GeekTG и Hikka |
| ▶️ **Инлайн-элементы** | Поддержка интерактивных форм, галерей и списков |

---

## 📋 Требования

- **Python 3.10+**
- **Учетные данные API** (API ID и API HASH из [my.telegram.org/apps](https://my.telegram.org/apps))

---

## 💬 Сообщество и поддержка

| Ресурс | Ссылка |
|--------|-------|
| **Чат поддержки Telegram** | [@ElysTalk](https://t.me/ElysTalk) |
| **Облачный хостинг** | [host.rooni.dev](https://host.rooni.dev) |
| **Баг-трекер и предложения** | [GitHub Issues](https://github.com/ZavozDevs/Elys/issues) |

---

## ⚠️ Отказ от ответственности за использование

> Этот проект предоставляется «как есть». Разработчики НЕ несут ответственности за:
> - Блокировки или ограничения аккаунта
> - Удаления сообщений Telegram
> - Проблемы безопасности, вызванные сторонними модулями
> - Утечки сессий из-за вредоносных скриптов
>
> **Рекомендации по безопасности:**
> - Включите `.api_fw_protection`
> - Избегайте установки непроверенных модулей
> - Ознакомьтесь с [Telegram Terms of Service](https://core.telegram.org/api/terms)

---

## 🙏 Благодарности и авторы

- [**Codrago**](https://github.com/coddrago) за [Heroku Userbot](https://github.com/coddrago/Heroku)
- [**Hikari**](https://gitlab.com/hikariatama) за [Hikka Userbot](https://github.com/hikariatama/hikka) (основа проекта)
- [**Lonami**](https://t.me/lonami) за [Telethon](https://codeberg.org/Lonami/Telethon)
