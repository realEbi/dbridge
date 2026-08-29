-- Sample database for manual testing and demos.
--
-- Deliberately exercises the things that have broken before:
--   * non-alphabetical column order (so a scrambled render is obvious)
--   * NULLs alongside empty strings
--   * foreign keys, for JOIN completion and the future ERD extractor
--   * more than max_rows (100) in one table, to show truncation
--
-- Rebuild with:  uv run python scripts/make_sample_db.py

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    email       TEXT,               -- nullable on purpose
    country     TEXT    NOT NULL,
    signed_up   TEXT    NOT NULL
);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    sku         TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    price       REAL    NOT NULL,
    discontinued INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date  TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    notes       TEXT                -- mix of NULL and '' below
);

CREATE TABLE order_items (
    id          INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL,
    unit_price  REAL    NOT NULL
);

INSERT INTO customers (id, name, email, country, signed_up) VALUES
    (1, 'Alice Johnson',  'alice@example.com',  'US', '2024-01-15'),
    (2, 'Bob Martin',     'bob@example.com',    'GB', '2024-02-03'),
    (3, 'Chidi Okafor',   NULL,                 'NG', '2024-02-20'),
    (4, 'Dana Whitfield', 'dana@example.com',   'US', '2024-03-11'),
    (5, 'Émile Roux',     'emile@example.fr',   'FR', '2024-04-02'),
    (6, 'Fatima Haddad',  '',                   'MA', '2024-05-19'),
    (7, 'Grace Nakamura', 'grace@example.jp',   'JP', '2024-06-30'),
    (8, 'Hugo Almeida',   'hugo@example.br',    'BR', '2024-07-08');

INSERT INTO products (id, sku, name, category, price, discontinued) VALUES
    (1, 'KEY-001', 'Mechanical Keyboard', 'peripherals', 129.99, 0),
    (2, 'MOU-002', 'Trackball Mouse',     'peripherals',  69.50, 0),
    (3, 'MON-003', '27" 4K Monitor',      'displays',    449.00, 0),
    (4, 'MON-004', '34" Ultrawide',       'displays',    799.00, 0),
    (5, 'CAB-005', 'USB-C Cable 2m',      'cables',       19.99, 0),
    (6, 'CAB-006', 'HDMI Cable 3m',       'cables',       24.99, 1),
    (7, 'DOC-007', 'Thunderbolt Dock',    'docks',       299.00, 0),
    (8, 'HUB-008', '7-Port USB Hub',      'docks',        54.00, 0),
    (9, 'STA-009', 'Laptop Stand',        'accessories',  89.00, 0),
   (10, 'LMP-010', 'Monitor Light Bar',   'accessories',  99.00, 1);

INSERT INTO orders (id, customer_id, order_date, status, notes) VALUES
    (1, 1, '2024-08-01', 'shipped',   'leave at door'),
    (2, 1, '2024-08-14', 'shipped',   NULL),
    (3, 2, '2024-08-16', 'pending',   ''),
    (4, 3, '2024-08-19', 'cancelled', 'duplicate order'),
    (5, 4, '2024-09-02', 'shipped',   NULL),
    (6, 5, '2024-09-07', 'pending',   NULL),
    (7, 6, '2024-09-11', 'shipped',   'gift wrap'),
    (8, 7, '2024-09-15', 'refunded',  'damaged in transit'),
    (9, 8, '2024-09-21', 'pending',   ''),
   (10, 2, '2024-09-28', 'shipped',   NULL);
