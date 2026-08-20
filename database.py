import mysql.connector as m
from config import HOST, USER, PASSWORD, DATABASE


# =========================================================
# CONNECT TO MYSQL SERVER
# =========================================================

myconn = m.connect(
    host=HOST,
    user=USER,
    password=PASSWORD
)

mycur = myconn.cursor()


# =========================================================
# CREATE DATABASE
# =========================================================

mycur.execute(
    f"CREATE DATABASE IF NOT EXISTS {DATABASE}"
)

mycur.execute(
    f"USE {DATABASE}"
)


# =========================================================
# ADMIN TABLE
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS admin(
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(50)
)
""")


# =========================================================
# DEFAULT ADMIN
# =========================================================

mycur.execute(
    "SELECT COUNT(*) FROM admin"
)

count = mycur.fetchone()[0]

if count == 0:
    mycur.execute("""
        INSERT INTO admin(username, password)
        VALUES(%s, %s)
    """, (
        "dharshan",
        "2010dharsh"
    ))

    myconn.commit()


# =========================================================
# RESTAURANT TABLES
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS restaurant_tables(
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_no INT UNIQUE,
    qrcode VARCHAR(255),
    status VARCHAR(20) DEFAULT 'Available'
)
""")


# =========================================================
# 1. ORDERS TABLE (MUST BE CREATED BEFORE ORDER_ITEMS)
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS orders(
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_no INT,
    order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_amt DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'Pending',
    trackid VARCHAR(100)
)
""")

mycur.execute("SHOW COLUMNS FROM orders LIKE 'trackid'")
if mycur.fetchone() is None:
    mycur.execute("ALTER TABLE orders ADD COLUMN trackid VARCHAR(100)")
    myconn.commit()


# =========================================================
# 2. MENU ITEMS TABLE
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS menu_items(
    id INT AUTO_INCREMENT PRIMARY KEY,
    dish_name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10,2),
    description VARCHAR(255),
    availability VARCHAR(20) DEFAULT 'Available',
    active TINYINT(1) DEFAULT 1,
    image VARCHAR(255)
)
""")

mycur.execute("SHOW COLUMNS FROM menu_items LIKE 'image'")
if mycur.fetchone() is None:
    mycur.execute("ALTER TABLE menu_items ADD COLUMN image VARCHAR(255)")
    myconn.commit()

mycur.execute("SHOW COLUMNS FROM menu_items LIKE 'active'")
if mycur.fetchone() is None:
    mycur.execute("ALTER TABLE menu_items ADD COLUMN active TINYINT(1) DEFAULT 1")
    myconn.commit()


# =========================================================
# 3. ORDER ITEMS TABLE (DEPENDS ON ORDERS & MENU_ITEMS)
# =========================================================

mycur.execute('''
CREATE TABLE IF NOT EXISTS order_items(
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT,
    menu_item_id INT,
    quantity INT,
    price DECIMAL(10,2),
    spice_level VARCHAR(20) DEFAULT 'Medium',
    notes VARCHAR(255) DEFAULT '',

    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(menu_item_id) REFERENCES menu_items(id)
)
''')

try:
    mycur.execute("ALTER TABLE order_items ADD COLUMN spice_level VARCHAR(20) DEFAULT 'Medium'")
    myconn.commit()
except Exception:
    pass

try:
    mycur.execute("ALTER TABLE order_items ADD COLUMN notes VARCHAR(255) DEFAULT ''")
    myconn.commit()
except Exception:
    pass


# =========================================================
# CART TABLE
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS cart(
    id INT AUTO_INCREMENT PRIMARY KEY,
    menu_id INT,
    dish_name VARCHAR(100),
    price DECIMAL(10,2),
    quantity INT,
    total DECIMAL(10,2),
    session_id VARCHAR(100),
    spice_level VARCHAR(20) DEFAULT 'Medium',
    notes VARCHAR(255) DEFAULT ''
)
""")

try:
    mycur.execute("ALTER TABLE cart ADD COLUMN session_id VARCHAR(100)")
    myconn.commit()
except Exception:
    pass

try:
    mycur.execute("ALTER TABLE cart ADD COLUMN spice_level VARCHAR(20) DEFAULT 'Medium'")
    myconn.commit()
except Exception:
    pass

try:
    mycur.execute("ALTER TABLE cart ADD COLUMN notes VARCHAR(255) DEFAULT ''")
    myconn.commit()
except Exception:
    pass


# =========================================================
# CUSTOMER FEEDBACK
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS customer_feedback(
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_no INT,
    customer_name VARCHAR(100),
    rating INT,
    comments TEXT,
    feedback_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


# =========================================================
# WAITER CALLS
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS waiter_calls(
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_no INT,
    status VARCHAR(20) DEFAULT 'Pending',
    request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


# =========================================================
# ANNOUNCEMENTS
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS announcements(
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    message VARCHAR(500) NOT NULL,
    active TINYINT(1) DEFAULT 1,
    announcement_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

mycur.execute("SHOW COLUMNS FROM announcements LIKE 'active'")
if mycur.fetchone() is None:
    mycur.execute("ALTER TABLE announcements ADD COLUMN active TINYINT(1) DEFAULT 1")
    myconn.commit()


# =========================================================
# ORDER PARTICIPANTS (For Split Bills)
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS order_participants(
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT,
    participant_name VARCHAR(100),
    amount DECIMAL(10,2),
    payment_status VARCHAR(20) DEFAULT 'Pending',
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
)
""")


# =========================================================
# ORDER ITEM PARTICIPANTS (For Itemized Split Bills)
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS order_item_participants(
    id INT AUTO_INCREMENT PRIMARY KEY,
    participant_id INT,
    order_item_id INT,
    quantity INT,
    amount DECIMAL(10,2),
    FOREIGN KEY (participant_id) REFERENCES order_participants(id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
)
""")


# =========================================================
# INITIAL MENU ITEMS
# =========================================================

mycur.execute("SELECT COUNT(*) FROM menu_items")
menu_count = mycur.fetchone()[0]

if menu_count == 0:
    mycur.execute("""
    INSERT INTO menu_items
    (
        dish_name,
        category,
        price,
        description,
        availability,
        active,
        image
    )
    VALUES
    ('Chicken Biryani', 'Main Course', 180.00, 'Delicious chicken biryani', 'Available', 1, 'Chicken_biriyani.jpg'),
    ('Veg Biryani', 'Main Course', 140.00, 'Tasty vegetable biryani', 'Available', 1, 'Vegfriedrice.jpg'),
    ('Chicken Fried Rice', 'Rice', 160.00, 'Chinese style chicken fried rice', 'Available', 1, 'Chickenfriedrice.jpg'),
    ('Paneer Butter Masala', 'Main Course', 150.00, 'Creamy paneer curry', 'Available', 1, 'paneer_butter_masala.jpg'),
    ('Masala Dosa', 'South Indian', 80.00, 'Crispy masala dosa', 'Available', 1, 'Dosa.jpg'),
    ('Idli', 'South Indian', 50.00, 'Soft steamed idlis', 'Available', 1, 'idli.jpg'),
    ('French Fries', 'Starters', 90.00, 'Crispy golden fries', 'Available', 1, 'french_fries.jpg'),
    ('Fresh Lime Juice', 'Drinks', 60.00, 'Refreshing lime juice', 'Available', 1, 'Freshlimejuice.jpg')
    """)
    myconn.commit()
else:
    updates = [
        ("Chicken_biriyani.jpg", "Chicken Biryani"),
        ("Vegfriedrice.jpg", "Veg Biryani"),
        ("Chickenfriedrice.jpg", "Chicken Fried Rice"),
        ("paneer_butter_masala.jpg", "Paneer Butter Masala"),
        ("Dosa.jpg", "Masala Dosa"),
        ("idli.jpg", "Idli"),
        ("french_fries.jpg", "French Fries"),
        ("Freshlimejuice.jpg", "Fresh Lime Juice")
    ]

    for image_name, dish_name in updates:
        mycur.execute("""
            UPDATE menu_items
            SET image=%s, active=1
            WHERE dish_name=%s
        """, (image_name, dish_name))

    myconn.commit()


# =========================================================
# CART TABLE
# =========================================================

mycur.execute("""
CREATE TABLE IF NOT EXISTS cart(
    id INT AUTO_INCREMENT PRIMARY KEY,
    menu_id INT,
    dish_name VARCHAR(100),
    price DECIMAL(10,2),
    quantity INT,
    total DECIMAL(10,2),
    session_id VARCHAR(100),
    spice_level VARCHAR(20) DEFAULT 'Medium',
    notes VARCHAR(255) DEFAULT ''
)
""")

try:
    mycur.execute("ALTER TABLE cart ADD COLUMN session_id VARCHAR(100)")
    myconn.commit()
except Exception:
    pass

try:
    mycur.execute("ALTER TABLE cart ADD COLUMN spice_level VARCHAR(20) DEFAULT 'Medium'")
    myconn.commit()
except Exception:
    pass

try:
    mycur.execute("ALTER TABLE cart ADD COLUMN notes VARCHAR(255) DEFAULT ''")
    myconn.commit()
except Exception:
    pass
# =========================================================
# COMMIT ALL CHANGES & CLOSE
# =========================================================

myconn.commit()
mycur.close()
myconn.close()

print("--------------------------------------")
print("Database and tables created successfully!")
print("All execution sequences and dependencies fixed!")
print("Scan2Dine database is ready!")
print("--------------------------------------")
