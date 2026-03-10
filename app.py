from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, InventoryItem, StockMovement

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

LOW_STOCK_THRESHOLD = 5

@app.route("/init-db")
def init_db():
    db.create_all()
    return "Database initialized!"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return redirect(url_for("login"))


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful.", "success")

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("user_dashboard"))

    user_count = User.query.count()
    item_count = InventoryItem.query.count()
    low_stock_items = InventoryItem.query.filter(
        InventoryItem.quantity <= LOW_STOCK_THRESHOLD
    ).all()

    return render_template(
        "admin_dashboard.html",
        user_count=user_count,
        item_count=item_count,
        low_stock_items=low_stock_items
    )


# =========================
# USER DASHBOARD
# =========================
@app.route("/user/dashboard")
@login_required
def user_dashboard():
    items = InventoryItem.query.all()

    return render_template(
        "user_dashboard.html",
        items=items,
        threshold=LOW_STOCK_THRESHOLD
    )

# =========================
# MANAGE USERS
# =========================
@app.route("/admin/users")
@login_required
def manage_users():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("user_dashboard"))

    users = User.query.order_by(User.id.desc()).all()
    return render_template("users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@login_required
def add_user():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("user_dashboard"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "user").strip().lower()

    if not username or not password:
        flash("Username and password are required.", "danger")
        return redirect(url_for("manage_users"))

    if role not in ["admin", "user"]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("manage_users"))

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("Username already exists.", "warning")
        return redirect(url_for("manage_users"))

    hashed_password = generate_password_hash(password)

    user = User(
        username=username,
        password_hash=hashed_password,
        role=role
    )
    db.session.add(user)
    db.session.commit()

    flash("User added successfully.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("user_dashboard"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot delete your own admin account.", "warning")
        return redirect(url_for("manage_users"))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted successfully.", "success")
    return redirect(url_for("manage_users"))


# =========================
# INVENTORY
# =========================
@app.route("/inventory")
@login_required
def inventory():
    items = InventoryItem.query.order_by(InventoryItem.id.desc()).all()
    return render_template(
        "inventory.html",
        items=items,
        threshold=LOW_STOCK_THRESHOLD
    )


@app.route("/inventory/add", methods=["POST"])
@login_required
def add_item():
    if current_user.role != "admin":
        flash("Only admin can add items.", "danger")
        return redirect(url_for("inventory"))

    item_name = request.form.get("item_name", "").strip()
    category = request.form.get("category", "").strip()
    quantity = request.form.get("quantity", 0, type=int)
    unit = request.form.get("unit", "").strip()

    if not item_name or not category or not unit:
        flash("All item fields are required.", "danger")
        return redirect(url_for("inventory"))

    if quantity < 0:
        flash("Quantity cannot be negative.", "danger")
        return redirect(url_for("inventory"))

    item = InventoryItem(
        item_name=item_name,
        category=category,
        quantity=quantity,
        unit=unit
    )
    db.session.add(item)
    db.session.commit()

    flash("Item added successfully.", "success")
    return redirect(url_for("inventory"))


@app.route("/inventory/edit/<int:item_id>", methods=["POST"])
@login_required
def edit_item(item_id):
    if current_user.role != "admin":
        flash("Only admin can edit items.", "danger")
        return redirect(url_for("inventory"))

    item = InventoryItem.query.get_or_404(item_id)

    item_name = request.form.get("item_name", "").strip()
    category = request.form.get("category", "").strip()
    quantity = request.form.get("quantity", 0, type=int)
    unit = request.form.get("unit", "").strip()

    if not item_name or not category or not unit:
        flash("All item fields are required.", "danger")
        return redirect(url_for("inventory"))

    if quantity < 0:
        flash("Quantity cannot be negative.", "danger")
        return redirect(url_for("inventory"))

    item.item_name = item_name
    item.category = category
    item.quantity = quantity
    item.unit = unit

    db.session.commit()
    flash("Item updated successfully.", "success")
    return redirect(url_for("inventory"))


@app.route("/inventory/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_item(item_id):
    if current_user.role != "admin":
        flash("Only admin can delete items.", "danger")
        return redirect(url_for("inventory"))

    item = InventoryItem.query.get_or_404(item_id)

    db.session.delete(item)
    db.session.commit()

    flash("Item deleted successfully.", "success")
    return redirect(url_for("inventory"))


# =========================
# STOCK MOVEMENT
# Admin = IN and OUT
# User = OUT only
# =========================
@app.route("/inventory/move/<int:item_id>", methods=["POST"])
@login_required
def move_stock(item_id):
    item = InventoryItem.query.get_or_404(item_id)

    movement_type = request.form.get("movement_type", "").strip().upper()
    quantity = request.form.get("quantity", 0, type=int)
    remarks = request.form.get("remarks", "").strip()

    if quantity <= 0:
        flash("Quantity must be greater than zero.", "danger")
        return redirect(url_for("inventory"))

    # users can only decrease supplies
    if current_user.role == "user" and movement_type != "OUT":
        flash("Users can only decrease supplies.", "danger")
        return redirect(url_for("inventory"))

    if movement_type == "IN":
        if current_user.role != "admin":
            flash("Only admin can increase supplies.", "danger")
            return redirect(url_for("inventory"))
        item.quantity += quantity

    elif movement_type == "OUT":
        if item.quantity < quantity:
            flash("Not enough stock available.", "danger")
            return redirect(url_for("inventory"))
        item.quantity -= quantity

    else:
        flash("Invalid movement type.", "danger")
        return redirect(url_for("inventory"))

    movement = StockMovement(
        item_id=item.id,
        movement_type=movement_type,
        quantity=quantity,
        remarks=remarks,
        created_by=current_user.username
    )

    db.session.add(movement)
    db.session.commit()

    flash(f"Stock {movement_type} recorded successfully.", "success")
    return redirect(url_for("inventory"))


# =========================
# CREATE DEFAULT ADMIN
# =========================
@app.route("/create-admin")
def create_admin():
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        new_admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin"
        )
        db.session.add(new_admin)
        db.session.commit()
        return "Default admin created. Username: admin / Password: admin123"
    return "Admin already exists."


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)