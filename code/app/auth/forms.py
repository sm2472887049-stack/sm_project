from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models.user import User

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 80)])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 80)])
    email = StringField('邮箱', validators=[DataRequired(), Email(), Length(1, 120)])
    password = PasswordField('密码', validators=[
        DataRequired(),
        Length(min=6, message='密码长度至少为6个字符')
    ])
    password2 = PasswordField('确认密码', validators=[
        DataRequired(),
        EqualTo('password', message='两次输入的密码不一致')
    ])
    admin_code = StringField('管理员注册码', validators=[Optional(), Length(1, 20)])
    submit = SubmitField('注册')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('用户名已被使用')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('邮箱已被注册') 