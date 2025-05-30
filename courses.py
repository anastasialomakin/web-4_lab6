from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from models import db, Course, Category, User, Review, Image
from tools import CoursesFilter, ImageSaver
from sqlalchemy import desc

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

def params():
    return { p: request.form.get(p) or None for p in COURSE_PARAMS }

def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }

@bp.route('/')
def index():
    courses = CoursesFilter(**search_params()).perform()
    pagination = db.paginate(courses)
    courses = pagination.items
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())

@bp.route('/new')
@login_required
def new():
    course = Course()
    categories = db.session.execute(db.select(Category)).scalars()
    users = db.session.execute(db.select(User)).scalars()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users,
                           course=course)

@bp.route('/create', methods=['POST'])
@login_required
def create():
    f = request.files.get('background_img')
    img = None
    course = Course()
    try:
        if f and f.filename:
            img = ImageSaver(f).save()

        image_id = img.id if img else None
        course = Course(**params(), background_image_id=image_id)
        db.session.add(course)
        db.session.commit()
    except IntegrityError as err:
        flash(f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})', 'danger')
        db.session.rollback()
        categories = db.session.execute(db.select(Category)).scalars()
        users = db.session.execute(db.select(User)).scalars()
        return render_template('courses/new.html',
                            categories=categories,
                            users=users,
                            course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))

@bp.route('/<int:course_id>')
def show(course_id):
    course = db.get_or_404(Course, course_id)
    latest_reviews = course.reviews.order_by(desc(Review.created_at)).limit(5).all()
    current_user_review = None
    if current_user.is_authenticated:
        current_user_review = course.reviews.filter_by(user_id=current_user.id).first()
    return render_template('courses/show.html',
                           course=course,
                           latest_reviews=latest_reviews,
                           current_user_review=current_user_review)


@bp.route('/<int:course_id>/reviews')
def all_reviews(course_id):
    course = db.get_or_404(Course, course_id)
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by', 'newest')  # newest, positive, negative

    reviews_query = course.reviews

    if sort_by == 'positive':
        reviews_query = reviews_query.order_by(Review.rating.desc(), Review.created_at.desc())
    elif sort_by == 'negative':
        reviews_query = reviews_query.order_by(Review.rating.asc(), Review.created_at.desc())
    else:  # newest (default)
        reviews_query = reviews_query.order_by(Review.created_at.desc())

    # пагинация
    pagination_obj = db.paginate(reviews_query, page=page, per_page=5, error_out=False)
    reviews_list = pagination_obj.items

    # оставлял ли текущий пользователь отзыв
    current_user_review_on_course = None
    if current_user.is_authenticated:
        current_user_review_on_course = course.reviews.filter_by(user_id=current_user.id).first()

    return render_template('courses/all_reviews.html',
                           course=course,
                           reviews=reviews_list,
                           pagination=pagination_obj,
                           sort_by=sort_by,
                           current_user_review=current_user_review_on_course)


@bp.route('/<int:course_id>/add_review', methods=['POST'])
@login_required
def add_review(course_id):
    course = db.get_or_404(Course, course_id)

    # защита от повторной отправки отзыва
    existing_review = course.reviews.filter_by(user_id=current_user.id).first()
    if existing_review:
        flash('Вы уже оставляли отзыв на этот курс.', 'warning')
        return redirect(request.referrer or url_for('courses.show', course_id=course.id))

    try:
        rating = int(request.form.get('rating'))
        text = request.form.get('text', '').strip()

        if not (0 <= rating <= 5):
            flash('Некорректное значение оценки.', 'danger')
            return redirect(request.referrer or url_for('courses.show', course_id=course.id))
        if not text:
            flash('Текст отзыва не может быть пустым.', 'danger')
            return redirect(request.referrer or url_for('courses.show', course_id=course.id))

        review = Review(
            rating=rating,
            text=text,
            course_id=course.id,
            user_id=current_user.id
        )
        db.session.add(review)

        # обновляем рейтинг курса
        course.rating_sum = (course.rating_sum or 0) + rating 
        course.rating_num = (course.rating_num or 0) + 1

        db.session.commit()
        flash('Спасибо за ваш отзыв!', 'success')
    except ValueError:
        flash('Ошибка в данных формы. Оценка должна быть числом.', 'danger')
        db.session.rollback()
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при добавлении отзыва: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('courses.show', course_id=course.id))