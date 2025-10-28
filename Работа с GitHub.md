📘 **Работа с GitHub.md** — шаг за шагом объясняет, как взаимодействовать с GitHub через веб-интерфейс:
создание репозитория, push, ветки, Pull Request, слияние, просмотр истории, клонирование, работу с Issues и настройку репозитория.
Формат выдержан в твоём привычном стиле — технически точно, но спокойно и по делу.

---

````md
# Работа с GitHub
## Полное руководство для проекта Telegram Calendar Bot

---

## Зачем нужен GitHub

GitHub — это **удалённое хранилище кода** (репозиторий), связанное с твоим локальным проектом через Git.

Он позволяет:
- хранить резервные копии кода;
- синхронизировать работу между компьютерами;
- публиковать код (для ревью, сдачи, open-source);
- вести историю версий, комментарии и pull request;
- показывать результат работы преподавателю или коллегам.

> Git — локальная история.  
> GitHub — место, где эта история живёт в интернете.

---

## 🔹 Основная логика работы

1. Создаёшь **репозиторий** на GitHub.  
2. Привязываешь к нему локальный проект через `git remote add origin`.
3. Делаешь коммиты (`git commit`).
4. Отправляешь на GitHub (`git push`).
5. При необходимости подтягиваешь свежие изменения (`git pull`).
6. Для каждой части задания — новая ветка (`bot-part1`, `bot-part2`, `bot-part3`).
7. После завершения — **Pull Request → Merge → Main**.

---

## 🔹 Как создать репозиторий на GitHub

1. Перейди на [github.com](https://github.com).
2. В правом верхнем углу нажми **+ → New repository**.
3. Заполни поля:
   - Repository name:  
     ```
     Python_TelegramBot_Kabshanov
     ```
   - Description:  
     ```
     Telegram Calendar Bot project for Django + Python Telegram Bot
     ```
   - Public (или Private, если нужно).
4. Не добавляй `README` — мы его создадим локально.
5. Нажми **Create repository**.

GitHub покажет тебе подсказку вида:

```bash
git remote add origin git@github.com:kabshanov/Python_TelegramBot_Kabshanov.git
git branch -M main
git push -u origin main
````

---

## 🔹 Как связать локальный проект с GitHub

В терминале PyCharm (или PowerShell):

```bash
git init
git add .
git commit -m "part1: base telegram bot"
git remote add origin git@github.com:kabshanov/Python_TelegramBot_Kabshanov.git
git branch -M main
git push -u origin main
```

> Если проект уже под Git — просто добавь remote:
>
> ```bash
> git remote -v
> ```
>
> Проверяет, привязан ли репозиторий.
> Если нет — добавь `origin` по ссылке GitHub.

---

## 🔹 Как выглядит структура репозитория

На странице GitHub ты увидишь:

```
📁 Python_TelegramBot_Kabshanov
 ┣ 📂 tgapp/
 ┣ 📂 webapp/
 ┣ 📄 bot.py
 ┣ 📄 db.py
 ┣ 📄 README.md
 ┣ 📄 README_BOT.md
 ┣ 📄 README_DJANGO.md
 ┣ 📄 requirements_part2.txt
 ┗ 📄 .gitignore
```

Файлы, добавленные в `.gitignore`, не попадут в репозиторий (`.venv`, `.idea`, `bot_secrets.py` и т.п.).

---

## 🔹 Как отправлять обновления (push)

После изменений:

```bash
git add .
git commit -m "part3: meetings + invite FSM"
git push
```

Если ветка новая:

```bash
git push -u origin bot-part3
```

GitHub автоматически создаст ветку `bot-part3` в удалённом репозитории.

---

## 🔹 Как создать новую ветку

В PyCharm или терминале:

```bash
git checkout -b bot-part3
```

На GitHub появится новая ветка, когда ты сделаешь первый `push`.

> Ветки нужны, чтобы работать над разными частями проекта независимо:
>
> * `main` — стабильная версия,
> * `bot-part1` — часть 1,
> * `bot-part2` — интеграция Django,
> * `bot-part3` — встречи и FSM.

---

## 🔹 Что такое Pull Request (PR)

Pull Request — это **запрос на слияние ветки** в основную (`main`).

Ты создаёшь ветку `bot-part2`, пушишь код → GitHub предлагает:

```
Compare & Pull Request
```

1. Нажимаешь на кнопку.
2. Проверяешь изменения.
3. Пишешь комментарий (например, *"Задание 2: Django integration"*).
4. Нажимаешь **Create Pull Request**.
5. После проверки — **Merge Pull Request**.
6. Ветка объединяется с `main`.

---

## 🔹 Как слить ветку (Merge)

После Merge:

```bash
git checkout main
git pull
```

Теперь `main` содержит все изменения.

Если ветка больше не нужна:

```bash
git branch -d bot-part2
```

(локально)

И на GitHub можно удалить:

> На странице ветки → **Delete branch**.

---

## 🔹 Как просмотреть историю изменений

В репозитории GitHub:

* вкладка **Code** → кнопка **commits**;
* ты увидишь историю:

  ```
  part3: meetings + invite FSM + docstrings
  part2: Django integration
  part1: base telegram bot
  ```

Клик по коммиту покажет diff — какие файлы изменились и на что.

---

## 🔹 Как клонировать проект (если работаешь с нуля)

Если проект уже на GitHub:

```bash
git clone git@github.com:kabshanov/Python_TelegramBot_Kabshanov.git
```

Создаст папку `Python_TelegramBot_Kabshanov/` с кодом и всей историей.

---

## 🔹 Как подтянуть изменения с GitHub (pull)

Если ты работал с другого компьютера или сделал merge на сайте:

```bash
git pull
```

Git синхронизирует локальную копию с удалённой веткой.

---

## 🔹 Как просматривать файлы в GitHub

На странице репозитория:

* можно просматривать исходники прямо в браузере;
* GitHub подсвечивает Python, Markdown, HTML и т.д.;
* можно перейти по папкам (`tgapp`, `webapp`, `calendarapp`);
* кнопка **Raw** — показать чистый текст (например, чтобы скопировать код).

---

## 🔹 Как редактировать файл прямо на GitHub

1. Открой нужный файл.
2. Нажми ✏️ **Edit this file**.
3. Внеси изменения.
4. Внизу выбери:

   * Commit directly to this branch — если ты работаешь один;
   * Create a new branch — если это ревью.
5. Нажми **Commit changes**.

> Для крупных правок всегда лучше делать это в PyCharm и пушить,
> чтобы избежать конфликтов.

---

## 🔹 Как просматривать различия (Diff)

На вкладке **Pull Requests**:

* выбери свой PR;
* GitHub покажет все изменения построчно (зелёный — добавлено, красный — удалено);
* можно оставить комментарии прямо к строкам кода.

---

## 🔹 Как работать с Issues (по желанию)

**Issues** — это задачи, баги, заметки.
Можно использовать как TODO-лист:

1. Вкладка **Issues → New Issue**.
2. Название: `"Добавить FSM для приглашений"`.
3. Описание: `"Реализовать /invite с проверкой занятости"`.
4. После выполнения — закрыть Issue.

---

## 🔹 Как работать с README

Главная страница GitHub отображает `README.md`.

Можно добавить несколько файлов:

* `README.md` — общий обзор;
* `README_BOT.md` — логика телеграм-бота;
* `README_DJANGO.md` — Django-часть;
* `Работа с Git.md`, `Работа с PyCharm.md`, `Работа с GitHub.md` — технические инструкции.

---

## 🔹 Как оформить репозиторий красиво

* Добавь описание (Description) и теги (Topics):

  ```
  telegram-bot, django, python, calendar
  ```
* Добавь README с заголовками и списками.
* Добавь LICENSE (по желанию).
* Добавь раздел Releases (можно помечать завершённые части).
* В разделе Settings → Branches можно защитить `main` от случайных пушей.

---

## 🔹 Как защитить основную ветку (main)

1. Открой репозиторий → Settings → Branches.
2. В разделе **Branch protection rules** → Add rule.
3. Введи `main`.
4. Отметь:

   * ✅ Require pull request before merging
   * ✅ Require status checks to pass
   * ✅ Require conversation resolution
5. Сохрани.

Теперь изменения в `main` идут только через Pull Request.

---

## 🔹 Как создать release (например, после сдачи части)

1. Вкладка **Releases → Draft a new release**.
2. Тег: `v2.0` (или `part3-complete`).
3. Заголовок: `Часть 3: Встречи и FSM`.
4. Описание: что сделано, примеры, изменения.
5. Нажми **Publish release**.

---

## 🔹 Как использовать GitHub Desktop (альтернатива)

Если не хочется работать в терминале:

1. Установи [GitHub Desktop](https://desktop.github.com/).
2. Открой проект → выбери ветку → Commit → Push.
3. Всё визуально, синхронизируется с GitHub.

---

## 🔹 Мини-шпаргалка по GitHub

| Действие             | Где делается                    |
| -------------------- | ------------------------------- |
| Создать репозиторий  | GitHub → New Repository         |
| Привязать локальный  | `git remote add origin`         |
| Отправить изменения  | `git push`                      |
| Создать ветку        | `git checkout -b bot-part3`     |
| Создать Pull Request | GitHub → Compare & pull request |
| Слить ветку          | Merge Pull Request              |
| Посмотреть историю   | Code → Commits                  |
| Скачать проект       | `git clone ...`                 |
| Подтянуть изменения  | `git pull`                      |

---

## 🔹 Типичные ошибки

| Ошибка                          | Причина                                              | Решение                                                     |
| ------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------- |
| `Permission denied (publickey)` | Не настроен SSH-ключ                                 | `ssh-keygen` и добавить ключ в GitHub → Settings → SSH keys |
| `rejected (fetch first)`        | В удалённой ветке есть коммиты, которых нет локально | `git pull --allow-unrelated-histories` и повторный push     |
| `merge conflict`                | Несовпадающие изменения                              | Решить конфликт → Commit → Push                             |
| `secrets.choice` в Django       | Есть файл `secrets.py` в корне                       | Переименовать в `bot_secrets.py`                            |

---

## 🔹 Итоговый цикл работы

```bash
# локально
git checkout -b bot-part3
# работаешь в коде
git add .
git commit -m "part3: встречи и FSM"
git push -u origin bot-part3

# на GitHub
Compare & Pull Request → Merge Pull Request

# обратно локально
git checkout main
git pull
```

---

## 🔹 Заключение

GitHub — это зеркало твоего кода и хронология твоей работы.
Каждый commit и pull request показывает **рост проекта шаг за шагом**.

> **Git хранит — GitHub показывает.**
> Вместе они делают твой код прозрачным, проверяемым и безопасным.

---

📘 Рекомендуется держать этот файл прямо в проекте, рядом с:

* `Работа с Git.md`
* `Работа с Git в PyCharm.md`

Так ты всегда сможешь быстро вспомнить, что делать при работе с ветками, пушами и pull requests.

```
