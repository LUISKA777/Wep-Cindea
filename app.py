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

def format_date_spanish(date_str):
    if not date_str:
        return ""
    # date_str is usually 'YYYY-MM-DD'
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        days = [
            "Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"
        ]
        months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        return f"{days[dt.weekday()]}, {dt.day} de {months[dt.month-1]} de {dt.year}"
    except Exception:
        return date_str

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

    # Get administrative settings
    settings = sb_get('settings', 'select=*')
    s = settings[0] if (isinstance(settings, list) and len(settings) > 0) else {
        'work_days': '0,1,2,3,4',
        'start_time': '08:00',
        'end_time': '16:00',
        'lunch_start': '12:00',
        'lunch_end': '13:00',
        'apt_duration': '60'
    }

    today = date.today()

    # Filter dates based on working days
    work_days = [int(d) for d in s['work_days'].split(',')]
    available_dates = []
    for i in range(14): # Look ahead 14 days to find enough working days
        d = today + timedelta(days=i)
        if d.weekday() in work_days:
            available_dates.append(d)
        if len(available_dates) >= 7: # Limit to 7 available working days
            break

    # Generate time slots based on start, end, duration and lunch break
    available_times = []
    start_h, start_m = map(int, s['start_time'].split(':'))
    end_h, end_m = map(int, s['end_time'].split(':'))
    lunch_start_h, lunch_start_m = map(int, s['lunch_start'].split(':'))
    lunch_end_h, lunch_end_m = map(int, s['lunch_end'].split(':'))
    duration = int(s['apt_duration'])

    current_total_min = start_h * 60 + start_m
    end_total_min = end_h * 60 + end_m
    lunch_start_total = lunch_start_h * 60 + lunch_start_m
    lunch_end_total = lunch_end_h * 60 + lunch_end_m

    while current_total_min + duration <= end_total_min:
        # Check if slot overlaps with lunch break
        slot_end = current_total_min + duration
        if not (slot_end <= lunch_start_total or current_total_min >= lunch_end_total):
            # Overlaps with lunch
            current_total_min = lunch_end_total
            continue

        h, m = divmod(current_total_min, 60)
        available_times.append(f"{h:02d}:{m:02d}")
        current_total_min += duration

    # --- Logic to filter occupied slots ---
    occupied_slots = sb_get('appointments', f'course_id=eq.{course_id}&select=appointment_date,appointment_time')
    taken = []
    if isinstance(occupied_slots, list):
        for slot in occupied_slots:
            date_val = slot['appointment_date'].split('T')[0] if 'T' in slot['appointment_date'] else slot['appointment_date']
            taken.append([date_val, slot['appointment_time']])

    # Format dates for template
    formatted_dates = []
    for d in available_dates:
        formatted_dates.append({
            'value': d.isoformat(),
            'label': format_date_spanish(d.isoformat())
        })

    if request.method == 'POST':
        apt_date = request.form.get('date')
        apt_time = request.form.get('time')
        if not apt_date or not apt_time:
            flash('Por favor seleccione una fecha y hora.', 'warning')
            return render_template('appointment.html', course=course, name=name, phone=phone, dates=formatted_dates, times=available_times, taken=taken)

        apt_data = sb_post('appointments', {
            'student_name': name,
            'student_phone': phone,
            'course_id': course_id,
            'appointment_date': apt_date,
            'appointment_time': apt_time
        })
        sb_patch('courses', 'id', course_id, {'filled_vacancies': course['filled_vacancies'] + 1})

        flash('¡Cita de matrícula programada con éxito!', 'success')

        apt_id = apt_data.get('id') if isinstance(apt_data, dict) else (apt_data[0].get('id') if isinstance(apt_data, list) and apt_data else None)
        if apt_id:
            return redirect(url_for('appointment_receipt', apt_id=apt_id))
        return redirect(url_for('index'))

    return render_template('appointment.html', course=course, name=name, phone=phone, dates=formatted_dates, times=available_times, taken=taken)

@app.route('/appointment/receipt/<int:apt_id>')
def appointment_receipt(apt_id):
    apt = sb_get('appointments', f'id=eq.{apt_id}&select=*,courses(name)')
    if not apt or len(apt) == 0:
        return "Cita no encontrada", 404

    apt_details = apt[0]
    apt_details['course_name'] = apt_details.get('courses', {}).get('name', 'Unknown') if apt_details.get('courses') else 'Unknown'

    # Format dates for the receipt
    if 'appointment_date' in apt_details:
        apt_details['appointment_date'] = format_date_spanish(apt_details['appointment_date'].split('T')[0])

    return render_template('receipt.html', appointment=apt_details)

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
        # Format dates for display
        if 'appointment_date' in a:
            a['appointment_date'] = format_date_spanish(a['appointment_date'].split('T')[0])
        if 'created_at' in a:
            a['created_at'] = a['created_at'].split('T')[0] + ' ' + a['created_at'].split('T')[1][:5] if 'T' in a['created_at'] else a['created_at']

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

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        settings_data = {
            'work_days': request.form.get('work_days'), # e.g. "1,2,3,4,5" (Mon-Fri)
            'start_time': request.form.get('start_time'), # "08:00"
            'end_time': request.form.get('end_time'), # "16:00"
            'lunch_start': request.form.get('lunch_start'), # "12:00"
            'lunch_end': request.form.get('lunch_end'), # "13:00"
            'apt_duration': request.form.get('apt_duration', '60') # "60" minutes
        }

        # Get existing settings safely
        current = sb_get('settings', 'select=*')
        if isinstance(current, list) and len(current) > 0:
            sb_patch('settings', 'id', current[0]['id'], settings_data)
        else:
            # If it's a new table or empty, we post.
            # Note: If table doesn't exist, this will still fail via API, but not crash the server
            sb_post('settings', settings_data)

        flash('Configuración actualizada exitosamente.', 'success')
        return redirect(url_for('admin_settings'))

    settings = sb_get('settings', 'select=*')
    s = settings[0] if (isinstance(settings, list) and len(settings) > 0) else {
        'work_days': '0,1,2,3,4',
        'start_time': '08:00',
        'end_time': '16:00',
        'lunch_start': '12:00',
        'lunch_end': '13:00',
        'apt_duration': '60'
    }
    return render_template('admin_settings.html', settings=s)

@app.route('/admin/course/delete/<int:id>')
@login_required
def delete_course(id):
    sb_delete('courses', 'id', id)
    flash('Curso eliminado.', 'success')
    return redirect(url_for('admin_dashboard'))

handler = app

if __name__ == '__main__':
    app.run(debug=True)
