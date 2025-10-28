# app/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, DecimalField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError


# --- 认证表单 ---
class LoginForm(FlaskForm):
    """管理员登录表单"""
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('密码', validators=[DataRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')


# --- 商品管理表单 ---
class ProductForm(FlaskForm):
    """水果商品 CRUD 表单"""
    name = StringField('商品名称', validators=[DataRequired(), Length(max=100)])

    # DecimalField 用于价格
    retail_price = DecimalField('零售价 (元)', validators=[DataRequired(), NumberRange(min=0.01)])
    cost_price = DecimalField('成本价 (元)', validators=[DataRequired(), NumberRange(min=0.01)])

    unit = StringField('单位', validators=[DataRequired(), Length(max=20)])
    stock_quantity = IntegerField('当前库存量', validators=[DataRequired(), NumberRange(min=0)])

    # 类别字段需要动态填充，暂用占位符
    category_id = StringField('商品分类 ID', validators=[DataRequired()])

    submit = SubmitField('保存')


# --- 会员管理表单 ---
class MemberForm(FlaskForm):
    """会员信息 CRUD 表单"""
    name = StringField('会员姓名', validators=[DataRequired(), Length(max=50)])
    phone_number = StringField('手机号码', validators=[DataRequired(), Length(min=11, max=20)])
    # 折扣率：通常是 0 到 1 之间的数字（如 0.95 代表 95 折）
    discount_rate = DecimalField('会员折扣率 (例如 0.95)',
                                 validators=[DataRequired(), NumberRange(min=0.01, max=1.00)],
                                 default=1.00)

    submit = SubmitField('保存')


# --- 订单查询表单 ---
class OrderSearchForm(FlaskForm):
    """用于查询订单的表单"""
    order_id = StringField('订单号')
    member_phone = StringField('会员手机号')
    start_date = StringField('开始日期', validators=[Length(max=10)], description='格式: YYYY-MM-DD')
    end_date = StringField('结束日期', validators=[Length(max=10)], description='格式: YYYY-MM-DD')
    submit = SubmitField('查询')


# --- 分类管理视图 (B.2 商品分类管理) ---
class CategoryForm(FlaskForm):
    """分类 CRUD 表单 (定义在这里方便集中管理)"""
    name = StringField('分类名称', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('保存')


# 定义一个用于商品列表页搜索的表单
class ProductSearchForm(FlaskForm):
    # 搜索关键词：可以搜索名称或ID
    search_term = StringField('搜索', render_kw={"placeholder": "商品名称"})

    submit = SubmitField('搜索')


# 用于会员列表页搜索的表单
class MemberSearchForm(FlaskForm):
    search_term = StringField('手机号', render_kw={"placeholder": "会员手机号"})
    submit = SubmitField('搜索')
