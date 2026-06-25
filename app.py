from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import os
import requests as http
from datetime import date, timedelta, datetime, time
import pytz
from urllib.parse import unquote
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import csv
import io
from weasyprint import HTML, CSS


def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            flash('Acceso denegado. Se requieren privilegios de superadministrador.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cindea-secret-key-12345')

CR_TZ = pytz.timezone('America/Costa_Rica')

ENROLLMENT_KEYWORDS = {
    'Primer nivel': {
        'cycle_id': 'primaria',
        'keywords': ['primaria', '1ero', '2do', '3ero', '4to', '5to', '6to', '1ro', '2do', '3ro', '4to', '5to', '6to', 'primer nivel']
    },
    'Segundo nivel': {
        'cycle_id': 'segundo_nivel',
        'keywords': ['2do ciclo', 'segundo ciclo', 'segundo', '7mo', '8vo', '9no', '7vo', '8vo', '9no', 'sétimo', 'octavo', 'noveno', 'segundo nivel']
    },
    'Tercer nivel': {
        'cycle_id': 'tercer_nivel',
        'keywords': ['3er ciclo', 'tercer ciclo', 'tercer', '10mo', '11vo', '10vo', 'décimo', 'undécimo', 'tercer nivel']
    }
}

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
            "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
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
    try:
        r = http.get(url, headers=HEADERS)
        if r.status_code >= 400:
            print(f"Supabase Get Error {r.status_code}: {r.text}")
            return {'error': r.status_code, 'text': r.text}
        return r.json()
    except Exception as e:
        print(f"HTTP Request Exception: {e}")
        return {'error': 'EXCEPTION', 'text': str(e)}

def sb_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = http.post(url, json=data, headers=HEADERS)
    if r.status_code >= 400:
        print(f"Supabase Post Error {r.status_code}: {r.text}")
        return r  # devuelve response para chequear status_code
    try:
        return r.json()
    except Exception:
        return r

def sb_patch(table, match_col, match_val, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    r = http.patch(url, json=data, headers=HEADERS)
    if r.status_code >= 400:
        print(f"Supabase Patch Error {r.status_code}: {r.text}")
    return r

def sb_delete(table, match_col, match_val):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    # Custom headers for delete to avoid potential 'return=representation' issues
    delete_headers = HEADERS.copy()
    delete_headers['Prefer'] = 'return=minimal'
    r = http.delete(url, headers=delete_headers)
    return r

def user_has_appointment(cedula):
    # Check specific course appointments
    apt = sb_get('appointments', f'student_cedula=eq.{cedula}&select=id')
    if isinstance(apt, list) and len(apt) > 0:
        return True

    # Check general enrollment appointments
    mat_apt = sb_get('matricula_appointments', f'student_cedula=eq.{cedula}&select=id')
    if isinstance(mat_apt, list) and len(mat_apt) > 0:
        return True

    return False


# Role-based access control decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_admin or current_user.is_superadmin):
            flash('Acceso denegado. Se requieren privilegios de administrador o superadministrador.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_student:
            flash('Acceso denegado. Se requiere cuenta de estudiante.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def professor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_professor:
            flash('Acceso denegado. Se requiere cuenta de profesor.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


class User(UserMixin):
    def __init__(self, id, username, role='student', first_name=None, last_name=None,
                 cedula=None, email=None, phone=None, level=None):
        self.id = id
        self.username = username
        self.role = role
        self.first_name = first_name
        self.last_name = last_name
        self.cedula = cedula
        self.email = email
        self.phone = phone
        self.level = level

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_professor(self):
        return self.role == 'professor'

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Unified login for all roles

@login_manager.user_loader
def load_user(user_id):
    data = sb_get('users', f'id=eq.{user_id}&select=*')
    if data and len(data) > 0:
        user_data = data[0]
        return User(
            id=user_data['id'],
            username=user_data['username'],
            role=user_data.get('role', 'student'),
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            cedula=user_data.get('cedula'),
            email=user_data.get('email'),
            phone=user_data.get('phone'),
            level=user_data.get('level')
        )
    return None

def get_vacancies_left(course):
    val = course['total_vacancies'] - course['filled_vacancies']
    course['vacancies_left_val'] = val
    course['vacancies_left'] = val
    return course

@app.route('/')
def index():
    selected_level = request.args.get('level')
    selected_cycle = request.args.get('cycle')
    courses = sb_get('courses', 'select=*')
    if not isinstance(courses, list):
        courses = []

    # Filtro rapido por ciclo (Primaria / Secundaria)
    PRIMARIA_LEVELS = ['Primaria Aprobada', 'Solo saber leer y escribir']
    SECUNDARIA_LEVELS = ['Secundaria Incompleta', 'Secundaria Completa']

    if selected_cycle == 'primaria':
        courses = [c for c in courses if c.get('required_levels') and
                   any(lvl in c['required_levels'].split(',') for lvl in PRIMARIA_LEVELS)]
    elif selected_cycle == 'secundaria':
        courses = [c for c in courses if c.get('required_levels') and
                   any(lvl in c['required_levels'].split(',') for lvl in SECUNDARIA_LEVELS)]
    # Filter courses by educational level if a filter is selected
    elif selected_level:
        courses = [c for c in courses if c.get('required_levels') and selected_level in c['required_levels'].split(',')]

    today_str = datetime.now(CR_TZ).date().isoformat()

    # Filter out hidden courses for public view
    courses = [c for c in courses if not c.get('hidden', False)]

    for c in courses:
        get_vacancies_left(c)
        # Check if course is closed
        closing_date = c.get('closing_date')
        if closing_date and today_str > closing_date:
            c['is_closed'] = True
        else:
            c['is_closed'] = False

    return render_template('index.html', courses=courses, selected_level=selected_level, selected_cycle=selected_cycle)

@app.route('/posts')
def posts():
    res = sb_get('posts', 'select=*&order=created_at.desc')
    if isinstance(res, dict) and 'error' in res:
        return f"Error de Supabase ({res['error']}): {res['text']}", 500
    if not isinstance(res, list):
        res = []
    return render_template('posts.html', posts=res)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    res = sb_get('posts', f'id=eq.{post_id}&select=*')
    if isinstance(res, dict) and 'error' in res:
        return f"Error de Supabase ({res['error']}): {res['text']}", 500
    if not res or len(res) == 0:
        return "Post no encontrado", 404
    post = res[0]
    return render_template('post_detail.html', post=post)

@app.route('/enroll/<int:course_id>', methods=['GET', 'POST'])
def enroll(course_id):
    data = sb_get('courses', f'id=eq.{course_id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]
    get_vacancies_left(course)

    # Check if course is closed by date
    today_str = datetime.now(CR_TZ).date().isoformat()
    closing_date = course.get('closing_date')
    if closing_date and today_str > closing_date:
        flash('Lo sentimos, el periodo de inscripción para este curso ha finalizado.', 'danger')
        return redirect(url_for('index'))

    if course['vacancies_left'] <= 0:
        flash('Lo sentimos, este curso ya no tiene cupos disponibles.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cedula = request.form.get('cedula', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name or not cedula or not phone:
            flash('Por favor complete todos los campos.', 'warning')
            return render_template('enroll.html', course=course)

        if user_has_appointment(cedula):
            flash('Usted ya tiene una cita programada. Por favor, contacte a la administración si necesita realizar un cambio.', 'danger')
            return redirect(url_for('index'))

        return redirect(url_for('schedule_appointment', course_id=course_id, name=name, cedula=cedula, phone=phone))

    return render_template('enroll.html', course=course)

@app.route('/schedule/<int:course_id>/<name>/<cedula>/<phone>', methods=['GET', 'POST'])
def schedule_appointment(course_id, name, cedula, phone):
    name = unquote(name)
    cedula = unquote(cedula)
    phone = unquote(phone)
    data = sb_get('courses', f'id=eq.{course_id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]

    # Get global settings
    global_settings_data = sb_get('settings', 'select=*')
    global_s = global_settings_data[0] if (isinstance(global_settings_data, list) and len(global_settings_data) > 0) else {}

    # Get course-specific settings with defaults
    s = {
        'work_days': course.get('work_days') or global_s.get('work_days') or '0,1,2,3,4',
        'start_time': course.get('start_time') or global_s.get('start_time') or '08:00',
        'end_time': course.get('end_time') or global_s.get('end_time') or '16:00',
        'lunch_start': course.get('lunch_start') or global_s.get('lunch_start') or '12:00',
        'lunch_end': course.get('lunch_end') or global_s.get('lunch_end') or '13:00',
        'apt_duration': course.get('apt_duration') or global_s.get('apt_duration') or '60'
    }

    now_cr = datetime.now(CR_TZ)
    today = now_cr.date()
    current_time_str = now_cr.strftime('%H:%M')
    vacancies_left = course['total_vacancies'] - course['filled_vacancies']

    # Determine start date for slot generation
    opening_date_str = course.get('opening_date')
    global_opening_date_str = global_s.get('global_opening_date')

    start_date = today
    if opening_date_str:
        try:
            start_date = max(start_date, datetime.strptime(opening_date_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if global_opening_date_str:
        try:
            start_date = max(start_date, datetime.strptime(global_opening_date_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    effective_start_date = start_date

    # Determine end date for slot generation
    closing_date_str = course.get('closing_date')
    global_closing_date_str = global_s.get('global_closing_date')

    effective_end_date = None
    if closing_date_str:
        try:
            effective_end_date = datetime.strptime(closing_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if global_closing_date_str:
        try:
            g_closing = datetime.strptime(global_closing_date_str, '%Y-%m-%d').date()
            if effective_end_date is None or g_closing < effective_end_date:
                effective_end_date = g_closing
        except ValueError:
            pass

    # Generate all possible slots
    manual_slots_raw = course.get('manual_slots')
    all_possible_slots = []

    if manual_slots_raw and manual_slots_raw.strip():
        lines = manual_slots_raw.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                parts = line.split(' ')
                if len(parts) < 2:
                    continue
                date_part, time_part = parts[0], parts[1]

                slot_datetime = datetime.combine(datetime.strptime(date_part, '%Y-%m-%d').date(), time(int(time_part.split(':')[0]), int(time_part.split(':')[1])), tzinfo=CR_TZ)

                # Validate against now and start date
                if slot_datetime <= now_cr or datetime.strptime(date_part, '%Y-%m-%d').date() < effective_start_date:
                    continue

                # Validate against end date
                if effective_end_date and datetime.strptime(date_part, '%Y-%m-%d').date() > effective_end_date:
                    continue

                all_possible_slots.append({
                    'date': date_part,
                    'time': time_part
                })
            except Exception as e:
                print(f"Error parsing manual slot line '{line}': {e}")
                continue
    else:
        work_days = [int(d) for d in s['work_days'].split(',')]
        start_h, start_m = map(int, s['start_time'].split(':'))
        end_h, end_m = map(int, s['end_time'].split(':'))
        lunch_start_h, lunch_start_m = map(int, s['lunch_start'].split(':'))
        lunch_end_h, lunch_end_m = map(int, s['lunch_end'].split(':'))
        duration = int(s['apt_duration'])

        start_total_min = start_h * 60 + start_m
        end_total_min = end_h * 60 + end_m
        lunch_start_total = lunch_start_h * 60 + lunch_start_m
        lunch_end_total = lunch_end_h * 60 + lunch_end_m

        for i in range(30): # Increased range to ensure we hit end_date if it's far
            d = effective_start_date + timedelta(days=i)

            # Stop if we've passed the effective end date
            if effective_end_date and d > effective_end_date:
                break

            if d.weekday() in work_days:
                current_total_min = start_total_min
                while current_total_min + duration <= end_total_min:
                    slot_end = current_total_min + duration
                    if not (slot_end <= lunch_start_total or current_total_min >= lunch_end_total):
                        current_total_min = lunch_end_total
                        continue

                    h, m = divmod(current_total_min, 60)
                    time_str = f"{h:02d}:{m:02d}"

                    slot_datetime = datetime.combine(d, time(h, m), tzinfo=CR_TZ)
                    if slot_datetime <= now_cr:
                        current_total_min += duration
                        continue

                    all_possible_slots.append({
                        'date': d.isoformat(),
                        'time': time_str
                    })
                    current_total_min += duration

    # Filter out occupied slots
    occupied_slots = sb_get('appointments', f'course_id=eq.{course_id}&select=appointment_date,appointment_time')
    taken_set = set()
    if isinstance(occupied_slots, list):
        for slot in occupied_slots:
            d_val = slot['appointment_date'].split('T')[0] if 'T' in slot['appointment_date'] else slot['appointment_date']
            taken_set.add((d_val, slot['appointment_time']))

    available_slots = [slot for slot in all_possible_slots if (slot['date'], slot['time']) not in taken_set]

    # Show all available slots (not limited by vacancies_left)
    selected_slots = available_slots

    # Prepare data for template
    formatted_dates = []
    available_times = []

    # Build slots_by_date: date -> list of available times (for JS filtering)
    slots_by_date = {}
    for slot in selected_slots:
        slots_by_date.setdefault(slot['date'], [])
        if slot['time'] not in slots_by_date[slot['date']]:
            slots_by_date[slot['date']].append(slot['time'])
    for d in slots_by_date:
        slots_by_date[d].sort()

    all_selected_times = sorted(list(set(slot['time'] for slot in selected_slots)))
    available_times = all_selected_times

    unique_dates = sorted(list(set(slot['date'] for slot in selected_slots)))
    for d in unique_dates:
        formatted_dates.append({
            'value': d,
            'label': format_date_spanish(d)
        })

    fake_taken = []
    for slot in all_possible_slots:
        if slot not in selected_slots:
            fake_taken.append([slot['date'], slot['time']])
    for t in taken_set:
        fake_taken.append(list(t))

    def _apt_render():
        return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone,
                               dates=formatted_dates, times=available_times, taken=fake_taken,
                               slots_by_date=slots_by_date)

    if request.method == 'POST':
        apt_date = request.form.get('date')
        apt_time = request.form.get('time')
        if not apt_date or not apt_time:
            flash('Por favor seleccione una fecha y hora.', 'warning')
            return _apt_render()

        # SERVER-SIDE VALIDATION
        try:
            # Convert selected slot to datetime
            selected_dt = datetime.combine(datetime.strptime(apt_date, '%Y-%m-%d').date(), time(int(apt_time.split(':')[0]), int(apt_time.split(':')[1])), tzinfo=CR_TZ)

            # 1. Prevent past appointments
            if selected_dt <= now_cr:
                flash('Lo sentimos, no puede programar una cita en el pasado.', 'danger')
                return _apt_render()

            # 2. Validate against effective start and end dates
            selected_date_val = selected_dt.date()
            if selected_date_val < effective_start_date:
                flash('La fecha seleccionada es anterior a la fecha de apertura.', 'danger')
                return _apt_render()
            if effective_end_date and selected_date_val > effective_end_date:
                flash('La fecha seleccionada es posterior a la fecha de cierre.', 'danger')
                return _apt_render()

            # 3. Verify the slot was actually offered as available
            if not any(slot['date'] == apt_date and slot['time'] == apt_time for slot in selected_slots):
                flash('Lo sentimos, este horario ya no está disponible o no es válido.', 'danger')
                return _apt_render()
        except Exception as e:
            flash('Error al validar la fecha y hora seleccionadas.', 'danger')
            return _apt_render()

        if user_has_appointment(cedula):
            flash('Usted ya tiene una cita programada. Por favor, contacte a la administración si necesita realizar un cambio.', 'danger')
            return _apt_render()

        # Check if course still has vacancies left (prevent race condition)
        current_course_data = sb_get('courses', f'id=eq.{course_id}&select=total_vacancies,filled_vacancies')
        if isinstance(current_course_data, list) and len(current_course_data) > 0:
            current_course = current_course_data[0]
            if current_course['filled_vacancies'] >= current_course['total_vacancies']:
                flash('Lo sentimos, este curso ya no tiene cupos disponibles.', 'danger')
                return _apt_render()
        else:
            # Error fetching course, fallback to original course variable
            if course['filled_vacancies'] >= course['total_vacancies']:
                flash('Lo sentimos, este curso ya no tiene cupos disponibles.', 'danger')
                return _apt_render()

        apt_data = sb_post('appointments', {
            'student_name': name,
            'student_cedula': cedula,
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

    return _apt_render()

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Fetch user by username only
        user_data_list = sb_get('users', f'username=eq.{username}&select=*')
        if isinstance(user_data_list, list) and len(user_data_list) > 0:
            ud = user_data_list[0]
            stored_pw = ud.get('password')
            # Verify password: either direct match (legacy plaintext) or hash match
            pw_ok = False
            if stored_pw is not None:
                try:
                    # werkzeug's check_password_hash handles valid hashes
                    pw_ok = check_password_hash(stored_pw, password)
                except Exception:
                    # If check_password_hash raises (e.g., invalid hash format), treat as plaintext
                    pw_ok = False
                # Fallback to direct comparison for plaintext passwords
                if not pw_ok:
                    pw_ok = (stored_pw == password)
            if pw_ok:
                user = User(
                    id=ud['id'],
                    username=ud['username'],
                    role=ud.get('role', 'student'),
                    first_name=ud.get('first_name'),
                    last_name=ud.get('last_name'),
                    cedula=ud.get('cedula'),
                    email=ud.get('email'),
                    phone=ud.get('phone'),
                    level=ud.get('level')
                )
                login_user(user)

                # Redirect based on role
                if user.is_admin:
                    return redirect(url_for('admin_dashboard'))
                elif user.is_student:
                    return redirect(url_for('student_dashboard'))
                elif user.is_professor:
                    return redirect(url_for('professor_dashboard'))
                elif user.is_superadmin:
                    return redirect(url_for('admin_dashboard'))
            else:
                flash('Credenciales incorrectas.', 'danger')
        else:
            flash('Credenciales incorrectas.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    # Admin y Superadmin: panel limpio basado en botones (sin tabla de cursos)
    if current_user.is_authenticated and (current_user.is_admin or current_user.is_superadmin):
        return render_template('admin_button_dash.html')
    return redirect(url_for('login'))


@app.route('/admin/cursos')
@login_required
@admin_required
def admin_courses_dashboard():
    courses = sb_get('courses', 'select=*')
    if not isinstance(courses, list):
        courses = []
    for c in courses:
        get_vacancies_left(c)

    appointments = sb_get('appointments', 'select=*,courses(name)&order=appointment_date.asc,appointment_time.asc')
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

    # Nuevas configuraciones de horario por curso
    work_days = request.form.get('work_days')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    lunch_start = request.form.get('lunch_start')
    lunch_end = request.form.get('lunch_end')
    apt_duration = request.form.get('apt_duration')
    manual_slots = request.form.get('manual_slots')
    closing_date = request.form.get('closing_date')

    # Educational levels
    required_levels_list = request.form.getlist('required_levels')
    required_levels_str = ",".join(required_levels_list)

    if name and description and vacancies:
        course_data = {
            'name': name,
            'description': description,
            'total_vacancies': int(vacancies),
            'filled_vacancies': 0,
            'work_days': work_days,
            'start_time': start_time,
            'end_time': end_time,
            'lunch_start': lunch_start,
            'lunch_end': lunch_end,
            'apt_duration': apt_duration,
            'manual_slots': manual_slots,
            'required_levels': required_levels_str
        }

        opening_date = request.form.get('opening_date')
        if opening_date:
            course_data['opening_date'] = opening_date

        if closing_date:
            course_data['closing_date'] = closing_date

        res = sb_post('courses', course_data)
        if isinstance(res, list) or (isinstance(res, dict) and 'id' in res):
            flash('Curso agregado exitosamente.', 'success')
        else:
            flash(f'Error al agregar curso: {res}', 'danger')
    else:
        flash('Por favor complete todos los campos.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        # ── Guardar en bloques separados para que un campo faltante no rompa todo ──
        current = sb_get('settings', 'select=*')
        is_update = isinstance(current, list) and len(current) > 0
        settings_id = current[0]['id'] if is_update else None

        errors = []

        def _save(data, label):
            """Guarda un bloque de datos y registra errores sin lanzar excepción."""
            nonlocal is_update, settings_id
            try:
                if is_update:
                    r = sb_patch('settings', 'id', settings_id, data)
                    if hasattr(r, 'status_code') and r.status_code >= 400:
                        errors.append(f"{label}: {r.text[:200]}")
                else:
                    r = sb_post('settings', data)
                    if hasattr(r, 'status_code') and r.status_code >= 400:
                        errors.append(f"{label}: {r.text[:200]}")
                    else:
                        # Primer insert exitoso — guardar id para PATCHes siguientes
                        if isinstance(r, list) and r:
                            is_update = True
                            settings_id = r[0].get('id')
                        elif isinstance(r, dict) and r.get('id'):
                            is_update = True
                            settings_id = r['id']
            except Exception as e:
                errors.append(f"{label}: {e}")

        # Bloque 1 — configuración de cursos (columnas que siempre existen)
        _save({
            'work_days': request.form.get('work_days'),
            'start_time': request.form.get('start_time'),
            'end_time': request.form.get('end_time'),
            'lunch_start': request.form.get('lunch_start'),
            'lunch_end': request.form.get('lunch_end'),
            'apt_duration': request.form.get('apt_duration', '60'),
            'global_opening_date': request.form.get('global_opening_date') or None,
            'global_closing_date': request.form.get('global_closing_date') or None,
        }, 'Horario cursos')

        # Bloque 2 — horario de matrícula compartido
        _save({
            'mat_work_days': request.form.get('mat_work_days'),
            'mat_start_time': request.form.get('mat_start_time'),
            'mat_end_time': request.form.get('mat_end_time'),
            'mat_lunch_start': request.form.get('mat_lunch_start'),
            'mat_lunch_end': request.form.get('mat_lunch_end'),
            'mat_apt_duration': request.form.get('mat_apt_duration', '30'),
        }, 'Horario matrícula')

        # Bloque 3 — fechas, cupos y horarios Primer Nivel (Primaria)
        _save({
            'mat_primaria_opening': request.form.get('mat_primaria_opening') or None,
            'mat_primaria_closing': request.form.get('mat_primaria_closing') or None,
            'mat_primaria_cupos':   request.form.get('mat_primaria_cupos') or None,
            'mat_primaria_work_days': request.form.get('mat_primaria_work_days') or None,
            'mat_primaria_start_time': request.form.get('mat_primaria_start_time') or None,
            'mat_primaria_end_time': request.form.get('mat_primaria_end_time') or None,
            'mat_primaria_apt_duration': request.form.get('mat_primaria_apt_duration') or None,
            'mat_primaria_reqs': request.form.get('mat_primaria_reqs') or None,
        }, 'Fechas/cupos Primaria')

        # Bloque 4 — fechas, cupos y horarios Segundo Nivel
        _save({
            'mat_segundo_nivel_opening': request.form.get('mat_segundo_nivel_opening') or None,
            'mat_segundo_nivel_closing': request.form.get('mat_segundo_nivel_closing') or None,
            'mat_segundo_nivel_cupos':   request.form.get('mat_segundo_nivel_cupos') or None,
            'mat_segundo_nivel_work_days': request.form.get('mat_segundo_nivel_work_days') or None,
            'mat_segundo_nivel_start_time': request.form.get('mat_segundo_nivel_start_time') or None,
            'mat_segundo_nivel_end_time': request.form.get('mat_segundo_nivel_end_time') or None,
            'mat_segundo_nivel_apt_duration': request.form.get('mat_segundo_nivel_apt_duration') or None,
            'mat_segundo_nivel_reqs': request.form.get('mat_segundo_nivel_reqs') or None,
        }, 'Fechas/cupos Segundo Nivel')

        # Bloque 5 — fechas, cupos y horarios Tercer Nivel
        _save({
            'mat_tercer_nivel_opening': request.form.get('mat_tercer_nivel_opening') or None,
            'mat_tercer_nivel_closing': request.form.get('mat_tercer_nivel_closing') or None,
            'mat_tercer_nivel_cupos':   request.form.get('mat_tercer_nivel_cupos') or None,
            'mat_tercer_nivel_work_days': request.form.get('mat_tercer_nivel_work_days') or None,
            'mat_tercer_nivel_start_time': request.form.get('mat_tercer_nivel_start_time') or None,
            'mat_tercer_nivel_end_time': request.form.get('mat_tercer_nivel_end_time') or None,
            'mat_tercer_nivel_apt_duration': request.form.get('mat_tercer_nivel_apt_duration') or None,
            'mat_tercer_nivel_reqs': request.form.get('mat_tercer_nivel_reqs') or None,
        }, 'Fechas/cupos Tercer Nivel')

        if errors:
            # Mostrar errores reales al admin en lugar de fingir éxito
            for e in errors:
                flash(f'⚠️ Error guardando — {e}', 'danger')
            flash('Algunos datos no se pudieron guardar. Verifique que ejecutó supabase_migration.sql en Supabase.', 'warning')
        else:
            flash('Configuración actualizada exitosamente.', 'success')
        return redirect(url_for('admin_settings'))

    settings = sb_get('settings', 'select=*')
    s = settings[0] if (isinstance(settings, list) and len(settings) > 0) else {}
    # Defaults cursos
    s.setdefault('work_days', '0,1,2,3,4')
    s.setdefault('start_time', '08:00')
    s.setdefault('end_time', '16:00')
    s.setdefault('lunch_start', '12:00')
    s.setdefault('lunch_end', '13:00')
    s.setdefault('apt_duration', '60')
    s.setdefault('global_opening_date', '')
    s.setdefault('global_closing_date', '')
    # Defaults matrícula
    s.setdefault('mat_work_days', '0,1,2,3,4')
    s.setdefault('mat_start_time', '08:00')
    s.setdefault('mat_end_time', '16:00')
    s.setdefault('mat_lunch_start', '12:00')
    s.setdefault('mat_lunch_end', '13:00')
    s.setdefault('mat_apt_duration', '30')
    s.setdefault('mat_primaria_opening', '')
    s.setdefault('mat_primaria_closing', '')
    s.setdefault('mat_primaria_cupos', '')
    s.setdefault('mat_primaria_work_days', '')
    s.setdefault('mat_primaria_start_time', '')
    s.setdefault('mat_primaria_end_time', '')
    s.setdefault('mat_primaria_apt_duration', '')
    s.setdefault('mat_primaria_reqs', '')
    s.setdefault('mat_segundo_nivel_opening', '')
    s.setdefault('mat_segundo_nivel_closing', '')
    s.setdefault('mat_segundo_nivel_cupos', '')
    s.setdefault('mat_segundo_nivel_work_days', '')
    s.setdefault('mat_segundo_nivel_start_time', '')
    s.setdefault('mat_segundo_nivel_end_time', '')
    s.setdefault('mat_segundo_nivel_apt_duration', '')
    s.setdefault('mat_segundo_nivel_reqs', '')
    s.setdefault('mat_tercer_nivel_opening', '')
    s.setdefault('mat_tercer_nivel_closing', '')
    s.setdefault('mat_tercer_nivel_cupos', '')
    s.setdefault('mat_tercer_nivel_work_days', '')
    s.setdefault('mat_tercer_nivel_start_time', '')
    s.setdefault('mat_tercer_nivel_end_time', '')
    s.setdefault('mat_tercer_nivel_apt_duration', '')
    s.setdefault('mat_tercer_nivel_reqs', '')
    return render_template('admin_settings.html', settings=s)

@app.route('/admin/course/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_course(id):
    data = sb_get('courses', f'id=eq.{id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        vacancies = request.form.get('vacancies')
        work_days = request.form.get('work_days')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        lunch_start = request.form.get('lunch_start')
        lunch_end = request.form.get('lunch_end')
        apt_duration = request.form.get('apt_duration')
        manual_slots = request.form.get('manual_slots')

        # Educational levels
        required_levels_list = request.form.getlist('required_levels')
        required_levels_str = ",".join(required_levels_list)

        if name and description and vacancies:
            course_data = {
                'name': name,
                'description': description,
                'total_vacancies': int(vacancies),
                'work_days': work_days,
                'start_time': start_time,
                'end_time': end_time,
                'lunch_start': lunch_start,
                'lunch_end': lunch_end,
                'apt_duration': apt_duration,
                'manual_slots': manual_slots,
                'required_levels': required_levels_str
            }

            opening_date = request.form.get('opening_date')
            if opening_date:
                course_data['opening_date'] = opening_date

            closing_date_val = request.form.get('closing_date')
            if closing_date_val:
                course_data['closing_date'] = closing_date_val

            r = sb_patch('courses', 'id', id, course_data)
            if r.status_code in [200, 204]:
                flash('Curso actualizado exitosamente.', 'success')
            else:
                flash(f'Error al actualizar curso: {r.text}', 'danger')
        else:
            flash('Por favor complete todos los campos obligatorios.', 'warning')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_course.html', course=course)

@app.route('/admin/course/delete/<int:id>')
@login_required
def delete_course(id):
    # Primero eliminamos todas las citas asociadas al curso para evitar el error 409 (Conflict)
    sb_delete('appointments', 'course_id', id)

    r = sb_delete('courses', 'id', id)
    if r.status_code in [200, 204]:
        flash('Curso y sus citas relacionadas fueron eliminados.', 'success')
    elif r.status_code == 409:
        flash('No se puede eliminar el curso debido a dependencias en la base de datos.', 'danger')
    else:
        flash(f'Error al eliminar el curso: {r.status_code}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/course/toggle-visibility/<int:id>')
@login_required
def toggle_course_visibility(id):
    data = sb_get('courses', f'id=eq.{id}&select=id,hidden')
    if not data or len(data) == 0:
        flash('Curso no encontrado.', 'danger')
        return redirect(url_for('admin_dashboard'))
    current_hidden = data[0].get('hidden', False)
    new_hidden = not current_hidden
    r = sb_patch('courses', 'id', id, {'hidden': new_hidden})
    if r.status_code in [200, 204]:
        estado = 'ocultado' if new_hidden else 'mostrado'
        flash(f'Curso {estado} en la página web.', 'success')
    else:
        flash(f'Error al cambiar visibilidad: {r.text}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/appointment/delete/<int:id>')
@login_required
def delete_appointment(id):
    r = sb_delete('appointments', 'id', id)
    if r.status_code in [200, 204]:
        flash('Cita procesada y eliminada.', 'success')
    else:
        flash(f'Error al procesar la cita: {r.status_code}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/posts')
@login_required
def admin_posts():
    posts = sb_get('posts', 'select=*&order=created_at.desc')
    if not isinstance(posts, list):
        posts = []
    return render_template('admin_posts.html', posts=posts)

@app.route('/admin/posts/add', methods=['GET', 'POST'])
@login_required
def add_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        published = 'true' if request.form.get('published') else 'false'
        if title and content:
            res = sb_post('posts', {'title': title, 'content': content})
            if isinstance(res, list) or (isinstance(res, dict) and 'id' in res):
                flash('Post agregado exitosamente.', 'success')
            else:
                flash(f'Error al agregar post: {res}', 'danger')
        else:
            flash('Por favor complete todos los campos.', 'warning')
        return redirect(url_for('admin_posts'))
    return render_template('admin_post_edit.html', post=None)

@app.route('/admin/posts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    data = sb_get('posts', f'id=eq.{id}&select=*')
    if not data or len(data) == 0:
        return "Post no encontrado", 404
    post = data[0]
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            r = sb_patch('posts', 'id', id, {'title': title, 'content': content})
            if r.status_code in [200, 204]:
                flash('Post actualizado exitosamente.', 'success')
            else:
                flash(f'Error al actualizar post: {r.text}', 'danger')
        else:
            flash('Por favor complete todos los campos obligatorios.', 'warning')
        return redirect(url_for('admin_posts'))
    return render_template('admin_post_edit.html', post=post)

@app.route('/admin/posts/delete/<int:id>')
@login_required
def delete_post(id):
    r = sb_delete('posts', 'id', id)
    if r.status_code in [200, 204]:
        flash('Post eliminado exitosamente.', 'success')
    else:
        # Log error for debugging
        print(f"Delete Post Error {r.status_code}: {r.text}")
        flash(f'Error al eliminar post: {r.status_code}', 'danger')
    return redirect(url_for('admin_posts'))

@app.route('/matriculas')
def matriculas():
    res = sb_get('enrollment_dates', 'select=*&order=level.asc')
    if isinstance(res, dict) and 'error' in res:
        return f"Error de Supabase ({res['error']}): {res['text']}", 500

    dates_list = res if isinstance(res, list) else []

    # Agrupamos los datos en Python para que la plantilla sea simple y no falle
    grouped_dates = {cycle: [] for cycle in ENROLLMENT_KEYWORDS.keys()}

    for d in dates_list:
        level_text = str(d.get('level', '')).lower()
        for cycle, info in ENROLLMENT_KEYWORDS.items():
            if any(k in level_text for k in info['keywords']):
                grouped_dates[cycle].append(d)
                break

    return render_template('matriculas.html', grouped_dates=grouped_dates, all_dates=dates_list)

def format_appointment_data(appointments):
    if not isinstance(appointments, list):
        return []
    for a in appointments:
        if 'appointment_date' in a:
            # Guard against already formatted dates (if the function is called twice)
            date_val = a['appointment_date']
            if date_val and ' de ' in date_val:
                pass # already formatted
            elif date_val:
                a['appointment_date'] = format_date_spanish(date_val.split('T')[0])
        if 'created_at' in a:
            created_val = a['created_at']
            if created_val and 'T' in created_val:
                a['created_at'] = created_val.split('T')[0] + ' ' + created_val.split('T')[1][:5]
    return appointments

@app.route('/admin/matriculas')
@login_required
def admin_matriculas():
    if request.method == 'POST':
        id = request.form.get('id')
        level = request.form.get('level')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if id:
            # Update existing
            if level and start_date and end_date:
                r = sb_patch('enrollment_dates', 'id', id, {'level': level, 'start_date': start_date, 'end_date': end_date})
                if r.status_code in [200, 204]:
                    flash('Fecha actualizada exitosamente.', 'success')
                else:
                    flash(f'Error al actualizar fecha: {r.text}', 'danger')
            else:
                flash('Por favor complete todos los campos.', 'warning')
        else:
            # Add new
            if level and start_date and end_date:
                res = sb_post('enrollment_dates', {'level': level, 'start_date': start_date, 'end_date': end_date})
                if isinstance(res, list) or (isinstance(res, dict) and 'id' in res):
                    flash('Fecha de matrícula agregada exitosamente.', 'success')
                else:
                    flash(f'Error al agregar fecha: {res}', 'danger')
            else:
                flash('Por favor complete todos los campos.', 'warning')

        return redirect(url_for('admin_matriculas'))

    data = sb_get('enrollment_dates', 'select=*&order=level.asc')
    if not isinstance(data, list):
        data = []
    return render_template('admin_matriculas.html', dates=data)


@app.route('/admin/matriculas/delete/<int:id>')
@login_required
def delete_enrollment_date(id):
    r = sb_delete('enrollment_dates', 'id', id)
    if r.status_code in [200, 204]:
        flash('Fecha de matrícula eliminada exitosamente.', 'success')
    else:
        flash(f'Error al eliminar fecha: {r.status_code}', 'danger')
    return redirect(url_for('admin_matriculas'))



# ─── Matrícula con cita (Primaria / Secundaria) ─────────────────────────────

MATRICULA_CYCLES = {
    'primaria': {
        'label': 'Primer Nivel (Primer nivel)',
        'icon': 'bi-book',
        'color': 'warning',
        'description': 'Matrícula para estudiantes de Educación Primaria (1° a 6° grado).'
    },
    'segundo_nivel': {
        'label': 'Segundo Nivel (7°, 8° y 9°)',
        'icon': 'bi-mortarboard',
        'color': 'info',
        'description': 'Matrícula para estudiantes de Segundo Nivel: Equivalente a Sétimo, Octavo y Noveno año.'
    },
    'tercer_nivel': {
        'label': 'Tercer nivel — Plan de estudios de educación de adultos k',
        'icon': 'bi-award',
        'color': 'success',
        'description': 'Matrícula para estudiantes del Ciclo Diversificado: Equivalente a Décimo y Undécimo año.'
    }
}

# ─── Horarios (Primer, Segundo, Tercer nivel) ───────────────────────────────

HORARIOS_LEVELS = {
    'primer_nivel': {
        'label': 'Primer Nivel',
        'icon': 'bi-clock-history',
        'color': 'primary',
        'description': 'Horarios de atención para Primer Nivel'
    },
    'segundo_nivel': {
        'label': 'Segundo Nivel',
        'icon': 'bi-clock-history',
        'color': 'secondary',
        'description': 'Horarios de atención para Segundo Nivel'
    },
    'tercer_nivel': {
        'label': 'Tercer Nivel',
        'icon': 'bi-clock-history',
        'color': 'info',
        'description': 'Horarios de atención para Tercer Nivel'
    }
}

def _get_cycle_availability(cycle):
    """Retorna (max_cupos, booked_count, remaining, matricula_configured, opening_val, closing_val, gs)"""
    settings_data = sb_get('settings', 'select=*')
    gs = settings_data[0] if (isinstance(settings_data, list) and len(settings_data) > 0) else {}

    cycle_key_map = {
        'primaria':      ('mat_primaria_opening',      'mat_primaria_closing',      'mat_primaria_cupos'),
        'segundo_nivel': ('mat_segundo_nivel_opening', 'mat_segundo_nivel_closing', 'mat_segundo_nivel_cupos'),
        'tercer_nivel':  ('mat_tercer_nivel_opening',  'mat_tercer_nivel_closing',  'mat_tercer_nivel_cupos'),
    }
    opening_key, closing_key, cupos_key = cycle_key_map.get(cycle, ('mat_primaria_opening', 'mat_primaria_closing', 'mat_primaria_cupos'))

    today_str = datetime.now(CR_TZ).date().isoformat()

    # 1. Intentar obtener fechas desde la tabla enrollment_dates
    opening_val, closing_val = None, None

    # Buscar el ciclo correspondiente en ENROLLMENT_KEYWORDS
    matching_cycle = next((name, info) for name, info in ENROLLMENT_KEYWORDS.items() if info['cycle_id'] == cycle)
    keywords = matching_cycle[1]['keywords']

    if keywords:
        enroll_dates = sb_get('enrollment_dates', 'select=level,start_date,end_date')
        if isinstance(enroll_dates, list):
            for ed in enroll_dates:
                lvl = str(ed.get('level', '')).lower()
                if any(k in lvl for k in keywords):
                    e_open = ed.get('start_date')
                    e_close = ed.get('end_date')
                    # Solo usar si el periodo NO ha terminado totalmente (está activo o es futuro)
                    if not e_close or e_close >= today_str:
                        opening_val = e_open
                        closing_val = e_close
                        break

    # 2. Si no se encontraron fechas activas en enrollment_dates, usar las de settings
    if not opening_val and not closing_val:
        opening_val = gs.get(opening_key) or None
        closing_val = gs.get(closing_key) or None
        # Validar también que las de settings no estén vencidas
        if closing_val and closing_val < today_str:
            if not opening_val or opening_val <= today_str:
                opening_val, closing_val = None, None

    cupos_val = gs.get(cupos_key)
    max_cupos = int(cupos_val) if cupos_val and str(cupos_val).isdigit() else None

    occupied = sb_get('matricula_appointments', f'cycle=eq.{cycle}&select=appointment_date,appointment_time')
    if isinstance(occupied, list):
        filtered = occupied
        if opening_val:
            filtered = [a for a in filtered if a['appointment_date'] >= opening_val]
        if closing_val:
            filtered = [a for a in filtered if a['appointment_date'] <= closing_val]
        booked_count = len(filtered)
    else:
        booked_count = 0

    if max_cupos is not None:
        remaining = max(0, max_cupos - booked_count)
    else:
        remaining = None

    matricula_configured = bool(opening_val or closing_val)
    return max_cupos, booked_count, remaining, matricula_configured, opening_val, closing_val, gs


def _get_horarios_availability(level):
    """Retorna (configured, opening_val, closing_val, gs) para horarios"""
    settings_data = sb_get('settings', 'select=*')
    gs = settings_data[0] if (isinstance(settings_data, list) and len(settings_data) > 0) else {}

    # Mapeo de niveles a columnas de settings
    level_key_map = {
        'primer_nivel':      ('hor_primera_apertura',      'hor_primera_cierre'),
        'segundo_nivel':     ('hor_segunda_apertura',     'hor_segunda_cierre'),
        'tercer_nivel':      ('hor_tercera_apertura',     'hor_tercera_cierre'),
    }
    opening_key, closing_key = level_key_map.get(level, ('hor_primera_apertura', 'hor_primera_cierre'))

    today_str = datetime.now(CR_TZ).date().isoformat()

    # Obtener fechas desde settings
    opening_val = gs.get(opening_key) or None
    closing_val = gs.get(closing_key) or None

    # Validar que las fechas no estén vencidas
    if closing_val and closing_val < today_str:
        if not opening_val or opening_val <= today_str:
            opening_val, closing_val = None, None

    configured = bool(opening_val or closing_val)
    return configured, opening_val, closing_val, gs


@app.route('/matricula/<cycle>', methods=['GET', 'POST'])
def matricula_enroll(cycle):
    if cycle not in MATRICULA_CYCLES:
        return "Ciclo no válido", 404
    info = MATRICULA_CYCLES[cycle]

    # Verificar disponibilidad ANTES de mostrar el formulario
    max_cupos, booked_count, remaining, matricula_configured, opening_val, closing_val, gs = _get_cycle_availability(cycle)

    # Sin cupos disponibles → mostrar bloqueo, no el formulario
    no_cupos = (remaining is not None and remaining <= 0)
    no_config = not matricula_configured

    if request.method == 'POST':
        if no_cupos or no_config:
            flash('No hay cupos disponibles para este nivel en este momento.', 'danger')
            return render_template('matricula_enroll.html', cycle=cycle, info=info,
                                   no_cupos=no_cupos, no_config=no_config,
                                   remaining=remaining, max_cupos=max_cupos,
                                   requirements=gs.get(f'mat_{cycle}_reqs'))
        name = request.form.get('name', '').strip()
        cedula = request.form.get('cedula', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name or not cedula or not phone:
            flash('Por favor complete todos los campos.', 'warning')
            return render_template('matricula_enroll.html', cycle=cycle, info=info,
                                   no_cupos=no_cupos, no_config=no_config,
                                   remaining=remaining, max_cupos=max_cupos,
                                   requirements=gs.get(f'mat_{cycle}_reqs'))

        if user_has_appointment(cedula):
            flash('Usted ya tiene una cita programada. Por favor, contacte a la administración si necesita realizar un cambio.', 'danger')
            return render_template('matricula_enroll.html', cycle=cycle, info=info,
                                   no_cupos=no_cupos, no_config=no_config,
                                   remaining=remaining, max_cupos=max_cupos,
                                   requirements=gs.get(f'mat_{cycle}_reqs'))

        return redirect(url_for('matricula_schedule', cycle=cycle, name=name, cedula=cedula, phone=phone))

    return render_template('matricula_enroll.html', cycle=cycle, info=info,
                           no_cupos=no_cupos, no_config=no_config,
                           remaining=remaining, max_cupos=max_cupos,
                           requirements=gs.get(f'mat_{cycle}_reqs'))


@app.route('/matricula/<cycle>/cita/<name>/<cedula>/<phone>', methods=['GET', 'POST'])
def matricula_schedule(cycle, name, cedula, phone):
    name = unquote(name)
    cedula = unquote(cedula)
    phone = unquote(phone)
    if cycle not in MATRICULA_CYCLES:
        return "Ciclo no válido", 404
    info = MATRICULA_CYCLES[cycle]

    # Configuración específica de matrícula desde settings
    max_cupos, booked_count, remaining, matricula_configured, opening_val, closing_val, gs = _get_cycle_availability(cycle)

    s = {
        'work_days': gs.get(f'mat_{cycle}_work_days') or gs.get('mat_work_days') or gs.get('work_days') or '0,1,2,3,4',
        'start_time': gs.get(f'mat_{cycle}_start_time') or gs.get('mat_start_time') or gs.get('start_time') or '08:00',
        'end_time': gs.get(f'mat_{cycle}_end_time') or gs.get('mat_end_time') or gs.get('end_time') or '16:00',
        'lunch_start': gs.get('mat_lunch_start') or gs.get('lunch_start') or '12:00',
        'lunch_end': gs.get('mat_lunch_end') or gs.get('lunch_end') or '13:00',
        'apt_duration': gs.get(f'mat_{cycle}_apt_duration') or gs.get('mat_apt_duration') or '30'
    }

    now_cr = datetime.now(CR_TZ)
    today = now_cr.date()

    # matricula_configured ya viene de _get_cycle_availability

    effective_start_date = today
    effective_end_date = None

    if opening_val:
        try:
            effective_start_date = max(today, datetime.strptime(opening_val, '%Y-%m-%d').date())
        except Exception:
            pass
    if closing_val:
        try:
            effective_end_date = datetime.strptime(closing_val, '%Y-%m-%d').date()
        except Exception:
            pass

    # Si no hay configuración, forzar sin slots
    if not matricula_configured:
        effective_end_date = today - timedelta(days=1)

    # Generar slots disponibles
    work_days = [int(d) for d in s['work_days'].split(',')]
    start_h, start_m = map(int, s['start_time'].split(':'))
    end_h, end_m = map(int, s['end_time'].split(':'))
    lunch_start_h, lunch_start_m = map(int, s['lunch_start'].split(':'))
    lunch_end_h, lunch_end_m = map(int, s['lunch_end'].split(':'))
    duration = int(s['apt_duration'])

    start_total_min = start_h * 60 + start_m
    end_total_min = end_h * 60 + end_m
    lunch_start_total = lunch_start_h * 60 + lunch_start_m
    lunch_end_total = lunch_end_h * 60 + lunch_end_m

    all_possible_slots = []
    for i in range(60):
        d = effective_start_date + timedelta(days=i)
        if effective_end_date and d > effective_end_date:
            break
        if d.weekday() in work_days:
            current_total_min = start_total_min
            while current_total_min + duration <= end_total_min:
                slot_end = current_total_min + duration
                if not (slot_end <= lunch_start_total or current_total_min >= lunch_end_total):
                    current_total_min = lunch_end_total
                    continue
                h, m = divmod(current_total_min, 60)
                time_str = f"{h:02d}:{m:02d}"
                slot_datetime = datetime.combine(d, time(h, m), tzinfo=CR_TZ)
                if slot_datetime > now_cr:
                    all_possible_slots.append({'date': d.isoformat(), 'time': time_str})
                current_total_min += duration

    # Filtrar ocupados (tabla matricula_appointments) - GLOBAL (todos los ciclos)
    occupied = sb_get('matricula_appointments', 'select=appointment_date,appointment_time')
    taken_set = set()
    if isinstance(occupied, list):
        for slot in occupied:
            d_val = slot['appointment_date'].split('T')[0] if 'T' in slot['appointment_date'] else slot['appointment_date']
            taken_set.add((d_val, slot['appointment_time']))

    available_slots = [s2 for s2 in all_possible_slots if (s2['date'], s2['time']) not in taken_set]

    # Los cupos controlan cuántas reservas totales se permiten (chequeado en matricula_enroll).
    # Aquí mostramos todos los slots libres dentro del periodo — no cortamos por cupos.

    # Construir mapa fecha → lista de horas disponibles (para el JS del template)
    slots_by_date = {}
    for s2 in available_slots:
        slots_by_date.setdefault(s2['date'], [])
        if s2['time'] not in slots_by_date[s2['date']]:
            slots_by_date[s2['date']].append(s2['time'])
    for d in slots_by_date:
        slots_by_date[d].sort()

    unique_dates = sorted(slots_by_date.keys())
    formatted_dates = [{'value': d, 'label': format_date_spanish(d)} for d in unique_dates]
    # available_times: todas las horas únicas (usadas como base en el select, el JS filtra por fecha)
    available_times = sorted(list(set(s2['time'] for s2 in available_slots)))

    fake_taken = []
    for s2 in all_possible_slots:
        if (s2['date'], s2['time']) in taken_set:
            fake_taken.append([s2['date'], s2['time']])

    if request.method == 'POST':
        apt_date = request.form.get('date')
        apt_time = request.form.get('time')
        if not apt_date or not apt_time:
            flash('Por favor seleccione una fecha y hora.', 'warning')
            return render_template('matricula_appointment.html', cycle=cycle, info=info, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken, slots_by_date=slots_by_date, matricula_configured=matricula_configured)

        try:
            selected_dt = datetime.combine(datetime.strptime(apt_date, '%Y-%m-%d').date(), time(int(apt_time.split(':')[0]), int(apt_time.split(':')[1])), tzinfo=CR_TZ)
            if selected_dt <= now_cr:
                flash('No puede programar una cita en el pasado.', 'danger')
                return render_template('matricula_appointment.html', cycle=cycle, info=info, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken, slots_by_date=slots_by_date, matricula_configured=matricula_configured)
            if not any(s2['date'] == apt_date and s2['time'] == apt_time for s2 in available_slots):
                flash('Lo sentimos, ese horario ya no está disponible.', 'danger')
                return render_template('matricula_appointment.html', cycle=cycle, info=info, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken, slots_by_date=slots_by_date, matricula_configured=matricula_configured)
        except Exception:
            flash('Error al validar la fecha seleccionada.', 'danger')
            return render_template('matricula_appointment.html', cycle=cycle, info=info, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken, slots_by_date=slots_by_date, matricula_configured=matricula_configured)

        if user_has_appointment(cedula):
            flash('Usted ya tiene una cita programada. Por favor, contacte a la administración si necesita realizar un cambio.', 'danger')
            return render_template('matricula_appointment.html', cycle=cycle, info=info, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken, slots_by_date=slots_by_date, matricula_configured=matricula_configured)

        apt_data = sb_post('matricula_appointments', {
            'student_name': name,
            'student_cedula': cedula,
            'student_phone': phone,
            'cycle': cycle,
            'appointment_date': apt_date,
            'appointment_time': apt_time
        })
        flash('¡Cita de matrícula programada con éxito!', 'success')
        apt_id = apt_data.get('id') if isinstance(apt_data, dict) else (apt_data[0].get('id') if isinstance(apt_data, list) and apt_data else None)
        if apt_id:
            return redirect(url_for('matricula_receipt', apt_id=apt_id))
        return redirect(url_for('index'))

    return render_template('matricula_appointment.html', cycle=cycle, info=info, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken, slots_by_date=slots_by_date, matricula_configured=matricula_configured)


@app.route('/matricula/receipt/<int:apt_id>')
def matricula_receipt(apt_id):
    apt = sb_get('matricula_appointments', f'id=eq.{apt_id}&select=*')
    if not apt or len(apt) == 0:
        return "Cita no encontrada", 404
    apt_details = apt[0]
    if 'appointment_date' in apt_details:
        apt_details['appointment_date'] = format_date_spanish(apt_details['appointment_date'].split('T')[0])
    cycle = apt_details.get('cycle', 'primaria')
    info = MATRICULA_CYCLES.get(cycle, MATRICULA_CYCLES['primaria'])
    return render_template('matricula_receipt.html', appointment=apt_details, info=info)


# ─── Horarios Rutas ────────────────────────────────────────────────────────

@app.route('/horarios')
def horarios():
    """Página principal de horarios con selector de nivel interactivo"""
    return render_template('horarios.html', levels=HORARIOS_LEVELS)


@app.route('/api/horarios/<level>')
def api_horarios_level(level):
    """Devuelve en JSON los horarios de un nivel para cargarlos sin recargar la página"""
    if level not in HORARIOS_LEVELS:
        return {'error': 'Nivel no válido'}, 404

    horarios = sb_get('horarios', f'level=eq.{level}&select=*&order=created_at.desc')
    if not isinstance(horarios, list):
        horarios = []

    for h in horarios:
        if h.get('photo_url') and h['photo_url'].startswith('/'):
            h['photo_url'] = f"{request.url_root.rstrip('/')}{h['photo_url']}"
        if h.get('created_at'):
            h['created_at'] = h['created_at'].split('T')[0]

    return {
        'level': level,
        'label': HORARIOS_LEVELS[level]['label'],
        'horarios': horarios,
        'can_manage': bool(current_user.is_authenticated and current_user.is_superadmin)
    }


@app.route('/horarios/<level>')
def horarios_level(level):
    """Muestra los horarios disponibles para un nivel específico"""
    if level not in HORARIOS_LEVELS:
        return "Nivel no válido", 404

    info = HORARIOS_LEVELS[level]
    configured, opening_val, closing_val, gs = _get_horarios_availability(level)

    # Obtener horarios existentes para este nivel
    horarios = sb_get('horarios', f'level=eq.{level}&select=*&order=created_at.desc')
    if not isinstance(horarios, list):
        horarios = []

    # Procesar las URLs de las imágenes para asegurar que tengan el formato correcto
    for h in horarios:
        if h.get('photo_url'):
            # Si es una ruta relativa, convertirla a URL absoluta
            if h['photo_url'].startswith('/'):
                h['photo_url'] = f"{request.url_root.rstrip('/')}{h['photo_url']}"

    return render_template('horarios_level.html',
                         level=level,
                         info=info,
                         horarios=horarios,
                         configured=configured,
                         opening_val=opening_val,
                         closing_val=closing_val)


@app.route('/admin/horarios')
@login_required
@admin_required
def admin_horarios():
    """Panel de administración para gestionar horarios"""
    result = sb_get('horarios', 'select=*&order=level,created_at.desc')
    if isinstance(result, dict) and 'error' in result:
        flash(f'Error al cargar horarios: {result.get("text", "Error desconocido")}', 'danger')
        horarios = []
    elif not isinstance(result, list):
        horarios = []
    else:
        horarios = result
    return render_template('admin_horarios.html', horarios=horarios)


@app.route('/admin/horarios/add', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_add_horario():
    """Agregar un nuevo horario"""
    if request.method == 'POST':
        level = request.form.get('level')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        photo_url = request.form.get('photo_url', '').strip()

        if not level or not name:
            flash('Nivel y nombre son requeridos.', 'danger')
            return render_template('admin_horario_form.html', action='create', levels=HORARIOS_LEVELS)

        horario_data = {
            'level': level,
            'name': name,
            'description': description,
            'photo_url': photo_url if photo_url else None
        }

        result = sb_post('horarios', horario_data)
        if isinstance(result, dict) and 'error' in result:
            flash(f'Error al agregar horario: {result["error"]}', 'danger')
        elif isinstance(result, list) or (isinstance(result, dict) and 'id' in result):
            flash('Horario agregado exitosamente.', 'success')
            return redirect(url_for('admin_horarios'))
        else:
            flash('Error inesperado al agregar horario.', 'danger')

    return render_template('admin_horario_form.html', action='create', levels=HORARIOS_LEVELS)


@app.route('/admin/horarios/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_edit_horario(id):
    """Editar un horario existente"""
    horario_data = sb_get('horarios', f'id=eq.{id}&select=*')
    if isinstance(horario_data, dict) and 'error' in horario_data:
        flash(f'Error al obtener horario: {horario_data["error"]}', 'danger')
        return redirect(url_for('admin_horarios'))
    if not isinstance(horario_data, list) or len(horario_data) == 0:
        flash('Horario no encontrado.', 'danger')
        return redirect(url_for('admin_horarios'))

    horario = horario_data[0]

    if request.method == 'POST':
        level = request.form.get('level')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        photo_url = request.form.get('photo_url', '').strip()

        if not level or not name:
            flash('Nivel y nombre son requeridos.', 'danger')
            return render_template('admin_horario_form.html', horario=horario, action='edit', levels=HORARIOS_LEVELS)

        update_data = {
            'level': level,
            'name': name,
            'description': description,
            'photo_url': photo_url if photo_url else None
        }

        result = sb_patch('horarios', 'id', id, update_data)
        if isinstance(result, dict) and 'error' in result:
            flash(f'Error al actualizar horario: {result["error"]}', 'danger')
        elif hasattr(result, 'status_code') and result.status_code in [200, 204]:
            flash('Horario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_horarios'))
        else:
            flash('Error inesperado al actualizar horario.', 'danger')

    return render_template('admin_horario_form.html', horario=horario, action='edit', levels=HORARIOS_LEVELS)


@app.route('/admin/horarios/delete/<int:id>', methods=['POST'])
@login_required
@superadmin_required
def admin_delete_horario(id):
    """Eliminar un horario"""
    result = sb_delete('horarios', 'id', id)
    if isinstance(result, dict) and 'error' in result:
        flash(f'Error al eliminar horario: {result["error"]}', 'danger')
    elif hasattr(result, 'status_code') and result.status_code in [200, 204]:
        flash('Horario eliminado exitosamente.', 'success')
    else:
        flash('Error inesperado al eliminar horario.', 'danger')
    return redirect(url_for('admin_horarios'))


@app.route('/admin/matricula-citas/api')
@login_required
def api_admin_matricula_citas():
    # Ordenar por fecha y hora ascendente
    date_filter = request.args.get('date')
    params = 'order=appointment_date.asc,appointment_time.asc'
    if date_filter:
        params += f'&appointment_date=eq.{date_filter}'
    appointments = sb_get('matricula_appointments', f'select=*&{params}')
    return format_appointment_data(appointments)

@app.route('/admin/matricula-citas')
@login_required
def admin_matricula_citas():
    date_filter = request.args.get('date')
    format_type = request.args.get('format')
    params = 'order=appointment_date.asc,appointment_time.asc'
    if date_filter:
        params += f'&appointment_date=eq.{date_filter}'
    appointments = sb_get('matricula_appointments', f'select=*&{params}')
    if not isinstance(appointments, list):
        appointments = []
    appointments = format_appointment_data(appointments)

    if format_type == 'csv':
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Estudiante', 'Cédula', 'Teléfono', 'Ciclo', 'Fecha', 'Hora', 'Fecha de Creación'])
        for a in appointments:
            cycle_map = {
                'primaria': '1er Nivel (Primaria)',
                'segundo_nivel': '2do Nivel (7°-9°)',
                'tercer_nivel': '3er Nivel (10°-11°)'
            }
            cycle_label = cycle_map.get(a.get('cycle', ''), a.get('cycle', ''))
            cw.writerow([
                a.get('student_name', ''),
                a.get('student_cedula', ''),
                a.get('student_phone', ''),
                cycle_label,
                a.get('appointment_date', ''),
                a.get('appointment_time', ''),
                a.get('created_at', '')
            ])
        output = si.getvalue()
        si.close()
        filename = f'citas_matricula_{date_filter if date_filter else datetime.now().date().isoformat()}.csv'
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={filename}'}
        )

    elif format_type == 'pdf':
        # Render the template to HTML with export_mode=True to hide interactive elements
        html_string = render_template('admin_matricula_citas.html', appointments=appointments, export_mode=True)
        # Convert HTML to PDF
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        # Create response
        response = make_response(pdf)
        filename = f'citas_matricula_{date_filter if date_filter else datetime.now().date().isoformat()}.pdf'
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    return render_template('admin_matricula_citas.html', appointments=appointments, export_mode=False)


@app.route('/admin/matricula-citas/delete/<int:id>')
@login_required
def delete_matricula_cita(id):
    r = sb_delete('matricula_appointments', 'id', id)
    if r.status_code in [200, 204]:
        flash('Cita de matrícula eliminada.', 'success')
    else:
        flash(f'Error al eliminar: {r.status_code}', 'danger')
    return redirect(url_for('admin_matricula_citas'))




# Student Dashboard Route
@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():
    # Get student's enrolled subjects with grades
    # First, get the student's enrolled subjects
    enrollments = sb_get('student_subjects', f'student_id=eq.{current_user.id}&is_active=eq.true')
    if not isinstance(enrollments, list):
        enrollments = []

    subjects_with_grades = []
    for enrollment in enrollments:
        if isinstance(enrollment, dict) and 'subject_id' in enrollment:
            subject_id = enrollment['subject_id']
            # Get subject details
            subject_data = sb_get('subjects', f'id=eq.{subject_id}&select=*')
            if isinstance(subject_data, list) and len(subject_data) > 0:
                subject = subject_data[0]
                # Get grade for this subject
                grade_data = sb_get('grades', f'student_subject_id=eq.{enrollment["id"]}&select=*')
                grade = None
                passed = False
                if isinstance(grade_data, list) and len(grade_data) > 0:
                    grade = grade_data[0].get('final_grade')
                    passed = grade_data[0].get('passed', False)

                subjects_with_grades.append({
                    'subject': subject,
                    'enrollment': enrollment,
                    'final_grade': grade,
                    'passed': passed
                })

    return render_template('student_dashboard.html', subjects=subjects_with_grades)


# Professor Dashboard Route
@app.route('/professor/dashboard', methods=['GET', 'POST'])
@login_required
@professor_required
def professor_dashboard():
    search_results = []
    if request.method == 'POST':
        cedula = request.form.get('cedula', '').strip()
        if cedula:
            # Search for student by cedula
            students = sb_get('users', f'cedula=eq.{cedula}&role=eq.student&select=*')
            if isinstance(students, list) and len(students) > 0:
                student = students[0]
                # Get student's enrolled subjects with grades
                enrollments = sb_get('student_subjects', f'student_id=eq.{student["id"]}&is_active=eq.true')
                if isinstance(enrollments, list):
                    for enrollment in enrollments:
                        if isinstance(enrollment, dict) and 'subject_id' in enrollment:
                            subject_id = enrollment['subject_id']
                            # Get subject details
                            subject_data = sb_get('subjects', f'id=eq.{subject_id}&select=*')
                            if isinstance(subject_data, list) and len(subject_data) > 0:
                                subject = subject_data[0]
                                # Get grade for this subject
                                grade_data = sb_get('grades', f'student_subject_id=eq.{enrollment["id"]}&select=*')
                                grade = None
                                passed = False
                                if isinstance(grade_data, list) and len(grade_data) > 0:
                                    grade = grade_data[0].get('final_grade')
                                    passed = grade_data[0].get('passed', False)

                                search_results.append({
                                    'student': student,
                                    'subject': subject,
                                    'enrollment': enrollment,
                                    'final_grade': grade,
                                    'passed': passed
                                })

    return render_template('professor_dashboard.html', search_results=search_results)


# Admin User Management Routes
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = sb_get('users', 'select=*')
    if not isinstance(users, list):
        users = []
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_create_user():
    print("DEBUG: admin_create_user accessed")  # Debug line
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'student')
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            cedula = request.form.get('cedula', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            level = request.form.get('level', '') if role == 'student' else None

            if not username or not password:
                flash('Usuario y contraseña son requeridos.', 'danger')
                return render_template('admin_user_form.html', action='create')

            # Check if username already exists
            existing = sb_get('users', f'username=eq.{username}&select=id')
            if isinstance(existing, list) and len(existing) > 0:
                flash('El nombre de usuario ya existe.', 'danger')
                return render_template('admin_user_form.html', action='create')

            # Hash password
            hashed_password = generate_password_hash(password)

            # Create user
            user_data = {
                'username': username,
                'password': hashed_password,
                'role': role,
                'first_name': first_name,
                'last_name': last_name,
                'cedula': cedula,
                'email': email,
                'phone': phone,
                'level': level
            }

            result = sb_post('users', user_data)
            if isinstance(result, list) or (isinstance(result, dict) and 'id' in result):
                flash('Usuario creado exitosamente.', 'success')
                return redirect(url_for('admin_users'))
            else:
                flash(f'Error al crear usuario: {result}', 'danger')
        except Exception as e:
            flash(f'Error inesperado: {str(e)}', 'danger')
            # Optionally log the error
            print(f"Error in admin_create_user: {e}")

    return render_template('admin_user_form.html', action='create')


@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_edit_user(id):
    # Get user data
    user_data = sb_get('users', f'id=eq.{id}&select=*')
    if not isinstance(user_data, list) or len(user_data) == 0:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('admin_users'))
    user = user_data[0]

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        cedula = request.form.get('cedula', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        level = request.form.get('level', '') if role == 'student' else None

        if not username:
            flash('El nombre de usuario es requerido.', 'danger')
            return render_template('admin_user_form.html', user=user, action='edit')

        # Check if username already exists (excluding current user)
        existing = sb_get('users', f'username=eq.{username}&id=neq.{id}&select=id')
        if isinstance(existing, list) and len(existing) > 0:
            flash('El nombre de usuario ya existe.', 'danger')
            return render_template('admin_user_form.html', user=user, action='edit')

        # Prepare update data
        update_data = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'cedula': cedula,
            'email': email,
            'phone': phone,
            'role': role,
            'level': level
        }

        # Only update password if provided
        if password:
            update_data['password'] = generate_password_hash(password)

        result = sb_patch('users', 'id', id, update_data)
        if hasattr(result, 'status_code') and result.status_code in [200, 204]:
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_users'))
        else:
            flash(f'Error al actualizar usuario: {result}', 'danger')

    return render_template('admin_user_form.html', user=user, action='edit')


@app.route('/admin/users/delete/<int:id>')
@login_required
@superadmin_required
def admin_delete_user(id):
    # Delete user (this will cascade to related records due to foreign keys)
    result = sb_delete('users', 'id', id)
    if hasattr(result, 'status_code') and result.status_code in [200, 204]:
        flash('Usuario eliminado exitosamente.', 'success')
    else:
        flash(f'Error al eliminar usuario: {result}', 'danger')
    return redirect(url_for('admin_users'))


# Grade Entry Route for Professors
@app.route('/professor/grade/enter', methods=['POST'])
@login_required
@professor_required
def professor_enter_grade():
    enrollment_id = request.form.get('enrollment_id')
    final_grade = request.form.get('final_grade')

    if not enrollment_id or not final_grade:
        flash('ID de inscripción y nota final son requeridos.', 'danger')
        return redirect(url_for('professor_dashboard'))

    try:
        final_grade = float(final_grade)
        if final_grade < 0 or final_grade > 100:
            flash('La nota debe estar entre 0 y 100.', 'danger')
            return redirect(url_for('professor_dashboard'))
    except ValueError:
        flash('La nota debe ser un número válido.', 'danger')
        return redirect(url_for('professor_dashboard'))

    # Get the enrollment to verify it belongs to a student
    enrollment = sb_get('student_subjects', f'id=eq.{enrollment_id}&select=*')
    if not isinstance(enrollment, list) or len(enrollment) == 0:
        flash('Inscripción no encontrada.', 'danger')
        return redirect(url_for('professor_dashboard'))

    enrollment = enrollment[0]

    # Get student level to determine passing grade
    student_id = enrollment['student_id']
    student_data = sb_get('users', f'id=eq.{student_id}&select=level')
    student_level = 'segundo_nivel'  # default
    if isinstance(student_data, list) and len(student_data) > 0:
        student_level = student_data[0].get('level', 'segundo_nivel')

    # Determine if passed based on level
    if student_level in ['primaria', 'segundo_nivel']:
        passed = final_grade >= 65
    elif student_level == 'tercer_nivel':
        passed = final_grade >= 70
    else:
        passed = final_grade >= 65  # default

    # Check if grade already exists
    existing_grade = sb_get('grades', f'student_subject_id=eq.{enrollment_id}&select=id')
    if isinstance(existing_grade, list) and len(existing_grade) > 0:
        # Update existing grade
        grade_data = {
            'final_grade': final_grade,
            'passed': passed
        }
        result = sb_patch('grades', 'id', existing_grade[0]['id'], grade_data)
    else:
        # Create new grade
        grade_data = {
            'student_subject_id': enrollment_id,
            'final_grade': final_grade,
            'passed': passed,
            'graded_by': current_user.id
        }
        result = sb_post('grades', grade_data)

    if isinstance(result, list) or (isinstance(result, dict) and 'id' in result):
        flash('Nota guardada exitosamente.', 'success')
    else:
        flash(f'Error al guardar nota: {result}', 'danger')

    return redirect(url_for('professor_dashboard'))


@app.route('/test')
def test():
    return 'OK'

handler = app