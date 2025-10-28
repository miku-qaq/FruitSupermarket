# app/models.py

from datetime import datetime
from app.extensions import db, bcrypt
from flask_login import UserMixin
from sqlalchemy.orm import relationship


# --- 1. 管理员表 ---
class Admin(db.Model, UserMixin):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 密码处理方法
    def set_password(self, password):
        """将密码哈希后存储"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """验证密码"""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Admin {self.username}>"


# --- 2. 商品分类表 ---
class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    # 关系：一个分类下有多个商品
    products = relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self):
        return f"<Category {self.name}>"


# --- 3. 水果商品表 ---
class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

    retail_price = db.Column(db.Numeric(10, 2), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)

    # 关系：一个商品可以出现在多个订单详情中
    order_items = relationship('OrderItem', backref='product', lazy='dynamic')

    def __repr__(self):
        return f"<Product {self.name}>"


# --- 4. 会员表 ---
class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    # 折扣率，如 0.95 (95折)
    discount_rate = db.Column(db.Numeric(5, 2), default=1.00)
    total_spent = db.Column(db.Numeric(10, 2), default=0.00)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系：一个会员可以有多个订单
    orders = relationship('Order', backref='member', lazy='dynamic')

    def __repr__(self):
        return f"<Member {self.name}>"


# --- 5. 销售订单表 ---
class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)  # 可为空，非会员订单

    original_amount = db.Column(db.Numeric(10, 2), default=0.00)  # 原价总额
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00)  # 折扣金额
    final_amount = db.Column(db.Numeric(10, 2), default=0.00)  # 最终支付金额

    # 状态：Completed, Deleted/Cancelled
    status = db.Column(db.String(20), default='Completed')

    # 关系：一个订单包含多个订单详情
    items = relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Order {self.id}>"


# --- 6. 订单详情表 ---
class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    # 存储销售时的价格和成本，用于利润分析和历史记录，防止商品调价影响历史数据
    price_at_sale = db.Column(db.Numeric(10, 2), nullable=False)
    cost_at_sale = db.Column(db.Numeric(10, 2), nullable=False)

    line_subtotal = db.Column(db.Numeric(10, 2), nullable=False)  # 行小计金额

    def __repr__(self):
        return f"<OrderItem {self.id} for Order {self.order_id}>"