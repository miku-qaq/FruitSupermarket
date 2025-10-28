# app/__init__.py

from flask import Flask
from app.config import Config
from app.extensions import init_extensions

# 导入蓝图
from app.routes.auth import auth as auth_bp
# from app.routes.admin import admin as admin_bp # 通用管理主页，暂不创建
from app.routes.product import product as product_bp
from app.routes.member import member as member_bp # 新增会员管理蓝图
from app.routes.order import order as order_bp   # 新增订单管理蓝图
from app.routes.report import report as report_bp

def create_app(config_class=Config):
    """应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. 初始化扩展
    init_extensions(app)

    # 2. 注册蓝图
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(product_bp, url_prefix='/product')
    app.register_blueprint(member_bp, url_prefix='/member')
    app.register_blueprint(order_bp, url_prefix='/order')
    app.register_blueprint(report_bp, url_prefix='/report')

    # 3. 注册一个简单的首页路由
    @app.route('/')
    def index():
        from flask import redirect, url_for
        # 默认重定向到报表页
        return redirect(url_for('report.dashboard'))

    return app