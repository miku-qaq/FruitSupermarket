# run.py

from app import create_app
from app.extensions import db
from app.models import Admin

app = create_app()

@app.cli.command('init_db')
def init_db():
    """初始化数据库和创建表"""
    with app.app_context():
        # 删除现有表（仅用于开发环境）
        db.drop_all()
        # 创建所有表
        db.create_all()
        print("数据库表已创建！")

        # 创建一个初始管理员账号
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin', name='超级管理员')
            admin.set_password('123456') # 初始密码：123456，**生产环境中必须更改**
            db.session.add(admin)
            db.session.commit()
            print("已创建初始管理员账号：admin / 123456")
        else:
            print("管理员账号已存在。")

if __name__ == '__main__':
    # 建议使用 flask run 来运行应用
    # app.run(debug=True)
    print("请使用 'flask init_db' 初始化数据库，然后使用 'flask run' 运行应用。")