# app/extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect

# 实例化扩展
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = 0

def init_extensions(app):
    """初始化所有 Flask 扩展"""
    db.init_app(app)
    bcrypt.init_app(app)
    CSRFProtect(app)

    login_manager.init_app(app)
    # 设置登录视图的端点名称
    login_manager.login_view = 'auth.login'
    # 登录提示信息
    login_manager.login_message = '请登录以访问此页面。'
    login_manager.login_message_category = 'info'

    # 用户加载器，必须注册到 Flask-Login
    from app.models import Admin
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Admin, int(user_id))