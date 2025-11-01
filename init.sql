-- "Чертёж" для таблицы пользователей
CREATE TABLE IF NOT EXISTS users (
    tg_user_id BIGINT PRIMARY KEY,
    username TEXT NULL,
    first_name TEXT NULL,
    created_at TIMESTAMP DEFAULT now()
);

-- "Чертёж" для таблицы событий
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    details TEXT DEFAULT '',
    is_public BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);