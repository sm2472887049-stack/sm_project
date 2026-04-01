from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
from .forms import LoginForm, RegistrationForm
from app.models.user import User, UserRole
from app import db

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('用户名或密码错误', 'error')
            return redirect(url_for('auth.login'))
        
        login_user(user)
        user.update_last_login()
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # 判断是否是管理员注册
        role = UserRole.USER
        if form.admin_code.data:
            admin_code = current_app.config.get('ADMIN_REGISTRATION_CODE')
            if admin_code and form.admin_code.data == admin_code:
                role = UserRole.ADMIN
            else:
                flash('管理员注册码无效', 'error')
                return redirect(url_for('auth.register'))

        user = User(
            username=form.username.data, 
            email=form.email.data,
            role=role
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('注册成功！请登录', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('注册失败，请稍后重试', 'error')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出登录', 'success')
    return redirect(url_for('main.index'))

@auth.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

@auth.route('/settings')
@login_required
def settings():
    return render_template('auth/settings.html')

@auth.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    email = request.form.get('email')
    if not email:
        flash('邮箱地址不能为空', 'error')
        return redirect(url_for('auth.settings'))
    
    try:
        current_user.email = email
        db.session.commit()
        flash('个人信息更新成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash('更新失败，请稍后重试', 'error')
    
    return redirect(url_for('auth.settings'))

@auth.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('请填写所有密码字段', 'error')
        return redirect(url_for('auth.settings'))
    
    if not current_user.check_password(current_password):
        flash('当前密码错误', 'error')
        return redirect(url_for('auth.settings'))
    
    if new_password != confirm_password:
        flash('两次输入的新密码不一致', 'error')
        return redirect(url_for('auth.settings'))
    
    if len(new_password) < 6:
        flash('新密码长度至少为6个字符', 'error')
        return redirect(url_for('auth.settings'))
    
    try:
        current_user.set_password(new_password)
        db.session.commit()
        flash('密码修改成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash('密码修改失败，请稍后重试', 'error')
    
    return redirect(url_for('auth.settings')) 