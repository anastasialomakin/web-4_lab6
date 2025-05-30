from flask import Flask, render_template, send_from_directory
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError
from models import db, Category, Image 
from auth import bp as auth_bp, init_login_manager
from courses import bp as courses_bp

app = Flask(__name__)
application = app

app.config.from_pyfile('config.py')

db.init_app(app)
migrate = Migrate(app, db)

init_login_manager(app)

@app.errorhandler(SQLAlchemyError)
def handle_sqlalchemy_error(err):
    error_msg = ('Возникла ошибка при подключении к базе данных. '
                 'Повторите попытку позже.')
    return f'{error_msg} (Подробнее: {err})', 500

app.register_blueprint(auth_bp)
app.register_blueprint(courses_bp)

@app.route('/')
def index():
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template(
        'index.html',
        categories=categories,
    )

@app.route('/images/<image_id>')
def image(image_id):
    img = db.get_or_404(Image, image_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               img.storage_filename)

if __name__ == '__main__':
    app.run(debug=True)


""" from models import db, User

existing_user = db.session.execute(db.select(User).filter_by(login='user2')).scalar_one_or_none()

if not existing_user:
    user = User(first_name='Алексей', last_name='Алексеев', middle_name='Михайлович', login='user2') 
    user.set_password('qwerty')
    db.session.add(user)
    db.session.commit()
    print("Пользователь 'user2' успешно создан.")
else:
    print("Пользователь 'user2' уже существует.")

exit() """