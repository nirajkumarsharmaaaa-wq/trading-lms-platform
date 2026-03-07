from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta


# --- Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here' # Change in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

import razorpay


# Replace with your actual Test API keys from the Razorpay Dashboard
RAZORPAY_KEY_ID = 'rzp_test_SOKXVlwNUiJxdn'
RAZORPAY_KEY_SECRET = 'm9f7agd1mUThm1Q5DoWzhK5o'

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# --- MONETIZATION & ENROLLMENT ROUTES (RAZORPAY) ---

@app.route('/course/<int:course_id>/enroll')
@login_required
def enroll(course_id):
    course = Course.query.get_or_404(course_id)
    
    # 1. Check if they are already enrolled
    existing_enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if existing_enrollment:
        flash('You are already enrolled in this course.')
        return redirect(url_for('view_course', course_id=course.id))
        
    # 2. If the course is FREE, enroll them instantly
    if course.price <= 0:
        new_enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
        db.session.add(new_enrollment)
        db.session.commit()
        flash(f'Successfully enrolled in {course.title}!')
        return redirect(url_for('view_course', course_id=course.id))
        
    # 3. If PAID, create a Razorpay Order and send it to the frontend
    amount_in_paise = int(course.price * 100) # Razorpay expects paise (₹1 = 100 paise)
    
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"receipt_course_{course.id}_user_{current_user.id}",
        "notes": {
            "course_id": course.id,
            "user_id": current_user.id
        }
    }
    
    # Generate the order on Razorpay's servers
    razorpay_order = razorpay_client.order.create(data=order_data)
    
    # Send the order details to a dedicated checkout page
    return render_template('razorpay_checkout.html', 
                           course=course, 
                           order=razorpay_order, 
                           key_id=RAZORPAY_KEY_ID)

@app.route('/verify_payment', methods=['POST'])
@login_required
def verify_payment():
    # Razorpay sends these hidden fields back after a successful UI payment
    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_signature = request.form.get('razorpay_signature')
    course_id = request.form.get('course_id') # We pass this in our HTML form
    
    # Verify the signature mathematically to prevent hacking
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        
        # Signature matches! Grant access to the course.
        new_enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
        db.session.add(new_enrollment)
        db.session.commit()
        
        flash('Payment successful! Your course is now unlocked.')
        return redirect(url_for('view_course', course_id=course_id))
        
    except razorpay.errors.SignatureVerificationError:
        flash('Payment verification failed. If money was deducted, it will be refunded automatically.')
        return redirect(url_for('dashboard'))

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    enrollments = db.relationship('Enrollment', backref='student', lazy=True)
    certificates = db.relationship('Certificate', backref='earner', lazy=True)
    
    #help ticket raised database
    
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Open') # Status: Open or Closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Link it back to the user
    user = db.relationship('User', backref=db.backref('tickets', lazy=True))

# --- Updated Database Models ---
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.String(50))
    price = db.Column(db.Float, default=0.0) 
    # NEW: 0 means Lifetime Access. 365 means 1 year.
    access_days = db.Column(db.Integer, default=0)
    # Link to chapters:
    chapters = db.relationship('Chapter', backref='course', lazy=True, cascade="all, delete-orphan")

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, default=0) # To sort chapters (e.g., 1, 2, 3)
    lessons = db.relationship('Lesson', backref='chapter', lazy=True, cascade="all, delete-orphan")

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapter.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500), nullable=False) # e.g., YouTube embed link
    order = db.Column(db.Integer, default=0) # To sort lessons within a chapter

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    # NEW: Track exactly when they bought it
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Started') # 'Started', 'In Progress', 'Completed'
    course = db.relationship('Course')

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course')

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from functools import wraps
from flask import abort

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Block users who aren't logged in OR aren't admins
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403) # 403 Forbidden error
        return f(*args, **kwargs)
    return decorated_function

# --- ADMIN ROUTES ---

@app.route('/admin/courses')
@login_required
@admin_required
def manage_courses():
    courses = Course.query.all()
    return render_template('admin_courses.html', courses=courses)

# --- ADMIN REVENUE DASHBOARD ---

@app.route('/admin/revenue')
@login_required
@admin_required
def admin_revenue():
    # Fetch all enrollments, newest first
    all_enrollments = Enrollment.query.order_by(Enrollment.id.desc()).all()
    
    paid_sales = []
    total_revenue = 0.0
    
    # Filter out free courses and calculate totals
    for enrollment in all_enrollments:
        if enrollment.course and enrollment.course.price > 0:
            paid_sales.append(enrollment)
            total_revenue += enrollment.course.price
            
    total_sales = len(paid_sales)
    
    return render_template('admin_revenue.html', 
                           sales=paid_sales, 
                           total_revenue=total_revenue, 
                           total_sales=total_sales)

# --- ADMIN USER MANAGEMENT ROUTES ---

@app.route('/admin/users')
@login_required
@admin_required
def manage_users():
    # Fetch all users from the database, ordered by newest first
    all_users = User.query.order_by(User.id.desc()).all()
    return render_template('admin_users.html', users=all_users)

@app.route('/admin/user/<int:user_id>/delete')
@login_required
@admin_required
def delete_user(user_id):
    # Prevent the admin from accidentally deleting themselves!
    if user_id == current_user.id:
        flash('You cannot delete your own admin account!')
        return redirect(url_for('manage_users'))
        
    user_to_delete = User.query.get_or_404(user_id)
    
    # Delete all their enrollments and certificates first to prevent database errors
    Enrollment.query.filter_by(user_id=user_id).delete()
    Certificate.query.filter_by(user_id=user_id).delete()
    
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f'User {user_to_delete.name} has been permanently deleted.')
    return redirect(url_for('manage_users'))

@app.route('/admin/courses/new', methods=['GET', 'POST'])
@login_required
@admin_required
def add_course():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        content_type = request.form.get('content_type')
        
        # Save the new course directly to the database
        new_course = Course(title=title, description=description, content_type=content_type)
        db.session.add(new_course)
        db.session.commit()
        
        flash('New course successfully published!')
        return redirect(url_for('manage_courses'))
        
    return render_template('admin_add_course.html')

@app.route('/admin/courses/delete/<int:id>')
@login_required
@admin_required
def delete_course(id):
    course_to_delete = Course.query.get_or_404(id)
    
    # We also need to delete any enrollments and certificates tied to this course
    Enrollment.query.filter_by(course_id=id).delete()
    Certificate.query.filter_by(course_id=id).delete()
    
    db.session.delete(course_to_delete)
    db.session.commit()
    
    flash('Course deleted successfully.')
    return redirect(url_for('manage_courses'))

# --- COURSE BUILDER & EDITING ROUTES ---

@app.route('/admin/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    # If the admin submits the form to update course details
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        course.content_type = request.form.get('content_type')
        course.price = request.form.get('price', 0.0, type=float)
        # ADD THIS NEW LINE:
        course.access_days = request.form.get('access_days', 0, type=int)
        
        db.session.commit()
        flash('Course details updated successfully!')
        return redirect(url_for('edit_course', course_id=course.id))
        
    return render_template('admin_edit_course.html', course=course)

@app.route('/admin/course/<int:course_id>/chapter/new', methods=['POST'])
@login_required
@admin_required
def add_chapter(course_id):
    title = request.form.get('title')
    order = request.form.get('order', 0, type=int)
    
    new_chapter = Chapter(course_id=course_id, title=title, order=order)
    db.session.add(new_chapter)
    db.session.commit()
    
    flash(f'Chapter "{title}" added!')
    return redirect(url_for('edit_course', course_id=course_id))

@app.route('/admin/chapter/<int:chapter_id>/lesson/new', methods=['POST'])
@login_required
@admin_required
def add_lesson(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    title = request.form.get('title')
    video_url = request.form.get('video_url')
    order = request.form.get('order', 0, type=int)
    
    new_lesson = Lesson(chapter_id=chapter_id, title=title, video_url=video_url, order=order)
    db.session.add(new_lesson)
    db.session.commit()
    
    flash(f'Lesson added to {chapter.title}!')
    return redirect(url_for('edit_course', course_id=chapter.course_id))

@app.route('/admin/chapter/<int:chapter_id>/delete')
@login_required
@admin_required
def delete_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    course_id = chapter.course_id
    db.session.delete(chapter)
    db.session.commit()
    flash('Chapter deleted.')
    return redirect(url_for('edit_course', course_id=course_id))

@app.route('/admin/lesson/<int:lesson_id>/delete')
@admin_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.chapter.course_id
    db.session.delete(lesson)
    db.session.commit()
    flash('Lesson deleted.')
    return redirect(url_for('edit_course', course_id=course_id))

# --- Authentication Routes ---

# --- Public Landing Page ---
@app.route('/')
def index():
    # If the user is already logged in, send them straight to their dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Otherwise, show the public landing page
    return render_template('index.html')

# --- Authentication Routes ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists. Please login.')
            return redirect(url_for('login'))
            
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('signup.html') # You will create this HTML file

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Get data from the form
        name = request.form.get('name')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        
        # Check if they are trying to change to an email that already exists
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('That email is already in use by another account.')
                return redirect(url_for('profile'))
                
        # Update user details
        current_user.name = name
        current_user.email = email
        
        # Only update password if they typed something in the new password box
        if new_password:
            from werkzeug.security import generate_password_hash
            current_user.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
            
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.')
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    # In a real app, this sends an email with a secure reset token
    if request.method == 'POST':
        flash('If an account exists, a password reset link has been sent to your email.')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Main Application Routes ---
@app.route('/dashboard')
@login_required
def dashboard():
    # Calculate analytics
    total_enrollments = Enrollment.query.filter_by(user_id=current_user.id).count()
    completed_certs = Certificate.query.filter_by(user_id=current_user.id).count()
    available_courses = Course.query.limit(5).all() # Show some recommended courses
    
    return render_template('dashboard.html', 
                           user=current_user, 
                           total_enrollments=total_enrollments, 
                           completed_certs=completed_certs,
                           available_courses=available_courses)
    
# --- STOREFRONT / BROWSE COURSES ---

@app.route('/browse')
@login_required
def browse():
    # Grab the search query from the URL (e.g., /browse?q=trading)
    search_query = request.args.get('q', '')
    
    if search_query:
        # Search both the title AND description (ilike makes it case-insensitive)
        courses = Course.query.filter(
            db.or_(
                Course.title.ilike(f'%{search_query}%'),
                Course.description.ilike(f'%{search_query}%')
            )
        ).all()
    else:
        # If no search, just show all published courses
        courses = Course.query.all()
    
    # Keep the smart button logic intact
    enrolled_course_ids = [enrollment.course_id for enrollment in current_user.enrollments]
    
    return render_template('browse.html', 
                           courses=courses, 
                           enrolled_course_ids=enrolled_course_ids, 
                           search_query=search_query)

@app.route('/my-courses')
@login_required
def my_courses():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    
    # Categorize courses
    started = [e for e in enrollments if e.status == 'Started']
    in_progress = [e for e in enrollments if e.status == 'In Progress']
    completed = [e for e in enrollments if e.status == 'Completed']
    
    return render_template('my_courses.html', started=started, in_progress=in_progress, completed=completed)

@app.route('/my-certificates')
@login_required
def my_certificates():
    certificates = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template('certificates.html', certificates=certificates)

# --- SUPPORT TICKET ROUTES ---

@app.route('/help', methods=['GET', 'POST'])
@login_required
def help_support():
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        new_ticket = Ticket(user_id=current_user.id, subject=subject, message=message)
        db.session.add(new_ticket)
        db.session.commit()
        
        flash('Your support ticket has been submitted! The admin will review it shortly.')
        return redirect(url_for('help_support'))
        
    # Fetch the user's past tickets so they can see the status
    my_tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.created_at.desc()).all()
    return render_template('help.html', tickets=my_tickets)

@app.route('/admin/tickets')
@login_required
@admin_required
def manage_tickets():
    # Fetch all tickets from all users
    all_tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    return render_template('admin_tickets.html', tickets=all_tickets)

@app.route('/admin/ticket/<int:ticket_id>/close')
@login_required
@admin_required
def close_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = 'Closed'
    db.session.commit()
    flash('Ticket marked as closed.')
    return redirect(url_for('manage_tickets'))


@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    # Global search across course titles and descriptions
    results = Course.query.filter(
        (Course.title.ilike(f'%{query}%')) | 
        (Course.description.ilike(f'%{query}%'))
    ).all()
    return render_template('search_results.html', query=query, results=results)

@app.route('/course/<int:course_id>')
@app.route('/course/<int:course_id>/lesson/<int:lesson_id>')
@login_required
def view_course(course_id, lesson_id=None):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    
    if not enrollment:
        flash('You must be enrolled to view this course.')
        return redirect(url_for('dashboard'))
        
    if enrollment.status == 'Started':
        enrollment.status = 'In Progress'
        db.session.commit()

    # Figure out which lesson to play
    current_lesson = None
    if lesson_id:
        current_lesson = Lesson.query.get_or_404(lesson_id)
    else:
        # If no lesson is specified in the URL, load the very first lesson of the first chapter
        if course.chapters and course.chapters[0].lessons:
            current_lesson = course.chapters[0].lessons[0]

    return render_template('course_view.html', course=course, enrollment=enrollment, current_lesson=current_lesson)
@app.route('/course/<int:course_id>/complete', methods=['POST'])
@login_required
def complete_course(course_id):
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    
    if enrollment and enrollment.status != 'Completed':
        enrollment.status = 'Completed'
        
        # Check if they already have a certificate to avoid duplicates
        existing_cert = Certificate.query.filter_by(user_id=current_user.id, course_id=course_id).first()
        if not existing_cert:
            new_cert = Certificate(user_id=current_user.id, course_id=course_id)
            db.session.add(new_cert)
            
        db.session.commit()
        flash(f'Congratulations! You completed "{enrollment.course.title}" and earned a new certificate!')
        
    return redirect(url_for('my_certificates'))


# ... (all your other routes above)

@app.route('/make-me-admin')
@login_required
def make_admin():
    current_user.is_admin = True
    db.session.commit()
    return 'You are now an admin! Go to <a href="/admin/courses">/admin/courses</a>'

# --- Initialization ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Creates the database tables automatically
    app.run(debug=True)