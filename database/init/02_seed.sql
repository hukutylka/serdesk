-- IT Helpdesk: reference data and default admin account
-- Default admin password: admin123 (change after first login)

INSERT INTO categories (name) VALUES
    ('Проблемы с компьютером'),
    ('Проблемы с периферией'),
    ('Проблемы с принтером'),
    ('Проблемы с сетью'),
    ('Нет доступа к интернету'),
    ('Нет доступа к корпоративным ресурсам'),
    ('Проблемы с электронной почтой'),
    ('Проблемы с программным обеспечением'),
    ('Установка программ'),
    ('Другое');

INSERT INTO statuses (name, sort_order) VALUES
    ('Новая', 10),
    ('В работе', 20),
    ('Завершена', 30),
    ('Ожидает пользователя', 40),
    ('Отменена', 50);

-- bcrypt hash for "admin123" (cost 12)
INSERT INTO users (login, password_hash, full_name, role, account_status)
VALUES (
    'admin',
    '$2b$12$prIqXbzO6EqbpdAs7lK/guD1dkf4.56umGQtBOrslQ4i08aBni5ei',
    'Администратор системы',
    'admin',
    'active'
);
