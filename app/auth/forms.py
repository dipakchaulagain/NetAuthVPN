from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import WebUIUser

class LoginForm(FlaskForm):
    """Login form"""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class ChangePasswordForm(FlaskForm):
    """Change password form"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters')
        ]
    )
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(),
            EqualTo('new_password', message='Passwords must match')
        ]
    )
    submit = SubmitField('Change Password')

class UserForm(FlaskForm):
    """Web UI user management form"""
    username = StringField(
        'Username',
        validators=[DataRequired(), Length(min=3, max=64)]
    )
    full_name = StringField(
        'Full Name',
        validators=[DataRequired(), Length(max=128)]
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(), Length(max=128)]
    )
    role = SelectField(
        'Role',
        choices=[
            ('Administrator', 'Administrator'),
            ('Operator', 'Operator'),
            ('Viewer', 'Viewer'),
            ('Auditor', 'Auditor')
        ],
        validators=[DataRequired()]
    )
    password = PasswordField(
        'Password',
        validators=[Length(min=8, message='Password must be at least 8 characters')]
    )
    active = BooleanField('Active')
    submit = SubmitField('Save')
    
    def __init__(self, user=None, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.user = user
    
    def validate_username(self, field):
        if self.user is None:
            # New user - check if username exists
            if WebUIUser.query.filter_by(username=field.data).first():
                raise ValidationError('Username already exists')
        else:
            # Editing existing user - check if username changed and conflicts
            if field.data != self.user.username:
                if WebUIUser.query.filter_by(username=field.data).first():
                    raise ValidationError('Username already exists')
    
    def validate_email(self, field):
        if self.user is None:
            # New user - check if email exists
            if WebUIUser.query.filter_by(email=field.data).first():
                raise ValidationError('Email already exists')
        else:
            # Editing existing user - check if email changed and conflicts
            if field.data != self.user.email:
                if WebUIUser.query.filter_by(email=field.data).first():
                    raise ValidationError('Email already exists')
