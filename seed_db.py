from app import app, db, User, Course, Chapter, Lesson, Enrollment, Certificate
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def seed_data():
    with app.app_context():
        # 1. Clear the old database and create the new tables
        db.drop_all()
        db.create_all()

        # 2. Create an Admin account so you can test both student and admin views
        hashed_pw = generate_password_hash('password123', method='pbkdf2:sha256')
        admin_user = User(
            name='Niraj Sharma', 
            email='admin@example.com', 
            password_hash=hashed_pw, 
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()

        # ==========================================
        # COURSE 1: The Trading Masterclass (Multi-Chapter)
        # ==========================================
        course1 = Course(
            title='Advanced Price Action Trading Masterclass',
            description='A complete online trading course covering technical analysis, candlestick patterns, and risk management to help you master the markets.',
            content_type='Video'
        )
        db.session.add(course1)
        db.session.commit() # Commit to generate the course1.id

        # --- Chapter 1: Market Basics ---
        c1_chap1 = Chapter(course_id=course1.id, title='Market Basics & Candlesticks', order=1)
        db.session.add(c1_chap1)
        db.session.commit()

        lesson1 = Lesson(chapter_id=c1_chap1.id, title='Introduction to Candlestick Patterns', video_url='https://www.youtube.com/embed/tgbNymZ7vqY', order=1)
        lesson2 = Lesson(chapter_id=c1_chap1.id, title='Understanding Support & Resistance', video_url='https://www.youtube.com/embed/tgbNymZ7vqY', order=2)
        
        # --- Chapter 2: Advanced Strategies ---
        c1_chap2 = Chapter(course_id=course1.id, title='Advanced Price Action Strategies', order=2)
        db.session.add(c1_chap2)
        db.session.commit()

        lesson3 = Lesson(chapter_id=c1_chap2.id, title='Trading Trendline Breakouts', video_url='https://www.youtube.com/embed/tgbNymZ7vqY', order=1)
        lesson4 = Lesson(chapter_id=c1_chap2.id, title='Risk Management & Position Sizing', video_url='https://www.youtube.com/embed/tgbNymZ7vqY', order=2)

        db.session.add_all([lesson1, lesson2, lesson3, lesson4])

        # ==========================================
        # COURSE 2: YouTube Live Streaming & PC Build
        # ==========================================
        course2 = Course(
            title='Ultimate Streaming PC Build & YouTube Analytics',
            description='Learn how to build a high-performance PC for seamless live streaming and analyze your YouTube earnings and analytics for channel growth.',
            content_type='Video'
        )
        db.session.add(course2)
        db.session.commit()

        c2_chap1 = Chapter(course_id=course2.id, title='Hardware & PC Assembly', order=1)
        db.session.add(c2_chap1)
        db.session.commit()
        
        c2_lesson1 = Lesson(chapter_id=c2_chap1.id, title='Selecting the Best CPU for Streaming', video_url='https://www.youtube.com/embed/tgbNymZ7vqY', order=1)
        db.session.add(c2_lesson1)

        # ==========================================
        # COURSE 3: Build Your Own LMS Platform
        # ==========================================
        course3 = Course(
            title='Build a Website like CodeWithHarry',
            description='Learn Python, Flask, and Bootstrap to build your own custom Learning Management System from scratch.',
            content_type='Video'
        )
        db.session.add(course3)
        db.session.commit()

        # 3. Create Dummy Enrollments for the Admin user to test the dashboard
        enrollment1 = Enrollment(user_id=admin_user.id, course_id=course1.id, status='In Progress')
        enrollment2 = Enrollment(user_id=admin_user.id, course_id=course2.id, status='Started')
        db.session.add_all([enrollment1, enrollment2])
        
        db.session.commit()
        
        print("✅ Database successfully rebuilt with Chapters and Lessons!")
        print("Login with Email: admin@example.com | Password: password123")

if __name__ == '__main__':
    seed_data()