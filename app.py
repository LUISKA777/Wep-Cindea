from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from supabase import create_client, Client
import os
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cindea-secret-key-12345')

# Supabase Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://cdhwvbbbboqkxzichrxt.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNkaHd2YmJiYm9xa3h6aWNocnh0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTAzNTAxOSwiZXhwIjoyMDk0NjExMDE5fQ.JBYZbzsbe7cAAxwZ6oUDW-XFUmpt0makEPmx5kNFz2A')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

@login_manager.user_loader
def load_user(user_id):
    # Verify user exists in Supabase
    res = supabase.table('users').select('*').eq('id', int(user_id)).single().execute()
    if res.data:
        return User(user_id=res.data['id'], username=res.data['username'])
    return None

# Helper to calculate vacancies
def get_vacancies_left(course):
    return course['total_vacancies'] - course['filled_vacancies']

# --- Public Routes ---

@app.route('/')
def index():
    res = supabase.table('courses').select('*').execute()
    courses = res.data if res.data else []
    # Add vacancies_left helper to the dictionaries for templates
    for c in courses:
        c['vacancies_left'] = lambda course=c: get_vacancies_left(course)

    # The template uses course.vacancies_left(), so we need a wrapper or a different way.
    # I'll modify the template logic slightly or just pass a function.
    # Actually, let's just add the value as a property.
    for c in courses:
        c['vacancies_left_val'] = get_vacancies_left(c)

    return render_template('index.html', courses=courses)

# Need to fix template to use vacancies_left_val instead of calling a method
# I will update index.html and other templates to use a property instead of a method.

@app.route('/enroll/<int:course_id>', methods=['GET', 'POST'])
def enroll(course_id):
    res = supabase.table('courses').select('*').eq('id', course_id).single().execute()
    if not res.data:
        return "Curso no encontrado", 404

    course = res.data
    if get_vacancies_left(course) <= 0:
        flash('Lo sentimos, este curso ya no tiene cupos disponibles.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')

        if not name or not phone:
            flash('Por favor complete todos los campos.', 'warning')
            return render_template('enroll.html', course=course)

        return redirect(url_for('schedule_appointment', course_id=course_id, name=name, phone=phone))

    return render_template('enroll.html', course=course)

@app.route('/schedule/<int:course_id>/<name>/<phone>', methods=['GET', 'POST'])
def schedule_appointment(course_id, name, phone):
    res = supabase.table('courses').select('*').eq('id', course_id).single().execute()
    if not res.data:
        return "Curso no encontrado", 404
    course = res.data

    available_dates = [date.today(), date.today().replace(day=date.today().day+1)]
    available_times = ['08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00']

    if request.method == 'POST':
        apt_date = request.form.get('date')
        apt_time = request.form.get('time')

        if not apt_date or not apt_time:
            flash('Por favor seleccione una fecha y hora.', 'warning')
            return render_template('appointment.html', course=course, name=name, phone=phone, dates=available_dates, times=available_times)

        # Create appointment in Supabase
        supabase.table('appointments').insert({
            'student_name': name,
            'student_phone': phone,
            'course_id': course_id,
            'appointment_date': apt_date,
            'appointment_time': apt_time
        }).execute()

        # Update course vacancies
        new_filled = course['filled_vacancies'] + 1
        supabase.table('courses').update({'filled_vacancies': new_filled}).eq('id', course_id).execute()

        flash('¡Cita de matrícula programada con éxito!', 'success')
        return redirect(url_for('index'))

    return render_template('appointment.html', course=course, name=name, phone=phone, dates=available_dates, times=available_times)

# --- Admin Routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        res = supabase.table('users').select('*').eq('username', username).eq('password', password).execute()

        if res.data and len(res.data) > 0:
            user_data = res.data[0]
            user = User(user_id=user_data['id'], username=user_data['username'])
            login_user(user)
            return redirect(url_for('admin_dashboard'))

        flash('Credenciales incorrectas.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    # Get courses
    courses_res = supabase.table('courses').select('*').execute()
    courses = courses_res.data if courses_res.data else []
    for c in courses:
        c['vacancies_left'] = get_vacancies_left(c)

    # Get appointments with course info (using a join or separate fetch)
    # Supabase allows joining by referencing the table name in select
    apt_res = supabase.table('appointments').select('*, courses(*)').order('created_at', ascending=False).execute()
    appointments = apt_res.data if apt_res.data else []

    # Flatten the course name for the template
    for a in appointments:
        a['course_name'] = a['courses']['name'] if a['courses'] else 'Unknown'

    return render_template('admin_dash.html', courses=courses, appointments=appointments)

@app.route('/admin/course/add', methods=['POST'])
@login_required
def add_course():
    name = request.form.get('name')
    description = request.form.get('description')
    vacancies = request.form.get('vacancies')

    if name and description and vacancies:
        supabase.table('courses').insert({
            'name': name,
            'description': description,
            'total_vacancies': int(vacancies),
            'filled_vacancies': 0
        }).execute()
        flash('Curso agregado exitosamente.', 'success')
    else:
        flash('Por favor complete todos los campos.', 'warning')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/course/delete/<int:id>')
@login_required
def delete_course(id):
    supabase.table('courses').delete().eq('id', id).execute()
    flash('Curso eliminado.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
