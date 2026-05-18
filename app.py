from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import os
import requests as http
from datetime import date, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cindea-secret-key-12345')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://cdhwvbbbboqkxzichrxt.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNkaHd2YmJiYm9xa3h6aWNocnh0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTAzNTAxOSwiZXhwIjoyMDk0NjExMDE5fQ.JBYZbzsbe7cAAxwZ6oUDW-XFUmpt0makEPmx5kNFz2A')

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

def sb_get(table, params=''):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    r = http.get(url, headers=HEADERS)
    return r.json()

def sb_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = http.post(url, json=data, headers=HEADERS)
    return r.json()

def sb_patch(table, match_col, match_val, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    r = http.patch(url, json=data, headers=HEADERS)
    return r

def sb_delete(table, match_col, match_val):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    r = http.delete(url, headers=HEADERS)
    return r

class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

@login_manager.user_loader
def load_user(user_id):
    data = sb_get('users', f'id=eq.{user_id}&select=*')
    if data and len(data) > 0:
        return User(user_id=data[0]['id'], username=data[0]['username'])
    return None

def get_vacancies_left(course):
    val = course['total_vacancies'] - course['filled_vacancies']
    course['vacancies_left_val'] = val
    course['vacancies_left'] = val
    return course

@app.route('/')
def index():
    courses = sb_get('courses', 'select=*')
    if not isinstance(courses, list):
        courses = []
    for c in courses:
        get_vacancies_left(c)
    return render_template('index.html', courses=courses)

@app.route('/enroll/<int:course_id>', methods=['GET', 'POST'])
def enroll(course_id):
    data = sb_get('courses', f'id=eq.{course_id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]
    get_vacancies_left(course)

    if course['vacancies_left'] <= 0:
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
    data = sb_get('courses', f'id=eq.{course_id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]

    today = date.today()
    available_dates = [today + timedelta(days=i) for i in range(7)]
    available_times = ['08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00']

    if request.method == 'POST':
        apt_date = request.form.get('date')
        apt_time = request.form.get('time')
        if not apt_date or not apt_time:
            flash('Por favor seleccione una fecha y hora.', 'warning')
            return render_template('appointment.html', course=course, name=name, phone=phone, dates=available_dates, times=available_times)

        sb_post('appointments', {
            'student_name': name,
            'student_phone': phone,
            'course_id': course_id,
            'appointment_date': apt_date,
            'appointment_time': apt_time
        })
        sb_patch('courses', 'id', course_id, {'filled_vacancies': course['filled_vacancies'] + 1})

        flash('¡Cita de matrícula programada con éxito!', 'success')
        return redirect(url_for('index'))

    return render_template('appointment.html', course=course, name=name, phone=phone, dates=available_dates, times=available_times)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        data = sb_get('users', f'username=eq.{username}&password=eq.{password}&select=*')
        if data and len(data) > 0:
            user = User(user_id=data[0]['id'], username=data[0]['username'])
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
    courses = sb_get('courses', 'select=*')
    if not isinstance(courses, list):
        courses = []
    for c in courses:
        get_vacancies_left(c)

    appointments = sb_get('appointments', 'select=*,courses(name)&order=created_at.desc')
    if not isinstance(appointments, list):
        appointments = []
    for a in appointments:
        a['course_name'] = a.get('courses', {}).get('name', 'Unknown') if a.get('courses') else 'Unknown'

    return render_template('admin_dash.html', courses=courses, appointments=appointments)

@app.route('/admin/course/add', methods=['POST'])
@login_required
def add_course():
    name = request.form.get('name')
    description = request.form.get('description')
    vacancies = request.form.get('vacancies')
    if name and description and vacancies:
        sb_post('courses', {
            'name': name,
            'description': description,
            'total_vacancies': int(vacancies),
            'filled_vacancies': 0
        })
        flash('Curso agregado exitosamente.', 'success')
    else:
        flash('Por favor complete todos los campos.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/course/delete/<int:id>')
@login_required
def delete_course(id):
    sb_delete('courses', 'id', id)
    flash('Curso eliminado.', 'success')
    return redirect(url_for('admin_dashboard'))

handler = app

if __name__ == '__main__':
    app.run(debug=True)
