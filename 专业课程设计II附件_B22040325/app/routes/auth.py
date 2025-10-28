# app/routes/auth.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.models import Admin
from app.extensions import db
from app.forms import LoginForm  # 稍后创建

# 创建认证蓝图
auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # 如果用户已登录，则直接重定向到主页
    if current_user.is_authenticated:
        return redirect(url_for('report.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        # 1. 查找用户
        admin = Admin.query.filter_by(username=form.username.data).first()

        # 2. 验证用户和密码
        if admin is None or not admin.check_password(form.password.data):
            flash('无效的用户名或密码。', 'danger')
            return redirect(url_for('.login'))

        # 3. 登录用户
        login_user(admin, remember=form.remember_me.data)

        # 处理 next 参数（用户试图访问受保护页面时被重定向到登录页）
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)

        flash('登录成功！', 'success')
        # 默认重定向到报表页
        return redirect(url_for('report.dashboard'))

    return render_template('auth/login.html', form=form, title='管理员登录')


@auth.route('/logout')
def logout():
    logout_user()
    flash('您已成功退出登录。', 'info')
    return redirect(url_for('.login'))

# 提示：我们不提供注册功能，管理员账号通过 run.py 的 init_db 命令初始化。