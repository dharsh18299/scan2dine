from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import random
import uuid
from datetime import datetime
import mysql.connector as m
from config import HOST, USER, PASSWORD, DATABASE


app = Flask(__name__)
app.secret_key = "Scan2Dine_Project_2026"
WEBSITE_PASSWORD = "himynameisdevil"


@app.route("/website-login", methods=["GET", "POST"])
def website_login():

    if request.method == "POST":

        password = request.form.get("password")

        if password == WEBSITE_PASSWORD:
            session["website_access"] = True
            return redirect(url_for("home"))

        return render_template(
            "website_login.html",
            error="Incorrect password"
        )

    return render_template("website_login.html")


@app.before_request
def protect_website():

    allowed_routes = [
        "website_login",
        "static"
    ]

    if request.endpoint in allowed_routes:
        return

    if not session.get("website_access"):
        return redirect(url_for("website_login"))

# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    return m.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )

@app.route('/creator')
def creator():
    return render_template('creator.html')
# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("Home.html")


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        myconn = get_connection()
        mycur = myconn.cursor()

        mycur.execute(
            """
            SELECT *
            FROM admin
            WHERE username=%s AND password=%s
            """,
            (username, password)
        )

        admin_user = mycur.fetchone()

        mycur.close()
        myconn.close()

        if admin_user:
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(url_for("dashboard"))
        else:
            return "Invalid Admin Username or Password"

    return render_template("Admin_login.html")


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("SELECT COUNT(*) FROM orders")
    total_orders = mycur.fetchone()[0] or 0

    mycur.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE MONTH(order_time) = MONTH(CURRENT_DATE())
        AND YEAR(order_time) = YEAR(CURRENT_DATE())
        AND status != 'Cancelled'
        """
    )
    monthly_orders = mycur.fetchone()[0] or 0

    mycur.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Pending'
        """
    )
    pending_orders = mycur.fetchone()[0] or 0

    mycur.execute(
        """
        SELECT COALESCE(SUM(total_amt), 0)
        FROM orders
        WHERE status != 'Cancelled'
        """
    )
    amount_earned = mycur.fetchone()[0] or 0.0

    mycur.execute(
        """
        SELECT COALESCE(SUM(oi.quantity), 0)
        FROM order_items oi
        JOIN orders o
            ON oi.order_id = o.id
        WHERE o.status != 'Cancelled'
        """
    )
    dishes_served = mycur.fetchone()[0] or 0

    mycur.execute(
        """
        SELECT COALESCE(AVG(rating), 5.0)
        FROM customer_feedback
        """
    )
    overall_rating = mycur.fetchone()[0] or 5.0

    mycur.execute(
        """
        SELECT menu_items.id,
               menu_items.dish_name,
               menu_items.category,
               menu_items.price,
               menu_items.description,
               menu_items.image,
               SUM(order_items.quantity) AS total_quantity
        FROM order_items
        JOIN menu_items
            ON order_items.menu_item_id = menu_items.id
        JOIN orders
            ON order_items.order_id = orders.id
        WHERE orders.status != 'Cancelled'
          AND menu_items.availability = 'Available'
        GROUP BY menu_items.id,
                 menu_items.dish_name,
                 menu_items.category,
                 menu_items.price,
                 menu_items.description,
                 menu_items.image
        ORDER BY total_quantity DESC
        LIMIT 1
        """
    )
    top_selling = mycur.fetchone()

    mycur.close()
    myconn.close()

    return render_template(
        "Dashboard.html",
        total_orders=total_orders,
        monthly_orders=monthly_orders,
        pending_orders=pending_orders,
        amount_earned=amount_earned,
        dishes_served=dishes_served,
        overall_rating=overall_rating,
        top_selling=top_selling
    )


# =========================================================
# ADMIN CONTROL & ORDER MANAGEMENT ROUTES
# =========================================================

@app.route('/admin/orders')
@app.route('/admin/orders/<int:order_id>')
def admin_orders(order_id=None):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    
    if order_id is None:
        mycur.execute("SELECT id, table_no, total_amt, status, order_time FROM orders ORDER BY order_time DESC")
        orders = mycur.fetchall()
        mycur.close()
        myconn.close()
        return render_template('admin_orders.html', orders=orders)
        
    mycur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    order_result = mycur.fetchone()
    
    if not order_result:
        mycur.close()
        myconn.close()
        return "Order not found", 404
        
    status = order_result[0]
    
    mycur.execute("""
        SELECT m.dish_name, oi.quantity, oi.price, oi.spice_level 
        FROM order_items oi 
        JOIN menu_items m ON oi.menu_item_id = m.id 
        WHERE oi.order_id = %s
    """, (order_id,))
    items = mycur.fetchall()
    
    mycur.close()
    myconn.close()
    
    return render_template('Order_details.html', items=items, status=status, order_id=order_id)


@app.route('/admin/order/status/<int:order_id>/<string:status>')
def update_order_status(order_id, status):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
        
    if status not in ['Pending', 'Preparing', 'Ready', 'Completed', 'Cancelled', 'Delivered']:
        return "Invalid Status", 400
        
    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    myconn.commit()
    mycur.close()
    myconn.close()
    
    return redirect(url_for('admin_orders'))


@app.route("/admin_menu")
def admin_menu():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))
    return redirect(url_for("view_menu"))


@app.route("/admin_waiter_requests")
def admin_waiter_requests():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))
    return redirect(url_for("waiter_requests"))


# =========================================================
# ADD MENU
# =========================================================

@app.route("/add_menu", methods=["GET", "POST"])
def add_menu():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    if request.method == "POST":
        dish_name = request.form["dish_name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]

        myconn = get_connection()
        mycur = myconn.cursor()

        mycur.execute(
            """
            INSERT INTO menu_items
            (dish_name, category, price, description)
            VALUES (%s, %s, %s, %s)
            """,
            (dish_name, category, price, description)
        )

        myconn.commit()
        mycur.close()
        myconn.close()

        return redirect(url_for("dashboard"))

    return render_template("Add_menu.html")


# =========================================================
# ANNOUNCEMENTS ADMIN BUTTON & MANAGEMENT
# =========================================================

@app.route("/admin_announcements")
def admin_announcements():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))
    return redirect(url_for("manage_announcements"))


@app.route("/manage_announcements", methods=["GET", "POST"])
def manage_announcements():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()

        if title and message:
            mycur.execute(
                """
                INSERT INTO announcements
                (title, message, announcement_time, active)
                VALUES (%s, %s, NOW(), 1)
                """,
                (title, message)
            )
            myconn.commit()

        mycur.close()
        myconn.close()
        return redirect(url_for("manage_announcements"))

    mycur.execute(
        """
        SELECT id, title, message, announcement_time, active
        FROM announcements
        ORDER BY announcement_time DESC
        """
    )
    announcements = mycur.fetchall()

    mycur.close()
    myconn.close()

    return render_template("Manage_announcements.html", announcements=announcements)


@app.route("/delete_announcement/<int:id>")
def delete_announcement(id):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("DELETE FROM announcements WHERE id=%s", (id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return redirect(url_for("manage_announcements"))


@app.route("/toggle_announcement/<int:id>")
def toggle_announcement(id):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("UPDATE announcements SET active = NOT active WHERE id=%s", (id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return redirect(url_for("manage_announcements"))



@app.route('/announcements')
@app.route('/announcements')
def announcements():
    print("-> Route reached!")
    myconn = get_connection()
    print("-> Connected to database!")
    cursor = myconn.cursor()

    cursor.execute("SELECT id, title, message, announcement_time FROM announcements ORDER BY id DESC")
    announcements_list = cursor.fetchall()
    print(f"-> Fetched {len(announcements_list)} announcements")

    cursor.close()
    myconn.close()

    return render_template('Announcements.html', announcements=announcements_list)
# =========================================================
# VIEW & EDIT MENU - ADMIN
# =========================================================

@app.route("/view_menu")
def view_menu():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("SELECT id, dish_name, category, price, description, availability FROM menu_items")
    menu = mycur.fetchall()

    mycur.close()
    myconn.close()

    return render_template("View_menu.html", menu=menu)


@app.route("/delete_menu/<int:id>")
def delete_menu(id):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("DELETE FROM menu_items WHERE id=%s", (id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return redirect(url_for("view_menu"))


@app.route("/edit_menu/<int:id>", methods=["GET", "POST"])
def edit_menu(id):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    if request.method == "POST":
        dish_name = request.form["dish_name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]
        availability = request.form["availability"]

        myconn = get_connection()
        mycur = myconn.cursor()
        mycur.execute(
            """
            UPDATE menu_items
            SET dish_name=%s, category=%s, price=%s, description=%s, availability=%s
            WHERE id=%s
            """,
            (dish_name, category, price, description, availability, id)
        )
        myconn.commit()
        mycur.close()
        myconn.close()

        return redirect(url_for("view_menu"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("SELECT id, dish_name, category, price, description, availability FROM menu_items WHERE id=%s", (id,))
    item = mycur.fetchone()

    mycur.close()
    myconn.close()

    if item is None:
        return "<h2>Menu item not found</h2>"

    return render_template("Edit_menu.html", item=item)


# =========================================================
# SPLIT BILL ROUTES
# =========================================================

@app.route('/split-bill', methods=['POST'])
def split_bill_api():
    data = request.get_json()
    total_amount = float(data.get('total_amount', 0))
    num_people = int(data.get('num_people', 1))
    
    if num_people < 1:
        return jsonify({'error': 'Invalid number of people'}), 400
        
    per_person_share = round(total_amount / num_people, 2)
    
    return jsonify({
        'success': True,
        'total_amount': total_amount,
        'num_people': num_people,
        'per_person_share': per_person_share
    })


@app.route("/split_bill/<int:table_no>", methods=["GET", "POST"])
def split_bill_page(table_no):
    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("SELECT SUM(total) FROM cart WHERE session_id = %s", (str(table_no),))
    res = mycur.fetchone()
    grand_total = res[0] if res and res[0] else 0.00
    mycur.close()
    myconn.close()

    if request.method == 'POST':
        people = int(request.form.get('people', 2))
        split_type = request.form.get('split_type', 'equal')
        session["split_people"] = people
        session["split_type"] = split_type
        return redirect(url_for('split_bill_assignment', table_no=table_no, people=people, split_type=split_type))

    return render_template('Split_bill.html', grand_total=grand_total)


@app.route("/split_bill_assign/<int:table_no>/<int:people>/<string:split_type>", methods=["GET", "POST"])
def split_bill_assignment(table_no, people, split_type):
    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("SELECT id, menu_id, dish_name, price, quantity, total, notes FROM cart WHERE session_id = %s", (str(table_no),))
    cart = mycur.fetchall()
    mycur.close()
    myconn.close()
    
    grand_total = sum(float(item[5]) for item in cart) if cart else 0.00

    if request.method == 'POST':
        names = []
        for i in range(1, people + 1):
            name = request.form.get(f'person_{i}', f'Person {i}').strip()
            names.append(name if name else f"Person {i}")

        session["split_names"] = names

        if split_type == 'equal':
            return redirect(url_for("place_split_equal"))

        assignments = {}
        for item in cart:
            cart_id = item[0]
            assigned_person = request.form.get(f'item_{cart_id}')
            if not assigned_person:
                return "<h2>Please assign every item to a person.</h2>"
            assignments[str(cart_id)] = int(assigned_person)

        session["split_assignments"] = assignments
        return redirect(url_for("place_split_items"))

    return render_template('Split_bill_assign.html', people=people, split_type=split_type, cart=cart, grand_total=grand_total)


@app.route("/place_split_equal")
def place_split_equal():
    if "cart_session" not in session and "table_no" not in session:
        return "<h2>Your Cart is Empty</h2>"

    people = session.get("split_people")
    names = session.get("split_names")
    table_no = session.get("table_no", 1)
    session_id = str(table_no)

    if not people or not names:
        return redirect(url_for("home"))

    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("SELECT id, menu_id, dish_name, price, quantity, total, notes FROM cart WHERE session_id=%s", (session_id,))
    cart_items = mycur.fetchall()

    if not cart_items:
        mycur.close()
        myconn.close()
        return "<h2>Your Cart is Empty</h2>"

    grand_total = sum(float(item[5]) for item in cart_items)
    trackid = "SD" + str(random.randint(100000, 999999))

    mycur.execute(
        """
        INSERT INTO orders (table_no, total_amt, status, trackid)
        VALUES (%s, %s, %s, %s)
        """,
        (table_no, grand_total, "Pending", trackid)
    )
    order_id = mycur.lastrowid

    for item in cart_items:
        mycur.execute(
            """
            INSERT INTO order_items (order_id, menu_item_id, quantity, price, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (order_id, item[1], item[4], item[3], item[6])
        )

    base_amount = round(grand_total / people, 2)
    amounts = [base_amount for _ in range(people)]
    difference = round(grand_total - sum(amounts), 2)
    amounts[-1] = round(amounts[-1] + difference, 2)

    for i in range(people):
        mycur.execute(
            """
            INSERT INTO order_participants (order_id, participant_name, amount, payment_status)
            VALUES (%s, %s, %s, 'Pending')
            """,
            (order_id, names[i], amounts[i])
        )

    mycur.execute("DELETE FROM cart WHERE session_id=%s", (session_id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return render_template(
        "Split_order_success.html",
        order_id=order_id,
        trackid=trackid,
        grand_total=grand_total,
        names=names,
        amounts=amounts,
        table_no=table_no
    )


@app.route("/place_split_items")
def place_split_items():
    people = session.get("split_people")
    names = session.get("split_names")
    assignments = session.get("split_assignments")
    table_no = session.get("table_no", 1)
    session_id = str(table_no)

    if not people or not names or not assignments:
        return redirect(url_for("home"))

    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("SELECT id, menu_id, dish_name, price, quantity, total, notes FROM cart WHERE session_id=%s", (session_id,))
    cart_items = mycur.fetchall()

    if not cart_items:
        mycur.close()
        myconn.close()
        return "<h2>Your Cart is Empty</h2>"

    grand_total = sum(float(item[5]) for item in cart_items)
    trackid = "SD" + str(random.randint(100000, 999999))

    mycur.execute(
        """
        INSERT INTO orders (table_no, total_amt, status, trackid)
        VALUES (%s, %s, %s, %s)
        """,
        (table_no, grand_total, "Pending", trackid)
    )
    order_id = mycur.lastrowid

    participant_ids = []
    for name in names:
        mycur.execute(
            """
            INSERT INTO order_participants (order_id, participant_name, amount, payment_status)
            VALUES (%s, %s, 0, 'Pending')
            """,
            (order_id, name)
        )
        participant_ids.append(mycur.lastrowid)

    participant_amounts = [0.0 for _ in range(people)]

    for item in cart_items:
        cart_id, menu_id, dish_name, price, quantity, total, notes = item
        person_number = assignments.get(str(cart_id))
        if person_number is None:
            continue

        person_index = int(person_number) - 1
        participant_id = participant_ids[person_index]

        mycur.execute(
            """
            INSERT INTO order_items (order_id, menu_item_id, quantity, price, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (order_id, menu_id, quantity, price, notes)
        )
        order_item_id = mycur.lastrowid

        mycur.execute(
            """
            INSERT INTO order_item_participants (participant_id, order_item_id, quantity, amount)
            VALUES (%s, %s, %s, %s)
            """,
            (participant_id, order_item_id, quantity, total)
        )

        participant_amounts[person_index] += float(total)

    for i in range(people):
        mycur.execute(
            "UPDATE order_participants SET amount=%s WHERE id=%s",
            (round(participant_amounts[i], 2), participant_ids[i])
        )

    mycur.execute("DELETE FROM cart WHERE session_id=%s", (session_id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return render_template(
        "Split_order_success.html",
        order_id=order_id,
        trackid=trackid,
        grand_total=grand_total,
        names=names,
        amounts=participant_amounts,
        table_no=table_no
    )


# =========================================================
# CUSTOMER MENU & CART
# =========================================================

@app.route("/menu", defaults={"table_no": 1})
@app.route("/menu/<int:table_no>")
def menu(table_no):
    session["table_no"] = table_no

    search_query = request.args.get("search", "").strip()
    category_filter = request.args.get("category", "All")
    sort_by = request.args.get("sort", "default")

    myconn = get_connection()
    mycur = myconn.cursor()

    query = """
        SELECT id, dish_name, category, price, description, availability, image
        FROM menu_items
        WHERE availability='Available'
    """
    params = []

    if search_query:
        query += " AND dish_name LIKE %s"
        params.append(f"%{search_query}%")

    if category_filter and category_filter != "All":
        query += " AND category = %s"
        params.append(category_filter)

    if sort_by == "price_low":
        query += " ORDER BY price ASC"
    elif sort_by == "price_high":
        query += " ORDER BY price DESC"
    elif sort_by == "name_asc":
        query += " ORDER BY dish_name ASC"

    mycur.execute(query, tuple(params))
    menu_items = mycur.fetchall()

    mycur.close()
    myconn.close()

    return render_template(
        "Menu.html",
        menu=menu_items,
        search_query=search_query,
        category_filter=category_filter,
        sort_by=sort_by,
        table_no=table_no
    )


@app.route('/cart')
def cart():
    myconn = get_connection()
    mycur = myconn.cursor()

    session_id = str(session.get('table_no', 1))

    mycur.execute("""
        SELECT id, menu_id, dish_name, price, quantity, total 
        FROM cart 
        WHERE session_id = %s
    """, (session_id,))
    cart_items = mycur.fetchall()

    mycur.close()
    myconn.close()

    return render_template('Cart.html', cart_items=cart_items)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    myconn = get_connection()
    mycur = myconn.cursor()

    menu_id = request.form.get('menu_id')
    dish_name = request.form.get('dish_name')
    price = float(request.form.get('price', 0))
    quantity = int(request.form.get('quantity', 1))
    total = price * quantity
    session_id = str(session.get('table_no', 1))

    mycur.execute("""
        INSERT INTO cart (menu_id, dish_name, price, quantity, total, session_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (menu_id, dish_name, price, quantity, total, session_id))

    myconn.commit()
    mycur.close()
    myconn.close()

    return redirect(url_for('cart'))


@app.route('/remove_from_cart/<int:id>', methods=['GET', 'POST'])
def remove_from_cart(id):
    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("DELETE FROM cart WHERE id = %s", (id,))
    myconn.commit()

    mycur.close()
    myconn.close()

    return redirect(url_for('cart'))


@app.route('/order/<int:id>', methods=['GET', 'POST'])

def order(id):
    myconn = get_connection()
    mycur = myconn.cursor()

    if request.method == 'POST':
        table_no = session.get('table_no', 1)
        session_id = str(table_no)
        
        quantity = int(request.form.get('quantity', 1))
        spice_level = request.form.get('spice_level', 'Medium')
        notes = request.form.get('notes', '')

        mycur.execute("SELECT dish_name, price FROM menu_items WHERE id = %s", (id,))
        menu_item = mycur.fetchone()
        
        if not menu_item:
            mycur.close()
            myconn.close()
            return "Item not found", 404
            
        dish_name, unit_price = menu_item
        total_price = unit_price * quantity

        mycur.execute("""
            INSERT INTO cart (menu_id, dish_name, price, quantity, total, session_id, spice_level, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (id, dish_name, unit_price, quantity, total_price, session_id, spice_level, notes))
        
        myconn.commit()
        mycur.close()
        myconn.close()

        return redirect(url_for('cart'))

    mycur.execute("SELECT id, dish_name, category, price, description, availability, image FROM menu_items WHERE id = %s", (id,))
    food_item = mycur.fetchone()
    
    mycur.close()
    myconn.close()

    if not food_item:
        return "Item not found", 404

    return render_template('Order.html', item=food_item)


@app.route('/place_order', methods=['POST'])
def place_order():
    myconn = get_connection()
    mycur = myconn.cursor()

    table_no = session.get('table_no', 1)
    session_id = str(table_no)

    mycur.execute("""
        SELECT menu_id, dish_name, price, quantity, total, spice_level, notes 
        FROM cart 
        WHERE session_id = %s
    """, (session_id,))
    cart_items = mycur.fetchall()

    if not cart_items:
        mycur.close()
        myconn.close()
        return redirect(url_for('cart'))

    total_amt = sum(item[4] for item in cart_items)
    trackid = "SD" + str(uuid.uuid4())[:6].upper()

    mycur.execute("""
        INSERT INTO orders (table_no, total_amt, status, trackid)
        VALUES (%s, %s, 'Pending', %s)
    """, (table_no, total_amt, trackid))

    order_id = mycur.lastrowid

    for item in cart_items:
        menu_id, dish_name, price, quantity, total, spice_level, notes = item
        mycur.execute("""
            INSERT INTO order_items (order_id, menu_item_id, quantity, price, spice_level, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (order_id, menu_id, quantity, price, spice_level, notes))

    mycur.execute("DELETE FROM cart WHERE session_id = %s", (session_id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return render_template('Order_success.html', trackid=trackid)


# =========================================================
# ORDERS TRACKING & BILLING
# =========================================================

@app.route('/orders')
def orders():
    myconn = get_connection()
    mycur = myconn.cursor(dictionary=True)
    table_no = session.get('table_no', 1)

    mycur.execute("SELECT * FROM orders WHERE table_no = %s ORDER BY id DESC", (table_no,))
    user_orders = mycur.fetchall()

    mycur.close()
    myconn.close()

    return render_template('Orders.html', orders=user_orders)


@app.route('/track-order/<trackid>')
def track_order(trackid):
    myconn = get_connection()
    mycur = myconn.cursor(dictionary=True)
    
    mycur.execute("SELECT * FROM orders WHERE trackid = %s", (trackid,))
    order = mycur.fetchone()
    
    if not order:
        mycur.close()
        myconn.close()
        return "Order not found", 404
        
    mycur.execute("""
        SELECT oi.*, m.dish_name 
        FROM order_items oi 
        JOIN menu_items m ON oi.menu_item_id = m.id 
        WHERE oi.order_id = %s
    """, (order['id'],))
    items = mycur.fetchall()
    
    mycur.close()
    myconn.close()
    
    return render_template('Track_order.html', order=order, items=items)


@app.route("/bill/<int:order_id>")
def bill(order_id):
    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
    order = mycur.fetchone()

    if order is None:
        mycur.close()
        myconn.close()
        return "<h2>Invalid Order</h2>"

    mycur.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
    status = mycur.fetchone()

    if status is None or status[0] not in ["Delivered", "Completed"]:
        mycur.close()
        myconn.close()
        return "<h2>Bill is available only after your order is delivered.</h2>"

    mycur.execute(
        """
        SELECT menu_items.dish_name, order_items.quantity, order_items.price
        FROM order_items
        INNER JOIN menu_items ON order_items.menu_item_id = menu_items.id
        WHERE order_items.order_id=%s
        """,
        (order_id,)
    )
    items = mycur.fetchall()

    mycur.close()
    myconn.close()

    now = datetime.now()
    date = now.strftime("%d-%m-%Y")
    time = now.strftime("%I:%M %p")

    return render_template("Bill.html", order=order, items=items, date=date, time=time)


# =========================================================
# REPORTS & FEEDBACK
# =========================================================

@app.route("/sales_report")
def sales_report():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute("SELECT COALESCE(SUM(total_amt), 0) FROM orders WHERE status != 'Cancelled'")
    total_sales = mycur.fetchone()[0]

    mycur.execute("SELECT COUNT(*) FROM orders WHERE status != 'Cancelled'")
    total_orders = mycur.fetchone()[0]

    mycur.execute("SELECT COALESCE(SUM(total_amt), 0) FROM orders WHERE DATE(order_time) = CURDATE() AND status != 'Cancelled'")
    today_sales = mycur.fetchone()[0]

    mycur.execute("SELECT COUNT(*) FROM orders WHERE DATE(order_time) = CURDATE() AND status != 'Cancelled'")
    today_orders = mycur.fetchone()[0]

    mycur.close()
    myconn.close()

    return render_template(
        "Sales_report.html",
        total_sales=total_sales,
        total_orders=total_orders,
        today_sales=today_sales,
        today_orders=today_orders
    )


@app.route("/monthly_report")
def monthly_report():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()

    mycur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(total_amt), 0)
        FROM orders
        WHERE MONTH(order_time) = MONTH(CURRENT_DATE())
        AND YEAR(order_time) = YEAR(CURRENT_DATE())
        AND status != 'Cancelled'
        """
    )
    monthly_data = mycur.fetchone()
    mycur.close()
    myconn.close()

    return render_template(
        "Monthly_report.html",
        monthly_orders=monthly_data[0] or 0,
        monthly_revenue=monthly_data[1] or 0.0
    )


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    table_no = session.get("table_no", 1)

    if request.method == "POST":
        customer_name = request.form["customer_name"]
        rating = request.form["rating"]
        comments = request.form["comments"]

        myconn = get_connection()
        mycur = myconn.cursor()
        mycur.execute(
            """
            INSERT INTO customer_feedback (table_no, customer_name, rating, comments)
            VALUES (%s, %s, %s, %s)
            """,
            (table_no, customer_name, rating, comments)
        )
        myconn.commit()
        mycur.close()
        myconn.close()

        return redirect(url_for("feedback_success"))

    return render_template("Feedback.html", table_no=table_no)


@app.route("/feedback_success")
def feedback_success():
    return render_template("Feedback_success.html")


@app.route("/admin_feedback")
def admin_feedback():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("SELECT id, table_no, customer_name, rating, comments, feedback_time FROM customer_feedback ORDER BY id DESC")
    feedbacks = mycur.fetchall()
    mycur.close()
    myconn.close()

    return render_template("Admin_feedback.html", feedbacks=feedbacks)


# =========================================================
# CALL WAITER & WAITER REQUESTS
# =========================================================

@app.route("/call_waiter", defaults={"table_no": 1})
@app.route("/call_waiter/<int:table_no>")
def call_waiter(table_no):
    session["table_no"] = table_no

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("INSERT INTO waiter_calls (table_no, status) VALUES (%s, 'Pending')", (table_no,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Waiter Called</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f0fdf4; text-align: center; padding: 50px; color: #166534; }}
            .card {{ background: white; max-width: 400px; margin: auto; padding: 40px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }}
            h1 {{ color: #15803d; font-size: 28px; }}
            p {{ color: #4b5563; font-size: 16px; }}
            .btn {{ display: inline-block; margin-top: 20px; background: #2563eb; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; }}
            .btn:hover {{ background: #1d4ed8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎉 Waiter on the Way!</h1>
            <p>Staff has been notified for <strong>Table {table_no}</strong>. Someone will be with you shortly.</p>
            <a href="/menu/{table_no}" class="btn">Back to Menu</a>
        </div>
    </body>
    </html>
    """


@app.route("/waiter_requests")
def waiter_requests():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("SELECT id, table_no, status, request_time FROM waiter_calls ORDER BY id DESC")
    requests = mycur.fetchall()
    mycur.close()
    myconn.close()

    return render_template("waiter_requests.html", requests=requests)


@app.route("/resolve_waiter/<int:call_id>")
def resolve_waiter(call_id):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin"))

    myconn = get_connection()
    mycur = myconn.cursor()
    mycur.execute("DELETE FROM waiter_calls WHERE id=%s", (call_id,))
    myconn.commit()
    mycur.close()
    myconn.close()

    return redirect(url_for("waiter_requests"))


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
